# Cały Wrocław na serwerze z Qwen3.8-27B

Instrukcja krok po kroku dla przebiegu `eksperymenty/wroclaw_qwen.toml`: 826 arkuszy ortofotomapy skośnej, ok. 70 tys. budynków
z BDOT10k (51 tys. mieszkalnych), ocena na 375 rejonach SRLM. Na laptopie da się zrobić krok 1 i sprawdzić kod; reszta wymaga serwera.

## Co gdzie pracuje

- **GPU** obsługuje model. vLLM wystawia Qwen3.8-27B jako serwer zgodny z API OpenAI, a nasz kod wysyła do niego zapytania
  (`src/agenci/llm.py`, każdy model spoza `claude-*`). Czas przebiegu zależy prawie wyłącznie od GPU.
- **CPU i RAM** obsługują potok: wczytanie budynków, wycinki ze zdjęć, rubryka, pętla. 768 GB RAM to ogromny zapas; potok
  zajmuje kilka do kilkunastu GB.
- **Dysk:** ok. 280 GB na arkusze (3304 pliki po ok. 85 MB), kilka GB na kafle LiDAR-u i OSM, reszta danych poniżej 1 GB.
  Wolne miejsce sprawdź poleceniem `df -h` przed pobieraniem.

## 1. Kod i dane, które nie pobierają się same

```bash
git clone <repo> && cd ortofotomapa
uv sync                       # środowisko Pythona z pyproject.toml
```

Z laptopa skopiuj na serwer (np. `rsync -av data/ serwer:ortofotomapa/data/`) trzy rzeczy, które pobiera się ręcznie (README, sekcja
„Instalacja i dane”):

```text
data/0264_powiat_m.Wrocław/BDOT10K/...OT_BUBD_A.xml   BDOT10k
data/populacja/Grid_125_{1,2}.xlsx                     NSP 2021, kwadraty 125 m
data/SRLM/SRLM_Wroclaw_20221231.*                      SRLM, tylko do oceny
```

Folder `data/kafle/` też można skopiować: to już pobrane kafle OSM i LiDAR-u.

## 2. Arkusze ortofotomapy (ok. 280 GB)

```bash
tmux new -s pobieranie                                   # sesja przetrwa rozłączenie SSH; wyjście: Ctrl-b d, powrót: tmux a -t pobieranie
uv run python -m ortofoto.pobierz --srlm --tylko-lista   # ile arkuszy i ile GB
uv run python -m ortofoto.pobierz --srlm                 # pobieranie, 4 pliki naraz
```

Przerwane pobieranie wznawia to samo polecenie: gotowe pliki są pomijane, niedokończone mają końcówkę `.czesc`
(można je usunąć). Skorowidz arkuszy zapisuje się w `data/skorowidz_ukosne.gpkg`.

## 3. Budynki, LiDAR i OSM, zanim ruszy model

```bash
uv run python -c "from ortofoto.budynki import wczytaj_budynki; b = wczytaj_budynki(); print(len(b), b.zrodlo_h.value_counts())"
```

Za pierwszym razem pobiera ok. 330 kafli LiDAR-u (WCS GUGiK) i ok. 100 kafli OSM (Overpass) do `data/kafle/`; to może trwać
1–3 godziny. Overpass bywa przeciążony: kod ponawia zapytania, a jeśli mimo to padnie, uruchom polecenie jeszcze raz (gotowe kafle
zostają). Robimy to osobno, żeby GPU nie czekało na pobieranie.

## 4. Serwer modelu (vLLM)

Polecenie z oficjalnego przepisu vLLM dla Qwen3.8-27B (vLLM 0.17 lub nowszy); sprawdź przepis przed uruchomieniem, bo flagi się zmieniają:

```bash
tmux new -s vllm
vllm serve Qwen/Qwen3.8-27B --reasoning-parser qwen3 --mm-encoder-tp-mode data --max-model-len 131072
```

- Wagi BF16 zajmują ok. 55 GB pamięci GPU; na mniejszej karcie użyj `Qwen/Qwen3.8-27B-FP8`, a w konfiguracji przebiegu wpisz tę
  samą nazwę w polu `model`. Przy kilku GPU dodaj `--tensor-parallel-size <liczba kart>`.
- `--reasoning-parser qwen3` jest potrzebny: bez niego rozumowanie modelu trafia do odpowiedzi i JSON się nie parsuje.
- Poziom rozumowania ustawia `EFFORT` w `llm.py` (`medium`; Qwen zna też `low` i `xhigh`).
- Działa, gdy `curl http://localhost:8000/v1/models` zwraca nazwę modelu.

## 5. Próba na 40 budynkach

```bash
export LOKALNY_URL=http://localhost:8000/v1   # adres serwera vLLM (to jest domyślna wartość)
export ROWNOLEGLE=32                          # tyle zapytań naraz; vLLM łączy je w paczki, więc więcej = szybciej, do granicy pamięci GPU
uv run python -m agenci.eksperyment eksperymenty/qwen_proba.toml
```

Sprawdź w `wyniki/eksperymenty/qwen_proba.csv`, że kolumna `blad` jest pusta, a `typ` i `kondygnacje` mają sens. Z logu w
`wyniki/eksperymenty.sqlite` (tabela `wywolania`, kolumny `czas_s`, `tokeny_wy`) wyjdzie, ile trwa jedno wywołanie. Czas całego
miasta to w przybliżeniu 70 tys. wywołań świadka razy średni czas wywołania podzielony przez `ROWNOLEGLE`, plus pętla.

## 6. Cały Wrocław

```bash
tmux new -s wroclaw
export ROWNOLEGLE=32 ANTHROPIC_API_KEY=...    # klucz tylko dla szperacza na Haiku; bez niego ustaw szukaj = false w TOML
uv run python -m agenci.eksperyment eksperymenty/wroclaw_objetosc_bdot.toml   # baseline, kilka minut, bez modelu
uv run python -m agenci.eksperyment eksperymenty/wroclaw_qwen.toml 2>&1 | tee wyniki/wroclaw_qwen.log
```

- Co 500 budynków przebieg wypisuje postęp.
- **Wznawianie:** każda odpowiedź modelu trafia od razu do `wyniki/eksperymenty.sqlite`. Po awarii uruchom to samo polecenie:
  gotowe odpowiedzi przyjdą z bazy w milisekundach, a model dostanie tylko brakujące. Nie zmieniaj w tym czasie promptów ani
  kodu wycinków, bo zmienią się klucze i model zacznie od nowa.
- Wynik: `wyniki/eksperymenty/wroclaw_qwen.csv` (jeden wiersz na budynek) oraz `__dialog.csv` i `__bilans.csv` z pętli.

## 7. Ocena

```bash
uv run python -m agenci.ewaluacja          # kwadraty NSP 2021 (przed pętlą)
uv run python -m agenci.ewaluacja --srlm   # rejony SRLM: poziom, Spearman, WAPE; baseline i sam NSP dla porównania
```

SRLM nie wchodzi do żadnego promptu ani do pętli; oglądamy go tylko tutaj, raz, na końcu.
