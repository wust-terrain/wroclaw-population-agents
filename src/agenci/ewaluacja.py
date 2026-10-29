"""Ewaluacja przebiegów: koszt, czas, stabilność, zgodność z BDOT10k i proxy (woda, obwody wyborcze).

    python -m agenci.ewaluacja                          # tabela porównawcza wszystkich przebiegów
    python -m agenci.ewaluacja swiadek_s2 wprost_s2     # tylko wybrane

Dopóki nie mamy danych MPWiK ani obwodów, zewnętrzną kontrolą jest BDOT10k: kondygnacje oraz to,
czy budynek jest mieszkalny i eksploatowany. To sprawdza świadka, a nie liczbę mieszkańców, i jest
koliste dla przebiegów, które widzą rekord BDOT w prompcie (źródło "tabela"); uczciwy test to
przebieg bez tabeli. ocena_per_budynek i ocena_per_obszar czekają na dane referencyjne.
"""

import argparse
import sqlite3

import geopandas as gpd
import numpy as np
import pandas as pd

from agenci import BAZA
from ortofoto.budynki import wczytaj_budynki


def wczytaj_predykcje(baza=BAZA, eksperymenty=None):
    with sqlite3.connect(baza) as db:
        pred = pd.read_sql("SELECT * FROM predykcje", db)
    if "blad" not in pred:
        pred["blad"] = None
    return pred[pred.eksperyment.isin(eksperymenty)] if eksperymenty else pred


def koszty(baza=BAZA):
    """Koszt nominalny (jak bez pamięci odpowiedzi) i faktycznie zapłacony, z ostatniego przebiegu eksperymentu."""
    with sqlite3.connect(baza) as db:
        return pd.read_sql("""SELECT w.eksperyment, COUNT(*) AS wywolania, SUM(w.koszt_usd) AS koszt_usd,
                              SUM(CASE WHEN w.z_pamieci = 0 THEN w.koszt_usd ELSE 0 END) AS koszt_zaplacony,
                              SUM(w.tokeny_we) AS tokeny_we, SUM(w.tokeny_wy) AS tokeny_wy
                              FROM wywolania w JOIN przebiegi p ON w.eksperyment = p.eksperyment AND w.czas >= p.start
                              GROUP BY w.eksperyment""", db).set_index("eksperyment")


def spearman(a, b):
    """Korelacja rang (Pearson na rangach, remisy uśrednione) na wspólnych indeksach."""
    a, b = pd.Series(a), pd.Series(b)
    wspolne = a.index.intersection(b.index)
    a, b = a[wspolne], b[wspolne]
    if len(wspolne) < 3 or a.nunique() < 2 or b.nunique() < 2:  # stała seria nie ma rangi
        return np.nan
    return a.rank().corr(b.rank())


def zgodnosc_z_bdot(pred, bud):
    """Kondygnacje świadka a BDOT10k oraz 'mieszkańcy > 0' a 'mieszkalny i eksploatowany' w BDOT10k."""
    ref = pd.DataFrame({"kond_bdot": bud.kondygnacje,
                        "mieszkalny": bud.mieszkalny_bdot & (bud.kategoria == "eksploatowany")})
    p = pred.join(ref, on="budynek")
    wynik = {}
    if "kondygnacje" in p:
        k = p.dropna(subset=["kondygnacje", "kond_bdot"])
        wynik |= {"kond_mae": (k.kondygnacje - k.kond_bdot).abs().mean(),
                  "kond_trafne": (k.kondygnacje == k.kond_bdot).mean()}
    znane = p.dropna(subset=["mieszkancy"])
    if len(znane):
        prawda, przewidziane = znane.mieszkalny.astype(bool), znane.mieszkancy > 0
        tp = (prawda & przewidziane).sum()
        wynik |= {"mieszk_trafnosc": (prawda == przewidziane).mean(),
                  "mieszk_f1": 2 * tp / (prawda.sum() + przewidziane.sum()) if tp else 0.0}
    return wynik


def stabilnosc(pred):
    """Przy kilku powtórzeniach: zgodność typu i rozrzut liczby mieszkańców między powtórzeniami."""
    if pred.powtorzenie.nunique() < 2:
        return {}
    wynik = {}
    if "typ" in pred:
        wynik["typ_zgodny"] = pred.groupby("budynek").typ.agg(lambda t: t.value_counts(normalize=True).iloc[0]).mean()
    m = pred.groupby("budynek").mieszkancy
    wynik["wsp_zmiennosci"] = (m.std() / m.mean()).replace([np.inf, -np.inf], np.nan).mean()
    return wynik


def ocena_per_budynek(pred, referencja):
    """Spearman predykcji z referencją per budynek (Series indeksowana id budynku, np. zużycie wody)."""
    s = pred.groupby("budynek").mieszkancy.mean()
    return {"n": len(s.index.intersection(referencja.index)), "spearman": spearman(s, referencja)}


def ocena_per_obszar(pred, bud, obszary, kolumna):
    """Sumy predykcji w obszarach (np. obwody wyborcze, kwadraty NSP 2021) a liczba referencyjna w kolumnie.

    obszary to GeoDataFrame w EPSG:2177. Budynek należy do obszaru, w którym leży jego środek.
    Ma sens tylko wtedy, gdy predykcje obejmują wszystkie budynki mieszkalne w obszarach.
    """
    s = pred.groupby("budynek").mieszkancy.mean()
    punkty = gpd.GeoDataFrame({"mieszkancy": s.values}, geometry=bud.loc[s.index].centroid.values, crs=bud.crs)
    j = gpd.sjoin(punkty, obszary[[kolumna, "geometry"]], predicate="within")
    suma = j.groupby("index_right").mieszkancy.sum()
    ref = obszary.loc[suma.index, kolumna].astype(float)
    skala = ref.sum() / suma.sum()
    return {"n_obszarow": len(suma), "spearman": spearman(suma, ref), "iloraz_sum": suma.sum() / ref.sum(),
            "wape_po_skalowaniu": (suma * skala - ref).abs().sum() / ref.sum()}


def podsumowanie(baza=BAZA, eksperymenty=None):
    pred = wczytaj_predykcje(baza, eksperymenty)
    bud = wczytaj_budynki()
    koszt = koszty(baza)
    obj = bud.geometry.area * bud.h  # baseline do porównania rankingów
    wiersze = []
    for nazwa, p in pred.groupby("eksperyment"):
        ok = p[p.blad.isna() & p.mieszkancy.notna()]
        n = p.budynek.nunique()
        k = koszt.loc[nazwa] if nazwa in koszt.index else pd.Series({"koszt_usd": 0.0, "koszt_zaplacony": 0.0})
        mieszkancy = ok.groupby("budynek").mieszkancy.mean()
        wiersze.append({"eksperyment": nazwa, "budynki": n, "bledy": int(p.blad.notna().sum()),
                        "usd_na_budynek": k.koszt_usd / n, "usd_zaplacone": k.koszt_zaplacony,
                        "czas_p50": p.czas_s.median(), "czas_p95": p.czas_s.quantile(0.95),
                        **zgodnosc_z_bdot(ok, bud), "spearman_z_objetoscia": spearman(mieszkancy, obj),
                        "suma_mieszkancow": mieszkancy.sum(), **stabilnosc(ok)})
    return pd.DataFrame(wiersze).set_index("eksperyment")


def main():
    parser = argparse.ArgumentParser(description="Porównanie przebiegów eksperymentów.")
    parser.add_argument("eksperymenty", nargs="*", help="nazwy przebiegów (domyślnie wszystkie)")
    args = parser.parse_args()
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(podsumowanie(eksperymenty=args.eksperymenty or None).round(3).to_string())


if __name__ == "__main__":
    main()
