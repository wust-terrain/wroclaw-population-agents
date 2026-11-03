"""Estymatory liczby mieszkańców budynku.

objetosc      - baseline: powierzchnia zabudowy × wysokość (wynik względny, bez modelu)
objetosc_bdot - jak wyżej, ale 0 dla budynków, które BDOT10k uznaje za niemieszkalne albo nieużytkowane
ze_wzoru      - obserwacje świadka × rubryka:
                dom:        mieszkańcy = osoby_na_dom × udział mieszkalny
                mieszkania: mieszkańcy = powierzchnia zabudowy × kondygnacje × udział mieszkalny × gęstość[klasa] / 100

Klasy idą za Pirowskim i Bartos (2018) oraz Pirowskim i Szypułą (2024): w domach jednorodzinnych liczba
mieszkańców słabo zależy od powierzchni, więc liczymy osoby na budynek; budynki wielorodzinne dzielimy na
niskie (do 5 kondygnacji) i wysokie, bo wysokie bloki są zaludnione dużo gęściej. Kondygnacje bierzemy
z BDOT10k, a od świadka tylko wtedy, gdy BDOT ich nie ma: zero-shot VLM myli się średnio o ok. 2,4
kondygnacji (OpenFACADES). Wzór bierze je z BDOT także w przebiegach, w których świadek nie widzi rekordu,
więc obraz wnosi do wyniku typ, udział mieszkalny i stan.

Rubrykę daje agent rubryki z wiedzy ogólnej (rubryka_llm, poziom L1) albo kalibracja na NSP 2021
(agenci.kalibracja, plik wczytywany przez rubryka_z_pliku, poziom L2). Wzór nie potrzebuje sumy kwadratu,
więc działa też dla osiedli oddanych po 2021 roku.
"""

import tomllib

import pandas as pd

from agenci.llm import tekst
from agenci.swiadkowie import TYPY

PROG_WYSOKI = 5  # wielorodzinny powyżej tylu kondygnacji jest "wysoki" (Pirowski i Bartos 2018, wariant 4)
KLASY = ["wielorodzinny_niski", "wielorodzinny_wysoki", "zbiorowy"]  # klasy z gęstością na 100 m²
DOMY = {"dom_jednorodzinny", "szeregowiec"}
WIELORODZINNE = {"kamienica", "blok_prl", "blok_nowy"}
DOMY_BDOT = {"budynek jednorodzinny", "dom letniskowy", "leśniczówka", "dom parafialny", "rezydencja biskupia"}


def _wielorodzinny(kondygnacje):
    return "wielorodzinny_wysoki" if kondygnacje > PROG_WYSOKI else "wielorodzinny_niski"


def klasa(typ, kondygnacje):
    """Klasa rubryki dla typu ze świadka: 'dom', klasa gęstości albo None dla budynku niemieszkalnego."""
    if typ in DOMY:
        return "dom"
    if typ == "zbiorowy":
        return "zbiorowy"
    return _wielorodzinny(kondygnacje) if typ in WIELORODZINNE else None


def klasa_bdot(funkcja, kondygnacje):
    """Ta sama klasa z przeważającej funkcji budynku mieszkalnego w BDOT10k (do kalibracji i bilansu kwadratów)."""
    if funkcja in DOMY_BDOT:
        return "dom"
    if funkcja == "budynek wielorodzinny":
        return _wielorodzinny(1 if pd.isna(kondygnacje) else kondygnacje)
    return "zbiorowy"  # dom studencki, dom opieki, internat, klasztor, koszary itd.


def objetosc(karta):
    return karta.pow_zabudowy_m2 * karta.h_m


def objetosc_bdot(karta):
    """Objętość budynków mieszkalnych i eksploatowanych według BDOT10k, 0 dla pozostałych."""
    return objetosc(karta) if karta.zamieszkany_bdot else 0.0


SCHEMAT_RUBRYKI = {
    "type": "object",
    "properties": {
        "osoby_na_dom": {"type": "number"},
        "gestosci": {"type": "object", "properties": {k: {"type": "number"} for k in KLASY},
                     "required": KLASY, "additionalProperties": False},
        "uzasadnienie": {"type": "string"},
    },
    "required": ["osoby_na_dom", "gestosci", "uzasadnienie"],
    "additionalProperties": False,
}

SYSTEM_RUBRYKI = (
    "Układasz rubrykę dla systemu, który szacuje liczbę mieszkańców budynków we Wrocławiu w 2025 roku. "
    "Podaj: osoby_na_dom, czyli przeciętną liczbę mieszkańców jednego domu jednorodzinnego lub segmentu "
    "zabudowy szeregowej; oraz dla każdej klasy budynku typową liczbę mieszkańców na 100 m² powierzchni "
    "całkowitej kondygnacji, czyli powierzchni zabudowy pomnożonej przez liczbę kondygnacji, razem ze ścianami, "
    "klatkami schodowymi i korytarzami. Uwzględnij typową wielkość mieszkań, liczbę osób w gospodarstwie "
    "domowym i pustostany. W uzasadnieniu napisz krótko, skąd biorą się różnice między klasami.")

OPISY_KLAS = {"wielorodzinny_niski": f"budynek wielorodzinny do {PROG_WYSOKI} kondygnacji (kamienice, niskie bloki)",
              "wielorodzinny_wysoki": f"budynek wielorodzinny powyżej {PROG_WYSOKI} kondygnacji (wysokie bloki)",
              "zbiorowy": TYPY["zbiorowy"]}


def _rubryka(dane):
    return {"osoby_na_dom": max(0.0, float(dane["osoby_na_dom"])),
            "gestosci": {k: max(0.0, float(dane["gestosci"][k])) for k in KLASY}}


def rubryka_llm(klient):
    """Rubryka z wiedzy modelu (L1): agent rubryki, jedno wywołanie na przebieg."""
    tresc = [tekst("Klasy budynków:\n" + "\n".join(f"- {k}: {opis}" for k, opis in OPISY_KLAS.items()))]
    odp = klient.zapytaj(rola="rubryka", system=SYSTEM_RUBRYKI, tresc=tresc, schemat=SCHEMAT_RUBRYKI)
    if odp.dane is None:
        raise RuntimeError(f"Model nie zwrócił rubryki (stop_reason: {odp.stop})")
    return _rubryka(odp.dane)


def rubryka_z_pliku(sciezka):
    """Rubryka z pliku TOML: osoby_na_dom i tabela [gestosci] (z kalibracji na NSP 2021, L2)."""
    with open(sciezka, "rb") as f:
        return _rubryka(tomllib.load(f))


def z_rubryki(klasa, pow_kondygnacji, rubryka):
    """Mieszkańcy całego budynku danej klasy: osoby na dom albo gęstość × powierzchnia kondygnacji; 0 bez klasy."""
    if pd.isna(klasa):
        return 0.0
    return rubryka["osoby_na_dom"] if klasa == "dom" else pow_kondygnacji * rubryka["gestosci"][klasa] / 100


def ze_wzoru(obs, karta, rubryka, z_rekordem=False):
    """Liczba mieszkańców z obserwacji świadka i rubryki.

    z_rekordem - przebieg widzi rekord BDOT10k. Typ "inny" znaczy też, że świadek nie umie określić typu (np. nie ma zdjęć),
    więc gdy rekord mówi o budynku mieszkalnym i eksploatowanym, klasę bierzemy z rekordu. Bez tabeli rekord nie może
    podsuwać wyniku, bo kontrola świadka z BDOT10k byłaby kolista.
    """
    if obs["stan"] != "uzytkowany":
        return 0.0
    kondygnacje = karta.kondygnacje or obs["kondygnacje"] or max(1, round(karta.h_m / 3))  # BDOT10k, świadek, wysokość
    k = klasa(obs["typ"], kondygnacje)
    if z_rekordem and obs["typ"] == "inny" and karta.zamieszkany_bdot:
        k = klasa_bdot(karta.funkcja, kondygnacje)
    return z_rubryki(k, karta.pow_zabudowy_m2 * kondygnacje, rubryka) * obs["udzial_mieszkalny"]
