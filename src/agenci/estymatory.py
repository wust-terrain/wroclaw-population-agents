"""Estymatory liczby mieszkańców budynku.

objetosc      - baseline: powierzchnia zabudowy × wysokość (wynik względny, bez modelu)
objetosc_bdot - jak wyżej, ale 0 dla budynków, które BDOT10k uznaje za niemieszkalne albo nieużytkowane
ze_wzoru      - obserwacje świadka × rubryka:
                dom:                     mieszkańcy = OSOBY_NA_DOM × udział mieszkalny
                wielorodzinny, zbiorowy: mieszkańcy = powierzchnia zabudowy × kondygnacje × udział mieszkalny / M2_NA_OSOBE[klasa]

W domach jednorodzinnych liczba mieszkańców słabo zależy od powierzchni, więc liczymy osoby na budynek (Pirowski
i Bartos 2018). Kondygnacje bierzemy z BDOT10k, a od świadka tylko wtedy, gdy BDOT ich nie ma: zero-shot VLM myli się
średnio o ok. 2,4 kondygnacji (OpenFACADES). Wzór bierze je z BDOT także w przebiegach, w których świadek nie widzi
rekordu, więc obraz wnosi do wyniku typ, udział mieszkalny i stan.

Rubryka to stałe z literatury. Wzór nie potrzebuje sumy kwadratu, więc działa też dla osiedli oddanych po 2021 roku.
"""

OSOBY_NA_DOM = 2.88  # Pirowski i Bartos 2018, tab. 1, wariant 3 (Kraków, BDOT10k); to samo Pirowski i Szypuła 2024
M2_NA_OSOBE = {  # powierzchnia zabudowy × kondygnacje na osobę
    "wielorodzinny": 37.08,  # jak wyżej
    "zbiorowy": 31.0,  # College Planning & Management 2014, tab. 1: mediana 333,3 stopy² na miejsce w akademiku
}
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


def objetosc(karta):
    return karta.pow_zabudowy_m2 * karta.h_m


def objetosc_bdot(karta):
    """Objętość budynków mieszkalnych i eksploatowanych według BDOT10k, 0 dla pozostałych."""
    return objetosc(karta) if karta.zamieszkany_bdot else 0.0


def ze_wzoru(obs, karta, z_rekordem=False):
    """Liczba mieszkańców z obserwacji świadka i rubryki.

    z_rekordem - przebieg widzi rekord BDOT10k. Typ "inny" znaczy też, że świadek nie umie określić typu (np. nie ma zdjęć),
    więc gdy rekord mówi o budynku mieszkalnym i eksploatowanym, klasę bierzemy z rekordu. Bez tabeli rekord nie może
    podsuwać wyniku, bo kontrola świadka z BDOT10k byłaby kolista.
    """
    if obs["stan"] != "uzytkowany":
        return 0.0
    k = klasa_bdot(karta.funkcja) if z_rekordem and obs["typ"] == "inny" and karta.zamieszkany_bdot else klasa(obs["typ"])
    if k is None:
        return 0.0
    if k == "dom":
        return OSOBY_NA_DOM * obs["udzial_mieszkalny"]
    kondygnacje = karta.kondygnacje or obs["kondygnacje"] or max(1, round(karta.h_m / 3))  # BDOT10k, świadek, wysokość
    return karta.pow_zabudowy_m2 * kondygnacje * obs["udzial_mieszkalny"] / M2_NA_OSOBE[k]
