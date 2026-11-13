"""Szperacz: agent z wyszukiwarką internetową, który dla kilku największych budynków szuka opublikowanej liczby miejsc albo mieszkań.

Większość ludzi i większość błędu siedzi w kilku dużych budynkach: akademikach i nowych osiedlach. Liczba miejsc w akademiku
i liczba mieszkań w inwestycji dewelopera bywają podane w sieci, więc dla takich budynków pytamy o nią zamiast liczyć z
powierzchni. Szperacz dostaje adres i rekord, nie widzi zdjęć ani spisu, i ma odpowiedzieć "brak", gdy źródło nie mówi
o tym konkretnym budynku.

Ewidencja dzieli jeden budynek zamieszkania zbiorowego (np. akademik) na kilka segmentów, a liczba miejsc w sieci dotyczy
całości. Stykające się segmenty takiego budynku z tą samą funkcją w BDOT10k tworzą więc jedną grupę: szperacz szuka raz na
grupę, a znalezioną liczbę dzielimy między segmenty według powierzchni brutto. Pozostałe budynki są osobno, bo stykające się
kamienice to osobne budynki z osobnymi adresami.
"""

from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

from agenci.estymatory import OSOBY_NA_MIESZKANIE, klasa_bdot
from agenci.llm import ROWNOLEGLE, tekst
from ortofoto.arkusze import ARKUSZE, KOLEJNOSC

NA_ARKUSZ = 4  # najwięcej tyle budynków (grup segmentów) z jednego arkusza; wartość na start, do ustalenia z ekspertami
STYK = 0.5  # [m] segmenty bliżej siebie niż tyle uznajemy za stykające się
MAX_WYSZUKAN = 2  # najwięcej tyle zapytań do wyszukiwarki na budynek

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
    "uczelni, dewelopera, zarządcy, urzędu albo prasa. Budynek może mieć w ewidencji kilka segmentów i kilka adresów; liczba ma "
    "dotyczyć całego budynku. Nie szacuj i nie przeliczaj z powierzchni ani z liczby pięter. Liczba dla całego osiedla albo "
    "kilku osobnych budynków naraz się nie liczy.\n\n"
    "Zwróć:\n"
    "- znalezione: miejsca, mieszkania albo brak,\n"
    "- liczba: znaleziona liczba, a przy braku 0,\n"
    "- zrodlo: adres strony, a przy braku pusty tekst,\n"
    "- cytat: zdanie ze źródła, w którym pada ta liczba, a przy braku krótko, czego szukałeś.")


def grupy(bud):
    """Numer grupy dla każdego budynku: stykające się segmenty zamieszkania zbiorowego z tą samą funkcją mają wspólny numer,
    pozostałe budynki są każdy osobno (numerem jest id jednego z segmentów)."""
    z = bud[bud.mieszkalny_bdot & (bud.funkcja.map(klasa_bdot) == "zbiorowy")][["funkcja", "geometry"]]
    pary = gpd.sjoin(z.assign(geometry=z.buffer(STYK)).reset_index(), z.reset_index(), predicate="intersects")
    rodzic = {i: i for i in z.index}

    def korzen(i):
        while rodzic[i] != i:
            i = rodzic[i]
        return i

    for a, b in zip(pary.id_left[pary.funkcja_left == pary.funkcja_right], pary.id_right[pary.funkcja_left == pary.funkcja_right]):
        rodzic[korzen(a)] = korzen(b)
    return pd.Series({i: korzen(i) if i in rodzic else i for i in bud.index})


def wybierz(pred, bud):
    """Grupy segmentów do sprawdzenia (lista list id): z każdego arkusza najwyżej NA_ARKUSZ, najpierw zamieszkanie zbiorowe,
    potem największe szacunki grupy."""
    p = pred[pred.mieszkancy > 0].set_index("budynek")
    p["grupa"] = grupy(bud).reindex(p.index)
    g = p.groupby("grupa").agg(mieszkancy=("mieszkancy", "sum"), zbiorowy=("typ", lambda t: (t == "zbiorowy").any()))
    kolejka = g.sort_values("mieszkancy", ascending=False).sort_values("zbiorowy", ascending=False, kind="stable").index
    czlonkowie = p.groupby("grupa").groups
    srodki = gpd.GeoSeries([bud.geometry.loc[czlonkowie[k]].union_all().centroid for k in kolejka], index=kolejka, crs=bud.crs)
    wybrane = dict.fromkeys(k for arkusz in ARKUSZE[KOLEJNOSC[0]]
                            for k in kolejka[srodki.within(box(*arkusz.bounds)).to_numpy()][:NA_ARKUSZ])  # bez powtórek na styku arkuszy
    return [sorted(czlonkowie[k]) for k in wybrane]


def opis(ids, pred, bud):
    """Treść pytania o jeden budynek (grupę segmentów): adresy z punktów adresowych, nazwa i rekord z BDOT10k oraz typ od świadka."""
    b = bud.loc[ids]
    srodek = b.geometry.union_all().centroid
    lon, lat = Transformer.from_crs(2177, 4326, always_xy=True).transform(srodek.x, srodek.y)
    adresy = sorted({a.strip() for lista in b.adresy.dropna() for a in lista.split(",")} |
                    {f"{u} {n}" for u, n in zip(b["addr:street"], b["addr:housenumber"]) if isinstance(u, str)})
    if adresy:  # punkty adresowe w obrysie; blok z kilkoma klatkami ma ich kilka
        adres = f"Adres: {', '.join(adresy)}, Wrocław"
    else:  # brak adresu, więc podajemy adres najbliższego budynku, który go ma
        z_adresem = bud[bud["addr:street"].notna()]
        sasiad = z_adresem.loc[z_adresem.distance(srodek).idxmin()]
        adres = (f"Adres nieznany; najbliższy budynek z adresem ({sasiad.geometry.distance(srodek):.0f} m dalej): "
                 f"{sasiad['addr:street']} {sasiad['addr:housenumber']}, Wrocław")
    linie = [f"{adres} (współrzędne: {lat:.5f}, {lon:.5f})."]
    if b.nazwa.notna().any():
        linie.append(f"Nazwa w BDOT10k: {'; '.join(b.nazwa.dropna().unique())}.")
    brutto = (b.geometry.area * b.kondygnacje.fillna(1)).sum()
    segmenty = f", {len(ids)} segmenty w ewidencji" if len(ids) > 1 else ""
    linie.append(f"BDOT10k: {'; '.join(b.funkcja.unique())}, powierzchnia zabudowy {b.geometry.area.sum():.0f} m², "
                 f"powierzchnia brutto (zabudowa × kondygnacje) {brutto:.0f} m²{segmenty}.")
    typy = pred.set_index("budynek").typ.reindex(ids).dropna().unique()
    linie.append(f"Typ według zdjęć lotniczych: {', '.join(typy) or 'brak'}.")
    return "\n".join(linie)


def z_sieci(dane):
    """Liczba mieszkańców z odpowiedzi szperacza albo None, gdy niczego nie znalazł."""
    if dane is None or dane["znalezione"] == "brak" or dane["liczba"] <= 0 or not dane["zrodlo"]:
        return None
    return float(dane["liczba"]) * (OSOBY_NA_MIESZKANIE if dane["znalezione"] == "mieszkania" else 1.0)


def poszukaj(klient, pred, bud):
    """Predykcje z kolumnami szperacza; mieszkancy_wzor zachowuje szacunek sprzed szukania, mieszkancy bierze liczbę z sieci
    podzieloną między segmenty grupy według powierzchni brutto."""
    lista = wybierz(pred, bud)

    def jeden(ids):
        return klient.zapytaj(rola="szperacz", system=SYSTEM, tresc=[tekst(opis(ids, pred, bud))], schemat=SCHEMAT,
                              budynek=ids[0], wyszukiwan=MAX_WYSZUKAN)

    with ThreadPoolExecutor(ROWNOLEGLE) as ex:
        odpowiedzi = list(ex.map(jeden, lista))

    p = pred.copy()
    p["mieszkancy_wzor"] = p.mieszkancy
    p["szukany"] = p.budynek.isin({i for ids in lista for i in ids})
    for ids, odp in zip(lista, odpowiedzi):
        maska = p.budynek.isin(ids)
        dane = odp.dane or {"znalezione": "brak", "liczba": 0, "zrodlo": "", "cytat": f"szperacz: {odp.stop}"}
        p.loc[maska, ["znalezione", "liczba_z_sieci", "zrodlo", "cytat"]] = [dane["znalezione"], dane["liczba"], dane["zrodlo"], dane["cytat"]]
        if (m := z_sieci(odp.dane)) is not None:
            brutto = bud.geometry.area.loc[ids] * bud.kondygnacje.loc[ids].fillna(1)
            p.loc[maska, "mieszkancy"] = p.loc[maska, "budynek"].map(m * brutto / brutto.sum())
        p.loc[maska, "koszt_usd"] = p.loc[maska, "koszt_usd"].fillna(0.0) + odp.koszt_usd / len(ids)
    return p
