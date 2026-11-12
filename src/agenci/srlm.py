"""SRLM: szacowana rzeczywista liczba mieszkańców w rejonach komunikacyjnych Wrocławia (stan na 31.12.2022).

Plik data/SRLM/SRLM_Wroclaw_20221231.shp (załącznik raportu Uniwersytetu Wrocławskiego dla UMW, 2023, w BIP UMW):
375 rejonów, EPSG:2177, LUD_SZAC to ludność rejonu, razem 893 506 osób, czyli więcej niż zameldowanych i niż w NSP 2021.
Raport liczy ją z meldunków stałych i czasowych, dodaje niezameldowanych w zamieszkanych lokalach (lokale GUS minus
lokale z meldunkami w PESEL), połowę pustych lokali po 3 osoby i 95% miejsc w akademikach i bursach; powierzchnię
budynków z BDOT10k bierze tylko w kilku rejonach bez meldunków. Służy wyłącznie do oceny na końcu: nie widzi go ani
pętla (ta używa NSP 2021), ani żaden prompt.

    obszar = obszar_pracy(rejony.loc[30].geometry)   # kwadraty NSP przecinające rejon: tu działa system
    u = udzialy_w_rejonach(bud, rejony)              # budynek przy granicy dzieli się między rejony
"""

import geopandas as gpd
import pandas as pd

from agenci.statystyka import wczytaj_nsp
from ortofoto import DATA
from ortofoto.budynki import wczytaj_bdot

PLIK = DATA / "SRLM" / "SRLM_Wroclaw_20221231.shp"
PLAC_GRUNWALDZKI = 30


def wczytaj_srlm(numery=None):
    """Rejony SRLM o numerach `numery` (domyślnie wszystkie): indeks NR_REJ, kolumny nazwa, ludnosc, geometry (EPSG:2177)."""
    r = gpd.read_file(PLIK).set_index("NR_REJ")
    r = gpd.GeoDataFrame({"nazwa": r.NAZWA_REJ, "ludnosc": r.LUD_SZAC.astype(float)}, geometry=r.geometry, crs=r.crs)
    return r if numery is None else r.loc[list(numery)]


def obszar_pracy(rejon):
    """Suma kwadratów NSP 125 m, które mają część wspólną z rejonem (wielokąt, EPSG:2177).

    Cały kwadrat, a nie sam rejon, bo pętla porównuje sumy ze spisem tylko w kwadratach, w których predykcję ma każdy
    budynek mieszkalny; przy samym rejonie kwadraty przy jego granicy byłyby ucięte i pętla nic by nie uzgadniała.
    """
    nsp = wczytaj_nsp(rejon)
    return nsp[nsp.intersection(rejon).area > 1.0].union_all()


def udzialy_w_rejonach(bud, rejony):
    """Seria (id budynku, numer rejonu) -> część obrysu budynku leżąca w rejonie; budynki poza rejonami pomijamy."""
    czesci = gpd.overlay(bud[["geometry"]].reset_index(), rejony[["geometry"]].reset_index(), how="intersection")
    czesci["udzial"] = czesci.area / czesci["id"].map(bud.area)
    return czesci.set_index(["id", "NR_REJ"]).udzial.rename_axis(["id", "rejon"])


def suma_w_rejonach(wartosci, bud, rejony):
    """Suma wartości budynków (seria o indeksie id) w każdym rejonie; budynek wnosi tyle, ile wynosi jego udział w rejonie."""
    u = udzialy_w_rejonach(bud, rejony)
    u = u[u.index.get_level_values("id").isin(wartosci.index)]
    return (u * wartosci.reindex(u.index.get_level_values("id")).to_numpy()).groupby(level="rejon").sum().reindex(rejony.index).fillna(0.0)


def pokrycie(rejony, ids):
    """Część powierzchni mieszkalnej rejonu (obrys × kondygnacje z BDOT10k, budynki mieszkalne), która ma predykcję.

    Rejon ocenia się tylko przy pokryciu bliskim 1: inaczej suma predykcji jest zaniżona przez budynki poza arkuszami.
    """
    bdot = wczytaj_bdot(rejony.union_all())
    bdot = bdot[bdot.funkcja_ogolna == "budynki mieszkalne"]
    u = udzialy_w_rejonach(bdot, rejony)
    pow_ = u * (bdot.area * bdot.kondygnacje.fillna(1)).reindex(u.index.get_level_values("id")).to_numpy()
    z_predykcja = pow_[u.index.get_level_values("id").isin(ids)].groupby(level="rejon").sum()
    return (z_predykcja / pow_.groupby(level="rejon").sum()).reindex(rejony.index).fillna(0.0)
