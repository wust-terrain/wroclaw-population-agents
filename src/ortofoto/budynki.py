"""Budynki na arkuszach: obrysy i funkcja z BDOT10k, wysokość z lotniczego skaningu laserowego, adres z punktów adresowych OSM.

BDOT10k (warstwa OT_BUBD_A, obrysy z ewidencji gruntów i budynków) to główne źródło: każdy budynek
ma tam funkcję (np. budynek wielorodzinny), liczbę kondygnacji i stan (eksploatowany, w budowie...).
Wysokość to różnica dwóch rastrów GUGiK ze skaningu laserowego (LiDAR): NMPT (powierzchnia z dachami, piksel 0,5 m)
i NMT (sam teren, 1 m). Adres to punkty adresowe OSM (w Polsce głównie z importu PRG) leżące w obrysie budynku.
"""

import json
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import rasterio.mask
from pyproj import Transformer
from shapely.geometry import Point, box

from ortofoto import DATA
from ortofoto.arkusze import zasieg

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
WCS = ("https://mapy.geoportal.gov.pl/wss/service/PZGIK/{0}/GRID1/WCS/{1}?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
       "&COVERAGEID={2}_PL-EVRF2007-NH&FORMAT=image/x-aaigrid&SUBSET=x({3},{5})&SUBSET=y({4},{6})")
MODELE = {"nmpt": ("NMPT", "DigitalSurfaceModel", "DSM"), "nmt": ("NMT", "DigitalTerrainModel", "DTM")}
KAFLE = DATA / "kafle"  # pobrane raz kafle punktów adresowych i LiDAR-u
KAFEL_OSM = 2000  # bok kafla [m] dla zapytań Overpass
KAFEL_LIDAR = 1000  # bok kafla [m] dla rastrów wysokości (0,5 m, więc ok. 2000 × 2000 pikseli)
MARGINES_LIDAR = 100  # rastry sięgają tyle poza kafel, żeby objąć budynki na jego granicy


def _zapytaj(zapytanie, rundy=3):
    """Wysyła zapytanie do kolejnych serwerów Overpass, aż któryś odpowie; przy przeciążeniu czeka minutę i próbuje znowu."""
    for runda in range(rundy):
        for url in OVERPASS:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": zapytanie}).encode(),
                                         headers={"User-Agent": "wroclaw-population-agents/0.1"})
            try:
                return json.load(urllib.request.urlopen(req, timeout=200))["elements"]
            except OSError as e:  # HTTPError i timeout dziedziczą po OSError
                blad = e
        if runda < rundy - 1:
            time.sleep(60)
    raise blad


def kafle(obszar, bok):
    """Lewe dolne rogi kwadratów bok × bok [m] (EPSG:2177, wyrównanych do wielokrotności bok), które przecinają obszar."""
    x0, y0, x1, y1 = obszar.bounds
    return [(x, y) for x in range(int(x0 // bok * bok), int(x1), bok) for y in range(int(y0 // bok * bok), int(y1), bok)
            if box(x, y, x + bok, y + bok).intersects(obszar)]


def _adresy_kafel(x, y):
    """Punkty adresowe OSM z jednego kafla KAFEL_OSM, pobrane raz i zapisane w data/kafle/."""
    plik = KAFLE / f"osm_adresy_{x}_{y}.geojson"
    if not plik.exists():
        lon0, lat0, lon1, lat1 = Transformer.from_crs(2177, 4326, always_xy=True).transform_bounds(x, y, x + KAFEL_OSM, y + KAFEL_OSM)
        elementy = _zapytaj(f'[out:json][timeout:180];node["addr:housenumber"]({lat0},{lon0},{lat1},{lon1});out;')
        wiersze = [{"ulica": e["tags"].get("addr:street") or e["tags"].get("addr:place"), "numer": e["tags"]["addr:housenumber"],
                    "geometry": Point(e["lon"], e["lat"])} for e in elementy]
        KAFLE.mkdir(exist_ok=True)
        gpd.GeoDataFrame(wiersze, geometry="geometry", crs=4326).to_file(plik, driver="GeoJSON")
    return gpd.read_file(plik).to_crs(2177)


def wczytaj_adresy(obszar=None):
    """Punkty adresowe z OSM (węzły z numerem domu, w Polsce głównie z importu PRG): kolumny ulica, numer; EPSG:2177."""
    obszar = obszar if obszar is not None else zasieg()
    adresy = pd.concat([_adresy_kafel(x, y) for x, y in kafle(obszar, KAFEL_OSM)]).drop_duplicates()
    return adresy[adresy.ulica.notna()]


def _dolacz_adresy(bud, adresy):
    """Adresy z punktów adresowych w obrysie: kolumna adresy ma wszystkie, addr:street i addr:housenumber pierwszy z nich."""
    pkt = gpd.sjoin(adresy, bud[["geometry"]].rename_axis("budynek").reset_index(), predicate="within")
    pkt = pkt.drop_duplicates(["budynek", "ulica", "numer"]).sort_values(["ulica", "numer"])
    bud["adresy"] = pkt.groupby("budynek").apply(lambda p: ", ".join(p.ulica + " " + p.numer))
    pierwszy = pkt.groupby("budynek").first()
    bud["addr:street"] = pierwszy.ulica.reindex(bud.index)
    bud["addr:housenumber"] = pierwszy.numer.reindex(bud.index)
    return bud


def model_wysokosci(nazwa, x, y):
    """Plik rastra wysokości z GUGiK ("nmpt" albo "nmt") dla kafla KAFEL_LIDAR z rogiem (x, y) i marginesem, pobrany raz przez
    WCS i zapisany w data/kafle/; EPSG:2180."""
    plik = KAFLE / f"{nazwa}_{x}_{y}.tif"
    if not plik.exists():
        m = MARGINES_LIDAR
        ramka = Transformer.from_crs(2177, 2180, always_xy=True).transform_bounds(x - m, y - m, x + KAFEL_LIDAR + m, y + KAFEL_LIDAR + m)
        odp = urllib.request.urlopen(WCS.format(*MODELE[nazwa], *(round(v) for v in ramka)), timeout=300).read()
        siatka = odp[odp.find(b"ncols"):].split(b"--wcs")[0]  # serwer pakuje siatkę ASCII w odpowiedź wieloczęściową
        KAFLE.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".asc") as tmp:
            tmp.write(siatka)
            tmp.flush()
            with rasterio.open(tmp.name) as src:
                profil = src.profile | {"driver": "GTiff", "crs": 2180, "compress": "deflate"}
                with rasterio.open(plik.with_suffix(".czesc"), "w", **profil) as dst:
                    dst.write(src.read())
        plik.with_suffix(".czesc").rename(plik)
    return plik


def wysokosc_lidar(bud):
    """Wysokość budynków [m]: mediana NMPT w obrysie (bez metra przy krawędzi) minus teren, czyli 10. percentyl NMT wokół obrysu.

    Budynek bierze rastry z kafla, w którym leży jego środek; kafle pobieramy po kilka naraz.
    """
    def wartosci(src, geom):
        z = rasterio.mask.mask(src, [geom], crop=True, filled=False)[0].compressed()
        return z[z > -100]  # poza zasięgiem danych serwer zwraca dużą liczbę ujemną

    srodki = bud.centroid
    kx, ky = ((srodki.x // KAFEL_LIDAR * KAFEL_LIDAR).astype(int).to_numpy(), (srodki.y // KAFEL_LIDAR * KAFEL_LIDAR).astype(int).to_numpy())
    grupy = bud.index.to_series().groupby([kx, ky])
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda k: [model_wysokosci(n, int(k[0]), int(k[1])) for n in ("nmpt", "nmt")], grupy.groups))
    wynik = {}
    geom = bud.geometry.to_crs(2180)
    for k, idx in grupy.groups.items():
        x, y = int(k[0]), int(k[1])
        with rasterio.open(model_wysokosci("nmpt", x, y)) as nmpt, rasterio.open(model_wysokosci("nmt", x, y)) as nmt:
            for i, g in geom.loc[idx].items():
                srodek = g.buffer(-1)
                try:
                    dach, teren = wartosci(nmpt, g if srodek.is_empty else srodek), wartosci(nmt, g.buffer(3))
                except ValueError:  # obrys poza rastrem kafla (bardzo duży budynek na granicy)
                    continue
                if len(dach) and len(teren):
                    wynik[i] = float(np.median(dach) - np.percentile(teren, 10))
    return pd.Series(wynik, dtype=float)


def plik_bdot():
    """Warstwa budynków BDOT10k (OT_BUBD_A) z data/, np. data/0264_powiat_m.Wrocław/BDOT10K/..."""
    pliki = sorted(DATA.glob("*/BDOT10K/*OT_BUBD_A.xml"))
    if not pliki:
        raise FileNotFoundError(f"Brak warstwy budynków BDOT10k (*OT_BUBD_A.xml) w {DATA}/<powiat>/BDOT10K/")
    return pliki[0]


def wczytaj_bdot(obszar=None):
    """Budynki z BDOT10k, których środek leży w obszarze; EPSG:2177, indeks id (lokalnyId z BDOT)."""
    obszar = obszar if obszar is not None else zasieg()
    bbox = Transformer.from_crs(2177, 2180, always_xy=True).transform_bounds(*obszar.bounds)
    surowe = pyogrio.read_dataframe(plik_bdot(), bbox=bbox).to_crs(2177).set_index("lokalnyId")
    surowe.index.name = "id"
    bdot = gpd.GeoDataFrame({
        "funkcja": surowe.przewazajacaFunkcjaBudynku,
        "funkcja_ogolna": surowe.funkcjaOgolnaBudynku,
        "funkcje": surowe.funkcjaSzczegolowaBudynku.apply(lambda f: "; ".join(map(str, f))),
        "kategoria": surowe.kategoriaIstnienia,
        "kondygnacje": surowe.liczbaKondygnacji.astype(float),
        "nazwa": surowe.nazwa,
    }, geometry=surowe.geometry, crs=2177)
    bdot["kondygnacje"] = bdot.kondygnacje.where(bdot.kondygnacje > 0)
    return bdot[bdot.centroid.within(obszar)]


def wczytaj_budynki(obszar=None):
    """Budynki na arkuszach: BDOT10k z adresami z punktów adresowych.

    Kolumna h to wysokość [m] z LiDAR-u. Budynek, którego skaning jeszcze nie widział (poniżej 2 m), dostaje
    3,3 · kondygnacje + 2 m, a bez kondygnacji 8 m. Kolumna zrodlo_h mówi, skąd jest wysokość.
    mieszkalny_bdot to funkcja ogólna 'budynki mieszkalne'.
    """
    obszar = obszar if obszar is not None else zasieg()
    bud = _dolacz_adresy(wczytaj_bdot(obszar), wczytaj_adresy(obszar))
    bud["mieszkalny_bdot"] = bud.funkcja_ogolna == "budynki mieszkalne"
    kond = bud.kondygnacje
    lidar = wysokosc_lidar(bud).reindex(bud.index)
    lidar = lidar.where(lidar >= 2)
    bud["h"] = lidar.fillna(3.3 * kond + 2).fillna(8.0)
    bud["zrodlo_h"] = np.select([lidar.notna(), kond.notna()], ["LiDAR", "z kondygnacji"], "domyślna")
    return bud
