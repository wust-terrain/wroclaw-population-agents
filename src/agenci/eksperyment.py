"""Uruchamianie przebiegów z plików TOML.

    python -m agenci.eksperyment eksperymenty/arkusze_haiku.toml            # prawdziwy przebieg
    python -m agenci.eksperyment eksperymenty/arkusze_haiku.toml --na-sucho # bez API i bez zapisu: test i wycena

Wynik trafia do wyniki/eksperymenty/<nazwa pliku TOML>.csv, jeden wiersz na budynek; pętla dokłada <nazwa>__dialog.csv
i <nazwa>__bilans.csv. Konfiguracje z tymi samymi `arkusze` dostają te same budynki, więc wyniki da się porównywać parami.

Świadek dopisuje każdy gotowy budynek do <nazwa>.czesc.csv. Przerwany przebieg uruchomiony jeszcze raz pomija budynki z tego
pliku, więc nie buduje dla nich kart od nowa. Plik znika po zapisaniu wyniku; po zmianie promptu w trakcie przebiegu usuń go ręcznie.
"""

import argparse
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from shapely.geometry import box
from shapely.ops import unary_union

from agenci import PRZEBIEGI
from agenci.estymatory import objetosc_bdot, z_rekordu, ze_wzoru
from agenci.karta import zbuduj_karte
from agenci.llm import ROWNOLEGLE, Klient
from agenci.petla import uzgodnij
from agenci.swiadkowie import SCHEMAT_OBSERWACJI, swiadek_wizualny
from agenci.szperacz import poszukaj
from ortofoto.arkusze import ARKUSZE
from ortofoto.budynki import wczytaj_budynki

BASELINE = {"objetosc_bdot": objetosc_bdot}
KOLUMNY_SWIADKA = ["budynek", "liczba_widokow", *SCHEMAT_OBSERWACJI["required"], "mieszkancy", "zapasowy", "koszt_usd", "stop", "blad"]


@dataclass
class Konfiguracja:
    nazwa: str  # nazwa pliku TOML
    opis: str = ""
    estymator: str = "wzor"  # objetosc_bdot (baseline) | wzor (świadek + rubryka) | petla (wzór + uzgadnianie)
    szukaj: bool = False  # czy szperacz szuka w sieci liczby miejsc albo mieszkań dla największych budynków
    model: str = "claude-haiku-5-5"
    model_szperacza: str | None = None  # szperacz potrzebuje wyszukiwarki z API Claude; None = ten sam model co reszta
    arkusze: list[str] | None = None  # godła arkuszy; None = wszystkie arkusze z data/

    def __post_init__(self):
        if self.estymator not in (*BASELINE, "wzor", "petla"):
            raise ValueError(f"nieznany estymator: {self.estymator!r}")


def wczytaj_konfiguracje(sciezka):
    with open(sciezka, "rb") as f:
        return Konfiguracja(nazwa=Path(sciezka).stem, **tomllib.load(f))


def obszar_konfiguracji(konf):
    """Wielokąt, na którym działa przebieg: zasięg arkuszy o godłach `arkusze` albo None (wszystkie arkusze z data/)."""
    if konf.arkusze is None:
        return None
    return unary_union([box(*a.bounds) for zrodla in ARKUSZE.values() for a in zrodla if a.godlo in konf.arkusze])


def _swiadek_i_wzor(klient, bud, ids, czesc=None):
    """Jeden wiersz predykcji na budynek: obserwacje świadka i liczba mieszkańców ze wzoru.

    Gdy świadek nie da odpowiedzi albo budynek się wywróci (kolumna blad), wynik to rubryka z samego rekordu (zapasowy = True).
    czesc to plik CSV z gotowymi wierszami: budynki z niego (bez błędu) pomijamy, a nowe wiersze dopisujemy na bieżąco.
    """
    gotowe = pd.DataFrame(columns=KOLUMNY_SWIADKA)
    if czesc is not None and czesc.exists():
        gotowe = pd.read_csv(czesc, dtype={"budynek": str})
        gotowe = gotowe[gotowe.blad.isna() & gotowe.budynek.isin(ids)]
        print(f"świadek: {len(gotowe)} budynków z {czesc.name}", flush=True)
        gotowe.to_csv(czesc, index=False)  # bez wierszy z błędem, które teraz spróbujemy jeszcze raz
    zostale = [i for i in ids if i not in set(gotowe.budynek)]

    def jeden(budynek):
        wiersz = {"budynek": budynek, "zapasowy": False}
        try:
            karta = zbuduj_karte(bud.loc[budynek])
            wiersz["liczba_widokow"] = len(karta.widoki)
            obs, odp = swiadek_wizualny(klient, karta)
            wiersz |= {"koszt_usd": odp.koszt_usd, "stop": odp.stop}
            if obs is None:
                raise RuntimeError(f"świadek bez odpowiedzi po kolejnych próbach ({odp.stop})")
            wiersz |= obs | {"mieszkancy": ze_wzoru(obs, karta)}
        except Exception as e:  # jeden zepsuty budynek nie zatrzymuje przebiegu
            wiersz |= {"blad": f"{type(e).__name__}: {e}"[:300], "zapasowy": True,
                       "mieszkancy": z_rekordu(zbuduj_karte(bud.loc[budynek], obrazy=False))}
        return wiersz

    wiersze, start = [], time.perf_counter()
    with ThreadPoolExecutor(ROWNOLEGLE) as ex:
        for n, w in enumerate(ex.map(jeden, zostale), 1):
            wiersze.append(w)
            if czesc is not None:
                pd.DataFrame([w]).reindex(columns=KOLUMNY_SWIADKA).to_csv(czesc, mode="a", header=not czesc.exists(), index=False)
            if n % 500 == 0 or n == len(zostale):  # długi przebieg: postęp co 500 budynków
                print(f"świadek: {n}/{len(zostale)} budynków, {(time.perf_counter() - start) / 60:.0f} min", flush=True)
    nowe = pd.DataFrame(wiersze).reindex(columns=KOLUMNY_SWIADKA)
    return pd.concat([gotowe, nowe], ignore_index=True) if len(gotowe) else nowe


def uruchom(konf, na_sucho=False):
    """Przebieg eksperymentu; zapisuje wyniki (chyba że na sucho) i zwraca DataFrame predykcji."""
    obszar = obszar_konfiguracji(konf)
    bud = wczytaj_budynki(obszar)  # budynki, których środek leży na obszarze; przy krawędzi bez pełnego widoku dostają mniej zdjęć
    ids = sorted(bud.index)
    tabele = {}
    koszt = 0.0
    if konf.estymator in BASELINE:
        policz = BASELINE[konf.estymator]
        pred = pd.DataFrame({"budynek": ids, "objetosc_m3": [policz(zbuduj_karte(bud.loc[i], obrazy=False)) for i in ids], "blad": None})
    else:
        klient = Klient(konf.model, konf.nazwa, na_sucho)
        czesc = None if na_sucho else PRZEBIEGI / f"{konf.nazwa}.czesc.csv"
        if czesc is not None:
            PRZEBIEGI.mkdir(parents=True, exist_ok=True)
        pred = _swiadek_i_wzor(klient, bud, ids, czesc)
        if konf.estymator == "petla" and pred.typ.notna().any():
            pred, tabele["dialog"], tabele["bilans"] = uzgodnij(klient, pred, bud, obszar)
        szperacz = Klient(konf.model_szperacza, konf.nazwa, na_sucho) if konf.model_szperacza else klient
        if konf.szukaj and pred.typ.notna().any():
            pred = poszukaj(szperacz, pred, bud)
        koszt = klient.koszt + (szperacz.koszt if szperacz is not klient else 0.0)

    if not na_sucho:
        PRZEBIEGI.mkdir(parents=True, exist_ok=True)
        pred.to_csv(PRZEBIEGI / f"{konf.nazwa}.csv", index=False)
        for nazwa, tabela in tabele.items():
            tabela.to_csv(PRZEBIEGI / f"{konf.nazwa}__{nazwa}.csv", index=False)
        (PRZEBIEGI / f"{konf.nazwa}.czesc.csv").unlink(missing_ok=True)

    bledy = pred[pred.blad.notna()]
    print(f"{konf.nazwa}: {len(pred)} budynków, błędów {len(bledy)} (wynik z rekordu), koszt {koszt:.3f} USD{' (szacunek na sucho)' if na_sucho else ''}")
    if len(bledy):
        print(bledy[["budynek", "blad"]].head().to_string(index=False))
    return pred


def main():
    parser = argparse.ArgumentParser(description="Uruchamia przebiegi z plików TOML.")
    parser.add_argument("konfiguracja", nargs="+", help="plik(i) TOML z katalogu eksperymenty/")
    parser.add_argument("--na-sucho", action="store_true", help="bez API i bez zapisu: odpowiedzi ze schematu i szacunek kosztu")
    args = parser.parse_args()
    for sciezka in args.konfiguracja:
        uruchom(wczytaj_konfiguracje(sciezka), na_sucho=args.na_sucho)


if __name__ == "__main__":
    main()
