"""Szperacz: agent z wyszukiwarką internetową, który szuka opublikowanej liczby miejsc albo mieszkań w budynku.

Większość ludzi i większość błędu siedzi w kilku dużych budynkach: akademikach i nowych osiedlach. Liczba miejsc w akademiku
i liczba mieszkań w inwestycji dewelopera bywają podane w sieci, więc dla takich budynków pytamy o nią zamiast liczyć z
powierzchni. Sprawdzamy zawsze wszystkie akademiki, internaty i budynki hotelowe z BDOT10k (w „hotelu” bywają prywatne akademiki
i mikroapartamenty na wynajem długoterminowy, np. Starter przy wybrzeżu Pasteura 18), a do tego z każdego arkusza kilka
budynków z największym szacunkiem. Szperacz dostaje adres i rekord, nie widzi zdjęć ani spisu, i ma odpowiedzieć "brak", gdy źródło nie mówi
o tym konkretnym budynku.

Ewidencja dzieli jeden budynek zamieszkania zbiorowego (np. akademik) na kilka segmentów, a liczba miejsc w sieci dotyczy
całości. Stykające się segmenty takiego budynku z tą samą funkcją w BDOT10k tworzą więc jedną grupę: szperacz szuka raz na
grupę, a znalezioną liczbę dzielimy między segmenty według powierzchni brutto. Gdy grupa obejmuje kilka akademików spiętych
łącznikami, szperacz podaje sumę ich miejsc albo brak. Grupy bez własnego punktu adresowego nie szukamy: dostałaby adres
sąsiada i znalazłaby jego liczbę drugi raz. Pozostałe budynki są osobno, bo stykające się kamienice to osobne budynki
z osobnymi adresami.
"""

from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

from agenci.estymatory import OSOBY_NA_MIESZKANIE, klasa_bdot
from agenci.llm import ROWNOLEGLE, tekst
from ortofoto.arkusze import ARKUSZE, KOLEJNOSC

NA_ARKUSZ = 4  # oprócz ZAWSZE: najwięcej tyle budynków (grup segmentów) z jednego arkusza; wartość na start, do ustalenia z ekspertami
ZAWSZE = {"dom studencki", "internat lub bursa szkolna", "hotel robotniczy", "hotel", "motel", "pensjonat"}  # funkcje BDOT10k sprawdzane zawsze
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
    "dotyczyć całego budynku; gdy adresy obejmują kilka osobnych budynków (np. akademiki połączone łącznikami), podaj sumę miejsc "
    "wszystkich, ale tylko gdy znajdziesz liczbę dla każdego z nich, a inaczej brak. Hotel, aparthotel albo budynek z mikroapartamentami sprawdź, czy ludzie mieszkają w nim na stałe "
    "(prywatny akademik, mikroapartamenty albo pokoje na wynajem długoterminowy, hotel pracowniczy): wtedy podaj liczbę miejsc, "
    "licząc kawalerkę lub mikroapartament jako jedno miejsce; zwykły hotel dla turystów to brak. Nie szacuj i nie przeliczaj z powierzchni ani z liczby pięter. Liczba dla całego osiedla albo "
    "kilku osobnych budynków naraz się nie liczy.\n\n"
    "Zwróć:\n"
    "- znalezione: miejsca, mieszkania albo brak,\n"
    "- liczba: znaleziona liczba, a przy braku 0,\n"
    "- zrodlo: adres strony, a przy braku pusty tekst,\n"
    "- cytat: zdanie ze źródła, w którym pada ta liczba, a przy braku krótko, czego szukałeś.")


def grupy(bud):
    """Numer grupy dla każdego budynku: stykające się segmenty zamieszkania zbiorowego albo hotelu z tą samą funkcją mają
    wspólny numer, pozostałe budynki są każdy osobno (numerem jest id jednego z segmentów)."""
    zbiorowe = (bud.mieszkalny_bdot & (bud.funkcja.map(klasa_bdot) == "zbiorowy")) | bud.funkcja.isin(ZAWSZE)
    z = bud[zbiorowe][["funkcja", "geometry"]]
    pary = gpd.sjoin(z.assign(geometry=z.buffer(STYK)).reset_index(), z.reset_index(), predicate="intersects")
    pary = pary[pary.funkcja_left == pary.funkcja_right]
    rodzic = {i: i for i in z.index}

    def korzen(i):
        while rodzic[i] != i:
            i = rodzic[i]
        return i

    for a, b in zip(pary.id_left, pary.id_right):
        rodzic[korzen(a)] = korzen(b)
    return pd.Series({i: korzen(i) if i in rodzic else i for i in bud.index})


def wybierz(pred, bud):
    """Grupy segmentów do sprawdzenia (lista list id): wszystkie z funkcją z ZAWSZE, a z każdego arkusza do tego najwyżej
    NA_ARKUSZ innych, najpierw zamieszkanie zbiorowe ze świadka, potem największe szacunki grupy. Tylko grupy z własnym
    punktem adresowym: bez niego szperacz dostałby adres sąsiada i policzył jego miejsca drugi raz."""
    p = pred.set_index("budynek").join(bud[["funkcja", "adresy"]])
    p["grupa"] = grupy(bud).reindex(p.index)
    g = p.groupby("grupa").agg(mieszkancy=("mieszkancy", "sum"), zbiorowy=("typ", lambda t: (t == "zbiorowy").any()),
                               zawsze=("funkcja", lambda f: f.isin(ZAWSZE).any()), adres=("adresy", lambda a: a.notna().any()))
    g = g[g.adres]
    czlonkowie = p.groupby("grupa").groups
    reszta = g[~g.zawsze & (g.mieszkancy > 0)]
    kolejka = reszta.sort_values("mieszkancy", ascending=False).sort_values("zbiorowy", ascending=False, kind="stable").index
    srodki = gpd.GeoSeries([bud.geometry.loc[czlonkowie[k]].union_all().centroid for k in kolejka], index=kolejka, crs=bud.crs)
    wybrane = dict.fromkeys(list(g.index[g.zawsze]) + [k for arkusz in ARKUSZE[KOLEJNOSC[0]]
                                                       for k in kolejka[srodki.within(box(*arkusz.bounds)).to_numpy()][:NA_ARKUSZ]])
    return [sorted(czlonkowie[k]) for k in wybrane]  # dict.fromkeys: bez powtórek na styku arkuszy


def opis(ids, pred, bud):
    """Treść pytania o jeden budynek (grupę segmentów): adresy z punktów adresowych, nazwa i rekord z BDOT10k oraz typ od świadka."""
    b = bud.loc[ids]
    srodek = b.geometry.union_all().centroid
    lon, lat = Transformer.from_crs(2177, 4326, always_xy=True).transform(srodek.x, srodek.y)
    adresy = sorted({a.strip() for lista in b.adresy.dropna() for a in lista.split(",")} |
                    {f"{u} {n}" for u, n in zip(b["addr:street"], b["addr:housenumber"]) if isinstance(u, str)})
    adres = f"Adres: {', '.join(adresy)}, Wrocław"  # punkty adresowe w obrysie; blok z kilkoma klatkami ma ich kilka
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
