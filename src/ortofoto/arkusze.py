"""Arkusze ortofotomapy skośnej z katalogu data/ i czytanie z nich wycinków.

Każdy plik `*_N.tif`, `*_E.tif`, `*_S.tif`, `*_W.tif` to jeden arkusz widziany z jednego kierunku.
Arkusze tego samego kierunku tworzą mozaikę, więc wycinek może przechodzić przez granicę arkuszy.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from shapely.geometry import box
from shapely.ops import unary_union

from ortofoto import DATA

KIERUNKI = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}  # kierunek patrzenia = kierunek przesunięcia dachu
NA = {"N": "północ", "E": "wschód", "S": "południe", "W": "zachód"}
ELEWACJE = {"N": "południowe", "E": "zachodnie", "S": "północne", "W": "wschodnie"}

ARKUSZE = {k: [rasterio.open(p) for p in sorted(DATA.glob(f"*_{k}.tif"))] for k in KIERUNKI}
ARKUSZE = {k: v for k, v in ARKUSZE.items() if v}
KOLEJNOSC = list(ARKUSZE)  # kierunki, dla których jest choć jeden arkusz


def zasieg(kier=None):
    """Obszar pokryty arkuszami jednego kierunku albo (kier=None) wszystkich razem."""
    zrodla = ARKUSZE[kier] if kier else [s for v in ARKUSZE.values() for s in v]
    return unary_union([box(*s.bounds) for s in zrodla])


def pokrywa(kier, bounds):
    """Czy prostokąt bounds w całości leży na arkuszach kierunku kier."""
    return kier in ARKUSZE and box(*bounds).within(zasieg(kier))


def opis_arkuszy():
    """Tabela z metadanymi wszystkich arkuszy."""
    wiersze = []
    for kier, zrodla in ARKUSZE.items():
        for s in zrodla:
            p = Path(s.name)
            wiersze.append({"plik": p.name, "kierunek": kier, "godło": p.stem.split("_")[2], "MB": round(p.stat().st_size / 1e6),
                            "CRS": str(s.crs), "rozmiar [px]": f"{s.width} × {s.height}", "piksel [m]": s.res[0],
                            "x od–do": f"{s.bounds.left:.0f}–{s.bounds.right:.0f}",
                            "y od–do": f"{s.bounds.bottom:.0f}–{s.bounds.top:.0f}",
                            "kafelki": s.block_shapes[0], "kompresja": s.tags(ns="IMAGE_STRUCTURE")["COMPRESSION"],
                            "piramidy": s.overviews(1)})
    return pd.DataFrame(wiersze).set_index("plik")


def _mozaika(zrodla, bounds, res):
    """Skleja wycinek z kilku arkuszy; piksele bez pokrycia są białe, wcześniejszy arkusz ma pierwszeństwo."""
    x0, y0, x1, y1 = bounds
    out = np.full((round((y1 - y0) / res), round((x1 - x0) / res), 3), 255, np.uint8)
    pusty = np.ones(out.shape[:2], bool)
    for src in zrodla:
        ix0, iy0 = max(x0, src.bounds.left), max(y0, src.bounds.bottom)
        ix1, iy1 = min(x1, src.bounds.right), min(y1, src.bounds.top)
        c0, c1 = round((ix0 - x0) / res), round((ix1 - x0) / res)
        r0, r1 = round((y1 - iy1) / res), round((y1 - iy0) / res)
        if c1 <= c0 or r1 <= r0:
            continue
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
    return _mozaika(ARKUSZE[kier], bounds, res), (x0, x1, y0, y1)


def podklad(bounds, res=1.0):
    """Wycinek z dowolnego dostępnego kierunku (do map poglądowych)."""
    x0, y0, x1, y1 = bounds
    return _mozaika([s for k in KOLEJNOSC for s in ARKUSZE[k]], bounds, res), (x0, x1, y0, y1)
