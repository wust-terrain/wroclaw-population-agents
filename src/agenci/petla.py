"""Pętla uzgadniania: agent bilansujący porównuje szacunki z NSP 2021 i dopytuje świadka wizualnego. Tylko tu NSP wpływa na wynik.

Runda: estymator -> bilans kwadratów -> agent bilansujący (LLM, bez obrazów) -> świadek ogląda wskazane budynki jeszcze
raz -> estymator. Najwyżej dwie rundy, a wynik po każdej zostaje w predykcjach, więc da się ocenić stan przed i po.

Pętla zgłasza rozjazdy, a nie wymusza zgodności, bo debaty agentów zbiegają też do złej odpowiedzi (Du i in. 2024):
- szacunek zmienia się tylko przez nową obserwację świadka, nigdy przez skalowanie do sumy kwadratu,
- świadek nie widzi liczb ze spisu, a z pytań agenta wycinamy cyfry,
- rubryka zostaje stała.

Rozjazd jest słabym sygnałem błędu świadka (idealny świadek, czyli sam BDOT10k z rubryką, dostaje flagę w 23% kwadratów od 100 osób), więc kandydatami do dopytania są też budynki,
których opis przeczy rekordowi BDOT10k, o ile przebieg ten rekord widzi. Przebieg bez tabeli go nie widzi również tutaj,
inaczej kontrola z BDOT10k byłaby kolista.

Ocena po pętli na kwadratach NSP jest kolista, bo agent widział te sumy. Awaria API przerywa pętlę, ale powtórka przebiegu
bierze dotychczasowe odpowiedzi z pamięci, więc nic nie przepada.
"""

import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from agenci.estymatory import M2_NA_OSOBE, OSOBY_NA_DOM, klasa, ze_wzoru
from agenci.karta import zbuduj_karte
from agenci.llm import ROWNOLEGLE, tekst
from agenci.statystyka import budynki_w_kwadratach, kompletne_kwadraty, sumy, udzialy
from agenci.swiadkowie import OPIS, SCHEMAT_OBSERWACJI, dopytaj_swiadka
from ortofoto.arkusze import zasieg

RUNDY = 2  # Du i in. 2024
MAX_PYTAN = 20  # najwięcej tyle dopytań świadka z jednego wywołania agenta (limit kosztu)
PACZKA = 25  # najwięcej tyle kwadratów z flagą w jednym wywołaniu agenta (ok. 90 tys. tokenów; całe miasto ma ich tysiące)
PACZKA_SPRZECZNYCH = 50  # i tyle budynków sprzecznych z rekordem
PROG_ILORAZU = 1.5  # kwadrat ma rozjazd, gdy szacunek różni się od spisu ponad tyle razy...
MIN_OSOB = 25  # ...i o co najmniej tyle osób; przy idealnym świadku daje to 2 flagi na 14 kwadratów arkusza
DIAGNOZY = ["blad_swiadka", "nowa_zabudowa", "rubryka", "szum_spisu", "nieznana"]
ATRYBUTY = ["typ", "udzial_mieszkalny", "stan"]
KOLUMNY_DIALOGU = ["runda", "rodzaj", "kod", "diagnoza", "uzasadnienie", "budynek", "atrybut", "pytanie", "odpowiedz", "zmiana",
                   "mieszkancy_przed", "mieszkancy_po", "blad"]

SCHEMAT_BILANSU = {
    "type": "object",
    "properties": {
        "kwadraty": {"type": "array", "items": {
            "type": "object",
            "properties": {"kod": {"type": "string"}, "diagnoza": {"type": "string", "enum": DIAGNOZY},
                           "uzasadnienie": {"type": "string"}},
            "required": ["kod", "diagnoza", "uzasadnienie"], "additionalProperties": False}},
        "pytania": {"type": "array", "items": {
            "type": "object",
            "properties": {"budynek": {"type": "string"}, "atrybut": {"type": "string", "enum": ATRYBUTY},
                           "pytanie": {"type": "string"}},
            "required": ["budynek", "atrybut", "pytanie"], "additionalProperties": False}},
        "nowa_zabudowa": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kwadraty", "pytania", "nowa_zabudowa"],
    "additionalProperties": False,
}

SYSTEM_BILANSU = (
    "Porównujesz szacunki liczby mieszkańców budynków we Wrocławiu ze spisem NSP 2021 w kwadratach 125 m. Szacunek budynku "
    "wylicza wzór z opisu, który świadek wizualny zrobił na podstawie zdjęć lotniczych; ty tych zdjęć nie widzisz. Szacunki "
    "są przeskalowane tak, żeby suma na całym obszarze zgadzała się ze spisem, więc liczy się tylko rozkład między "
    "kwadratami.\n\n"
    "Wzór: dom = osoby na dom × udział mieszkalny; pozostałe budynki = powierzchnia zabudowy × kondygnacje × udział "
    "mieszkalny / m² na osobę w klasie. Kondygnacje wzór bierze z BDOT10k, a od świadka tylko wtedy, gdy BDOT10k ich nie "
    "podaje, więc liczba kondygnacji podana przez świadka zwykle nie wpływa na szacunek. Przyczyny rozjazdu szukaj w typie, "
    "udziale mieszkalnym i stanie; o kondygnacje nie pytaj.\n\n"
    "Dla każdego kwadratu z rozjazdem postaw jedną diagnozę:\n"
    "- blad_swiadka: któryś opis budynku wygląda na błędny, np. blok opisany jako usługi albo zły udział mieszkalny,\n"
    "- nowa_zabudowa: nadwyżka może być prawdziwa, bo budynek oddano po spisie z 2021 roku,\n"
    "- rubryka: rozjazd wynika z wartości przyjętej dla tej klasy budynków, a nie z opisu budynku,\n"
    "- szum_spisu: opisy są wiarygodne, a rozjazd może wynikać ze sposobu przypisania ludzi do kwadratów, np. budynek "
    "na granicy kwadratu,\n"
    "- nieznana: nie da się tego ocenić.\n\n"
    "Nie poprawiasz liczb i nie musisz doprowadzić do zgodności: spis bywa nieaktualny, a rozjazd bywa prawdziwy. Możesz "
    "poprosić świadka, żeby jeszcze raz obejrzał konkretny budynek, ale tylko wtedy, gdy jego opis naprawdę budzi "
    "wątpliwość. W pytaniu napisz, na co świadek ma spojrzeć. Nie podawaj liczb ze spisu ani odpowiedzi, której oczekujesz, "
    "bo świadek ma opisać to, co widzi.\n\n"
    "Zwróć:\n"
    "- kwadraty: kod kwadratu z rozjazdem, diagnoza i uzasadnienie w jednym zdaniu; gdy żaden kwadrat nie ma rozjazdu, "
    "pusta lista,\n"
    "- pytania: budynek (identyfikator z listy), atrybut (typ, udzial_mieszkalny albo stan) i pytanie do świadka,\n"
    "- nowa_zabudowa: identyfikatory budynków, które wyglądają na oddane po 2021 roku.")
CYFRY = re.compile(r"(bdot\s?10k)|\d+(?:[.,]\d+)?", re.IGNORECASE)  # nazwa bazy zostaje, reszta cyfr to możliwe liczby ze spisu


def bilans(mieszkancy, u, ludnosc):
    """Bilans kwadratów: szacunek przeskalowany do sumy spisu, iloraz do spisu i flaga rozjazdu. u to udziały budynków w kwadratach.

    Skala usuwa różnicę poziomu (np. zmiana liczby mieszkańców od 2021 roku); zostaje rozkład między kwadratami.
    """
    suma = sumy(mieszkancy, u).reindex(ludnosc.index).fillna(0.0)
    skala = ludnosc.sum() / suma.sum() if suma.sum() > 0 else 1.0
    b = pd.DataFrame({"ludnosc": ludnosc.astype(float), "szacunek": suma * skala})
    b["iloraz"] = (b.szacunek + 1) / (b.ludnosc + 1)
    b["flaga"] = (np.log(b.iloraz).abs() > np.log(PROG_ILORAZU)) & ((b.szacunek - b.ludnosc).abs() >= MIN_OSOB)
    b["skala"] = skala
    return b


def sprzeczny(obs, karta):
    """Czy świadek i BDOT10k różnią się co do tego, że ktoś w budynku mieszka. Typ inny z mieszkaniami niczego nie rozstrzyga."""
    if obs["typ"] == "inny" and obs["udzial_mieszkalny"] > 0:
        return False
    wg_swiadka = obs["stan"] == "uzytkowany" and obs["udzial_mieszkalny"] > 0 and klasa(obs["typ"]) is not None
    return wg_swiadka != karta.zamieszkany_bdot


def _opis_budynku(budynek, obs, karta, szacunek, z_rekordem):
    rekord = f"{karta.pow_zabudowy_m2:.0f} m²"
    if z_rekordem:
        kondygnacje = f", {karta.kondygnacje:.0f} kond." if karta.kondygnacje else ""
        rekord = f"BDOT10k: {karta.funkcja}{kondygnacje}, {karta.kategoria}, {rekord}"
    return (f"- {budynek}: {rekord}; świadek: {obs['typ']}, {obs['kondygnacje']} kond., udział mieszkalny "
            f"{obs['udzial_mieszkalny']:.2f}, {obs['stan']}, pewność {obs['pewnosc']:.2f} ({obs['uzasadnienie']}); "
            f"szacunek {szacunek:.0f} os.")


def opis_bilansu(b, obs, karty, m, u, sprzeczne, z_rekordem, historia, kody=None):
    """Treść promptu agenta bilansującego dla kwadratów `kody` (domyślnie wszystkich z flagą); rekord BDOT10k tylko wtedy,
    gdy przebieg go widzi."""
    skala = b.skala.iloc[0] if len(b) else 1.0
    linie = [f"Rubryka: {OSOBY_NA_DOM} osoby na dom, m² na osobę: {M2_NA_OSOBE}. Szacunki pomnożone przez {skala:.2f}."]
    for kod, k in b.loc[b.index[b.flaga] if kody is None else kody].iterrows():
        linie.append(f"\nKwadrat {kod}: spis 2021 {k.ludnosc:.0f} os., szacunek {k.szacunek:.0f} os., iloraz {k.iloraz:.2f}. Budynki:")
        linie += [_opis_budynku(i, obs[i], karty[i], m[i] * skala, z_rekordem) for i in u.xs(kod, level="kod").index]
    if sprzeczne:
        linie.append("\nBudynki, których opis przeczy rekordowi BDOT10k:")
        linie += [_opis_budynku(i, obs[i], karty[i], m[i] * skala, z_rekordem) for i in sprzeczne]
    if historia:
        linie.append("\nPoprzednie pytania i odpowiedzi świadka:")
        linie += historia
    return "\n".join(linie)


def wazne_pytania(pytania, kandydaci, zadane, w_rundzie=None):
    """Pytania o kandydatów, jedno na budynek w rundzie (w_rundzie: budynki już zapytane w tej rundzie), bez powtórek
    i najwyżej MAX_PYTAN; cyfry wycięte."""
    wynik, budynki = [], set() if w_rundzie is None else w_rundzie
    for p in pytania:
        klucz = p["budynek"], p["atrybut"]
        if p["budynek"] in kandydaci and p["budynek"] not in budynki and klucz not in zadane and len(wynik) < MAX_PYTAN:
            zadane.add(klucz)
            budynki.add(p["budynek"])
            wynik.append(p | {"pytanie": CYFRY.sub(lambda m: m[1] or "…", p["pytanie"])})
    return wynik


def _paczki(kody, sprzeczne):
    """Podział pracy agenta na wywołania: (kody kwadratów, budynki sprzeczne). Kwadraty po PACZKA, sprzeczne po PACZKA_SPRZECZNYCH;
    pierwsza porcja sprzecznych dołącza do ostatniej paczki kwadratów, więc mały przebieg to jedno wywołanie."""
    paczki = [[kody[i:i + PACZKA], []] for i in range(0, len(kody), PACZKA)]
    porcje = [sprzeczne[i:i + PACZKA_SPRZECZNYCH] for i in range(0, len(sprzeczne), PACZKA_SPRZECZNYCH)]
    if paczki and porcje:
        paczki[-1][1] = porcje.pop(0)
    return [tuple(p) for p in paczki] + [([], s) for s in porcje]


def uzgodnij(klient, pred, bud, z_rekordem, obszar=None):
    """Pętla na predykcjach całego przebiegu; zwraca (predykcje z kolumnami rund, dialog, bilanse kwadratów po rundach)."""
    miasto, kw = budynki_w_kwadratach(obszar if obszar is not None else zasieg())
    obs = {r["budynek"]: {k: r[k] for k in SCHEMAT_OBSERWACJI["required"]} | {"kondygnacje": int(r["kondygnacje"])}
           for _, r in pred[pred.typ.notna()].iterrows()}
    karty = {b: zbuduj_karte(bud.loc[b], obrazy=False) for b in obs}
    u = udzialy(miasto, obs)
    ludnosc = kw.ludnosc.reindex(kompletne_kwadraty(miasto, obs)).astype(float)

    def oszacuj():
        return pd.Series({b: ze_wzoru(o, karty[b], z_rekordem) for b, o in obs.items()}, dtype=float)

    obs_r0, szacunki = dict(obs), [oszacuj()]
    bilanse, dialog, historia, zadane, nowa_zabudowa, koszt_dopytan = [], [], [], set(), set(), {}

    for runda in range(1, RUNDY + 1):
        m = szacunki[-1]
        b = bilans(m, u, ludnosc)
        bilanse.append(b)
        sprzeczne = [i for i in obs if sprzeczny(obs[i], karty[i])] if z_rekordem else []
        paczki = _paczki(sorted(b.index[b.flaga]), sprzeczne)
        if not paczki:
            break

        def jedna(paczka):
            kody, sprz = paczka
            kandydaci = set(u.index.get_level_values("id")[u.index.get_level_values("kod").isin(kody)]) | set(sprz)
            hist = [t for i, t in historia if i in kandydaci]
            dane = klient.zapytaj(rola="bilansujacy", system=SYSTEM_BILANSU, schemat=SCHEMAT_BILANSU, tresc=[
                tekst(opis_bilansu(b, obs, karty, m, u, sprz, z_rekordem, hist, kody))]).dane
            return kody, kandydaci, dane

        with ThreadPoolExecutor(ROWNOLEGLE) as ex:
            odpowiedzi_agenta = list(ex.map(jedna, paczki))
        pytania, w_rundzie = [], set()
        for kody, kandydaci, dane in odpowiedzi_agenta:
            if dane is None:  # odmowa modelu: ta paczka zostaje z dotychczasowym wynikiem
                continue
            dialog += [{"runda": runda, "rodzaj": "kwadrat", **k} for k in dane["kwadraty"] if k["kod"] in kody]
            nowe = set(dane["nowa_zabudowa"]) & set(obs)
            nowa_zabudowa |= nowe
            dialog += [{"runda": runda, "rodzaj": "nowa_zabudowa", "budynek": i} for i in sorted(nowe)]
            pytania += wazne_pytania(dane["pytania"], kandydaci, zadane, w_rundzie)
        if not pytania:
            break

        def zadaj(p):
            return dopytaj_swiadka(klient, zbuduj_karte(bud.loc[p["budynek"]]), z_rekordem, obs[p["budynek"]], p["atrybut"], p["pytanie"])

        with ThreadPoolExecutor(ROWNOLEGLE) as ex:
            odpowiedzi = list(ex.map(zadaj, pytania))

        wiersze = []
        for p, (nowa, odp) in zip(pytania, odpowiedzi):
            i = p["budynek"]
            koszt_dopytan[i] = koszt_dopytan.get(i, 0.0) + odp.koszt_usd
            wiersz = {"runda": runda, "rodzaj": "pytanie", **p, "mieszkancy_przed": m[i], "zmiana": "", "odpowiedz": None, "blad": None}
            if nowa is None:
                wiersz["blad"] = f"świadek: {odp.stop}"
            else:
                wiersz["zmiana"] = "; ".join(f"{k}: {obs[i][k]} -> {nowa[k]}" for k in OPIS if obs[i][k] != nowa[k])
                wiersz["odpowiedz"] = nowa["uzasadnienie"]
                obs[i] = nowa
            wiersze.append(wiersz)

        szacunki.append(oszacuj())
        for w in wiersze:
            w["mieszkancy_po"] = szacunki[-1][w["budynek"]]
            historia.append((w["budynek"], f"- runda {runda}, {w['budynek']} ({w['atrybut']}): {w['pytanie']} Odpowiedź: "
                                           f"{w['odpowiedz'] or w['blad']} Zmiana: {w['zmiana'] or 'brak'}."))
        dialog += wiersze

    if len(bilanse) < len(szacunki):
        bilanse.append(bilans(szacunki[-1], u, ludnosc))

    p = pred.copy()
    for k in OPIS:
        p[f"{k}_r0"] = p.budynek.map(lambda b, k=k: obs_r0.get(b, {}).get(k))
    for r in range(RUNDY + 1):  # po wcześniejszym końcu pętli wartość się powtarza
        p[f"mieszkancy_r{r}"] = p.budynek.map(szacunki[min(r, len(szacunki) - 1)])
    for k in SCHEMAT_OBSERWACJI["required"]:
        p[k] = p.budynek.map(lambda b, k=k: obs.get(b, {}).get(k))
    p["mieszkancy"] = p.budynek.map(szacunki[-1])
    zapytane = [d for d in dialog if d["rodzaj"] == "pytanie"]
    p["dopytany"] = p.budynek.isin({d["budynek"] for d in zapytane})
    p["zmieniony"] = p.budynek.isin({d["budynek"] for d in zapytane if d["zmiana"]})
    p["nowa_zabudowa"] = p.budynek.isin(nowa_zabudowa)
    p["koszt_usd"] = p.koszt_usd + p.budynek.map(koszt_dopytan).fillna(0.0)
    return (p, pd.DataFrame(dialog, columns=KOLUMNY_DIALOGU),
            pd.concat([b.reset_index(names="kod").assign(runda=r) for r, b in enumerate(bilanse)], ignore_index=True))
