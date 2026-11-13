"""Ocena przebiegów na SRLM, czyli szacowanej rzeczywistej liczbie mieszkańców w 375 rejonach komunikacyjnych Wrocławia.

    python -m agenci.ewaluacja            # każdy przebieg z wynikami na rejonach pokrytych predykcjami, rejony z największym rozjazdem
    python -m agenci.ewaluacja 30 367     # tylko wybrane rejony, z tabelą rejonów

Dla pojedynczego budynku nie mamy prawdziwej liczby mieszkańców, więc sumujemy predykcje w rejonach SRLM (budynek przy granicy
dzieli się według obrysu) i porównujemy z SRLM. SRLM nie widzi żaden agent ani prompt; oceniamy raz, na końcu.
- poziom: suma predykcji / suma SRLM, czyli czy szacujemy tyle ludzi, ile jest naprawdę,
- spearman: czy kolejność rejonów od najmniej do najbardziej zaludnionego się zgadza (1 to ta sama kolejność),
- wape: jaką część ludzi trzeba by przesunąć między rejonami, gdy suma predykcji równa się sumie SRLM (0 to ten sam rozkład),
- stosunek w tabeli rejonów: suma / SRLM w jednym rejonie; największe i najmniejsze pokazują, gdzie się rozjeżdżamy.
Punktem odniesienia jest sam NSP 2021 rozłożony na rejony (wiersz nsp_2021).
"""

import argparse

import numpy as np
import pandas as pd

from agenci import EKSPERYMENTY, PRZEBIEGI
from agenci.eksperyment import obszar_konfiguracji, wczytaj_konfiguracje
from agenci.srlm import pokrycie, suma_w_rejonach, wczytaj_srlm
from agenci.statystyka import budynki_w_kwadratach, kompletne_kwadraty, sumy, udzialy, wczytaj_nsp
from ortofoto.arkusze import zasieg
from ortofoto.budynki import wczytaj_budynki

POKRYCIE = 0.95  # rejon SRLM oceniamy, gdy co najmniej tyle jego powierzchni mieszkalnej ma predykcję
NAJWIEKSZE = 10  # tyle rejonów z największym i najmniejszym stosunkiem pokazujemy


def wczytaj(nazwa):
    """Predykcje przebiegu: jeden wiersz na budynek."""
    return pd.read_csv(PRZEBIEGI / f"{nazwa}.csv", dtype={"budynek": str})


def kolumna(pred):
    """Kolumna z predykcją: mieszkancy albo, w baseline'ach, objetosc_m3."""
    return "mieszkancy" if "mieszkancy" in pred else "objetosc_m3"


def _spearman(a, b):
    """Korelacja rang z uśrednianiem remisów; stała seria nie ma rangi."""
    return np.nan if np.ptp(a) == 0 or np.ptp(b) == 0 else np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1]


def _wape(suma, ref):
    """WAPE po przeskalowaniu sumy predykcji do sumy referencyjnej (oceniamy rozkład, nie poziom)."""
    return np.nan if suma.sum() == 0 else float(np.abs(suma * ref.sum() / suma.sum() - ref).sum() / ref.sum())


def osoby(pred, bud, kw, kol):
    """Predykcja w osobach, seria o indeksie id budynku. Baseline (objetosc_m3) dostaje ludność NSP rozłożoną wg objętości:
    objętość razy (ludność / objętość) z kwadratów spisu, w których objętość ma każdy budynek mieszkalny, czyli klasyczny
    rozkład dazymetryczny; SRLM go nie widzi."""
    s = pred.dropna(subset=[kol]).set_index("budynek")[kol]
    if kol == "objetosc_m3":
        kody = kompletne_kwadraty(bud, s.index)
        s = s * kw.ludnosc.reindex(kody).sum() / sumy(s, udzialy(bud, s.index)).reindex(kody).sum()
    return s


def ocena_rejonow(s, bud, rejony):
    """Suma predykcji (osoby, seria o indeksie id) w rejonach SRLM, jeden wiersz na rejon.

    Budynek przy granicy wnosi tyle, ile wynosi udział jego obrysu w rejonie; `nsp` to ludność kwadratów spisu
    rozdzielona na rejon wg pola części wspólnej, czyli punkt odniesienia: ile rozjazdu z SRLM ma sam spis.
    """
    wynik = rejony[["nazwa", "ludnosc"]].rename(columns={"ludnosc": "srlm"})
    wynik["suma"] = suma_w_rejonach(s, bud, rejony)
    wynik["stosunek"] = wynik.suma / wynik.srlm
    wynik["pokrycie"] = pokrycie(rejony, s.index)
    nsp = wczytaj_nsp(rejony.union_all())
    wynik["nsp"] = pd.Series({n: (nsp.ludnosc * nsp.intersection(g).area / nsp.area).sum() for n, g in rejony.geometry.items()})
    return wynik


def miary_srlm(t, kolumna="suma"):
    """Spearman, WAPE po przeskalowaniu (rozkład) i poziom (suma / SRLM) na rejonach tabeli z ocena_rejonow."""
    a, b = t[kolumna].to_numpy(float), t.srlm.to_numpy(float)
    return {"n_rejonow": len(t), "srlm": b.sum(), "szacunek": a.sum(), "poziom": a.sum() / b.sum(),
            "spearman": _spearman(a, b) if len(t) >= 3 else np.nan, "wape": _wape(a, b)}


def podsumowanie_srlm(numery=None, prog=POKRYCIE):
    """Ocena na SRLM każdego przebiegu z wynikami: rejony, których zabudowa mieszkalna ma predykcję w co najmniej `prog`.

    Pętlę oceniamy przed i po uzgadnianiu (SRLM nie zna żadna runda); `nsp_2021` to sam spis rozłożony na rejony.
    Zwraca (miary na przebieg, tabela rejonów).
    """
    rejony = wczytaj_srlm(numery)
    miary, tabele = [], []
    for plik in sorted(EKSPERYMENTY.glob("*.toml")):
        if not (PRZEBIEGI / f"{plik.stem}.csv").exists():
            continue
        konf = wczytaj_konfiguracje(plik)
        obszar = obszar_konfiguracji(konf)
        bud = wczytaj_budynki(obszar)
        miasto, kw = budynki_w_kwadratach(obszar if obszar is not None else zasieg())
        p = wczytaj(plik.stem)
        kolumny = ["mieszkancy_r0", "mieszkancy"] if "mieszkancy_r0" in p else [kolumna(p)]
        tu = rejony[rejony.intersects(bud.union_all())]
        for kol in kolumny:
            t = ocena_rejonow(osoby(p, miasto, kw, kol), bud, tu)
            t = t[t.pokrycie >= prog].assign(przebieg=plik.stem, kolumna=kol)
            if len(t):
                tabele.append(t)
                miary.append({"przebieg": plik.stem, "kolumna": kol} | miary_srlm(t))
                if kol == kolumny[0]:
                    miary.append({"przebieg": plik.stem, "kolumna": "nsp_2021"} | miary_srlm(t, "nsp"))
    if not miary:
        return pd.DataFrame(), pd.DataFrame()
    return pd.DataFrame(miary).set_index(["przebieg", "kolumna"]), pd.concat(tabele).set_index(["przebieg", "kolumna"], append=True)


def rozjazdy(rejony, n=NAJWIEKSZE):
    """Rejony z największym i najmniejszym stosunkiem predykcji do SRLM (dla każdego przebiegu i kolumny osobno)."""
    r = rejony.drop(columns="geometry", errors="ignore").sort_values("stosunek")
    return r.groupby(level=["przebieg", "kolumna"], group_keys=False).apply(
        lambda t: t[::-1] if len(t) <= 2 * n else pd.concat([t.tail(n)[::-1], t.head(n)]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ocena przebiegów na rejonach SRLM.")
    parser.add_argument("rejony", type=int, nargs="*", help="numery rejonów SRLM (bez numerów: wszystkie pokryte predykcjami)")
    args = parser.parse_args()
    with pd.option_context("display.width", 200, "display.max_columns", None, "display.max_rows", None):
        miary, rejony = podsumowanie_srlm(args.rejony or None)
        print(miary.round(3).to_string())
        if len(rejony):
            print((rejony.drop(columns="geometry", errors="ignore") if args.rejony else rozjazdy(rejony)).round(2).to_string())
