"""Estymatory liczby mieszkańców budynku.

objetosc_bdot - baseline bez modelu: powierzchnia zabudowy × wysokość (wynik względny), 0 dla budynków, które BDOT10k uznaje
                za niemieszkalne albo nieużytkowane
ze_wzoru      - obserwacje świadka × rubryka:
                dom:                     mieszkańcy = OSOBY_NA_DOM × udział mieszkalny × gęstość
                wielorodzinny, zbiorowy: mieszkańcy = powierzchnia zabudowy × kondygnacje × udział mieszkalny × gęstość / M2_NA_OSOBE[klasa]
z_rekordu     - ta sama rubryka z klasą z BDOT10k i oboma mnożnikami równymi 1; wynik zapasowy, gdy świadek nie odpowie

W domach jednorodzinnych liczba mieszkańców słabo zależy od powierzchni, więc liczymy osoby na budynek (Pirowski
i Bartos 2018). Kondygnacje są z BDOT10k (mają je wszystkie budynki mieszkalne), a gdy ich brak, z wysokości z LiDAR-u.

Rubryka to stałe z literatury, liczone na całej powierzchni brutto budynków mieszkalnych, razem z klatkami i lokalami
usługowymi (Pirowski i Bartos 2018, wz. 1 i s. 468). Świadek doważa je dwoma mnożnikami: udział mieszkalny (0-1, 1 to typowy
budynek tej klasy) i gęstość (1 to typowo, więcej przy mikrokawalerkach, mniej przy dużych mieszkaniach). Wzór nie potrzebuje
sumy kwadratu, więc działa też dla osiedli oddanych po 2021 roku.
"""

OSOBY_NA_DOM = 2.88  # Pirowski i Bartos 2018, tab. 1, wariant 3 (Kraków, BDOT10k); to samo Pirowski i Szypuła 2024
M2_NA_OSOBE = {  # powierzchnia zabudowy × kondygnacje na osobę
    "wielorodzinny": 37.08,  # jak wyżej
    "zbiorowy": 31.0,  # College Planning & Management 2014, tab. 1: mediana 333,3 stopy² na miejsce w akademiku
}
OSOBY_NA_MIESZKANIE = 1.71  # GUS, Wrocław, koniec 2024 (polskawliczbach.pl); mnoży liczbę mieszkań znalezioną przez szperacza
DOMY = {"dom_jednorodzinny", "szeregowiec"}
WIELORODZINNE = {"kamienica", "blok_prl", "blok_nowy"}
DOMY_BDOT = {"budynek jednorodzinny", "dom letniskowy", "leśniczówka", "dom parafialny", "rezydencja biskupia"}


def klasa(typ):
    """Klasa rubryki dla typu ze świadka: 'dom', 'wielorodzinny', 'zbiorowy' albo None dla budynku niemieszkalnego."""
    if typ in DOMY:
        return "dom"
    if typ == "zbiorowy":
        return "zbiorowy"
    return "wielorodzinny" if typ in WIELORODZINNE else None


def klasa_bdot(funkcja):
    """Ta sama klasa z przeważającej funkcji budynku mieszkalnego w BDOT10k."""
    if funkcja in DOMY_BDOT:
        return "dom"
    return "wielorodzinny" if funkcja == "budynek wielorodzinny" else "zbiorowy"  # zbiorowy: dom studencki, dom opieki, internat, klasztor, koszary itd.


def objetosc_bdot(karta):
    """Objętość budynków mieszkalnych i eksploatowanych według BDOT10k, 0 dla pozostałych."""
    return karta.pow_zabudowy_m2 * karta.h_m if karta.zamieszkany_bdot else 0.0


def _rubryka(k, karta):
    """Mieszkańcy budynku klasy k według samej rubryki, czyli przy obu mnożnikach równych 1; None to budynek niemieszkalny."""
    if k is None:
        return 0.0
    if k == "dom":
        return OSOBY_NA_DOM
    kondygnacje = karta.kondygnacje or max(1, round(karta.h_m / 3))
    return karta.pow_zabudowy_m2 * kondygnacje / M2_NA_OSOBE[k]


def z_rekordu(karta):
    """Rubryka z klasą z BDOT10k: 0 dla budynków niemieszkalnych albo nieeksploatowanych."""
    return _rubryka(klasa_bdot(karta.funkcja), karta) if karta.zamieszkany_bdot else 0.0


def ze_wzoru(obs, karta):
    """Liczba mieszkańców z obserwacji świadka i rubryki.

    Typ "inny" znaczy też, że świadek nie umie określić typu (np. nie ma zdjęć), więc gdy rekord mówi o budynku mieszkalnym
    i eksploatowanym, klasę bierzemy z rekordu.
    """
    if obs["stan"] != "uzytkowany":
        return 0.0
    k = klasa_bdot(karta.funkcja) if obs["typ"] == "inny" and karta.zamieszkany_bdot else klasa(obs["typ"])
    return _rubryka(k, karta) * obs["udzial_mieszkalny"] * obs["gestosc"]
