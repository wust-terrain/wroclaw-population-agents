"""Arkusze ortofotomapy skośnej z katalogu data/ i czytanie z nich wycinków.

Każdy plik `*_N.tif`, `*_E.tif`, `*_S.tif`, `*_W.tif` to jeden arkusz widziany z jednego kierunku.
Arkusze tego samego kierunku tworzą mozaikę, więc wycinek może przechodzić przez granicę arkuszy.
Przy imporcie czytamy tylko zasięgi; plik otwieramy przy pierwszym odczycie, a każdy wątek ma własne uchwyty
(GDAL nie pozwala czytać jednego uchwytu z wielu wątków naraz, a przy całym mieście plików są tysiące).
"""

import threading
from functools import cache
from typing import NamedTuple

import numpy as np
import rasterio
import shapely
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from shapely import STRtree
from shapely.geometry import box
from shapely.ops import unary_union

from ortofoto import DATA

KIERUNKI = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}  # kierunek patrzenia = kierunek przesunięcia dachu
NA = {"N": "północ", "E": "wschód", "S": "południe", "W": "zachód"}
UCHWYTY = 64  # tyle otwartych plików najwyżej na wątek


class Arkusz(NamedTuple):
    name: str  # ścieżka pliku
    godlo: str
    bounds: rasterio.coords.BoundingBox


def _arkusze(kier):
    wynik = []
    for p in sorted(DATA.glob(f"*_{kier}.tif")):
        with rasterio.open(p) as s:
            wynik.append(Arkusz(str(p), p.stem.split("_")[-2], s.bounds))
    return wynik


ARKUSZE = {k: _arkusze(k) for k in KIERUNKI}
ARKUSZE = {k: v for k, v in ARKUSZE.items() if v}
KOLEJNOSC = list(ARKUSZE)  # kierunki, dla których jest choć jeden arkusz
_watki = threading.local()


def _otworz(sciezka):
    """Uchwyt pliku dla bieżącego wątku; najdawniej użyty zamykamy, gdy jest ich więcej niż UCHWYTY."""
    uchwyty = _watki.__dict__.setdefault("uchwyty", {})
    if sciezka in uchwyty:
        uchwyty[sciezka] = uchwyty.pop(sciezka)  # na koniec kolejki: ostatnio użyty
    else:
        if len(uchwyty) >= UCHWYTY:
            uchwyty.pop(next(iter(uchwyty))).close()
        uchwyty[sciezka] = rasterio.open(sciezka)
    return uchwyty[sciezka]


@cache
def zasieg(kier=None):
    """Obszar pokryty arkuszami jednego kierunku albo (kier=None) wszystkich razem."""
    zrodla = ARKUSZE[kier] if kier else [s for v in ARKUSZE.values() for s in v]
    obszar = unary_union([box(*s.bounds) for s in zrodla])
    shapely.prepare(obszar)  # szybkie within() przy każdym budynku
    return obszar


@cache
def _drzewo(kier):
    return STRtree([box(*a.bounds) for a in ARKUSZE[kier]])


def _na(kier, bounds):
    """Arkusze kierunku kier, które przecinają prostokąt bounds, w kolejności z ARKUSZE."""
    return [ARKUSZE[kier][i] for i in sorted(_drzewo(kier).query(box(*bounds)))]


def pokrywa(kier, bounds):
    """Czy prostokąt bounds w całości leży na arkuszach kierunku kier."""
    return kier in ARKUSZE and box(*bounds).within(zasieg(kier))


def _mozaika(zrodla, bounds, res):
    """Skleja wycinek z kilku arkuszy; piksele bez pokrycia są białe, wcześniejszy arkusz ma pierwszeństwo."""
    x0, y0, x1, y1 = bounds
    out = np.full((round((y1 - y0) / res), round((x1 - x0) / res), 3), 255, np.uint8)
    pusty = np.ones(out.shape[:2], bool)
    for a in zrodla:
        ix0, iy0 = max(x0, a.bounds.left), max(y0, a.bounds.bottom)
        ix1, iy1 = min(x1, a.bounds.right), min(y1, a.bounds.top)
        c0, c1 = round((ix0 - x0) / res), round((ix1 - x0) / res)
        r0, r1 = round((y1 - iy1) / res), round((y1 - iy0) / res)
        if c1 <= c0 or r1 <= r0:
            continue
        src = _otworz(a.name)
        img = src.read(window=from_bounds(ix0, iy0, ix1, iy1, transform=src.transform),
                       out_shape=(3, r1 - r0, c1 - c0), resampling=Resampling.average)
        wolne = pusty[r0:r1, c0:c1]
        out[r0:r1, c0:c1][wolne] = np.moveaxis(img, 0, -1)[wolne]
        pusty[r0:r1, c0:c1] = False
    return out


def czytaj(kier, bounds, res=0.1):
    """Wycinek (minx, miny, maxx, maxy) w EPSG:2177 z kierunku kier, piksel res [m].

    Przy res > 0,05 m GDAL czyta z piramid, więc podgląd całego arkusza jest szybki.
    Zwraca obraz (wiersze, kolumny, RGB) i extent do plt.imshow.
    """
    x0, y0, x1, y1 = bounds
    return _mozaika(_na(kier, bounds), bounds, res), (x0, x1, y0, y1)
