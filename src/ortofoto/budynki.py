"""Obrysy budynków z OpenStreetMap (Overpass API) dla zasięgu arkuszy, z kopią w data/."""

import json
import urllib.parse
import urllib.request

import geopandas as gpd
import numpy as np
import pandas as pd
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


def _pobierz(obszar, plik):
    lon, lat = Transformer.from_crs(2177, 4326, always_xy=True).transform(*np.array(obszar.envelope.exterior.coords).T)
    zapytanie = f'[out:json][timeout:90];way["building"]({lat.min()},{lon.min()},{lat.max()},{lon.max()});out tags geom;'
    elementy = _zapytaj(zapytanie)
    wiersze = [{"osm_id": e["id"], **{t: e["tags"].get(t) for t in TAGI},
                "geometry": Polygon([(p["lon"], p["lat"]) for p in e["geometry"]])}
               for e in elementy if len(e.get("geometry", [])) >= 4]
    gpd.GeoDataFrame(wiersze, crs=4326).to_file(plik, driver="GeoJSON")


def wczytaj_budynki(obszar=None):
    """Budynki, których środek leży na arkuszach, w EPSG:2177, z indeksem osm_id.

    Kolumna h to wysokość [m]: tag height z OSM, a gdy go brak 3,3 · kondygnacje + 2 m, a bez kondygnacji 8 m.
    Kolumna zrodlo_h mówi, która z tych reguł zadziałała.
    """
    obszar = obszar if obszar is not None else zasieg()
    x0, y0, x1, y1 = (round(v) for v in obszar.bounds)
    plik = DATA / f"osm_budynki_{x0}_{y0}_{x1}_{y1}.geojson"
    if not plik.exists():
        _pobierz(obszar, plik)

    bud = gpd.read_file(plik).to_crs(2177).set_index("osm_id").rename(columns={"name": "nazwa"})
    bud = bud[bud.centroid.within(obszar)].copy()
    bud["kondygnacje"] = pd.to_numeric(bud["building:levels"], errors="coerce")
    bud["h_osm"] = pd.to_numeric(bud["height"].astype(str).str.replace(",", "."), errors="coerce")
    bud["h"] = bud.h_osm.fillna(3.3 * bud.kondygnacje + 2).fillna(8.0)
    bud["zrodlo_h"] = np.select([bud.h_osm.notna(), bud.kondygnacje.notna()], ["pomiar OSM", "z kondygnacji"], "domyślna")
    return bud


def wybierz(bud, osm_id=None, adres=None):
    """Budynek po identyfikatorze OSM albo po adresie 'Ulica numer' (wystarczy końcówka nazwy ulicy)."""
    if osm_id is not None:
        return bud.loc[osm_id]
    ulica, numer = adres.rsplit(" ", 1)
    trafienia = bud[bud["addr:street"].str.endswith(ulica, na=False) & (bud["addr:housenumber"] == numer)]
    if trafienia.empty:
        raise KeyError(adres)
    return trafienia.iloc[0]


def opis(b):
    """Jednolinijkowy opis budynku do tytułów wykresów."""
    adres = f"{b['addr:street']} {b['addr:housenumber']}" if isinstance(b["addr:street"], str) else "bez adresu"
    kond = "?" if pd.isna(b.kondygnacje) else f"{b.kondygnacje:.0f}"
    return f"OSM {b.name} · {b.building} · {adres} · kondygnacje: {kond} · h = {b.h:.1f} m ({b.zrodlo_h})"
