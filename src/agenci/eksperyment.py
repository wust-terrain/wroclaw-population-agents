"""Uruchamianie eksperymentów (ablacji) z plików TOML.

    python -m agenci.eksperyment eksperymenty/swiadek_s2.toml             # prawdziwy przebieg
    python -m agenci.eksperyment eksperymenty/swiadek_s2.toml --na-sucho  # bez API: test i wycena

Każdy przebieg zapisuje predykcje do tabeli `predykcje` i do wyniki/eksperymenty/<nazwa>.csv,
a konfigurację i commit do tabeli `przebiegi`. Wszystkie konfiguracje z tym samym [budynki]
dostają tę samą próbkę budynków, więc ich wyniki da się porównywać budynek po budynku.
"""

import argparse
import json
import sqlite3
import subprocess
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import pandas as pd

from agenci import BAZA
from agenci.estymatory import objetosc, objetosc_bdot, rubryka_llm, rubryka_z_pliku, wprost, ze_wzoru
from agenci.karta import zbuduj_karte
from agenci.statystyka import przydzial_nsp, wczytaj_nsp
from agenci.llm import Dziennik, Klient
from agenci.swiadkowie import swiadek_wizualny
from ortofoto import KORZEN
from ortofoto.arkusze import KOLEJNOSC, zasieg
from ortofoto.budynki import wczytaj_budynki
from ortofoto.wycinki import dostepne_kierunki

ESTYMATORY = ("objetosc", "objetosc_bdot", "nsp_2021", "wprost", "wzor")
ZRODLA = ("tabela", "widoki", "fasady", "adres")


@dataclass
class Konfiguracja:
    nazwa: str
    opis: str = ""
    estymator: str = "wzor"  # objetosc | objetosc_bdot | nsp_2021 | wprost | wzor
    zrodla: list = field(default_factory=lambda: ["tabela", "widoki", "fasady"])
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    obrys: bool = True  # obrys podstawy i dachu na widokach
    max_px: int = 768  # dłuższy bok obrazu wysyłanego do modelu (oś ablacji: rozdzielczość)
    rubryka: str = "llm"  # "llm" albo ścieżka do pliku TOML z gęstościami (względem katalogu repo)
    placebo: bool = False  # każdy budynek dostaje obrazy innego budynku z próbki
    powtorzenia: int = 1
    rownolegle: int = 4
    budynki: dict = field(default_factory=lambda: {"liczba": 40, "ziarno": 0, "id": [], "z_adresem": False})

    def __post_init__(self):
        if self.estymator not in ESTYMATORY:
            raise ValueError(f"estymator musi być jednym z {ESTYMATORY}, jest {self.estymator!r}")
        if nieznane := set(self.zrodla) - set(ZRODLA):
            raise ValueError(f"nieznane źródła: {sorted(nieznane)}; dozwolone: {ZRODLA}")
        self.budynki = {"liczba": 40, "ziarno": 0, "id": [], "z_adresem": False} | self.budynki


def wczytaj_konfiguracje(sciezka):
    with open(sciezka, "rb") as f:
        return Konfiguracja(**tomllib.load(f))


def wybierz_budynki(bud, konf):
    """Lista id budynków (BDOT10k): podana wprost albo losowa próbka widocznych ze wszystkich kierunków."""
    if konf.budynki["id"]:
        return [str(i) for i in konf.budynki["id"]]
    pelne = bud[[len(dostepne_kierunki(b)) == len(KOLEJNOSC) for _, b in bud.iterrows()]]
    if konf.budynki["z_adresem"]:
        pelne = pelne[pelne["addr:street"].notna()]
    n = min(konf.budynki["liczba"], len(pelne))
    return sorted(pelne.sample(n, random_state=konf.budynki["ziarno"]).index)


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KORZEN, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def uruchom(konf, na_sucho=False, baza=BAZA):
    """Przebieg eksperymentu; zwraca DataFrame predykcji (jeden wiersz na budynek i powtórzenie)."""
    llm = konf.estymator in ("wprost", "wzor")
    nazwa = konf.nazwa + ("__na_sucho" if na_sucho and llm else "")  # baseline'y nie wołają modelu
    start = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # format jak CURRENT_TIMESTAMP w SQLite
    bud = wczytaj_budynki()
    ids = wybierz_budynki(bud, konf)
    dziennik = Dziennik(baza)
    klient = Klient(dziennik, konf.model, konf.effort, na_sucho) if llm else None

    rubryka = None
    nsp = przydzial_nsp(wczytaj_nsp(zasieg()))[0].przydzial_2021 if konf.estymator == "nsp_2021" else None
    if konf.estymator == "wzor":
        rubryka = (rubryka_llm(klient, eksperyment=nazwa) if konf.rubryka == "llm"
                   else rubryka_z_pliku(KORZEN / konf.rubryka))
    placebo = dict(zip(ids, ids[1:] + ids[:1])) if konf.placebo else {}  # przesunięcie o jeden w próbce

    def jeden(budynek, powtorzenie):
        start = time.perf_counter()
        wiersz = {"eksperyment": nazwa, "budynek": budynek, "powtorzenie": powtorzenie}
        try:
            b = bud.loc[budynek]
            karta = zbuduj_karte(b, max_px=konf.max_px, obrys=konf.obrys,
                                 widoki=llm and "widoki" in konf.zrodla, fasady=llm and "fasady" in konf.zrodla,
                                 obrazy_z=bud.loc[placebo[budynek]] if budynek in placebo else None)
            log = dict(eksperyment=nazwa, powtorzenie=powtorzenie)
            if konf.estymator == "objetosc":
                wiersz["mieszkancy"] = objetosc(karta)
            elif konf.estymator == "objetosc_bdot":
                wiersz["mieszkancy"] = objetosc_bdot(karta)
            elif konf.estymator == "nsp_2021":
                wiersz["mieszkancy"] = float(nsp.get(budynek, 0.0))
            elif konf.estymator == "wprost":
                wynik, odp = wprost(klient, karta, konf.zrodla, konf.max_px, **log)
                wiersz |= (wynik or {}) | {"koszt_usd": odp.koszt_usd, "z_pamieci": odp.z_pamieci, "stop": odp.stop}
            else:
                obs, odp = swiadek_wizualny(klient, karta, konf.zrodla, konf.obrys, konf.max_px, **log)
                wiersz |= {"koszt_usd": odp.koszt_usd, "z_pamieci": odp.z_pamieci, "stop": odp.stop}
                if obs is not None:
                    wiersz |= obs | {"mieszkancy": ze_wzoru(obs, karta, rubryka)}
        except Exception as e:  # jeden zepsuty budynek nie zatrzymuje przebiegu
            wiersz["blad"] = f"{type(e).__name__}: {e}"[:300]
        wiersz["czas_s"] = time.perf_counter() - start
        return wiersz

    zadania = [(budynek, p) for budynek in ids for p in range(konf.powtorzenia)]
    with ThreadPoolExecutor(max(1, konf.rownolegle)) as ex:
        pred = pd.DataFrame(list(ex.map(lambda z: jeden(*z), zadania)))

    with sqlite3.connect(baza) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS przebiegi (eksperyment TEXT PRIMARY KEY, start TEXT, koniec TEXT,
                      commit_git TEXT, na_sucho INTEGER, konfiguracja TEXT, rubryka TEXT)""")
        db.execute("INSERT OR REPLACE INTO przebiegi VALUES (?, ?, datetime('now'), ?, ?, ?, ?)",
                   (nazwa, start, _commit(), int(na_sucho), json.dumps(asdict(konf), ensure_ascii=False),
                    json.dumps(rubryka, ensure_ascii=False) if rubryka else None))
        istniejace = {r[1] for r in db.execute("PRAGMA table_info(predykcje)")}  # pusty zbiór, gdy brak tabeli
        if istniejace:
            db.execute("DELETE FROM predykcje WHERE eksperyment = ?", (nazwa,))
            for kolumna in set(pred.columns) - istniejace:  # przebiegi różnych estymatorów mają różne kolumny
                db.execute(f'ALTER TABLE predykcje ADD COLUMN "{kolumna}"')
        pred.to_sql("predykcje", db, if_exists="append", index=False)

    katalog = baza.parent / "eksperymenty"
    katalog.mkdir(parents=True, exist_ok=True)
    pred.to_csv(katalog / f"{nazwa}.csv", index=False)
    return pred


def main():
    parser = argparse.ArgumentParser(description="Uruchamia eksperyment z pliku TOML.")
    parser.add_argument("konfiguracja", nargs="+", help="plik(i) TOML z katalogu eksperymenty/")
    parser.add_argument("--na-sucho", action="store_true", help="bez API: odpowiedzi ze schematu i szacunek kosztu")
    parser.add_argument("--liczba", type=int, help="nadpisuje liczbę budynków w próbce")
    args = parser.parse_args()

    for sciezka in args.konfiguracja:
        konf = wczytaj_konfiguracje(sciezka)
        if args.liczba:
            konf.budynki["liczba"] = args.liczba
        pred = uruchom(konf, na_sucho=args.na_sucho)
        bledy = pred["blad"].notna().sum() if "blad" in pred else 0
        koszt = pred.get("koszt_usd", pd.Series(dtype=float)).sum()
        print(f"{konf.nazwa}: {len(pred)} predykcji, błędów {bledy}, koszt {koszt:.3f} USD"
              f"{' (szacunek na sucho)' if args.na_sucho else ''}, czas p50 {pred.czas_s.median():.1f} s")
        if bledy:
            print(pred.loc[pred["blad"].notna(), ["budynek", "blad"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
