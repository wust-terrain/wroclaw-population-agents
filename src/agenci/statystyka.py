"""NSP 2021 w siatce 125 m (GUS) i przypisanie budynków do kwadratów.

Plik w data/populacja/: Grid_125_*.xlsx, ludność NSP 2021 w kwadratach 125 m, cała Polska (GUS, usługa ATOM GRID).
"""

import re

import geopandas as gpd
import openpyxl
import pandas as pd
import pyogrio
from pyproj import Transformer
from shapely.geometry import box

from agenci.estymatory import klasa_bdot
from ortofoto import DATA
from ortofoto.budynki import plik_bdot, wczytaj_bdot

POPULACJA = DATA / "populacja"
KOD_KOMORKI = re.compile(r"CRS3035RES125mN(\d+)E(\d+)")  # współrzędne lewego dolnego narożnika w EPSG:3035


def zasieg_miasta():
    """Prostokąt (EPSG:2177) obejmujący wszystkie budynki z warstwy BDOT10k w data/."""
    x0, y0, x1, y1 = pyogrio.read_info(plik_bdot(), force_total_bounds=True)["total_bounds"]
    return box(*Transformer.from_crs(2180, 2177, always_xy=True).transform_bounds(x0, y0, x1, y1))


def wczytaj_nsp(obszar=None):
    """Kwadraty 125 m z ludnością NSP 2021, które przecinają obszar (domyślnie całe miasto), EPSG:2177.

    Indeks: kod komórki. Pierwsze wywołanie czyta arkusze XLSX z całej Polski (ok. 1,5 min) i zapisuje
    kwadraty z zasięgu miasta w data/populacja/. Geometrię liczymy z kodu komórki, więc osobny plik
    z siatką nie jest potrzebny.
    """
    miasto = zasieg_miasta()
    x0, y0, x1, y1 = (round(v) for v in miasto.bounds)
    plik = POPULACJA / f"nsp2021_125m_{x0}_{y0}_{x1}_{y1}.gpkg"
    if not plik.exists():
        e0, n0, e1, n1 = Transformer.from_crs(2177, 3035, always_xy=True).transform_bounds(*miasto.bounds)
        wiersze = []
        for xlsx in sorted(POPULACJA.glob("Grid_125_*.xlsx")):
            arkusz = openpyxl.load_workbook(xlsx, read_only=True).worksheets[0]
            for _, kod, ludnosc in arkusz.iter_rows(min_row=2, values_only=True):
                n, e = map(int, KOD_KOMORKI.fullmatch(kod).groups())
                if e0 - 125 <= e <= e1 and n0 - 125 <= n <= n1:
                    wiersze.append((kod, ludnosc, box(e, n, e + 125, n + 125)))
        kody, ludnosc, geometrie = zip(*wiersze)
        gpd.GeoDataFrame({"kod": kody, "ludnosc": ludnosc}, geometry=list(geometrie), crs=3035) \
            .to_crs(2177).to_file(plik, driver="GPKG")
    nsp = gpd.read_file(plik).set_index("kod")
    return nsp if obszar is None else nsp[nsp.intersects(obszar)]


def budynki_w_kwadratach(obszar=None):
    """(budynki z BDOT10k, kwadraty NSP) dla kwadratów przecinających obszar (domyślnie całe miasto).

    Budynki dostają kolumny komorka (kwadrat, w którym leży ich środek) oraz, gdy są mieszkalne i eksploatowane, klasa
    i pow_kondygnacji (powierzchnia zabudowy × kondygnacje, brak kondygnacji liczymy jako 1).
    """
    nsp = wczytaj_nsp(obszar)
    bud = wczytaj_bdot(nsp.union_all())
    mieszkalny = (bud.funkcja_ogolna == "budynki mieszkalne") & (bud.kategoria == "eksploatowany")
    bud["pow_kondygnacji"] = (bud.geometry.area * bud.kondygnacje.fillna(1)).where(mieszkalny, 0.0)
    bud["klasa"] = pd.Series([klasa_bdot(f, k) for f, k in zip(bud.funkcja, bud.kondygnacje)], index=bud.index).where(mieszkalny)
    srodki = gpd.GeoDataFrame(geometry=bud.centroid, crs=bud.crs)
    bud["komorka"] = gpd.sjoin(srodki, nsp[["geometry"]], predicate="within")["kod"]
    return bud, nsp


def kompletne_kwadraty(bud, dostepne):
    """Kody kwadratów, w których każdy budynek mieszkalny (kolumna klasa z budynki_w_kwadratach) należy do dostepne.

    Tylko w takich kwadratach suma predykcji da się porównać z ludnością; arkusz ucina kwadraty na brzegach.
    """
    mieszkalne = bud[bud.klasa.notna() & bud.komorka.notna()]
    pelne = pd.Series(mieszkalne.index.isin(dostepne), index=mieszkalne.index).groupby(mieszkalne.komorka).all()
    return pelne.index[pelne]
