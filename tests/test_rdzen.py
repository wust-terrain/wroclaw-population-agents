"""Trzy reguły, których złamanie po cichu psuje wyniki: wzór, flaga rozjazdu i odcięcie świadka od liczb ze spisu."""

import pandas as pd

from agenci.estymatory import ze_wzoru
from agenci.karta import Karta
from agenci.petla import bilans, wazne_pytania
from agenci.szperacz import z_sieci

KARTA = Karta(id="a", pow_zabudowy_m2=100.0, h_m=12.0, zrodlo_h="z kondygnacji", kondygnacje=4.0, funkcja="budynek wielorodzinny",
              funkcje="budynek wielorodzinny", kategoria="eksploatowany", mieszkalny_bdot=True)


def obs(typ, udzial=1.0, stan="uzytkowany"):
    return {"typ": typ, "kondygnacje": 9, "udzial_mieszkalny": udzial, "stan": stan}


def test_wzor():
    assert ze_wzoru(obs("kamienica", 0.5), KARTA) == 100 * 4 * 0.5 / 37.08  # kondygnacje z BDOT10k, nie od świadka
    assert ze_wzoru(obs("zbiorowy"), KARTA) == 100 * 4 / 31.0
    assert ze_wzoru(obs("dom_jednorodzinny"), KARTA) == 2.88
    assert ze_wzoru(obs("uslugi"), KARTA) == 0.0
    assert ze_wzoru(obs("kamienica", stan="pustostan"), KARTA) == 0.0
    assert ze_wzoru(obs("inny"), KARTA) == 0.0  # bez rekordu typ "inny" nic nie znaczy...
    assert ze_wzoru(obs("inny"), KARTA, z_rekordem=True) == 100 * 4 / 37.08  # ...a z rekordem klasę bierzemy z BDOT10k


def test_bilans_skaluje_do_sumy_spisu_i_flaguje_rozklad():
    u = pd.Series({("a", "k1"): 0.5, ("a", "k2"): 0.5}).rename_axis(["id", "kod"])  # budynek leży po połowie w dwóch kwadratach
    b = bilans(pd.Series({"a": 400.0}), u, pd.Series({"k1": 100, "k2": 300}))
    assert b.szacunek.sum() == 400
    assert b.flaga.tolist() == [True, False]  # 200 wobec 100 to rozjazd, 200 wobec 300 jest na progu ilorazu 1,5


def test_pytanie_do_swiadka_nie_ma_liczb_ze_spisu():
    pytania = [{"budynek": "a", "atrybut": "typ", "pytanie": "Spis ma 33,5 os., a BDOT10k 8 kond. Co widać?"},
               {"budynek": "a", "atrybut": "stan", "pytanie": "drugie o ten budynek"}, {"budynek": "x", "atrybut": "typ", "pytanie": "spoza listy"}]
    wynik = wazne_pytania(pytania, {"a"}, set())
    assert [p["pytanie"] for p in wynik] == ["Spis ma … os., a BDOT10k … kond. Co widać?"]


def test_szperacz_zmienia_szacunek_tylko_ze_zrodlem():
    znalezione = {"znalezione": "mieszkania", "liczba": 100, "zrodlo": "https://przyklad.pl", "cytat": "100 mieszkań"}
    assert z_sieci(znalezione) == 171.0  # 1,71 osoby na mieszkanie
    assert z_sieci(znalezione | {"znalezione": "miejsca"}) == 100.0
    assert z_sieci(znalezione | {"zrodlo": ""}) is None
    assert z_sieci(znalezione | {"znalezione": "brak"}) is None
    assert z_sieci(None) is None  # odmowa modelu


def test_suma_w_rejonach_dzieli_budynek_na_granicy():
    import geopandas as gpd
    from shapely.geometry import box

    from agenci.srlm import suma_w_rejonach

    rejony = gpd.GeoDataFrame({"nazwa": ["A", "B"], "ludnosc": [1.0, 1.0]}, geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)], crs=2177)
    rejony.index = pd.Index([30, 31], name="NR_REJ")
    bud = gpd.GeoDataFrame(geometry=[box(2, 2, 4, 4), box(8, 2, 12, 4)], index=pd.Index(["w", "g"], name="id"), crs=2177)
    s = suma_w_rejonach(pd.Series({"w": 10.0, "g": 100.0}), bud, rejony)
    assert s.to_dict() == {30: 10.0 + 50.0, 31: 50.0}  # "g" leży po połowie w obu rejonach
    assert s.sum() == 110.0


def test_paczki_dziela_kwadraty_i_sprzeczne():
    from agenci.petla import PACZKA, PACZKA_SPRZECZNYCH, _paczki

    assert _paczki(["k1", "k2"], ["s1"]) == [(["k1", "k2"], ["s1"])]  # mały przebieg: jedno wywołanie
    kody, sprz = [f"k{i}" for i in range(PACZKA + 1)], [f"s{i}" for i in range(PACZKA_SPRZECZNYCH + 1)]
    p = _paczki(kody, sprz)
    assert [len(k) for k, _ in p] == [PACZKA, 1, 0] and [len(s) for _, s in p] == [0, PACZKA_SPRZECZNYCH, 1]
    assert _paczki([], []) == []
