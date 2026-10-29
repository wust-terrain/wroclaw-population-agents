"""Budynki na arkuszach: obrysy i funkcja z BDOT10k, adres i zmierzona wysokość z OpenStreetMap.

BDOT10k (warstwa OT_BUBD_A, obrysy z ewidencji gruntów i budynków) to główne źródło: każdy budynek
ma tam funkcję (np. budynek wielorodzinny), liczbę kondygnacji i stan (eksploatowany, w budowie...).
Z OSM dołączamy adres i tag height tam, gdzie obrys OSM pokrywa co najmniej połowę obrysu BDOT.
"""

import json
import urllib.parse
import urllib.request

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer
from shapely.geometry import Polygon

from ortofoto import DATA
from ortofoto.arkusze import zasieg

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
TAGI = ["building", "building:levels", "height", "addr:street", "addr:housenumber", "name"]


def _zapytaj(zapytanie):
    """Wysyła zapytanie do kolejnych serwerów Overpass, aż któryś odpowie."""
    for url in OVERPASS:
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": zapytanie}).encode(),
                                     headers={"User-Agent": "wroclaw-population-agents/0.1"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))["elements"]
        except OSError as e:  # HTTPError i timeout dziedziczą po OSError
            blad = e
    raise blad


def _pobierz_osm(obszar, plik):
    lon, lat = Transformer.from_crs(2177, 4326, always_xy=True).transform(*np.array(obszar.envelope.exterior.coords).T)
    zapytanie = f'[out:json][timeout:90];way["building"]({lat.min()},{lon.min()},{lat.max()},{lon.max()});out tags geom;'
    wiersze = [{"osm_id": e["id"], **{t: e["tags"].get(t) for t in TAGI},
                "geometry": Polygon([(p["lon"], p["lat"]) for p in e["geometry"]])}
               for e in _zapytaj(zapytanie) if len(e.get("geometry", [])) >= 4]
    gpd.GeoDataFrame(wiersze, crs=4326).to_file(plik, driver="GeoJSON")


def wczytaj_osm(obszar=None):
    """Obrysy budynków z OSM (pobrane raz przez Overpass i zapisane w data/), indeks osm_id."""
    obszar = obszar if obszar is not None else zasieg()
    x0, y0, x1, y1 = (round(v) for v in obszar.bounds)
    plik = DATA / f"osm_budynki_{x0}_{y0}_{x1}_{y1}.geojson"
    if not plik.exists():
        _pobierz_osm(obszar, plik)
    osm = gpd.read_file(plik).to_crs(2177).set_index("osm_id")
    osm["kondygnacje_osm"] = pd.to_numeric(osm["building:levels"], errors="coerce")
    osm["h_osm"] = pd.to_numeric(osm["height"].astype(str).str.replace(",", "."), errors="coerce")
    return osm[osm.centroid.within(obszar)]


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


def _dopasuj_osm(bdot, osm, prog=0.5):
    """Dla każdego budynku BDOT obrys OSM, który pokrywa największą część jego obrysu (co najmniej prog).

    Kryterium to udział obrysu BDOT leżący w obrysie OSM, a nie IoU: ewidencja dzieli bloki na segmenty,
    a OSM często ma jeden obrys całego bloku; każdy segment dziedziczy wtedy wysokość i adres bloku.
    """
    pary = gpd.sjoin(bdot[["geometry"]].reset_index(), osm[["geometry"]].reset_index(), predicate="intersects")
    a = bdot.geometry.loc[pary["id"]].values
    b = osm.geometry.loc[pary["osm_id"]].values
    pary["pokrycie"] = a.intersection(b).area / a.area
    najlepsze = pary[pary.pokrycie >= prog].sort_values("pokrycie").drop_duplicates("id", keep="last")
    return najlepsze.set_index("id").osm_id


def wczytaj_budynki(obszar=None):
    """Budynki na arkuszach: BDOT10k z dołączonymi danymi OSM.

    Kolumna h to wysokość [m]: tag height z OSM, a gdy go brak 3,3 · kondygnacje + 2 m, a bez kondygnacji 8 m.
    Kolumna zrodlo_h mówi, która reguła zadziałała. mieszkalny_bdot to funkcja ogólna 'budynki mieszkalne'.
    """
    obszar = obszar if obszar is not None else zasieg()
    bud = wczytaj_bdot(obszar)
    osm = wczytaj_osm(obszar)
    bud["osm_id"] = _dopasuj_osm(bud, osm).astype("Int64")
    kolumny_osm = ["building", "addr:street", "addr:housenumber", "kondygnacje_osm", "h_osm"]
    bud = bud.join(osm[kolumny_osm], on="osm_id")
    bud["mieszkalny_bdot"] = bud.funkcja_ogolna == "budynki mieszkalne"
    kond = bud.kondygnacje.fillna(bud.kondygnacje_osm)
    bud["h"] = bud.h_osm.fillna(3.3 * kond + 2).fillna(8.0)
    bud["zrodlo_h"] = np.select([bud.h_osm.notna(), kond.notna()], ["pomiar OSM", "z kondygnacji"], "domyślna")
    return bud


def wybierz(bud, id=None, osm_id=None, adres=None):
    """Budynek po id z BDOT, po identyfikatorze OSM albo po adresie 'Ulica numer' (wystarczy końcówka ulicy)."""
    if id is not None:
        return bud.loc[id]
    if osm_id is not None:
        trafienia = bud[bud.osm_id == osm_id]
    else:
        ulica, numer = adres.rsplit(" ", 1)
        trafienia = bud[bud["addr:street"].str.endswith(ulica, na=False) & (bud["addr:housenumber"] == numer)]
    if trafienia.empty:
        raise KeyError(osm_id if osm_id is not None else adres)
    return trafienia.iloc[0]


def opis(b):
    """Jednolinijkowy opis budynku do tytułów wykresów."""
    adres = f"{b['addr:street']} {b['addr:housenumber']}" if isinstance(b["addr:street"], str) else "bez adresu"
    kond = "?" if pd.isna(b.kondygnacje) else f"{b.kondygnacje:.0f}"
    return f"{b.funkcja} · {adres} · kondygnacje: {kond} · h = {b.h:.1f} m ({b.zrodlo_h})"
