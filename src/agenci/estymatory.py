"""Estymatory liczby mieszkańców budynku.

objetosc      - baseline: powierzchnia zabudowy × wysokość (wynik względny, bez modelu)
objetosc_bdot - jak wyżej, ale 0 dla budynków, które BDOT10k uznaje za niemieszkalne albo nieużytkowane
wprost        - jedno wywołanie VLM, które od razu podaje liczbę mieszkańców (L0)
ze_wzoru      - obserwacje świadka × gęstość z rubryki:
                mieszkańcy = powierzchnia zabudowy × kondygnacje × udział mieszkalny × gęstość[typ] / 100

Rubryka to gęstość zaludnienia dla każdego typu (osoby na 100 m² powierzchni całkowitej kondygnacji).
Na razie daje ją model z wiedzy ogólnej (rubryka_llm); po dostaniu sum z 2021 roku można ją skalibrować
i wczytać z pliku (rubryka_z_pliku). Wzór nie potrzebuje sumy rejonu, więc działa też dla osiedli
oddanych po 2021 roku.
"""

import tomllib

from agenci.llm import tekst
from agenci.swiadkowie import MIESZKALNE, TYPY, tresc_karty

def objetosc(karta):
    return karta.pow_zabudowy_m2 * karta.h_m


def objetosc_bdot(karta):
    """Objętość budynków mieszkalnych i eksploatowanych według BDOT10k, 0 dla pozostałych."""
    return objetosc(karta) if karta.mieszkalny_bdot and karta.kategoria == "eksploatowany" else 0.0


SCHEMAT_WPROST = {
    "type": "object",
    "properties": {
        "mieszkancy": {"type": "number"},
        "typ": {"type": "string", "enum": list(TYPY)},
        "pewnosc": {"type": "number"},
        "uzasadnienie": {"type": "string"},
    },
    "required": ["mieszkancy", "typ", "pewnosc", "uzasadnienie"],
    "additionalProperties": False,
}

SYSTEM_WPROST = (
    "Szacujesz, ile osób mieszka w jednym budynku we Wrocławiu w 2025 roku. Dostajesz to, co jest dostępne: "
    "rekord z bazy BDOT10k, wycinki ortofotomapy skośnej (żółta linia to obrys podstawy, czerwona to obrys dachu) "
    "albo adres. Budynki niemieszkalne mają 0 mieszkańców. Zwróć liczbę mieszkańców, typ budynku "
    "(jeden z kodów poniżej), pewność od 0 do 1 i uzasadnienie w najwyżej dwóch zdaniach.\n\nTypy:\n"
    + "\n".join(f"- {kod}: {opis}" for kod, opis in TYPY.items()))


def wprost(klient, karta, zrodla, max_px=768, **log):
    """L0: jedno wywołanie, które od razu zwraca liczbę mieszkańców."""
    odp = klient.zapytaj(rola="wprost", system=SYSTEM_WPROST, tresc=tresc_karty(karta, zrodla, max_px),
                         schemat=SCHEMAT_WPROST, budynek=karta.id, **log)
    wynik = odp.dane
    if wynik is not None:
        wynik["mieszkancy"] = max(0.0, float(wynik["mieszkancy"]))
    return wynik, odp


SCHEMAT_RUBRYKI = {
    "type": "object",
    "properties": {
        "gestosci": {"type": "object", "properties": {t: {"type": "number"} for t in MIESZKALNE},
                     "required": MIESZKALNE, "additionalProperties": False},
        "uzasadnienie": {"type": "string"},
    },
    "required": ["gestosci", "uzasadnienie"],
    "additionalProperties": False,
}

SYSTEM_RUBRYKI = (
    "Układasz rubrykę dla systemu, który szacuje liczbę mieszkańców budynków we Wrocławiu w 2025 roku. "
    "Dla każdego typu budynku mieszkalnego podaj typową liczbę mieszkańców na 100 m² powierzchni całkowitej "
    "kondygnacji, czyli powierzchni zabudowy pomnożonej przez liczbę kondygnacji, razem ze ścianami, klatkami "
    "schodowymi i korytarzami. Uwzględnij typową wielkość mieszkań, liczbę osób w gospodarstwie domowym i "
    "pustostany. W uzasadnieniu napisz krótko, skąd biorą się różnice między typami.")


def rubryka_llm(klient, **log):
    """Gęstości per typ z wiedzy modelu (jedno wywołanie na przebieg, potem z pamięci)."""
    tresc = [tekst("Typy budynków mieszkalnych:\n" + "\n".join(f"- {t}: {TYPY[t]}" for t in MIESZKALNE))]
    odp = klient.zapytaj(rola="rubryka", system=SYSTEM_RUBRYKI, tresc=tresc, schemat=SCHEMAT_RUBRYKI, **log)
    if odp.dane is None:
        raise RuntimeError(f"Model nie zwrócił rubryki (stop_reason: {odp.stop})")
    return {t: max(0.0, float(g)) for t, g in odp.dane["gestosci"].items()}


def rubryka_z_pliku(sciezka):
    """Gęstości z pliku TOML z tabelą [gestosci] (np. po kalibracji na sumach z 2021 roku)."""
    with open(sciezka, "rb") as f:
        gestosci = tomllib.load(f)["gestosci"]
    if brak := set(MIESZKALNE) - set(gestosci):
        raise ValueError(f"W rubryce {sciezka} brakuje typów: {sorted(brak)}")
    return {t: float(gestosci[t]) for t in MIESZKALNE}


def ze_wzoru(obs, karta, rubryka):
    """Liczba mieszkańców z obserwacji świadka i rubryki gęstości."""
    if obs["typ"] not in rubryka or obs["stan"] != "uzytkowany":
        return 0.0
    kondygnacje = obs["kondygnacje"] or karta.kondygnacje or max(1, round(karta.h_m / 3))
    return karta.pow_zabudowy_m2 * kondygnacje * obs["udzial_mieszkalny"] * rubryka[obs["typ"]] / 100
