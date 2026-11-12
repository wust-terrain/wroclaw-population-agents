"""Ewaluacja przebiegów: zgodność z BDOT10k i sumy w kwadratach NSP 2021.

    python -m agenci.ewaluacja            # tabela wszystkich przebiegów, które mają wyniki
    python -m agenci.ewaluacja --rejon 30 # przebiegi z [budynki] rejon = 30 porównane z SRLM

Dla pojedynczego budynku nie mamy żadnej referencji, więc liczbę mieszkańców oceniamy tylko na kwadratach NSP 2021, w których
predykcję ma każdy budynek mieszkalny. Kwadraty są jednostką losowania: przedziały to bootstrap kwadratów, przy kilkunastu
kwadratach przybliżony i raczej za wąski, więc czytamy je jako dolne oszacowanie niepewności, a nie jako test.

BDOT10k kontroluje świadka, a nie liczbę mieszkańców: kondygnacje oraz to, czy budynek jest mieszkalny i eksploatowany.
Jest to koliste dla przebiegów, które widzą rekord BDOT w prompcie; uczciwy test to przebieg z z_rekordem = false.
"""

import argparse

import numpy as np
import pandas as pd

from agenci import EKSPERYMENTY, PRZEBIEGI
from agenci.eksperyment import BASELINE, obszar_konfiguracji, wczytaj_konfiguracje
from agenci.srlm import suma_w_rejonach, udzialy_w_rejonach, wczytaj_srlm
from agenci.statystyka import budynki_w_kwadratach, kompletne_kwadraty, sumy, udzialy
from ortofoto.arkusze import zasieg
from ortofoto.budynki import wczytaj_budynki

BOOTSTRAP = 2000  # liczba losowań do przedziałów


def wczytaj(nazwa):
    """Predykcje przebiegu: jeden wiersz na budynek."""
    return pd.read_csv(PRZEBIEGI / f"{nazwa}.csv", dtype={"budynek": str})


def zgodnosc_z_bdot(pred, bud):
    """Kondygnacje świadka a BDOT10k oraz 'mieszkańcy > 0' a 'mieszkalny i eksploatowany' w BDOT10k."""
    ref = pd.DataFrame({"kond_bdot": bud.kondygnacje, "mieszkalny": bud.mieszkalny_bdot & (bud.kategoria == "eksploatowany")})
    p = pred.join(ref, on="budynek")
    wynik = {}
    if "kondygnacje" in p:
        k = p.dropna(subset=["kondygnacje", "kond_bdot"])
        wynik |= {"kond_mae": (k.kondygnacje - k.kond_bdot).abs().mean(), "kond_trafne": (k.kondygnacje == k.kond_bdot).mean()}
    znane = p.dropna(subset=["mieszkancy"])
    prawda, przewidziane = znane.mieszkalny.astype(bool), znane.mieszkancy > 0
    tp = (prawda & przewidziane).sum()
    return wynik | {"mieszk_trafnosc": (prawda == przewidziane).mean(),
                    "mieszk_f1": 2 * tp / (prawda.sum() + przewidziane.sum()) if tp else 0.0}


def _spearman(a, b):
    """Korelacja rang z uśrednianiem remisów; stała seria nie ma rangi."""
    return np.nan if np.ptp(a) == 0 or np.ptp(b) == 0 else np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1]


def _wape(suma, ref):
    """WAPE po przeskalowaniu sumy predykcji do sumy referencyjnej (oceniamy rozkład, nie poziom)."""
    return np.nan if suma.sum() == 0 else float(np.abs(suma * ref.sum() / suma.sum() - ref).sum() / ref.sum())


MIARY = {"spearman": _spearman, "wape": _wape}


def przedzial(statystyka, n):
    """Percentylowy przedział 95% statystyki policzonej na indeksach kwadratów losowanych ze zwracaniem."""
    rng = np.random.default_rng(0)
    return tuple(np.nanquantile([statystyka(rng.integers(0, n, n)) for _ in range(BOOTSTRAP)], [0.025, 0.975]))


def sumy_kwadratow(pred, bud, kw, kolumna="mieszkancy"):
    """Suma predykcji i ludność NSP w kwadratach, w których predykcję ma każdy budynek mieszkalny.

    bud i kw jak z budynki_w_kwadratach; budynki niemieszkalne w BDOT10k też się liczą, jeśli świadek dał im mieszkańców.
    """
    s = pred.dropna(subset=[kolumna]).set_index("budynek")[kolumna]
    kody = kompletne_kwadraty(bud, s.index)
    suma = sumy(s, udzialy(bud, s.index)).reindex(kody).fillna(0.0)
    return suma, kw.ludnosc.reindex(kody).astype(float)


def ocena_kwadratow(pred, bud, kw, kolumna="mieszkancy"):
    """Spearman i WAPE sum w kwadratach, z przedziałami; z mniej niż trzech kwadratów rangi nic nie mówią."""
    suma, ref = sumy_kwadratow(pred, bud, kw, kolumna)
    a, b = suma.to_numpy(float), ref.to_numpy(float)
    wynik = {"n_kwadratow": len(a)}
    if len(a) >= 3:
        for nazwa, f in MIARY.items():
            lo, hi = przedzial(lambda i, f=f: f(a[i], b[i]), len(a))
            wynik |= {f"kw_{nazwa}": f(a, b), f"kw_{nazwa}_lo": lo, f"kw_{nazwa}_hi": hi}
    return wynik


def porownaj_sumy(a, b, ref):
    """Różnica a - b w Spearmanie i WAPE na wspólnych kwadratach, z przedziałami z bootstrapu par kwadratów."""
    wspolne = a.index.intersection(b.index).intersection(ref.index)
    x, y, r = a[wspolne].to_numpy(float), b[wspolne].to_numpy(float), ref[wspolne].to_numpy(float)
    wynik = {"n": len(wspolne)}
    for nazwa, f in MIARY.items():
        lo, hi = przedzial(lambda i, f=f: f(x[i], r[i]) - f(y[i], r[i]), len(x))
        wynik |= {f"d_{nazwa}": f(x, r) - f(y, r), f"d_{nazwa}_lo": lo, f"d_{nazwa}_hi": hi}
    return wynik


def ocena_rejonow(pred, bud, rejony, kw=None, kolumna="mieszkancy"):
    """Suma predykcji w rejonach SRLM i jej stosunek do SRLM (1 = zgodność), jeden wiersz na rejon.

    Budynek przy granicy wnosi tyle, ile wynosi udział jego obrysu w rejonie. `bez_predykcji` to budynki rejonu bez
    wyniku (błąd modelu): ich brak zaniża sumę. Z kw (kwadraty NSP) dodajemy `nsp`, czyli ludność kwadratów
    rozdzieloną na rejon wg pola części wspólnej; to rozróżnia błąd modelu od różnicy między spisem a SRLM.
    """
    ok = pred.dropna(subset=[kolumna]).set_index("budynek")[kolumna]
    wynik = rejony[["nazwa", "ludnosc"]].rename(columns={"ludnosc": "srlm"})
    wynik["suma"] = suma_w_rejonach(ok, bud, rejony)
    wynik["stosunek"] = wynik.suma / wynik.srlm
    wynik["blad_wzgl"] = wynik.stosunek - 1
    u = udzialy_w_rejonach(bud, rejony)
    u = u[u > 0.5]  # budynek należy do rejonu, jeśli ma w nim większość obrysu
    wynik["budynki"] = u.groupby(level="rejon").size().reindex(rejony.index).fillna(0).astype(int)
    wynik["bez_predykcji"] = [len(set(u.xs(n, level="rejon").index) - set(ok.index)) for n in rejony.index]
    if kw is not None:
        czesc = {n: sum(w * g.intersection(rejony.geometry[n]).area / g.area for w, g in zip(kw.ludnosc, kw.geometry)) for n in rejony.index}
        wynik["nsp"] = pd.Series(czesc)
    return wynik


def podsumowanie_srlm(numery):
    """Tabela rejonów SRLM `numery` dla każdego przebiegu z [budynki] rejon = n, który ma wyniki (przed pętlą i po niej).

    Baseline'y `objetosc*` dają metry sześcienne, więc zamiast stosunku do SRLM mają `m3_na_osobe` (objętość / SRLM):
    to stała, którą trzeba by wziąć z innych rejonów, żeby baseline dał osoby.
    """
    rejony = wczytaj_srlm(numery)
    wiersze = []
    for plik in sorted(EKSPERYMENTY.glob("*.toml")):
        konf = wczytaj_konfiguracje(plik)
        n = konf.budynki.get("rejon")
        if n not in numery or not (PRZEBIEGI / f"{plik.stem}.csv").exists():
            continue
        obszar = obszar_konfiguracji(konf)
        bud = wczytaj_budynki(obszar)
        kw = budynki_w_kwadratach(obszar)[1]
        p = wczytaj(plik.stem)
        for kolumna in dict.fromkeys(["mieszkancy_r0", "mieszkancy"] if "mieszkancy_r0" in p else ["mieszkancy"]):
            o = ocena_rejonow(p, bud, rejony.loc[[n]], kw, kolumna).assign(przebieg=plik.stem, kolumna=kolumna)
            if konf.estymator in BASELINE:  # baseline zwraca objętość [m³], nie osoby: poziomu nie porównujemy z SRLM
                o = o.rename(columns={"suma": "objetosc_m3", "stosunek": "m3_na_osobe"}).drop(columns="blad_wzgl")
            wiersze.append(o.reset_index())
    return pd.concat(wiersze).set_index(["przebieg", "kolumna", "NR_REJ"]) if wiersze else pd.DataFrame()


def podsumowanie():
    """Tabela przebiegów z eksperymenty/*.toml, które mają wyniki. Pętlę oceniamy na kwadratach sprzed uzgadniania: po nim byłoby to koło."""
    bud = wczytaj_budynki()
    miasto, kw = budynki_w_kwadratach(zasieg())
    wiersze = []
    for plik in sorted(EKSPERYMENTY.glob("*.toml")):
        if (PRZEBIEGI / f"{plik.stem}.csv").exists():
            p = wczytaj(plik.stem)
            ok = p[p.mieszkancy.notna()]
            kolumna = "mieszkancy_r0" if "mieszkancy_r0" in p else "mieszkancy"
            wiersze.append({"przebieg": plik.stem, "budynki": len(p), "bledy": int(p.blad.notna().sum()), "usd": p.get("koszt_usd", pd.Series([0.0])).sum(),
                            "suma_mieszkancow": ok.mieszkancy.sum(), **zgodnosc_z_bdot(ok, bud), **ocena_kwadratow(ok, miasto, kw, kolumna)})
    return pd.DataFrame(wiersze).set_index("przebieg")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Porównanie przebiegów.")
    parser.add_argument("--rejon", type=int, nargs="+", help="numery rejonów SRLM: porównanie sum z SRLM zamiast tabeli kwadratów NSP")
    args = parser.parse_args()
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print((podsumowanie_srlm(args.rejon) if args.rejon else podsumowanie()).round(3).to_string())
