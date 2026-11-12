"""Pobiera arkusze ortofotomapy skośnej (4 kierunki) ze skorowidza GUGiK do data/.

    python -m ortofoto.pobierz 6.148.12.04.1 6.148.12.05.1   # wybrane godła
    python -m ortofoto.pobierz --srlm                        # wszystkie arkusze przecinające rejony SRLM (cały Wrocław)
    python -m ortofoto.pobierz --srlm --tylko-lista          # ile arkuszy i ile GB, bez pobierania

Przerwane pobieranie można wznowić tym samym poleceniem: gotowe pliki są pomijane, niedokończone mają końcówkę .czesc.
"""

import argparse
import io
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

from ortofoto import DATA

SKOROWIDZ = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WFS/skorOrtoUkosne"
WARSTWY = {"N": "Polnoc", "E": "Wschod", "S": "Poludnie", "W": "Zachod"}
FILTR = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo><fes:ValueReference>Godlo</fes:ValueReference>'
         "<fes:Literal>{}</fes:Literal></fes:PropertyIsEqualTo></fes:Filter>")
MB_NA_PLIK = 85  # przeciętny rozmiar jednego pliku (arkusz z jednego kierunku)
LISTA = DATA / "skorowidz_ukosne.gpkg"  # skorowidz dla obszaru SRLM zapisany po pierwszym pobraniu


def _wfs(kier, **parametry):
    zapytanie = urllib.parse.urlencode({"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                                        "TYPENAMES": f"gugik:SkorowidzeOrtofotomapyUkosnej{WARSTWY[kier]}"} | parametry)
    return urllib.request.urlopen(f"{SKOROWIDZ}?{zapytanie}", timeout=600).read()


def adresy_godla(godlo):
    """Linki do plików arkusza z 4 kierunków według skorowidza."""
    linki = [re.findall(r"<gugik:URL_do_pobrania>([^<]+)<", _wfs(k, FILTER=FILTR.format(godlo)).decode()) for k in WARSTWY]
    if not all(linki):
        raise ValueError(f"Skorowidz nie ma arkusza {godlo} ze wszystkich 4 kierunków")
    return [lk[0] for lk in linki]


def skorowidz_srlm():
    """Arkusze (wszystkie kierunki) przecinające rejony SRLM: godło, kierunek, rok, link, geometria; zapisane w data/."""
    if LISTA.exists():
        return gpd.read_file(LISTA)
    from agenci.srlm import wczytaj_srlm  # tylko tu: pobieranie arkuszy nie potrzebuje reszty pakietu agenci

    wroclaw = wczytaj_srlm().union_all()
    x0, y0, x1, y1 = Transformer.from_crs(2177, 2180, always_xy=True).transform_bounds(*wroclaw.bounds)
    czesci = []
    for kier in WARSTWY:
        start = 0
        while True:  # serwer oddaje najwyżej 1000 obiektów na stronę
            strona = gpd.read_file(io.BytesIO(_wfs(kier, BBOX=f"{y0:.0f},{x0:.0f},{y1:.0f},{x1:.0f},urn:ogc:def:crs:EPSG::2180",
                                                   COUNT=1000, STARTINDEX=start)))
            czesci.append(strona.assign(kierunek=kier))
            if len(strona) < 1000:
                break
            start += 1000
    s = pd.concat(czesci).to_crs(2177)
    s = s[s.intersects(wroclaw)].sort_values("Rok").drop_duplicates(["Godlo", "kierunek"], keep="last")  # najnowszy nalot
    s = s.rename(columns={"Godlo": "godlo", "Rok": "rok", "URL_do_pobrania": "url"})[["godlo", "kierunek", "rok", "url", "geometry"]]
    s.to_file(LISTA)
    return s


def pobierz_pliki(adresy, watki=4):
    """Pobiera pliki do data/ (kilka naraz), pomija już pobrane."""
    def jeden(url):
        plik = DATA / url.rsplit("/", 1)[1]
        if not plik.exists():
            urllib.request.urlretrieve(url, plik.with_suffix(".czesc"))
            plik.with_suffix(".czesc").rename(plik)
        return plik.name

    brakujace = [u for u in adresy if not (DATA / u.rsplit("/", 1)[1]).exists()]
    print(f"{len(adresy)} plików, do pobrania {len(brakujace)} (ok. {len(brakujace) * MB_NA_PLIK / 1000:.0f} GB)", flush=True)
    with ThreadPoolExecutor(watki) as ex:
        for n, nazwa in enumerate(ex.map(jeden, brakujace), 1):
            print(f"{n}/{len(brakujace)} {nazwa}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pobiera arkusze ortofotomapy skośnej z GUGiK.")
    parser.add_argument("godla", nargs="*", help="godła arkuszy, np. 6.148.12.04.2")
    parser.add_argument("--srlm", action="store_true", help="wszystkie arkusze przecinające rejony SRLM (cały Wrocław)")
    parser.add_argument("--tylko-lista", action="store_true", help="tylko policz arkusze i miejsce na dysku")
    args = parser.parse_args()
    if args.srlm:
        lista = skorowidz_srlm()
        print(f"{lista.godlo.nunique()} arkuszy, {len(lista)} plików, lata nalotu: {sorted(lista.rok.unique())}")
        adresy = list(lista.url)
    else:
        adresy = [u for g in args.godla for u in adresy_godla(g)]
    if not args.tylko_lista:
        pobierz_pliki(adresy)
