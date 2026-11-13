"""Świadek wizualny: jedno wywołanie VLM na budynek, zwraca obserwacje (bez liczby mieszkańców).

To moduł percepcji: dostaje kartę budynku i zwraca typ zabudowy, stan oraz dwa mnożniki rubryki: udział mieszkalny i gęstość.
Liczbę mieszkańców liczy dopiero estymator, więc da się osobno sprawdzić, co wnosi obraz, a co rubryka.
"""

from agenci.estymatory import M2_NA_OSOBE, OSOBY_NA_DOM, PROG_PEWNOSCI, klasa_bdot, z_rekordu
from agenci.llm import obraz, tekst

TYPY = {
    "kamienica": "kamienica, przedwojenny budynek czynszowy",
    "blok_prl": "blok mieszkalny z lat 1950-1995, w tym wielka płyta",
    "blok_nowy": "budynek wielorodzinny zbudowany po 1995 roku",
    "dom_jednorodzinny": "dom jednorodzinny wolnostojący",
    "szeregowiec": "zabudowa szeregowa lub bliźniacza",
    "zbiorowy": "zamieszkanie zbiorowe: akademik, internat, dom opieki, hotel pracowniczy, klasztor",
    "uslugi": "budynek usługowy, biurowy lub publiczny (sklep, szkoła, szpital, kościół, hotel)",
    "przemysl": "budynek przemysłowy lub magazynowy",
    "garaz": "garaż, budynek gospodarczy, wiata",
    "inny": "inny albo nie da się określić",
}
STANY = ["uzytkowany", "w_budowie", "pustostan"]
GESTOSC = (0.3, 3.0)  # zakres mnożnika gęstości; poza nim przycinamy
WIDOKI = {"N": "kamera patrzy na północ, widać ścianę południową", "E": "kamera patrzy na wschód, widać ścianę zachodnią",
          "S": "kamera patrzy na południe, widać ścianę północną", "W": "kamera patrzy na zachód, widać ścianę wschodnią"}
OPIS = ["widac_mieszkania", "typ", "stan", "udzial_mieszkalny", "gestosc"]  # to, co świadek twierdzi o budynku i co czyta wzór

SCHEMAT_OBSERWACJI = {  # uzasadnienie pierwsze: model generuje pola po kolei, więc najpierw opisuje, co widzi, a potem daje liczby
    "type": "object",
    "properties": {
        "uzasadnienie": {"type": "string"},
        "widac_mieszkania": {"type": "boolean"},
        "typ": {"type": "string", "enum": list(TYPY)},
        "stan": {"type": "string", "enum": STANY},
        "udzial_mieszkalny": {"type": "number"},
        "gestosc": {"type": "number"},
        "pewnosc": {"type": "number"},
    },
    "required": ["uzasadnienie", "widac_mieszkania", "typ", "stan", "udzial_mieszkalny", "gestosc", "pewnosc"],
    "additionalProperties": False,
}

SYSTEM_DOPYTANIA = (
    "Oglądasz ten budynek drugi raz, bo agent bilansujący, który nie widzi zdjęć, ma wątpliwość co do jego opisu. Agent może "
    "się mylić. Zmień odpowiedź tylko wtedy, gdy obraz to uzasadnia; w przeciwnym razie powtórz poprzednią. W uzasadnieniu "
    "odnieś się do pytania.")


def system_swiadka():
    czesci = ["Opisujesz jeden budynek we Wrocławiu na potrzeby szacowania liczby jego mieszkańców.",
              ("Zdjęcia to wycinki ortofotomapy skośnej z nalotu w 2025 roku. Podstawa budynku leży na swoim miejscu, "
               "dach jest przesunięty od kamery, a między nimi widać ścianę zwróconą do kamery. "
               "Żółta linia to obrys podstawy, czerwona to obrys dachu. Opisz tylko budynek w tych obrysach, "
               "sąsiednie budynki pomiń.")]
    czesci.append("Rekord z bazy BDOT10k pochodzi z ewidencji budynków i bywa nieaktualny (np. nowe osiedla, "
                  "zmiana sposobu użytkowania). Gdy obraz wyraźnie mu przeczy, opisz to, co widzisz.")
    czesci.append("Fasady to ściany zwrócone do kamery, wyprostowane do prostokąta przy założonej wysokości "
                  "budynku; gdy ta wysokość jest błędna, fasada może obejmować kawałek dachu albo nie mieścić "
                  "całej ściany.")
    czesci.append(
        "Nie szacuj liczby mieszkańców sam. Policzy ją wzór ze stałych z literatury (Kraków, baza BDOT10k):\n"
        f"- dom jednorodzinny i szeregowiec: {OSOBY_NA_DOM} osoby na budynek,\n"
        f"- budynek wielorodzinny: 1 osoba na {M2_NA_OSOBE['wielorodzinny']} m² powierzchni brutto (obrys × kondygnacje), "
        "ze ścianami, klatkami schodowymi i typowymi lokalami usługowymi w parterach,\n"
        f"- zamieszkanie zbiorowe: 1 osoba na {M2_NA_OSOBE['zbiorowy']} m² powierzchni brutto,\n"
        "- budynki usługowe, przemysłowe, garaże i budynki nieużytkowane: 0.\n"
        "Wynik wzoru mnożymy przez udzial_mieszkalny i gestosc od ciebie. Tak doważasz stałą tym, co widzisz i co wiesz o "
        "architekturze tego typu budynków.")
    czesci.append(
        "Zwróć:\n"
        "- uzasadnienie: najwyżej trzy zdania: co widać na zdjęciach (np. witryny i szyldy, balkony, wielkość i rytm okien, "
        "liczba wejść) i skąd biorą się mnożniki,\n"
        "- widac_mieszkania: true, gdy na zdjęciach widać ślady, że ktoś tu mieszka: balkony z rzeczami (rośliny, suszarki "
        "z praniem, rowery, meble, skrzynki), różne zasłony, firanki i rolety w wielu oknach, kwiaty w oknach, anteny "
        "satelitarne na balkonach i ścianach; false, gdy takich śladów nie widać albo zdjęcia tego nie rozstrzygają "
        "(jednakowe okna bez balkonów, jak w biurze, szkole czy hotelu). Budynek niemieszkalny w rekordzie dostanie "
        "mieszkańców tylko przy true i pewności co najmniej " + f"{PROG_PEWNOSCI:g}".replace(".", ",") + ",\n"
        "- typ: jeden z kodów poniżej; wybiera klasę wzoru,\n"
        "- stan: uzytkowany, w_budowie albo pustostan,\n"
        "- udzial_mieszkalny: jaka część budynku to mieszkania w porównaniu z typowym budynkiem tej klasy, od 0 do 1. "
        "1 to typowo, także gdy w parterze są zwykłe sklepy albo lokale usługowe, bo stała już je obejmuje. Obniżaj tylko "
        "wtedy, gdy całe piętra powyżej parteru wyglądają na niemieszkalne (np. biura, szyldy i witryny na piętrach); "
        "reklamy, banery i murale na ścianie nie są powodem. 0, gdy nikt tu nie mieszka,\n"
        f"- gestosc: ile razy gęściej albo rzadziej niż w typowym budynku tej klasy mieszkają tu ludzie, od {GESTOSC[0]} do "
        f"{GESTOSC[1]:.0f}. 1 to typowo. Więcej niż 1: bardzo małe mieszkania (mikrokawalerki, hotel pracowniczy), "
        "gęsto zasiedlony blok. Mniej niż 1: duże mieszkania (apartamentowiec, kamienica z dużymi "
        "mieszkaniami), budynek częściowo pusty, mała wspólnota w dużym budynku (np. dom parafialny, klasztor). Dom z dwoma "
        "mieszkaniami to 2,\n"
        "- pewnosc: od 0 do 1.\n\n"
        "Co wiadomo o gęstości w polskich miastach:\n"
        "- gęściej niż typowo bywa w budynkach z mikroapartamentami i kawalerkami po 11-25 m² (budowane głównie w latach "
        "2010-2024 jako inwestycyjne, także w dawnych hotelach, biurowcach i akademikach), w prywatnych akademikach i w "
        "hotelach pracowniczych z pokojami wieloosobowymi; z zewnątrz: bardzo gęsty rytm jednakowych małych okien, przy "
        "każdym oknie balkon francuski albo mały balkon, wiele jednostek klimatyzacji, długie korytarze lub galerie,\n"
        "- rzadziej niż typowo bywa w kamienicach i apartamentowcach z dużymi mieszkaniami (wysokie, szerokie okna, mało "
        "okien na piętro), w budynkach częściowo pustych (zabite lub zamurowane okna, brak zasłon na całych piętrach) i "
        "tam, gdzie mała wspólnota zajmuje duży budynek (dom parafialny, klasztor),\n"
        "- wynajmu pokoi studentom w zwykłych kamienicach i blokach z zewnątrz nie widać, więc tego nie zgaduj.\n"
        "Gęstość podwyższasz i obniżasz na tych samych zasadach: tylko wtedy, gdy na zdjęciach widać taki powód.\n\n"
        "Gdy nie widzisz konkretnego powodu, wpisz 1 w obu mnożnikach. Każdą wartość inną niż 1 uzasadnij tym, co widać. "
        "Porównuj ten budynek z typowym budynkiem tej klasy w polskim mieście.\n\n"
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
    if karta.zamieszkany_bdot:
        wiersze.append(f"wzór policzy go według rekordu jako {klasa_bdot(karta.funkcja)}: ok. {z_rekordu(karta):.0f} os. przy obu "
                       "mnożnikach równych 1; inną klasę wybierz przez typ tylko wtedy, gdy obraz wyraźnie przeczy rekordowi")
    else:
        wiersze.append("według rekordu nikt tu nie mieszka (budynek niemieszkalny albo nieeksploatowany), więc wzór da 0, "
                       "chyba że obraz pokaże mieszkania")
    return "Dane z bazy BDOT10k:\n" + "\n".join(f"- {w}" for w in wiersze)


def tresc_karty(karta):
    """Bloki promptu z karty: widoki, fasady i rekord BDOT10k."""
    bloki = []
    for kier, img in karta.widoki.items():
        bloki += [tekst(f"Widok {kier}: {WIDOKI[kier]}."), obraz(img)]
    for kier, img in karta.fasady.items():
        bloki += [tekst(f"Fasada z widoku {kier}."), obraz(img)]
    bloki.append(tekst(tabela(karta)))
    if not karta.widoki:  # budynek przy krawędzi arkusza; prompt systemowy opisuje zdjęcia
        bloki.append(tekst("Brak zdjęć tego budynku: arkusze nie obejmują go w całości. Opieraj się na tym, co masz, i zaznacz to w pewności."))
    return bloki


def _przytnij(obs):
    """Schemat nie ogranicza zakresów liczb, więc przycinamy tutaj; None (odmowa modelu) przechodzi bez zmian."""
    if obs is not None:
        obs["udzial_mieszkalny"] = min(1.0, max(0.0, float(obs["udzial_mieszkalny"])))
        obs["gestosc"] = min(GESTOSC[1], max(GESTOSC[0], float(obs["gestosc"])))
        obs["pewnosc"] = min(1.0, max(0.0, float(obs["pewnosc"])))
    return obs


def swiadek_wizualny(klient, karta):
    """Obserwacje o budynku (słownik zgodny z SCHEMAT_OBSERWACJI albo None przy odmowie) i odpowiedź API."""
    odp = klient.zapytaj(rola="swiadek_wizualny", system=system_swiadka(), tresc=tresc_karty(karta),
                         schemat=SCHEMAT_OBSERWACJI, budynek=karta.id)
    return _przytnij(odp.dane), odp


def dopytaj_swiadka(klient, karta, obs, atrybut, pytanie):
    """Drugie spojrzenie w pętli uzgadniania: te same obrazy, poprzednia odpowiedź i pytanie agenta bilansującego."""
    poprzednia = ", ".join(f"{k}: {obs[k]}" for k in OPIS)
    tresc = [*tresc_karty(karta),
             tekst(f"Twoja poprzednia odpowiedź: {poprzednia}.\nPytanie agenta bilansującego ({atrybut}): {pytanie}")]
    odp = klient.zapytaj(rola="swiadek_dopytanie", system=f"{system_swiadka()}\n\n{SYSTEM_DOPYTANIA}",
                         tresc=tresc, schemat=SCHEMAT_OBSERWACJI, budynek=karta.id)
    return _przytnij(odp.dane), odp
