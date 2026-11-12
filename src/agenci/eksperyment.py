"""Uruchamianie przebiegów z plików TOML.

    python -m agenci.eksperyment eksperymenty/arkusz_haiku.toml             # prawdziwy przebieg
    python -m agenci.eksperyment eksperymenty/arkusz_haiku.toml --na-sucho  # bez API i bez zapisu: test i wycena

Wynik trafia do wyniki/eksperymenty/<nazwa pliku TOML>.csv, jeden wiersz na budynek; pętla dokłada <nazwa>__dialog.csv
i <nazwa>__bilans.csv. Konfiguracje z tym samym [budynki] dostają te same budynki, więc wyniki da się porównywać parami.
"""

import argparse
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from agenci import PRZEBIEGI
from agenci.estymatory import objetosc, objetosc_bdot, ze_wzoru
from agenci.karta import zbuduj_karte
from agenci.llm import ROWNOLEGLE, Klient
from agenci.petla import uzgodnij
from agenci.srlm import obszar_pracy, wczytaj_srlm
from agenci.statystyka import budynki_w_kwadratach, kompletne_kwadraty, udzialy
from agenci.swiadkowie import swiadek_wizualny
from agenci.szperacz import poszukaj
from ortofoto.arkusze import KOLEJNOSC, zasieg
from ortofoto.budynki import wczytaj_budynki
from ortofoto.wycinki import dostepne_kierunki

BASELINE = {"objetosc": objetosc, "objetosc_bdot": objetosc_bdot}


@dataclass
class Konfiguracja:
    nazwa: str  # nazwa pliku TOML
    opis: str = ""
    estymator: str = "wzor"  # objetosc | objetosc_bdot | wzor (świadek + rubryka) | petla (wzór + uzgadnianie)
    szukaj: bool = False  # czy szperacz szuka w sieci liczby miejsc albo mieszkań dla największych budynków
    z_rekordem: bool = True  # czy świadek i agent widzą rekord BDOT10k; bez niego kontrola z BDOT10k nie jest kolista
    model: str = "claude-opus-5-5"
    budynki: dict = field(default_factory=dict)  # wszystkie = true, rejon = numer SRLM, kwadraty = n albo liczba = n (domyślnie 40); ziarno

    def __post_init__(self):
        if self.estymator not in (*BASELINE, "wzor", "petla"):
            raise ValueError(f"nieznany estymator: {self.estymator!r}")


def wczytaj_konfiguracje(sciezka):
    with open(sciezka, "rb") as f:
        return Konfiguracja(nazwa=Path(sciezka).stem, **tomllib.load(f))


def obszar_konfiguracji(konf):
    """Wielokąt, na którym działa przebieg: przy `rejon` kwadraty NSP przecinające rejon SRLM, inaczej None (wszystkie arkusze)."""
    numer = konf.budynki.get("rejon")
    return None if numer is None else obszar_pracy(wczytaj_srlm([numer]).geometry.iloc[0])


def wybierz_budynki(bud, konf):
    """Lista id budynków: wszystkie z obszaru rejonu SRLM, cały arkusz, losowe kompletne kwadraty NSP albo losowa próbka widocznych ze wszystkich kierunków.

    Tylko cały arkusz i kwadraty pozwalają porównać sumę predykcji z ludnością kwadratu. Cały arkusz obejmuje też budynki
    przy krawędzi bez pełnego widoku, które dostają szacunek z samego rekordu.
    """
    b, ziarno = konf.budynki, konf.budynki.get("ziarno", 0)
    if b.get("wszystkie") or b.get("rejon") is not None:  # przy rejonie bud jest już ograniczone do obszaru rejonu
        return sorted(bud.index)
    if b.get("kwadraty"):
        miasto = budynki_w_kwadratach(zasieg())[0]
        widoczne = [i for i, w in bud.iterrows() if dostepne_kierunki(w)]
        kody = pd.Series(kompletne_kwadraty(miasto, widoczne)).sample(b["kwadraty"], random_state=ziarno)
        u = udzialy(miasto, widoczne)
        return sorted(set(u.index.get_level_values("id")[u.index.get_level_values("kod").isin(kody)]))
    pelne = bud[[len(dostepne_kierunki(w)) == len(KOLEJNOSC) for _, w in bud.iterrows()]]
    return sorted(pelne.sample(b.get("liczba", 40), random_state=ziarno).index)


def _swiadek_i_wzor(klient, bud, ids, z_rekordem):
    """Jeden wiersz predykcji na budynek: obserwacje świadka i liczba mieszkańców ze wzoru."""
    def jeden(budynek):
        wiersz = {"budynek": budynek, "blad": None}
        try:
            karta = zbuduj_karte(bud.loc[budynek])
            wiersz["liczba_widokow"] = len(karta.widoki)
            obs, odp = swiadek_wizualny(klient, karta, z_rekordem)
            wiersz |= {"koszt_usd": odp.koszt_usd, "stop": odp.stop}
            if obs is not None:
                wiersz |= obs | {"mieszkancy": ze_wzoru(obs, karta, z_rekordem)}
        except Exception as e:  # jeden zepsuty budynek nie zatrzymuje przebiegu
            wiersz["blad"] = f"{type(e).__name__}: {e}"[:300]
        return wiersz

    with ThreadPoolExecutor(ROWNOLEGLE) as ex:
        return pd.DataFrame(list(ex.map(jeden, ids)))


def uruchom(konf, na_sucho=False):
    """Przebieg eksperymentu; zapisuje wyniki (chyba że na sucho) i zwraca DataFrame predykcji."""
    obszar = obszar_konfiguracji(konf)
    bud = wczytaj_budynki(obszar)
    ids = wybierz_budynki(bud, konf)
    tabele = {}
    koszt = 0.0
    if konf.estymator in BASELINE:
        policz = BASELINE[konf.estymator]
        pred = pd.DataFrame({"budynek": ids, "mieszkancy": [policz(zbuduj_karte(bud.loc[i], obrazy=False)) for i in ids], "blad": None})
    else:
        klient = Klient(konf.model, konf.nazwa, na_sucho)
        pred = _swiadek_i_wzor(klient, bud, ids, konf.z_rekordem)
        if konf.estymator == "petla" and "typ" in pred:  # brak kolumny: wszystkie wywołania padły, błędy są w kolumnie blad
            pred, tabele["dialog"], tabele["bilans"] = uzgodnij(klient, pred, bud, konf.z_rekordem, obszar)
        if konf.szukaj and "typ" in pred:
            pred = poszukaj(klient, pred, bud)
        koszt = klient.koszt

    if not na_sucho:
        PRZEBIEGI.mkdir(parents=True, exist_ok=True)
        pred.to_csv(PRZEBIEGI / f"{konf.nazwa}.csv", index=False)
        for nazwa, tabela in tabele.items():
            tabela.to_csv(PRZEBIEGI / f"{konf.nazwa}__{nazwa}.csv", index=False)

    bledy = pred[pred.blad.notna()]
    print(f"{konf.nazwa}: {len(pred)} budynków, błędów {len(bledy)}, koszt {koszt:.3f} USD{' (szacunek na sucho)' if na_sucho else ''}")
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
