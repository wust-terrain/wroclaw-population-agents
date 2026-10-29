"""Świadek statystyczny: NSP 2021 w siatce 125 m (GUS) i obwody głosowania PKW 2025.

Pliki w data/populacja/:
    Grid_125_*.xlsx              ludność NSP 2021 w kwadratach 125 m, cała Polska (GUS, usługa ATOM GRID)
    obwody_glosowania_utf8.csv   obwody głosowania z wyborów prezydenckich 2025 (PKW): mieszkańcy, wyborcy, opis granic

Świadek jest deterministyczny: dla każdego budynku podaje ludność jego kwadratu z 2021 roku i część tej
ludności, która przypada na budynek według powierzchni kondygnacji mieszkalnych z BDOT10k.
"""

import re

import geopandas as gpd
import numpy as np
import openpyxl
import pandas as pd
import pyogrio
from pyproj import Transformer
from shapely.geometry import box

from ortofoto import DATA
from ortofoto.budynki import plik_bdot, wczytaj_bdot

POPULACJA = DATA / "populacja"
TERYT_WROCLAW = "026401"
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


def przydzial_nsp(nsp):
    """Ludność kwadratów rozdzielona na budynki proporcjonalnie do powierzchni kondygnacji mieszkalnych.

    Powierzchnia kondygnacji = powierzchnia zabudowy × kondygnacje z BDOT10k (brak kondygnacji liczymy jako 1),
    tylko dla budynków mieszkalnych i eksploatowanych. Budynek należy do kwadratu, w którym leży jego środek.
    Zwraca (budynki, kwadraty): przydział per budynek i bilans per kwadrat (z gęstością na 100 m²).
    """
    bud = wczytaj_bdot(nsp.union_all())
    mieszkalny = (bud.funkcja_ogolna == "budynki mieszkalne") & (bud.kategoria == "eksploatowany")
    bud["pow_kondygnacji"] = (bud.geometry.area * bud.kondygnacje.fillna(1)).where(mieszkalny, 0.0)
    srodki = gpd.GeoDataFrame(bud[["pow_kondygnacji"]], geometry=bud.centroid, crs=bud.crs)
    bud["komorka"] = gpd.sjoin(srodki, nsp[["geometry"]], predicate="within")["kod"]

    kw = nsp[["ludnosc", "geometry"]].copy()
    kw["pow_kondygnacji"] = bud.groupby("komorka").pow_kondygnacji.sum().reindex(kw.index).fillna(0.0)
    kw["gestosc_100m2"] = (kw.ludnosc / kw.pow_kondygnacji * 100).where(kw.pow_kondygnacji > 0)
    kw["bez_budynku"] = (kw.ludnosc > 0) & (kw.pow_kondygnacji == 0)  # ludność bez budynku mieszkalnego w BDOT

    bud = bud.join(kw[["ludnosc", "pow_kondygnacji"]].rename(columns={"ludnosc": "ludnosc_komorki",
                                                                       "pow_kondygnacji": "pow_komorki"}), on="komorka")
    bud["udzial"] = (bud.pow_kondygnacji / bud.pow_komorki).where(bud.pow_komorki > 0, 0.0)
    bud["przydzial_2021"] = bud.udzial * bud.ludnosc_komorki.fillna(0)
    return bud, kw


# --- obwody głosowania -------------------------------------------------------------------------

PRZEDROSTKI = {"ul.", "ulica", "al.", "aleja", "aleje", "pl.", "plac", "os.", "osiedle", "gen.", "kard.", "ks.", "św.", "bp",
               "bp.", "abp", "abp.", "prof.", "dr", "płk.", "płk", "mjr.", "kpt.", "por.", "ppor.", "marsz.", "inż.",
               "o.", "bł.", "im.", "rtm.", "hetm.", "kmdr.", "gen", "kard"}
NUMERY = re.compile(r"\d+[A-Za-z]?(?:\s*[-–]\s*\d+[A-Za-z]?|\s+do końca)?(?:\s+(?:nie)?parzyste)?")
ULICA_Z_NUMERAMI = re.compile(r"(.*?\D)\s+(" + NUMERY.pattern + r")")
ZAKRES = re.compile(r"(\d+)[A-Za-z]?(?:\s*[-–]\s*(\d+)[A-Za-z]?|\s+(do końca))?(?:\s+(nieparzyste|parzyste))?")
KONIEC_ULICY = 100_000  # "152 do końca" = od 152 do ostatniego numeru


def normalizuj_ulice(nazwa):
    """'pl. gen. Józefa Bema' -> 'józefa bema': małe litery, bez przedrostków, pojedyncze spacje."""
    slowa = [s for s in nazwa.lower().replace("„", " ").replace("”", " ").split() if s not in PRZEDROSTKI]
    return " ".join(slowa)


def _zakres(tekst):
    od, do, do_konca, parzystosc = ZAKRES.fullmatch(tekst).groups()
    return int(od), KONIEC_ULICY if do_konca else int(do or od), {"parzyste": 0, "nieparzyste": 1}.get(parzystosc)


def parsuj_granice(opis):
    """Opis granic obwodu -> {ulica: None (cała ulica) albo lista zakresów (od, do, parzystość)}.

    Format PKW dla Wrocławia: 'Wrocław-Śródmieście ulice: Henryka Sienkiewicza 24 - 60 parzyste, Krzywa,
    Piastowska 56, 58'. Sam numer po przecinku należy do poprzedniej ulicy.
    """
    reguly, ostatnia = {}, None
    for sekcja in str(opis).split(";"):
        for kawalek in re.split(r",\s*", sekcja.split("ulice:", 1)[-1]):
            kawalek = kawalek.strip().rstrip(".")
            if not kawalek:
                continue
            if NUMERY.fullmatch(kawalek) and ostatnia is not None:
                reguly[ostatnia] = (reguly[ostatnia] or []) + [_zakres(kawalek)]
                continue
            m = ULICA_Z_NUMERAMI.fullmatch(kawalek)
            ostatnia = normalizuj_ulice(m[1] if m else kawalek)
            if m:
                reguly[ostatnia] = (reguly.get(ostatnia) or []) + [_zakres(m[2])]
            else:
                reguly.setdefault(ostatnia, None)
    return reguly


def wczytaj_obwody(teryt=TERYT_WROCLAW):
    """Obwody głosowania gminy (domyślnie Wrocław) z PKW 2025, indeks: numer obwodu, z kolumną reguly."""
    obwody = pd.read_csv(POPULACJA / "obwody_glosowania_utf8.csv", sep=";", dtype={"TERYT gminy": str})
    obwody = obwody[obwody["TERYT gminy"] == teryt].set_index("Numer")
    obwody["reguly"] = obwody["Opis granic"].map(parsuj_granice)
    return obwody


def obwody_adresu(ulica, numer, obwody):
    """Numery obwodów, których opis granic obejmuje adres (zwykle jeden; pusta lista, gdy żaden)."""
    u = normalizuj_ulice(ulica)
    numery = [int(n) for n in re.findall(r"\d+", str(numer))]
    wynik = []
    for nr, reguly in obwody.reguly.items():
        if u not in reguly:
            continue
        zakresy = reguly[u]
        if zakresy is None or any(od <= n <= do and (p is None or n % 2 == p)
                                  for n in numery for od, do, p in zakresy):
            wynik.append(nr)
    return wynik
