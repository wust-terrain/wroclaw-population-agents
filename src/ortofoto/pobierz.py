"""Pobiera arkusze ortofotomapy skośnej (4 kierunki) ze skorowidza GUGiK do data/.

    python -m ortofoto.pobierz 6.148.12.04.1 6.148.12.05.1   # godła arkuszy
"""

import re
import sys
import urllib.parse
import urllib.request

from ortofoto import DATA

SKOROWIDZ = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WFS/skorOrtoUkosne"
WARSTWY = {"N": "Polnoc", "E": "Wschod", "S": "Poludnie", "W": "Zachod"}
FILTR = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo><fes:ValueReference>Godlo</fes:ValueReference>'
         "<fes:Literal>{}</fes:Literal></fes:PropertyIsEqualTo></fes:Filter>")


def adres(godlo, kier):
    """Link do pliku arkusza z jednego kierunku według skorowidza WFS."""
    zapytanie = urllib.parse.urlencode({"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                                        "TYPENAMES": f"gugik:SkorowidzeOrtofotomapyUkosnej{WARSTWY[kier]}", "FILTER": FILTR.format(godlo)})
    odp = urllib.request.urlopen(f"{SKOROWIDZ}?{zapytanie}", timeout=120).read().decode()
    linki = re.findall(r"<gugik:URL_do_pobrania>([^<]+)<", odp)
    if not linki:
        raise ValueError(f"Skorowidz nie ma arkusza {godlo} z kierunku {kier}")
    return linki[0]


def pobierz(godlo):
    for kier in WARSTWY:
        url = adres(godlo, kier)
        plik = DATA / url.rsplit("/", 1)[1]
        if not plik.exists():
            print(f"{plik.name} ...", flush=True)
            urllib.request.urlretrieve(url, plik.with_suffix(".czesc"))
            plik.with_suffix(".czesc").rename(plik)


if __name__ == "__main__":
    for g in sys.argv[1:]:
        pobierz(g)
