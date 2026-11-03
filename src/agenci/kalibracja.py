"""Kalibracja rubryki na NSP 2021 (poziom L2).

    python -m agenci.kalibracja    # dopasowanie, walidacja na odłożonych blokach, zapis eksperymenty/rubryki/nsp2021_bez_arkusza.toml

Model kwadratu 125 m: ludność = osoby_na_dom × liczba domów + Σ gęstość[klasa] × powierzchnia kondygnacji[klasa] / 100,
z klasami budynków mieszkalnych i eksploatowanych z BDOT10k (klasa_bdot). Współczynniki są nieujemne: bez tego
dopasowanie na małej liczbie jednostek daje ujemne powierzchnie na osobę (Pirowski i Bartos 2018). Jakość mierzymy
na kwadratach z odłożonych bloków 1 × 1 km, bo niski błąd na kwadratach użytych do dopasowania nie dowodzi dobrego
rozkładu (tamże). Punktem odniesienia jest jedna gęstość dla całej powierzchni kondygnacji.

Siatka GUS zawiera tylko zaludnione kwadraty, więc budynki w kwadratach pustych w 2021 roku wypadają z dopasowania,
a budynki oddane po 2021 roku w zaludnionych kwadratach zaniżają gęstość. Gęstości liczymy na całą powierzchnię
budynków mieszkalnych, więc zawierają już przeciętną część niemieszkalną; mnożenie przez udział mieszkalny świadka
zmienia wynik o stały czynnik, na który ocena (rangi, WAPE po przeskalowaniu) jest niewrażliwa.
Rubrykę zapisujemy bez kwadratów przecinających arkusz, więc na tych kwadratach jest poza próbą.
"""

import itertools
from datetime import date

import numpy as np
import pandas as pd

from agenci import EKSPERYMENTY
from agenci.estymatory import KLASY
from agenci.statystyka import budynki_w_kwadratach
from ortofoto.arkusze import zasieg

KOLUMNY = ["dom", *KLASY]  # dom: liczba budynków; reszta: powierzchnia kondygnacji / 100 m²
PLIK = EKSPERYMENTY / "rubryki" / "nsp2021_bez_arkusza.toml"
FOLDY = 5
BLOK_M = 1000


def nnls(X, y):
    """Najmniejsze kwadraty z nieujemnymi współczynnikami.

    Rozwiązanie ma na swoim nośniku postać zwykłych MNK, więc przy kilku kolumnach wystarczy przejrzeć wszystkie
    podzbiory kolumn i wybrać dopuszczalne rozwiązanie z najmniejszym błędem.
    """
    X, y = np.asarray(X, float), np.asarray(y, float)
    najlepsze, blad = np.zeros(X.shape[1]), float(y @ y)
    for r in range(1, X.shape[1] + 1):
        for kolumny in itertools.combinations(range(X.shape[1]), r):
            b = np.linalg.lstsq(X[:, kolumny], y, rcond=None)[0]
            if (b < 0).any():
                continue
            e = float(((X[:, kolumny] @ b - y) ** 2).sum())
            if e < blad:
                najlepsze, blad = np.zeros(X.shape[1]), e
                najlepsze[list(kolumny)] = b
    return najlepsze


def foldy(kwadraty):
    """Numer foldu dla każdego kwadratu; cały blok BLOK_M × BLOK_M trafia do jednego foldu (walidacja przestrzenna)."""
    srodki = kwadraty.centroid
    blok = (srodki.x // BLOK_M).astype(int).astype(str) + "_" + (srodki.y // BLOK_M).astype(int).astype(str)
    bloki = np.random.default_rng(0).permutation(blok.unique())
    return blok.map({b: i % FOLDY for i, b in enumerate(bloki)})


def macierz(bud, kwadraty):
    """Kolumny KOLUMNY i powierzchnia łączna na kwadrat (tylko kwadraty z budynkiem mieszkalnym) oraz ludność."""
    b = bud[bud.klasa.notna() & bud.komorka.notna()]
    X = pd.DataFrame({"dom": (b.klasa == "dom").groupby(b.komorka).sum().astype(float)})
    for k in KLASY:
        X[k] = b.pow_kondygnacji.where(b.klasa == k, 0.0).groupby(b.komorka).sum() / 100
    X["pow_lacznie"] = b.pow_kondygnacji.groupby(b.komorka).sum() / 100
    return X, kwadraty.ludnosc.reindex(X.index).astype(float)


def wape(przewidziane, prawda):
    return float(np.abs(przewidziane - prawda).sum() / prawda.sum())


def kalibruj(dane=None, wyklucz=None):
    """(rubryka z dopasowania na wszystkich kwadratach, raport walidacji krzyżowej per fold).

    dane    - gotowe (budynki, kwadraty) z budynki_w_kwadratach(), żeby nie liczyć ich drugi raz
    wyklucz - geometria (np. arkusz, na którym oceniamy); kwadraty, które ją przecinają, nie biorą udziału w dopasowaniu
    """
    bud, kwadraty = dane or budynki_w_kwadratach()
    if wyklucz is not None:
        kwadraty = kwadraty[~kwadraty.intersects(wyklucz)]
        bud = bud[bud.komorka.isin(kwadraty.index)]
    X, y = macierz(bud, kwadraty)
    f = foldy(kwadraty.loc[X.index])
    wiersze, odlozone = [], pd.DataFrame(index=X.index, columns=["klasy", "jedna"], dtype=float)
    for nr in range(FOLDY):
        uczace, testowe = f != nr, f == nr
        beta = nnls(X.loc[uczace, KOLUMNY], y[uczace])
        jedna = nnls(X.loc[uczace, ["pow_lacznie"]], y[uczace])
        odlozone.loc[testowe, "klasy"] = X.loc[testowe, KOLUMNY].values @ beta
        odlozone.loc[testowe, "jedna"] = X.loc[testowe, ["pow_lacznie"]].values @ jedna
        wiersze.append({"fold": nr, "kwadraty": int(testowe.sum()), **dict(zip(KOLUMNY, beta)),
                        "gestosc_jedna": jedna[0], "wape_klasy": wape(odlozone.klasy[testowe], y[testowe]),
                        "wape_jedna": wape(odlozone.jedna[testowe], y[testowe])})
    raport = pd.DataFrame(wiersze).set_index("fold")
    raport.attrs |= {"wape_klasy": wape(odlozone.klasy, y), "wape_jedna": wape(odlozone.jedna, y),
                     "gestosc_jedna": float(nnls(X[["pow_lacznie"]], y)[0]), "kwadraty": len(X), "ludnosc": float(y.sum())}
    beta = nnls(X[KOLUMNY], y)
    rubryka = {"osoby_na_dom": float(beta[0]), "gestosci": {kl: float(g) for kl, g in zip(KLASY, beta[1:])}}
    return rubryka, raport


def main():
    rubryka, raport = kalibruj(wyklucz=zasieg())
    a = raport.attrs
    with pd.option_context("display.width", 200):
        print(raport.round(3).to_string())
    linie = [f"# Rubryka na NSP 2021 bez kwadratów przecinających arkusz (python -m agenci.kalibracja, {date.today()}).",
             f"# {a['kwadraty']} kwadratów; WAPE na odłożonych blokach 1 km: {a['wape_klasy']:.3f} (jedna gęstość: {a['wape_jedna']:.3f}).",
             f"osoby_na_dom = {rubryka['osoby_na_dom']:.4f}", "", "[gestosci]  # osoby na 100 m² powierzchni kondygnacji",
             *(f"{k} = {g:.4f}" for k, g in rubryka["gestosci"].items())]
    PLIK.parent.mkdir(exist_ok=True)
    PLIK.write_text("\n".join(linie) + "\n", encoding="utf-8")
    print(f"\n{a['kwadraty']} kwadratów, {a['ludnosc']:,.0f} osób. Zapisano {PLIK.relative_to(PLIK.parents[2])}: {rubryka}")


if __name__ == "__main__":
    main()
