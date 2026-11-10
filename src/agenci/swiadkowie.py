"""Świadek wizualny: jedno wywołanie VLM na budynek, zwraca obserwacje (bez liczby mieszkańców).

To moduł percepcji: dostaje kartę budynku i zwraca typ zabudowy, kondygnacje, udział mieszkalny i stan. Liczbę mieszkańców
liczy dopiero estymator, więc da się osobno sprawdzić, co wnosi obraz, a co rubryka.
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
STANY = ["uzytkowany", "w_budowie", "pustostan"]
WIDOKI = {"N": "kamera patrzy na północ, widać ścianę południową", "E": "kamera patrzy na wschód, widać ścianę zachodnią",
          "S": "kamera patrzy na południe, widać ścianę północną", "W": "kamera patrzy na zachód, widać ścianę wschodnią"}
OPIS = ["typ", "kondygnacje", "udzial_mieszkalny", "stan"]  # to, co świadek twierdzi o budynku

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

SYSTEM_DOPYTANIA = (
    "Oglądasz ten budynek drugi raz, bo agent bilansujący, który nie widzi zdjęć, ma wątpliwość co do jego opisu. Agent może "
    "się mylić. Zmień odpowiedź tylko wtedy, gdy obraz to uzasadnia; w przeciwnym razie powtórz poprzednią. W uzasadnieniu "
    "odnieś się do pytania.")


def system_swiadka(z_rekordem):
    czesci = ["Opisujesz jeden budynek we Wrocławiu na potrzeby szacowania liczby jego mieszkańców.",
              ("Zdjęcia to wycinki ortofotomapy skośnej z nalotu w 2025 roku. Podstawa budynku leży na swoim miejscu, "
               "dach jest przesunięty od kamery, a między nimi widać ścianę zwróconą do kamery. "
               "Żółta linia to obrys podstawy, czerwona to obrys dachu. Opisz tylko budynek w tych obrysach, "
               "sąsiednie budynki pomiń.")]
    if z_rekordem:
        czesci.append("Rekord z bazy BDOT10k pochodzi z ewidencji budynków i bywa nieaktualny (np. nowe osiedla, "
                      "zmiana sposobu użytkowania). Gdy obraz wyraźnie mu przeczy, opisz to, co widzisz.")
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
    """Rekord budynku z BDOT10k (ewidencja budynków) i wysokość, jeśli jest z LiDAR-u."""
    wiersze = [f"powierzchnia zabudowy: {karta.pow_zabudowy_m2:.0f} m²"]
    if karta.funkcja:
        wiersze.append(f"przeważająca funkcja: {karta.funkcja}")
    if karta.funkcje and karta.funkcje != karta.funkcja:
        wiersze.append(f"wszystkie funkcje: {karta.funkcje}")
    if karta.kondygnacje:
        wiersze.append(f"kondygnacje: {karta.kondygnacje:.0f}")
    if karta.kategoria:
        wiersze.append(f"stan: {karta.kategoria}")
    if karta.zrodlo_h == "LiDAR":
        wiersze.append(f"wysokość (skaning laserowy): {karta.h_m:.1f} m")
    return "Dane z bazy BDOT10k:\n" + "\n".join(f"- {w}" for w in wiersze)


def tresc_karty(karta, z_rekordem):
    """Bloki promptu z karty: widoki, fasady i rekord BDOT10k, jeśli przebieg go widzi."""
    bloki = []
    for kier, img in karta.widoki.items():
        bloki += [tekst(f"Widok {kier}: {WIDOKI[kier]}."), obraz(img)]
    for kier, img in karta.fasady.items():
        bloki += [tekst(f"Fasada z widoku {kier}."), obraz(img)]
    if z_rekordem:
        bloki.append(tekst(tabela(karta)))
    if not karta.widoki:  # budynek przy krawędzi arkusza; prompt systemowy opisuje zdjęcia
        bloki.append(tekst("Brak zdjęć tego budynku: arkusze nie obejmują go w całości. Opieraj się na tym, co masz, i zaznacz to w pewności."))
    return bloki


def _przytnij(obs):
    """Schemat nie ogranicza zakresów liczb, więc przycinamy tutaj; None (odmowa modelu) przechodzi bez zmian."""
    if obs is not None:
        obs["kondygnacje"] = max(0, int(obs["kondygnacje"]))
        obs["udzial_mieszkalny"] = min(1.0, max(0.0, float(obs["udzial_mieszkalny"])))
        obs["pewnosc"] = min(1.0, max(0.0, float(obs["pewnosc"])))
    return obs


def swiadek_wizualny(klient, karta, z_rekordem):
    """Obserwacje o budynku (słownik zgodny z SCHEMAT_OBSERWACJI albo None przy odmowie) i odpowiedź API."""
    odp = klient.zapytaj(rola="swiadek_wizualny", system=system_swiadka(z_rekordem), tresc=tresc_karty(karta, z_rekordem),
                         schemat=SCHEMAT_OBSERWACJI, budynek=karta.id)
    return _przytnij(odp.dane), odp


def dopytaj_swiadka(klient, karta, z_rekordem, obs, atrybut, pytanie):
    """Drugie spojrzenie w pętli uzgadniania: te same obrazy, poprzednia odpowiedź i pytanie agenta bilansującego."""
    poprzednia = ", ".join(f"{k}: {obs[k]}" for k in OPIS)
    tresc = [*tresc_karty(karta, z_rekordem),
             tekst(f"Twoja poprzednia odpowiedź: {poprzednia}.\nPytanie agenta bilansującego ({atrybut}): {pytanie}")]
    odp = klient.zapytaj(rola="swiadek_dopytanie", system=f"{system_swiadka(z_rekordem)}\n\n{SYSTEM_DOPYTANIA}",
                         tresc=tresc, schemat=SCHEMAT_OBSERWACJI, budynek=karta.id)
    return _przytnij(odp.dane), odp
