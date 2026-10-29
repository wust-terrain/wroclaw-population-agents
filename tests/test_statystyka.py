"""Testy świadka statystycznego: parser opisów granic obwodów i przydział NSP 2021."""

import pandas as pd
import pytest

from agenci.statystyka import KONIEC_ULICY, POPULACJA, normalizuj_ulice, obwody_adresu, parsuj_granice

dane = pytest.mark.skipif(not list(POPULACJA.glob("Grid_125_*.xlsx")), reason="brak NSP 2021 w data/populacja")


def test_parsuj_granice_format_wroclawia():
    opis = ("Wrocław-Śródmieście ulice: pl. gen. Józefa Bema 2 - 6, Henryka Sienkiewicza 5, 21, 23, Kanonia, "
            "Mikołaja Reja 23 - 47 nieparzyste, 36 - 56 parzyste, Tadeusza Kościuszki 152 do końca parzyste, "
            "1 Maja, Nowowiejska 82 - 104A parzyste")
    r = parsuj_granice(opis)
    assert r["józefa bema"] == [(2, 6, None)]
    assert r["henryka sienkiewicza"] == [(5, 5, None), (21, 21, None), (23, 23, None)]
    assert r["kanonia"] is None and r["1 maja"] is None
    assert r["mikołaja reja"] == [(23, 47, 1), (36, 56, 0)]
    assert r["tadeusza kościuszki"] == [(152, KONIEC_ULICY, 0)]
    assert r["nowowiejska"] == [(82, 104, 0)]


def test_obwody_adresu():
    obwody = pd.DataFrame({"reguly": [parsuj_granice("X ulice: Mikołaja Reja 23 - 47 nieparzyste, Krzywa"),
                                      parsuj_granice("X ulice: Mikołaja Reja 3 - 21 nieparzyste, 2 - 8 parzyste")]},
                          index=[67, 75])
    assert obwody_adresu("Mikołaja Reja", "25", obwody) == [67]
    assert obwody_adresu("Mikołaja Reja", "4", obwody) == [75]
    assert obwody_adresu("Mikołaja Reja", "24", obwody) == []  # parzyste 24 nie ma w żadnym opisie
    assert obwody_adresu("ulica Krzywa", "7A", obwody) == [67]  # cała ulica
    assert normalizuj_ulice("pl. gen. Józefa Bema") == "józefa bema"


@dane
def test_przydzial_nsp_sumuje_sie_do_kwadratow():
    from agenci.statystyka import przydzial_nsp, wczytaj_nsp
    from ortofoto.arkusze import zasieg

    bud, kw = przydzial_nsp(wczytaj_nsp(zasieg()))
    z_budynkiem = kw[kw.pow_kondygnacji > 0]
    przydzielone = bud.groupby("komorka").przydzial_2021.sum()
    assert przydzielone.reindex(z_budynkiem.index).values == pytest.approx(z_budynkiem.ludnosc.values)
