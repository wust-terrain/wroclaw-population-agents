# wroclaw-population-agents

Szacujemy, ile osób mieszka w każdym budynku we Wrocławiu. Zakładamy, że model ruchu będzie dokładniejszy z takim wyliczeniem a spis GUS podaje ludność tylko w kwadratach 125 × 125 m.

Model widzący obrazy (VLM) opisuje budynek ze zdjęć lotniczych z 4 stron świata, a liczbę mieszkańców liczy z tego wzór. Drugi model porównuje wyniki ze spisem i dopytuje pierwszego.

Działamy na jednym arkuszu ortofotomapy: 800 × 500 m, 341 budynków. Pilot na tanim modelu Claude Haiku pokazał, że kod działa, ale nie to, że szacunki są trafne. Docelowo system ma działać na otwartym modelu, np. Qwen, który uruchomimy jak będziemy mieć serwer. Architektura: `docs/architektura.md`, pełne prompty: `src/agenci/`, stan prac: `paper/population-estimation.tex`, wykresy: `notebooks/`.

## Instalacja i dane

Python 3.12+: `uv sync` albo `pip install -e .` (wtedy bez `uv run`).

Pobierz ortofotomapę z [geoportal.gov.pl](https://www.geoportal.gov.pl), BDOT10k z [geoportalu Dolnego Śląska](https://geoportal.dolnyslask.pl/imap/#gpmap=gp103), a `Grid_125_XLS.zip` z [ATOM GRID w GUS](https://geo.stat.gov.pl/atom-web/atom/GRID?spatial_dataset_identifier_code=GRID_2021_125m_xls&spatial_dataset_identifier_namespace=GRID), rozpakuj i ułóż tak, bez zmiany nazw:

```text
data/*_6.148.12.04.2_{N,E,S,W}.tif               ok. 80 MB każdy
data/*/BDOT10K/PL.PZGiK.337.0264__OT_BUBD_A.xml  powiat 0264, ok. 320 MB
data/populacja/Grid_125_{1,2}.xlsx
```

## Użycie

Jeden plik `eksperymenty/*.toml` to jeden przebieg. `objetosc` to powierzchnia × wysokość, `objetosc_bdot` to samo, ale 0 dla niemieszkalnych i nieużytkowanych, `wzor` to świadek i wzór, a `petla` dodaje pętlę.

```toml
estymator = "petla"
z_rekordem = true  # czy modele widzą rekord BDOT10k
model = "claude-haiku-5-5"
rubryka = "eksperymenty/rubryki/nsp2021_bez_arkusza.toml"  # albo "llm": agent rubryki
[budynki]
wszystkie = true   # albo kwadraty = 3, albo liczba = 40
```

```bash
uv run python -m agenci.eksperyment eksperymenty/arkusz_haiku.toml --na-sucho  # bez API i zapisu
ANTHROPIC_API_KEY=... uv run python -m agenci.eksperyment eksperymenty/arkusz_haiku.toml
uv run python -m agenci.ewaluacja   # porównanie przebiegów
uv run python -m agenci.kalibracja  # rubryka z NSP 2021
uv run pytest
```

Wyniki trafiają do `wyniki/eksperymenty/`: `<przebieg>.csv` (jeden wiersz na budynek), `__dialog.csv` (rozmowa agentów), `__bilans.csv` (kwadraty po rundach). Odpowiedzi modeli zostają w `wyniki/eksperymenty.sqlite`, więc powtórka jest darmowa, chyba że zmieni się prompt. Katalogu `wyniki/` nie ma w gicie.

## Jak wyglądają dane

| Źródło | Co to jest | Czego używamy |
| --- | --- | --- |
| Ortofotomapa skośna | Cztery pliki TIF: ten sam arkusz sfotografowany pod kątem z czterech stron, piksel 5 cm | obrazy dla modelu |
| BDOT10k, warstwa `OT_BUBD_A` | Państwowa baza budynków | obrys (stąd powierzchnia), funkcja, kondygnacje, stan |
| OpenStreetMap | Otwarta mapa, pobiera się sama | wysokość budynku, gdy jest |
| NSP 2021 | Spis powszechny: liczba osób w każdym zamieszkanym kwadracie | rubryka, flagi, ocena |

Budynek należy do kwadratu, w którym leży jego środek. Arkusz ucina kwadraty na brzegach, więc ze spisem porównujemy tylko 15 kompletnych, których wszystkie budynki mieszkalne leżą na arkuszu.

Zdjęcia mają współrzędne, więc obrys z BDOT10k da się na nie nałożyć. Zdjęcia z góry nie mamy, tylko skośne z 4 stron świata. Model dostaje te 4 zdjęcia i do 4 fasad, czyli wycinków tych samych zdjęć ze ścianą wyprostowaną do prostokąta. 29 budynków przy krawędzi arkusza ma 3 zdjęcia, a 30 nie ma żadnego i dostaje sam rekord.

## Jeden budynek od początku do końca

Prawdziwy przebieg `arkusz_haiku`. Wzór daje 73 osoby, kwadrat nie zgadza się ze spisem, agent dopytuje świadka, świadek potwierdza swój opis i wynik się nie zmienia.

![Schemat blokowy jednego budynku: rekord BDOT10k, 4 zdjęcia z obrysami, odpowiedź świadka, wzór dający 73,28 osoby, porównanie ze spisem, pytanie agenta i druga odpowiedź świadka](docs/przyklad_budynku.png)

Odpowiedzi modeli są dosłowne (`wyniki/eksperymenty.sqlite`), polecenia skrócone, a pełne są w `src/agenci/`.

### Co daje świadek

Świadek odpowiada w JSON o stałych polach, więc kod po prostu je czyta. Do wzoru wchodzą trzy z nich:

| Pole | Co robi we wzorze |
| --- | --- |
| `typ` | wybiera gęstość albo daje 0 (`uslugi`, `przemysl`, `garaz`) |
| `udzial_mieszkalny` | mnoży wynik |
| `stan` | inny niż `uzytkowany` daje 0 |

Powierzchnia jest zawsze z BDOT10k. Kondygnacje też, a od świadka tylko wtedy, gdy BDOT10k ich nie ma (9 z 341 budynków).

W pilocie świadek niewiele zmienia. Jego klasa budynku zgadza się z BDOT10k w 332 z 341 budynków, udział mieszkalny wynosi od 0,8 do 0,95 w 243 z 248 budynków z szacunkiem powyżej zera, a stan to `uzytkowany` w 339 z 341. Sam BDOT10k z tą samą rubryką, bez modelu, daje Spearmana 0,88 i WAPE 0,17, a ze świadkiem 0,89 i 0,16. Świadek widział rekord, więc mógł go przepisać: w przykładzie sam pisze, że liczbę kondygnacji przyjął z BDOT10k.

### Skąd są liczby

```text
dom:         osoby_na_dom × udział
mieszkania:  powierzchnia × kondygnacje × udział × gęstość / 100
```

Postać wzoru i klasy budynków są z literatury (Pirowski i Bartos 2018, Pirowski i Szypuła 2024). Liczby w rubryce są nasze: dopasowaliśmy je regresją do spisu. Każdy kwadrat NSP to jedno równanie:

```text
ludność = a × liczba domów + b × pow. niskich / 100 + c × pow. wysokich / 100 + d × pow. zbiorowych / 100
```

Powierzchnia to obrys × kondygnacje z BDOT10k. Kwadrat z 24 domami i 72 osobami sugeruje 3 osoby na dom. Regresja robi to samo na wszystkich kwadratach naraz, także mieszanych: dobiera a, b, c, d tak, żeby błąd był jak najmniejszy, a żadna liczba nie wyszła ujemna (NNLS, `kalibracja.py`).

| Liczba | Rubryka (regresja na NSP 2021) | Literatura |
| --- | --- | --- |
| a: osoby na dom | 3,21 | 2,88 |
| b: osoby na 100 m², do 5 kondygnacji | 2,05 | 2,70 |
| c: osoby na 100 m², powyżej 5 kondygnacji | 1,38 | 2,70 |
| d: osoby na 100 m², zamieszkanie zbiorowe | 0,22 | brak |

Literatura to Pirowski i Szypuła 2024: 2,88 osoby na dom i 37,1 m² na osobę w budynkach wielorodzinnych, czyli 2,70 na 100 m². Znamy z tej pracy tylko abstrakt. Pirowski i Bartos (2018) podają dla Krakowa 84 i 37 m² na osobę. Rubrykę może też podać LLM z własnej wiedzy (`rubryka = "llm"`).

Pozostałe liczby:

| Liczba | Wartość | Skąd | Do czego |
| --- | --- | --- | --- |
| wysokość | tag `height` z OSM (45 budynków), inaczej 3,3 m × kondygnacje + 2 m (287), a bez kondygnacji 8 m (9) | OSM, reszta to nasze założenie bez źródła | obrys dachu, fasady, baseline objętości |
| przesunięcie dachu | 0,85 × wysokość | dobrane na oko spośród 0,70, 0,85 i 1,00 na budynkach z wysokością z OSM (`demo_ortofotomapa_skosna.ipynb`) | obrys dachu, fasady |
| próg budynku wysokiego | 5 kondygnacji | Pirowski i Bartos 2018, wariant 4 | klasa we wzorze |
| flaga kwadratu | ponad 1,5 raza i co najmniej 25 osób | nasz próg sprawdzony w symulacji | pętla |
| rundy | 2 | Du i in. 2024 | pętla |
| pytania w rundzie | 20 | limit kosztu | pętla |

BDOT10k nie podaje wysokości, tylko liczbę kondygnacji. Wysokość i przesunięcie służą do rysowania i wycinania, do wzoru nie wchodzą.

## Jak działa pętla

Pętla rusza, gdy kwadrat ma flagę albo świadek przeczy BDOT10k, np. pisze, że nikt nie mieszka w budynku mieszkalnym. Agent bilansujący nie widzi zdjęć. Czyta opisy takich budynków i wybiera, o co zapytać świadka. Liczb nie zmienia, a jego diagnozy trafiają tylko do zapisu.

Filtr w kodzie przepuszcza pytania tylko o te budynki, jedno na budynek w rundzie, bez powtórek, najwyżej 20, i wycina z nich cyfry, żeby świadek nie poznał liczb ze spisu. Świadek odpowiada od nowa i ma zmienić zdanie tylko wtedy, gdy uzasadnia to obraz. Potem wzór liczy wszystko jeszcze raz. Rundy są najwyżej 2.

W pilocie agent zadał 8 pytań, a filtr przepuścił 7. Zmieniło się 5 odpowiedzi, a suma arkusza wzrosła z 5584 do 5618 osób. Budynek `2881C5D6-81A0` świadek najpierw uznał za usługi (0 osób), a po pytaniu za blok (13 osób). Wynik końcowy to kolumna `mieszkancy`, a stan sprzed pętli to `mieszkancy_r0`.

## Co sprawdzamy

Dla pojedynczego budynku nie mamy prawdziwej liczby mieszkańców, więc oceniamy pośrednio.

Sumy w kompletnych kwadratach porównujemy ze spisem. Spearman mówi, czy kolejność kwadratów się zgadza, a WAPE, jaką część ludzi trzeba by przesunąć między kwadratami. Przed WAPE każdą serię skalujemy do sumy spisu, więc oceniamy rozkład i da się porównać objętość w m³ z osobami. Punktem odniesienia jest `objetosc_bdot`, bo działa bez modelu. Wariant jest lepszy, gdy przedział różnicy względem niej (bootstrap po kwadratach) nie obejmuje zera.

Opis budynku porównujemy z BDOT10k: F1 dla pytania "czy ktoś tu mieszka" i błąd kondygnacji. Ma to sens tylko przy `z_rekordem = false`, bo inaczej model widzi odpowiedź.

Rubrykę dopasowujemy bez kwadratów arkusza, więc 15 kwadratów z oceny jest poza próbą. Agent w pętli widział jednak ich sumy, dlatego oceniamy `mieszkancy_r0`, choć wynikiem końcowym jest `mieszkancy`. Czy pętla pomaga, jeszcze nie wiemy: uczciwy test to zgodność z BDOT10k przed pętlą i po niej przy `z_rekordem = false`, a taki przebieg mamy tylko na 25 budynkach.

Pilot `arkusz_haiku` (rekord widoczny, 15 kwadratów, 0,29 USD): Haiku przed pętlą ma Spearmana 0,89 [0,64; 0,98] i WAPE 0,16, a objętość z BDOT10k 0,85 [0,52; 0,98] i 0,21. Różnica Haiku i objętości to +0,04 [-0,09; +0,23] w Spearmanie i -0,05 [-0,15; +0,04] w WAPE. Oba przedziały obejmują zero, a prawie cały zysk w WAPE to jeden kwadrat z akademikiem, więc przewagi nie mamy. Nie wiemy też, czy pomagają obrazy, bo świadka bez obrazów jeszcze nie ma.

Przed skalowaniem szacunek to 3 974 osoby wobec 5 476 w spisie. Część tej różnicy bierze się z mnożenia przez udział, bo gęstości z regresji zawierają już część niemieszkalną: z udziałem równym 1 byłoby 4 630 osób.
