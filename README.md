# wroclaw-population-agents

Szacujemy, ile osób mieszka w każdym budynku we Wrocławiu. Zakładamy, że model ruchu będzie dokładniejszy z takim wyliczeniem, a spis GUS podaje ludność tylko w kwadratach 125 × 125 m.

Model widzący obrazy (VLM), czyli świadek, opisuje budynek ze zdjęć lotniczych z 4 stron świata, a liczbę mieszkańców liczy z tego wzór ze stałymi z literatury. Drugi model, agent bilansujący, dostaje rozjazdy ze spisem i dopytuje świadka.

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

Jeden plik `eksperymenty/*.toml` to jeden przebieg. Pole `estymator` wybiera wariant: `objetosc` to powierzchnia × wysokość, `objetosc_bdot` to samo, ale 0 dla niemieszkalnych i nieużytkowanych, `wzor` to świadek i wzór, a `petla` dodaje pętlę.

```toml
estymator = "petla"
z_rekordem = true  # czy modele widzą rekord BDOT10k
model = "claude-haiku-5-5"
[budynki]
wszystkie = true   # albo kwadraty = 3, albo liczba = 40
```

```bash
uv run python -m agenci.eksperyment eksperymenty/arkusz_haiku.toml --na-sucho  # bez API i zapisu
ANTHROPIC_API_KEY=... uv run python -m agenci.eksperyment eksperymenty/arkusz_haiku.toml
uv run python -m agenci.ewaluacja   # porównanie przebiegów
uv run pytest
```

Wyniki trafiają do `wyniki/eksperymenty/`: `<przebieg>.csv` (jeden wiersz na budynek), `__dialog.csv` (rozmowa agentów), `__bilans.csv` (kwadraty po rundach). Odpowiedzi modeli zostają w `wyniki/eksperymenty.sqlite`, więc powtórka jest darmowa, chyba że zmieni się prompt. Katalogu `wyniki/` nie ma w gicie.

## Jak wyglądają dane

| Źródło | Co to jest | Czego używamy |
| --- | --- | --- |
| Ortofotomapa skośna | Cztery pliki TIF czyli cztery fotografie z kierunków N, S, W, E, piksel to 5 cm, jeden TIF to 500m x 800m | obrazy dla modelu |
| BDOT10k | Państwowa baza budynków z różnymi danymi o nich | obrys (stąd powierzchnia), funkcja, kondygnacje, stan |
| OpenStreetMap | Otwarta mapa | wysokość budynku, gdy jest |
| NSP 2021 | Spis powszechny, liczba osób w kwadracie 15m x 125m | gdy jest duża rozbieżność między spisem a sumą dla budynków w kwadracie to odpalamy agenta bilansującego |

Budynek należy do kwadratu, w którym leży jego środek. Kwadraty na brzegach się ucinają więc dopóki działamy na jednym arkuszu to te kwadraty których wszystkie budynki mieszkalne leżą na arkuszu.

Zdjęcia TIG mają współrzędne, więc obrys z BDOT10k da się na nie łatwo nałożyć. Model dostaje z tych zdjęć 4 fasady (czyli wycinki tych samych zdjęć ze ścianą wyprostowaną do prostokąta). Przy krawędzi arkusza 29 budynków ma 3 zdjęcia, a 30 nie ma żadnego i dostaje sam rekord.

## Jeden budynek od początku do końca

Prawdziwy przebieg modlei na Claude Haiku dla akademika przy pl. Grunwalldzkim Wzór daje 341 osób, a spis ma w tym kwadracie 33, więc kwadrat dostaje flagę i odpala się agent bilansujący - Agent dopytuje świadka, świadek potwierdza swój opis i wynik się nie zmienia.

![Schemat blokowy jednego budynku, od rekordu BDOT10k do wyniku 340,63 osoby](docs/przyklad_budynku.png)

Odpowiedzi modeli są dosłowne, a prompty które dostały skrócone.

### Wzór i rubryka

```text
dom:                      osoby_na_dom × udział
wielorodzinny, zbiorowy:  powierzchnia × kondygnacje × udział / m² na osobę
```

 Stałe tego ile ludzi mieszka średnio dla typu budynku bierzemy z literatury i hardocdujemy w `estymatory.py`. Powierzchnia to obrys × kondygnacje z BDOT10k.

| Klasa | Wartość w kodzie | Na 100 m² | Źródło |
| --- | --- | --- | --- |
| dom | 2,88 osoby na budynek | | [Pirowski i Bartos 2018](https://doi.org/10.15292/geodetski-vestnik.2018.03.458-471), tab. 1, wariant 3; te same liczby w [Pirowski i Szypuła 2024](https://doi.org/10.1080/24694452.2024.2313500) |
| budynek wielorodzinny | 37,08 m² na osobę | 2,70 osoby | jak wyżej |
| zamieszkanie zbiorowe | 31 m² na miejsce | 3,23 osoby | [College Housing Report 2014](http://www.mahlum.com/pdf/CPM2014CollegeHousingReport%281%29.pdf), tab. 1: mediana 333,3 stopy² z 52 akademików w USA |

Pracy z takimi liczbami dla samego Wrocławia nie znaleźliśmy, więc bierzemy Kraków. Pirowski i Bartos liczą z tej samej bazy BDOT10k i z tą samą definicją powierzchni co my, a mieszkania w obu miastach są podobne: GUS na koniec 2024 roku podaje 34,6 m² użytkowych na osobę i 1,71 osoby na mieszkanie we [Wrocławiu](https://www.polskawliczbach.pl/Wroclaw) oraz 33,4 m² i 1,73 osoby w [Krakowie](https://www.polskawliczbach.pl/Krakow). Różnica jest mała, więc pracujemy na tych stałych skoro nie mamy danych o zużyciu wody.

Dla akademików polskiego źródła nie znaleźliśmy, a liczba, którą wzieliśmy pochodzi z ankiety branżowego pisma z USA. Ponad połowa tamtych akademików ma też sale zajęciowe, a nasza klasa obejmuje też klasztory i domy opieki. Dla porównania [Dom Studencki nr 7 UW](https://www.uw.edu.pl/standard-domu-studenckiego-nr-7-uw/) ma prawie 13 000 m² i ponad 380 miejsc, czyli ok. 34 m² na miejsce, licząc z kondygnacją podziemną. TU MOŻNA WZIĄĆ POTEM STAŁĄ DLA ZABUDOWY RODZINNEJ

### Co daje świadek

Świadek to VLM i patrzy na otrzymane fasady i informacje o budynku z BDOT. Prompt każe mu odpowiedzieć w JSON o stałych polach, żeby potem to łądnie wczytać w kodzie. JSON ma `typ` który wybiera klasę rubryki (czyli dom, lub wielorodzinna, lub zamieszkanie zbiorowe) albo daje 0 (`uslugi`, `przemysl`, `garaz`), `udzial_mieszkalny` mnoży wynik (czyli np. tutaj damy udzial=0.8 bo na 1 pietrze z 5 nikt nie mieszka), a `stan` inny niż `uzytkowany` daje 0 (bo np. budynek jest zniszczony). Daje jescze `kondygnacje` czyli liczbe pięter, ale od VLM ierzemy je tylko wtedy gdy w BDOT10k ich ni ma (9 z 341 budynków) dla arkusza z Grnwaldu.

VLM dostaje powierzchnię i kondygnacje z BDOT10k.

W pilocie od świadka zależy praktycznie tylko udział mieszkalny. Klasa budynku zgadza się z BDOT10k w 332 z 341 budynków, stan to `uzytkowany` w 339, a udział wynosi od 0,8 do 0,95 w 243 z 248 budynków z szacunkiem powyżej zera.

### Wysokość i dach na zdjęciu

BDOT10k nie ma pola wysokości, tylko kondygnacje. Bierzemy więc tag `height` z OSM (45 budynków), inaczej 3,3 m × kondygnacje + 2 m (287), a bez kondygnacji 8 m (9). Te 3,3 m, 2 m i 8 m TUTAJ DO TYCH ZAŁOŻEŃ WYSOKOŚCI BUDYNKU TRZEBA LITERATURY ALBO JAKIŚ SOURCE NA WYSOKOŚĆ BUDYNKÓW WE WROCŁAWIU, LEPSZY OD TEJ HEURSYTYKI.

Dach leży na zdjęciu o 0,85 × wysokość od podstawy, w stronę od kamery. Mnożnik dobrany mądrą trygonometrią na budynkach z wysokością z OSM (`demo_ortofotomapa_skosna.ipynb`). To znaczy, że kamera była odchylona o ok. 40° od pionu przy robieniu zdjęć do ortofotomapy.

Znając tę trygonometrią możemy rysować obryss dachu i wycinać fasady. Wysokość liczy też baseline objętości, a do wzoru weszłaby tylko przy braku kondygnacji i w BDOT10k, i u świadka. W pilocie się to nie zdarzyło.

## Jak działa pętla

Kwadrat dostaje flagę, gdy szacunek po skalowaniu do spisu różni się od niego ponad 1,5 raza i o co najmniej 25 osób. To nasz próg, sprawdzony w symulacji. Pętla rusza przy fladze albo gdy świadek przeczy BDOT10k, np. pisze, że nikt nie mieszka w budynku mieszkalnym.

Agent nie widzi zdjęć. Czyta opisy takich budynków i wybiera, o co zapytać świadka. To jego jedyny wpływ na wynik, bo liczb nie zmienia, a diagnozy trafiają tylko do zapisu.

Filtr w kodzie przepuszcza pytania tylko o te budynki, jedno na budynek w rundzie, bez powtórek, najwyżej 20 (limit kosztu), i wycina z nich cyfry, żeby świadek nie poznał liczb ze spisu. Świadek ma zmienić zdanie tylko wtedy, gdy uzasadnia to obraz, a wzór liczy wszystko od nowa. Rundy są najwyżej 2 (Du i in. 2024).

W pilocie flagę ma 1 z 15 kwadratów, ten z przykładu. Agent zadał 2 pytania, filtr przepuścił oba, a świadek nie zmienił żadnej odpowiedzi, więc suma arkusza została 8855 osób. W rundzie 2 agent nie zapytał już o nic. Wynik końcowy to kolumna `mieszkancy`, a stan sprzed pętli to `mieszkancy_r0`.

## Co sprawdzamy

Dla pojedynczego budynku nie mamy prawdziwej liczby mieszkańców, więc sumy w kompletnych kwadratach porównujemy ze spisem. Rubryka nie pochodzi ze spisu, więc stan przed pętlą to ocena niezależna. Spearman mówi, czy kolejność kwadratów się zgadza, a WAPE, jaką część ludzi trzeba by przesunąć między kwadratami. Przed WAPE każdą serię skalujemy do sumy spisu, więc oceniamy rozkład i da się porównać objętość w m³ z osobami. Punktem odniesienia jest `objetosc_bdot`, bo działa bez modelu. Wariant jest lepszy, gdy przedział różnicy względem niej (bootstrap po kwadratach) nie obejmuje zera.

Opis budynku porównujemy z BDOT10k: F1 dla pytania "czy ktoś tu mieszka" i błąd kondygnacji. Ma to sens tylko przy `z_rekordem = false`, bo inaczej model widzi odpowiedź.

Agent w pętli widział sumy kwadratów, dlatego oceniamy `mieszkancy_r0`, choć wynikiem końcowym jest `mieszkancy`. Czy pętla pomaga, jeszcze nie wiemy: uczciwy test to zgodność z BDOT10k przed pętlą i po niej przy `z_rekordem = false`, a taki przebieg mamy tylko na 25 budynkach.

Pilot `arkusz_haiku` (rekord widoczny, 15 kwadratów, 0,28 USD): Haiku przed pętlą ma Spearmana 0,83 i WAPE 0,23, a objętość z BDOT10k 0,85 i 0,21. Różnica to -0,01 [-0,15; +0,12] w Spearmanie i +0,02 [-0,01; +0,08] w WAPE. Oba przedziały obejmują zero, więc przewagi nie mamy. Nie wiemy też, czy pomagają obrazy, bo świadka bez obrazów jeszcze nie ma.

Najbardziej odstaje kwadrat z przykładu: spis 33, Haiku po skalowaniu 289, objętość 199. Spis liczy miejsce zamieszkania, a nie pobyt, więc studenci w dużej części nie są przypisani do akademika. Bez tego kwadratu obie serie mają Spearmana ok. 0,82 i WAPE ok. 0,17.

Przed skalowaniem szacunek to 6 445 osób wobec 5 476 w spisie, czyli +18%. Gdyby nie mnożenie przez udział, byłoby 7 490, choć 37,08 m² liczono na całą powierzchnię budynków, razem z usługami na parterze. Na całe miasto sam BDOT10k z tą rubryką, bez udziału, daje ok. 864 tys. osób wobec 657 tys. w spisie na tych samych kwadratach. Nadwyżka nie musi być błędem: [Uniwersytet Wrocławski](https://uwr.edu.pl/en/our-scientists-counted-all-the-residents-of-wroclaw/) szacuje faktyczną liczbę mieszkańców na 893 506 na koniec 2022 roku.
