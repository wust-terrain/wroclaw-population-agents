"""Testy infrastruktury agentów. Działają bez klucza API (tryb na sucho)."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from agenci.eksperyment import Konfiguracja, uruchom, wybierz_budynki
from agenci.estymatory import ze_wzoru
from agenci.ewaluacja import ocena_per_obszar, podsumowanie, spearman
from agenci.karta import Karta, zbuduj_karte
from agenci.llm import Dziennik, Klient, obraz, tekst
from agenci.swiadkowie import SCHEMAT_OBSERWACJI
from ortofoto.arkusze import KOLEJNOSC

dane = pytest.mark.skipif(not KOLEJNOSC, reason="brak arkuszy ortofotomapy w data/")


def test_klient_na_sucho_pamieta_odpowiedzi(tmp_path):
    klient = Klient(Dziennik(tmp_path / "baza.sqlite"), na_sucho=True)
    tresc = [tekst("opis"), obraz(np.zeros((100, 200, 3), np.uint8))]
    pierwsza = klient.zapytaj(rola="test", system="s", tresc=tresc, schemat=SCHEMAT_OBSERWACJI)
    druga = klient.zapytaj(rola="test", system="s", tresc=tresc, schemat=SCHEMAT_OBSERWACJI)
    inne_powtorzenie = klient.zapytaj(rola="test", system="s", tresc=tresc, schemat=SCHEMAT_OBSERWACJI, powtorzenie=1)

    assert not pierwsza.z_pamieci and druga.z_pamieci and not inne_powtorzenie.z_pamieci
    assert druga.dane == pierwsza.dane and druga.koszt_usd == pierwsza.koszt_usd > 0
    assert set(pierwsza.dane) == set(SCHEMAT_OBSERWACJI["required"])


def test_wzor():
    karta = Karta(id="a", pow_zabudowy_m2=200, h_m=15, zrodlo_h="pomiar OSM", kondygnacje=5,
                  funkcja="budynek wielorodzinny", funkcje="budynek wielorodzinny", kategoria="eksploatowany",
                  mieszkalny_bdot=True, adres=None)
    obs = {"typ": "kamienica", "kondygnacje": 5, "udzial_mieszkalny": 0.8, "stan": "uzytkowany"}
    rubryka = {"kamienica": 2.5}
    assert ze_wzoru(obs, karta, rubryka) == pytest.approx(200 * 5 * 0.8 * 2.5 / 100)
    assert ze_wzoru(obs | {"typ": "garaz"}, karta, rubryka) == 0
    assert ze_wzoru(obs | {"stan": "w_budowie"}, karta, rubryka) == 0
    assert ze_wzoru(obs | {"kondygnacje": 0}, karta, rubryka) == pytest.approx(20)  # kondygnacje z BDOT


def test_ocena_per_obszar():
    bud = gpd.GeoDataFrame({"h": [10, 10, 10]}, index=["a", "b", "c"],
                           geometry=[Point(0.5, 0.5).buffer(0.1), Point(1.5, 0.5).buffer(0.1),
                                     Point(1.6, 0.6).buffer(0.1)], crs=2177)
    obszary = gpd.GeoDataFrame({"wyborcy": [10, 40]}, geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=2177)
    pred = pd.DataFrame({"budynek": ["a", "b", "c"], "mieszkancy": [10.0, 20.0, 20.0]})
    wynik = ocena_per_obszar(pred, bud, obszary, "wyborcy")
    assert wynik["n_obszarow"] == 2 and wynik["iloraz_sum"] == pytest.approx(1.0)
    assert spearman(pd.Series([1, 2, 3]), pd.Series([10, 20, 30])) == pytest.approx(1.0)


@dane
def test_placebo_bierze_obrazy_innego_budynku():
    from ortofoto.budynki import wczytaj_budynki, wybierz

    bud = wczytaj_budynki()
    b1, b2 = wybierz(bud, osm_id=101207542), wybierz(bud, osm_id=101211778)
    placebo = zbuduj_karte(b1, fasady=False, obrazy_z=b2)
    assert placebo.id == b1.name and placebo.h_m == pytest.approx(37.2)
    assert np.array_equal(placebo.widoki["N"], zbuduj_karte(b2, fasady=False).widoki["N"])


@dane
def test_eksperyment_na_sucho(tmp_path):
    baza = tmp_path / "baza.sqlite"
    konf = Konfiguracja(nazwa="test", estymator="wzor", zrodla=["tabela", "widoki", "fasady"], rownolegle=2,
                        budynki={"liczba": 3, "ziarno": 1})
    pred = uruchom(konf, na_sucho=True, baza=baza)
    assert len(pred) == 3 and pred["blad"].isna().all() if "blad" in pred else len(pred) == 3
    assert (pred.z_pamieci == False).all()  # noqa: E712

    ponownie = uruchom(konf, na_sucho=True, baza=baza)
    assert ponownie.z_pamieci.all()  # drugi przebieg w całości z pamięci

    uruchom(Konfiguracja(nazwa="obj", estymator="objetosc_bdot", budynki={"liczba": 3, "ziarno": 1}), baza=baza)
    tabela = podsumowanie(baza)
    assert {"test__na_sucho", "obj"} <= set(tabela.index)
    assert tabela.loc["test__na_sucho", "usd_zaplacone"] > 0


@dane
def test_ta_sama_probka_dla_roznych_konfiguracji():
    from ortofoto.budynki import wczytaj_budynki

    bud = wczytaj_budynki()
    a = wybierz_budynki(bud, Konfiguracja(nazwa="a", estymator="objetosc"))
    b = wybierz_budynki(bud, Konfiguracja(nazwa="b", estymator="wzor", zrodla=["tabela"]))
    assert a == b and len(a) == 40
