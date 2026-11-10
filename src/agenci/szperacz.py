"""Szperacz: agent z wyszukiwarką internetową, który dla kilku największych budynków szuka opublikowanej liczby miejsc albo mieszkań.

Większość ludzi i większość błędu siedzi w kilku dużych budynkach: akademikach i nowych osiedlach. Liczba miejsc w akademiku
i liczba mieszkań w inwestycji dewelopera bywają podane w sieci, więc dla takich budynków pytamy o nią zamiast liczyć z
powierzchni. Szperacz dostaje adres i rekord, nie widzi zdjęć ani spisu, i ma odpowiedzieć "brak", gdy źródło nie mówi
o tym konkretnym budynku.
"""

from concurrent.futures import ThreadPoolExecutor

from pyproj import Transformer

from agenci.estymatory import OSOBY_NA_MIESZKANIE
from agenci.llm import ROWNOLEGLE, tekst

MAX_BUDYNKOW = 4  # najwięcej tyle budynków w przebiegu (limit kosztu)
MAX_WYSZUKAN = 2  # najwięcej tyle zapytań do wyszukiwarki na budynek
KOLUMNY = ["szukany", "znalezione", "liczba_z_sieci", "zrodlo", "cytat"]

SCHEMAT = {
    "type": "object",
    "properties": {
        "znalezione": {"type": "string", "enum": ["miejsca", "mieszkania", "brak"]},
        "liczba": {"type": "integer"},
        "zrodlo": {"type": "string"},
        "cytat": {"type": "string"},
    },
    "required": ["znalezione", "liczba", "zrodlo", "cytat"],
    "additionalProperties": False,
}

SYSTEM = (
    "Szukasz w internecie jednej liczby o jednym budynku we Wrocławiu: liczby miejsc noclegowych, jeśli to akademik, internat, "
    "dom opieki albo inne zamieszkanie zbiorowe, albo liczby mieszkań, jeśli to budynek mieszkalny. Wykonaj najwyżej "
    f"{MAX_WYSZUKAN} wyszukiwania. Liczy się tylko źródło, które mówi o tym konkretnym budynku (ten adres albo ta nazwa): strona "
    "uczelni, dewelopera, zarządcy, urzędu albo prasa. Nie szacuj i nie przeliczaj z powierzchni ani z liczby pięter. Liczba dla "
    "całego osiedla albo kilku budynków naraz się nie liczy.\n\n"
    "Zwróć:\n"
    "- znalezione: miejsca, mieszkania albo brak,\n"
    "- liczba: znaleziona liczba, a przy braku 0,\n"
    "- zrodlo: adres strony, a przy braku pusty tekst,\n"
    "- cytat: zdanie ze źródła, w którym pada ta liczba, a przy braku krótko, czego szukałeś.")


def wybierz(pred):
    """Budynki do sprawdzenia: zamieszkanie zbiorowe i największe szacunki, razem najwyżej MAX_BUDYNKOW."""
    p = pred[pred.mieszkancy > 0].sort_values("mieszkancy", ascending=False)
    return list(p.sort_values("typ", key=lambda t: t != "zbiorowy", kind="stable").budynek.head(MAX_BUDYNKOW))


def opis(b, wiersz, bud):
    """Treść pytania o jeden budynek: adres i nazwa z OSM i BDOT10k, rekord oraz typ od świadka."""
    lon, lat = Transformer.from_crs(2177, 4326, always_xy=True).transform(b.geometry.centroid.x, b.geometry.centroid.y)
    if isinstance(b["addr:street"], str):
        adres = f"Adres: {b['addr:street']} {b['addr:housenumber']}, Wrocław"
    else:  # OSM nie ma adresu tego budynku, więc podajemy adres najbliższego budynku, który go ma
        z_adresem = bud[bud["addr:street"].notna()]
        sasiad = z_adresem.loc[z_adresem.distance(b.geometry).idxmin()]
        adres = (f"Adres nieznany; najbliższy budynek z adresem ({sasiad.geometry.distance(b.geometry):.0f} m dalej): "
                 f"{sasiad['addr:street']} {sasiad['addr:housenumber']}, Wrocław")
    linie = [f"{adres} (współrzędne: {lat:.5f}, {lon:.5f})."]
    if isinstance(b.nazwa, str):
        linie.append(f"Nazwa w BDOT10k: {b.nazwa}.")
    linie.append(f"BDOT10k: {b.funkcja}, powierzchnia zabudowy {b.geometry.area:.0f} m², kondygnacje: {b.kondygnacje:.0f}."
                 if b.kondygnacje == b.kondygnacje else f"BDOT10k: {b.funkcja}, powierzchnia zabudowy {b.geometry.area:.0f} m².")
    linie.append(f"Typ według zdjęć lotniczych: {wiersz.typ}.")
    return "\n".join(linie)


def z_sieci(dane):
    """Liczba mieszkańców z odpowiedzi szperacza albo None, gdy niczego nie znalazł."""
    if dane is None or dane["znalezione"] == "brak" or dane["liczba"] <= 0 or not dane["zrodlo"]:
        return None
    return float(dane["liczba"]) * (OSOBY_NA_MIESZKANIE if dane["znalezione"] == "mieszkania" else 1.0)


def poszukaj(klient, pred, bud):
    """Predykcje z kolumnami szperacza; mieszkancy_wzor zachowuje szacunek sprzed szukania, mieszkancy bierze liczbę z sieci."""
    wiersze = pred.set_index("budynek")
    ids = wybierz(pred)

    def jeden(i):
        return klient.zapytaj(rola="szperacz", system=SYSTEM, tresc=[tekst(opis(bud.loc[i], wiersze.loc[i], bud))], schemat=SCHEMAT,
                              budynek=i, wyszukiwan=MAX_WYSZUKAN)

    with ThreadPoolExecutor(ROWNOLEGLE) as ex:
        odpowiedzi = dict(zip(ids, ex.map(jeden, ids)))

    p = pred.copy()
    p["mieszkancy_wzor"] = p.mieszkancy
    p["szukany"] = p.budynek.isin(ids)
    for i, odp in odpowiedzi.items():
        maska = p.budynek == i
        dane = odp.dane or {"znalezione": "brak", "liczba": 0, "zrodlo": "", "cytat": f"szperacz: {odp.stop}"}
        p.loc[maska, ["znalezione", "liczba_z_sieci", "zrodlo", "cytat"]] = [dane["znalezione"], dane["liczba"], dane["zrodlo"], dane["cytat"]]
        if (m := z_sieci(odp.dane)) is not None:
            p.loc[maska, "mieszkancy"] = m
        p.loc[maska, "koszt_usd"] += odp.koszt_usd
    return p
