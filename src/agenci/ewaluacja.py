"""Ewaluacja przebiegów: zgodność z BDOT10k, sumy w kwadratach NSP 2021 i, na końcu, sumy w rejonach SRLM.

    python -m agenci.ewaluacja                # tabela wszystkich przebiegów, które mają wyniki (kwadraty NSP)
    python -m agenci.ewaluacja --srlm         # te same przebiegi na rejonach SRLM pokrytych arkuszami
    python -m agenci.ewaluacja --srlm 30 367  # tylko wybrane rejony, z tabelą rejonów

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
from agenci.srlm import pokrycie, suma_w_rejonach, wczytaj_srlm
from agenci.statystyka import budynki_w_kwadratach, kompletne_kwadraty, sumy, udzialy, wczytaj_nsp
from ortofoto.arkusze import zasieg
from ortofoto.budynki import wczytaj_budynki

BOOTSTRAP = 2000  # liczba losowań do przedziałów
POKRYCIE = 0.95  # rejon SRLM oceniamy, gdy co najmniej tyle jego powierzchni mieszkalnej ma predykcję


def wczytaj(nazwa):
    """Predykcje przebiegu: jeden wiersz na budynek."""
    return pd.read_csv(PRZEBIEGI / f"{nazwa}.csv", dtype={"budynek": str})


def kolumna(pred):
    """Kolumna z predykcją: mieszkancy albo, w baseline'ach, objetosc_m3. Ewaluacja i tak skaluje sumę do spisu, więc obie się nadają."""
    return "mieszkancy" if "mieszkancy" in pred else "objetosc_m3"


def zgodnosc_z_bdot(pred, bud):
    """Kondygnacje świadka a BDOT10k oraz 'mieszkańcy > 0' a 'mieszkalny i eksploatowany' w BDOT10k."""
    ref = pd.DataFrame({"kond_bdot": bud.kondygnacje, "mieszkalny": bud.mieszkalny_bdot & (bud.kategoria == "eksploatowany")})
    p = pred.join(ref, on="budynek")
    wynik = {}
    if "kondygnacje" in p:
        k = p.dropna(subset=["kondygnacje", "kond_bdot"])
        wynik |= {"kond_mae": (k.kondygnacje - k.kond_bdot).abs().mean(), "kond_trafne": (k.kondygnacje == k.kond_bdot).mean()}
    znane = p.dropna(subset=[kolumna(p)])
    prawda, przewidziane = znane.mieszkalny.astype(bool), znane[kolumna(p)] > 0
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


def sumy_kwadratow(pred, bud, kw, kol=None):
    """Suma predykcji i ludność NSP w kwadratach, w których predykcję ma każdy budynek mieszkalny.

    bud i kw jak z budynki_w_kwadratach; budynki niemieszkalne w BDOT10k też się liczą, jeśli świadek dał im mieszkańców.
    """
    kol = kol or kolumna(pred)
    s = pred.dropna(subset=[kol]).set_index("budynek")[kol]
    kody = kompletne_kwadraty(bud, s.index)
    suma = sumy(s, udzialy(bud, s.index)).reindex(kody).fillna(0.0)
    return suma, kw.ludnosc.reindex(kody).astype(float)


def ocena_kwadratow(pred, bud, kw, kol=None):
    """Spearman i WAPE sum w kwadratach, z przedziałami; z mniej niż trzech kwadratów rangi nic nie mówią."""
    suma, ref = sumy_kwadratow(pred, bud, kw, kol)
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


def osoby(pred, bud, kw, kol):
    """Predykcja w osobach, seria o indeksie id budynku. Baseline (objetosc_m3) dostaje ludność NSP rozłożoną wg objętości:
    objętość razy (ludność / objętość) z kompletnych kwadratów spisu, czyli klasyczny rozkład dazymetryczny; SRLM go nie widzi."""
    s = pred.dropna(subset=[kol]).set_index("budynek")[kol]
    if kol == "objetosc_m3":
        suma, ref = sumy_kwadratow(pred, bud, kw, kol)
        s = s * ref.sum() / suma.sum()
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


def podsumowanie():
    """Tabela przebiegów z eksperymenty/*.toml, które mają wyniki. Pętlę oceniamy na kwadratach sprzed uzgadniania: po nim byłoby to koło."""
    bud = wczytaj_budynki()
    miasto, kw = budynki_w_kwadratach(zasieg())
    wiersze = []
    for plik in sorted(EKSPERYMENTY.glob("*.toml")):
        if (PRZEBIEGI / f"{plik.stem}.csv").exists():
            p = wczytaj(plik.stem)
            ok = p[p[kolumna(p)].notna()]
            kol = "mieszkancy_r0" if "mieszkancy_r0" in p else kolumna(p)
            wiersze.append({"przebieg": plik.stem, "budynki": len(p), "bledy": int(p.blad.notna().sum()), "usd": p.get("koszt_usd", pd.Series([0.0])).sum(),
                            "suma_mieszkancow": ok.mieszkancy.sum() if "mieszkancy" in ok else np.nan,
                            **zgodnosc_z_bdot(ok, bud), **ocena_kwadratow(ok, miasto, kw, kol)})
    return pd.DataFrame(wiersze).set_index("przebieg")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Porównanie przebiegów.")
    parser.add_argument("--srlm", type=int, nargs="*", help="ocena na rejonach SRLM (bez numerów: wszystkie pokryte arkuszami)")
    args = parser.parse_args()
    with pd.option_context("display.width", 200, "display.max_columns", None):
        if args.srlm is None:
            print(podsumowanie().round(3).to_string())
        else:
            miary, rejony = podsumowanie_srlm(args.srlm or None)
            print(miary.round(3).to_string())
            if args.srlm:
                print(rejony.drop(columns="geometry", errors="ignore").round(2).to_string())
