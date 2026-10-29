"""Świadek wizualny: jedno wywołanie VLM na budynek, zwraca obserwacje (bez liczby mieszkańców).

To moduł percepcji, nie agent: dostaje kartę budynku i zwraca typ zabudowy, kondygnacje,
udział mieszkalny i stan. Liczbę mieszkańców liczy dopiero estymator, więc da się osobno
sprawdzić, co wnosi obraz (H1), a co reguła gęstości.
"""

from agenci.llm import obraz, tekst

TYPY = {
    "kamienica": "kamienica, przedwojenny budynek czynszowy",
    "blok_prl": "blok mieszkalny z lat 1950-1995, w tym wielka płyta",
    "blok_nowy": "budynek wielorodzinny zbudowany po 1995 roku",
    "dom_jednorodzinny": "dom jednorodzinny wolnostojący",
    "szeregowiec": "zabudowa szeregowa lub bliźniacza",
    "zbiorowy": "zamieszkanie zbiorowe: akademik, internat, dom opieki, hotel pracowniczy",
    "uslugi": "budynek usługowy, biurowy lub publiczny (sklep, szkoła, szpital, kościół)",
    "przemysl": "budynek przemysłowy lub magazynowy",
    "garaz": "garaż, budynek gospodarczy, wiata",
    "inny": "inny albo nie da się określić",
}
MIESZKALNE = ["kamienica", "blok_prl", "blok_nowy", "dom_jednorodzinny", "szeregowiec", "zbiorowy"]
STANY = ["uzytkowany", "w_budowie", "pustostan"]
WIDOKI = {"N": "kamera patrzy na północ, widać ścianę południową", "E": "kamera patrzy na wschód, widać ścianę zachodnią",
          "S": "kamera patrzy na południe, widać ścianę północną", "W": "kamera patrzy na zachód, widać ścianę wschodnią"}

SCHEMAT_OBSERWACJI = {
    "type": "object",
    "properties": {
        "typ": {"type": "string", "enum": list(TYPY)},
        "kondygnacje": {"type": "integer"},
        "udzial_mieszkalny": {"type": "number"},
        "stan": {"type": "string", "enum": STANY},
        "pewnosc": {"type": "number"},
        "uzasadnienie": {"type": "string"},
    },
    "required": ["typ", "kondygnacje", "udzial_mieszkalny", "stan", "pewnosc", "uzasadnienie"],
    "additionalProperties": False,
}


def system_swiadka(zrodla, obrys):
    czesci = ["Opisujesz jeden budynek we Wrocławiu na potrzeby szacowania liczby jego mieszkańców."]
    if "widoki" in zrodla:
        czesci.append(
            "Zdjęcia to wycinki ortofotomapy skośnej z nalotu w 2025 roku. Podstawa budynku leży na swoim miejscu, "
            "dach jest przesunięty od kamery, a między nimi widać ścianę zwróconą do kamery. "
            + ("Żółta linia to obrys podstawy, czerwona to obrys dachu. Opisz tylko budynek w tych obrysach, "
               "sąsiednie budynki pomiń." if obrys else "Opisz budynek na środku wycinka, sąsiednie budynki pomiń."))
    if "tabela" in zrodla:
        czesci.append("Rekord z bazy BDOT10k pochodzi z ewidencji budynków i bywa nieaktualny (np. nowe osiedla, "
                      "zmiana sposobu użytkowania). Gdy obraz wyraźnie mu przeczy, opisz to, co widzisz.")
    if "fasady" in zrodla:
        czesci.append("Fasady to ściany zwrócone do kamery, wyprostowane do prostokąta przy założonej wysokości "
                      "budynku; gdy ta wysokość jest błędna, fasada może obejmować kawałek dachu albo nie mieścić "
                      "całej ściany.")
    czesci.append(
        "Nie szacuj liczby mieszkańców. Zwróć:\n"
        "- typ: jeden z kodów poniżej,\n"
        "- kondygnacje: liczba kondygnacji nadziemnych łącznie z poddaszem użytkowym,\n"
        "- udzial_mieszkalny: część powierzchni przeznaczona na mieszkania, od 0 do 1 "
        "(np. 0,8, gdy parter zajmują sklepy),\n"
        "- stan: uzytkowany, w_budowie albo pustostan,\n"
        "- pewnosc: od 0 do 1,\n"
        "- uzasadnienie: najwyżej dwa zdania o tym, na czym opierasz odpowiedź.\n\n"
        "Typy:\n" + "\n".join(f"- {kod}: {opis}" for kod, opis in TYPY.items()))
    return "\n\n".join(czesci)


def tabela(karta):
    """Rekord budynku z BDOT10k (ewidencja budynków) i wysokość, jeśli jest zmierzona."""
    wiersze = [f"powierzchnia zabudowy: {karta.pow_zabudowy_m2:.0f} m²"]
    if karta.funkcja:
        wiersze.append(f"przeważająca funkcja: {karta.funkcja}")
    if karta.funkcje and karta.funkcje != karta.funkcja:
        wiersze.append(f"wszystkie funkcje: {karta.funkcje}")
    if karta.kondygnacje:
        wiersze.append(f"kondygnacje: {karta.kondygnacje:.0f}")
    if karta.kategoria:
        wiersze.append(f"stan: {karta.kategoria}")
    if karta.zrodlo_h == "pomiar OSM":
        wiersze.append(f"wysokość (OSM): {karta.h_m:.1f} m")
    return "Dane z bazy BDOT10k:\n" + "\n".join(f"- {w}" for w in wiersze)


def tresc_karty(karta, zrodla, max_px=768):
    """Bloki promptu z karty, tylko ze źródeł wymienionych w zrodla (tabela, widoki, fasady, adres)."""
    bloki = []
    if "widoki" in zrodla:
        for kier, img in karta.widoki.items():
            bloki += [tekst(f"Widok {kier}: {WIDOKI[kier]}."), obraz(img, max_px)]
    if "fasady" in zrodla:
        for kier, img in karta.fasady.items():
            bloki += [tekst(f"Fasada z widoku {kier}."), obraz(img, max_px)]
    if "tabela" in zrodla:
        bloki.append(tekst(tabela(karta)))
    if "adres" in zrodla:  # tylko sonda pamięci; zwykłe prompty nie zawierają adresu
        bloki.append(tekst(f"Adres: {karta.adres}, Wrocław."))
    if not bloki:
        bloki.append(tekst("Brak danych o budynku."))
    return bloki


def swiadek_wizualny(klient, karta, zrodla, obrys=True, max_px=768, **log):
    """Obserwacje o budynku (słownik zgodny z SCHEMAT_OBSERWACJI albo None przy odmowie) i odpowiedź API."""
    odp = klient.zapytaj(rola="swiadek_wizualny", system=system_swiadka(zrodla, obrys),
                         tresc=tresc_karty(karta, zrodla, max_px), schemat=SCHEMAT_OBSERWACJI,
                         budynek=karta.id, **log)
    obs = odp.dane
    if obs is not None:  # schemat nie ogranicza zakresów liczb, więc przycinamy tutaj
        obs["kondygnacje"] = max(0, int(obs["kondygnacje"]))
        obs["udzial_mieszkalny"] = min(1.0, max(0.0, float(obs["udzial_mieszkalny"])))
        obs["pewnosc"] = min(1.0, max(0.0, float(obs["pewnosc"])))
    return obs, odp
