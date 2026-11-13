# wroclaw-population-agents

Szacujemy, ile osób naprawdę mieszka w każdym budynku we Wrocławiu. Liczby trafią do modelu ruchu, a spis GUS podaje ludność tylko w kwadratach 125 × 125 m i tylko osoby zameldowane.

Model widzący obrazy (VLM), czyli świadek, ogląda budynek na zdjęciach lotniczych z 4 stron świata i czyta jego rekord z BDOT10k. Liczbę mieszkańców liczy wzór ze stałych z literatury, a świadek doważa go dwoma mnożnikami: udziałem mieszkalnym i gęstością. Drugi model, agent bilansujący, porównuje sumy ze spisem NSP 2021 i może dopytać świadka, a trzeci, szperacz, szuka w internecie liczby miejsc albo mieszkań dla największych budynków.

Przebieg testowy to 3 arkusze ortofotomapy wokół pl. Grunwaldzkiego (680 budynków) na tanim modelu Claude Haiku; cały potok krok po kroku, z rysunkami i wynikiem tego przebiegu, pokazuje `notebooks/proof_of_concept.ipynb`. Docelowo cały Wrocław (826 arkuszy, ok. 70 tys. budynków) przejdzie przez otwarty Qwen3.8-27B na własnym serwerze (`docs/serwer.md`), a wynik ocenimy raz, na końcu, na SRLM, czyli szacowanej rzeczywistej liczbie mieszkańców w 375 rejonach.

| Gdzie | Co |
| --- | --- |
| `notebooks/proof_of_concept.ipynb` | cały potok na 3 arkuszach: dane, zdjęcia, LiDAR, fasady, świadek, pętla, szperacz, rejony SRLM i walidacja |
| `docs/architektura.md` | agenci, pętla, dane w kodzie, gdzie co jest w `src/` |
| `docs/rubryka.md` | skąd są stałe rubryki (Pirowski i Bartos 2018) |
| `docs/serwer.md` | przebieg na całym mieście na serwerze z GPU |
| `docs/odkrycia.md` | dziennik odkryć i problemów po drodze, ze zdjęciami (materiał na artykuł blogowy) |
| `src/agenci/`, `src/ortofoto/` | kod i pełne prompty |
| `eksperymenty/*.toml` | konfiguracje przebiegów |
| `paper/` | artykuł na kurs (ACL) |

## Instalacja i dane

Python 3.12+: `uv sync` albo `pip install -e .` (wtedy bez `uv run`).

Arkusze ortofotomapy pobiera `uv run python -m ortofoto.pobierz <godło> ...` (np. `6.148.12.04.2`; `--srlm` pobiera cały Wrocław). Ręcznie trzeba pobrać BDOT10k z [geoportalu Dolnego Śląska](https://geoportal.dolnyslask.pl/imap/#gpmap=gp103), `Grid_125_XLS.zip` z [ATOM GRID w GUS](https://geo.stat.gov.pl/atom-web/atom/GRID?spatial_dataset_identifier_code=GRID_2021_125m_xls&spatial_dataset_identifier_namespace=GRID) i SRLM (załącznik raportu UWr dla UMW w BIP UMW), rozpakować i ułożyć tak, bez zmiany nazw:

```text
data/*_<godło>_{N,E,S,W}.tif                    ok. 80 MB każdy
data/*/BDOT10K/PL.PZGiK.337.0264__OT_BUBD_A.xml  powiat 0264, ok. 320 MB
data/populacja/Grid_125_{1,2}.xlsx
data/SRLM/SRLM_Wroclaw_20221231.shp              i pozostałe pliki shapefile
```

Wysokość z LiDAR-u i punkty adresowe OSM kod pobiera sam przy pierwszym uruchomieniu do `data/kafle/`.

## Użycie

Jeden plik `eksperymenty/*.toml` to jeden przebieg. Pole `estymator` wybiera wariant: `objetosc_bdot` to baseline bez modelu (objętość budynków mieszkalnych i eksploatowanych według BDOT10k), `wzor` to świadek i wzór, a `petla` dodaje pętlę ze spisem.

```toml
estymator = "petla"
szukaj = true                     # szperacz dla największych budynków
model = "claude-haiku-5-5"        # albo np. "Qwen/Qwen3.8-27B" przez vLLM
arkusze = ["6.148.12.04.2"]       # bez tego pola: wszystkie arkusze z data/
```

```bash
uv run python -m agenci.eksperyment eksperymenty/arkusze_haiku.toml --na-sucho  # bez API i zapisu: test i wycena
ANTHROPIC_API_KEY=... uv run python -m agenci.eksperyment eksperymenty/arkusze_haiku.toml
uv run python -m agenci.ewaluacja   # ocena na SRLM
uv run pytest
```

Wyniki trafiają do `wyniki/eksperymenty/`: `<przebieg>.csv` (jeden wiersz na budynek), `__dialog.csv` (rozmowa agentów), `__bilans.csv` (kwadraty po rundach). Odpowiedzi modeli zostają w `wyniki/eksperymenty.sqlite`, więc powtórka jest darmowa, chyba że zmieni się prompt. Odpowiedź bez poprawnego JSON-a nie trafia do pamięci, a klient ponawia ją do 5 razy; gdy świadek mimo to nie odpowie, budynek dostaje wynik z samej rubryki i rekordu (`zapasowy = True`). Gotowe budynki świadek dopisuje na bieżąco do `<przebieg>.czesc.csv`, więc przerwany przebieg wznawia się bez ponownego wycinania zdjęć. Katalogu `wyniki/` nie ma w gicie.

## Jak wyglądają dane

| Źródło | Co to jest | Czego używamy |
| --- | --- | --- |
| Ortofotomapa skośna (GUGiK, nalot 2025) | ten sam teren sfotografowany pod kątem z 4 kierunków (N, E, S, W), piksel 5 cm, arkusz 800 × 500 m | zdjęcia dla świadka |
| BDOT10k | państwowa baza budynków | obrys (stąd powierzchnia), funkcja, kondygnacje, stan |
| NMPT i NMT (GUGiK) | wysokość powierzchni z dachami i samego terenu ze skaningu laserowego (LiDAR), piksel 0,5 m i 1 m | wysokość budynku |
| Punkty adresowe OSM | adresy z importu państwowego rejestru | adres dla szperacza |
| NSP 2021 | spis powszechny: osoby przypisane do adresów, zsumowane w kwadratach 125 × 125 m | sygnał dla agenta bilansującego |
| SRLM | szacowana rzeczywista liczba mieszkańców w 375 rejonach, koniec 2022 (raport UWr dla UMW) | tylko ocena na końcu |

Zdjęcia mają współrzędne, więc obrys z BDOT10k da się na nie nałożyć. Podstawa budynku leży na swoim miejscu, a dach jest przesunięty od kamery o 0,96 × wysokość; między nimi widać ścianę. Z każdego kierunku świadek dostaje widok całego budynku i fasadę wyprostowaną do prostokąta. Budynki przy krawędzi obszaru, których zdjęcia nie obejmują w całości, dostają mniej widoków albo sam rekord.

## Jeden budynek od początku do końca

Prawdziwy przebieg `arkusze_haiku` (Claude Haiku) dla akademika przy Piastowskiej 1. Świadek widzi typowy akademik i zostawia oba mnożniki na 1, więc wzór daje 378 osób. Spis ma w tym kwadracie 33 osoby, kwadrat dostaje flagę, a agent bilansujący przypisuje nadwyżkę stałej dla zamieszkania zbiorowego i o budynek nie pyta. Szperacz znajduje na stronie uczelni 802 miejsca dla obu segmentów akademika, z których ten dostaje 674 według powierzchni brutto.

![Schemat blokowy jednego budynku, od rekordu BDOT10k do wyniku](docs/przyklad_budynku.png)

Odpowiedzi modeli są dosłowne, a prompty, które dostały, skrócone.

## Wzór i rubryka

```text
dom:                      2,88 osoby × udział × gęstość
wielorodzinny, zbiorowy:  obrys × kondygnacje × udział × gęstość / m² na osobę
```

Stałe są z literatury i siedzą w `src/agenci/estymatory.py`. Obrys × kondygnacje z BDOT10k to powierzchnia brutto. Udział i gęstość daje świadek; oba równe 1 znaczą „typowy budynek tej klasy”.

| Klasa | Wartość w kodzie | Na 100 m² | Źródło |
| --- | --- | --- | --- |
| dom | 2,88 osoby na budynek | | [Pirowski i Bartos 2018](https://doi.org/10.15292/geodetski-vestnik.2018.03.458-471), tab. 1, wariant 3; te same liczby w [Pirowski i Szypuła 2024](https://doi.org/10.1080/24694452.2024.2313500) |
| budynek wielorodzinny | 37,08 m² na osobę | 2,70 osoby | jak wyżej |
| zamieszkanie zbiorowe | 31 m² na miejsce | 3,23 osoby | [College Housing Report 2014](http://www.mahlum.com/pdf/CPM2014CollegeHousingReport%281%29.pdf), tab. 1: mediana 333,3 stopy² z 52 akademików w USA |

Pracy z takimi liczbami dla Wrocławia nie znaleźliśmy, więc bierzemy Kraków: Pirowski i Bartos liczą z tej samej bazy BDOT10k i z tą samą definicją powierzchni co my, a mieszkania w obu miastach są podobne (GUS, koniec 2024: 34,6 m² użytkowych na osobę i 1,71 osoby na mieszkanie we Wrocławiu, 33,4 m² i 1,73 w Krakowie). Stałą 37,08 m² dopasowano do zameldowanych mieszkańców Krakowa i liczono na całej powierzchni budynków mieszkalnych, razem z klatkami i lokalami usługowymi w parterach (`docs/rubryka.md`).

Dla akademików polskiego źródła nie znaleźliśmy; liczba pochodzi z ankiety branżowego pisma z USA, a nasza klasa obejmuje też klasztory i domy opieki. Dla porównania [Dom Studencki nr 7 UW](https://www.uw.edu.pl/standard-domu-studenckiego-nr-7-uw/) ma prawie 13 000 m² i ponad 380 miejsc, czyli ok. 34 m² na miejsce.

## Co daje świadek

Świadek dostaje widoki i fasady budynku, rekord z BDOT10k i to, ile osób da wzór dla klasy z rekordu przy obu mnożnikach równych 1. Sam liczby mieszkańców nie podaje. Odpowiada w JSON o stałych polach, w tej kolejności, żeby najpierw opisał, co widzi, a potem podał liczby:

| Pole | Co znaczy | Jak wchodzi do wzoru |
| --- | --- | --- |
| `uzasadnienie` | co widać na zdjęciach (witryny, balkony, okna, wejścia) i skąd mnożniki | nie wchodzi |
| `widac_mieszkania` | czy widać ślady, że ktoś tu mieszka: balkony z rzeczami, pranie, różne zasłony i rolety, kwiaty, anteny satelitarne | budynek niemieszkalny w BDOT10k dostaje mieszkańców tylko przy `true` i pewności od 0,6 |
| `typ` | kamienica, blok PRL, blok nowy, dom, szeregowiec, zbiorowy, usługi, przemysł, garaż, inny | wybiera klasę rubryki; usługi, przemysł i garaż dają 0 |
| `stan` | użytkowany, w budowie, pustostan | inny niż użytkowany daje 0 |
| `udzial_mieszkalny` | jaka część budynku to mieszkania w porównaniu z typowym budynkiem tej klasy, od 0 do 1 | mnoży wynik |
| `gestosc` | ile razy gęściej albo rzadziej niż typowo mieszkają tu ludzie, od 0,3 do 3 | mnoży wynik |
| `pewnosc` | od 0 do 1 | próg dla budynków niemieszkalnych w BDOT10k; czyta ją też agent bilansujący |

Udział mówi, gdzie są mieszkania: zwykły sklep w parterze to wciąż udział 1, bo stała już go obejmuje; obniża się go tylko wtedy, gdy całe piętra powyżej parteru wyglądają na niemieszkalne, a reklamy, banery i murale nie są powodem. Gęstość mówi, jak gęsto mieszkają ludzie: więcej niż 1 przy mikrokawalerkach, pokojach na wynajem czy hotelu pracowniczym, mniej przy dużych mieszkaniach, częściowo pustym budynku albo małej wspólnocie w dużym budynku (dom parafialny, klasztor). Dom z dwoma mieszkaniami ma gęstość 2. Prompt podaje świadkowi, gdzie w polskich miastach mieszka się gęściej (mikroapartamenty i kawalerki po 11–25 m², prywatne akademiki, hotele pracownicze) i rzadziej (duże mieszkania w kamienicach, pustostany), z cechami widocznymi z zewnątrz; źródła w `docs/rubryka.md`. Wynajmu pokoi studentom w zwykłych kamienicach z powietrza nie widać i świadek ma tego nie zgadywać.

Przy budynku, który BDOT10k uznaje za niemieszkalny (uczelnia, biuro, hotel), świadek przy niepewnym obrazie skłania się do połowicznych odpowiedzi („kamienica, udział 0,5”). Dlatego taki budynek dostaje mieszkańców tylko wtedy, gdy świadek widzi ślady mieszkań i jest ich pewny co najmniej w 0,6 (`PROG_PEWNOSCI` w `estymatory.py`, do ustawienia po testach). Gdy obraz wyraźnie przeczy rekordowi, świadek wybiera inny typ i tym samym inną klasę rubryki. Kondygnacje bierzemy tylko z BDOT10k, bo mają je wszystkie budynki mieszkalne.

## Wysokość i dach na zdjęciu

BDOT10k nie ma pola wysokości. Bierzemy ją ze skaningu laserowego GUGiK: mediana NMPT w obrysie budynku minus teren z NMT. Budynek, którego skaning jeszcze nie widział, dostaje 3,3 m × kondygnacje + 2 m. Dach leży na zdjęciu o 0,96 × wysokość od podstawy, w stronę od kamery; mnożnik to tangens odchylenia kamery od pionu (ok. 44°), wyznaczony z dopasowania tekstury dachów między czterema widokami na 61 budynkach. Wysokość służy do rysowania dachu i wycinania fasad, a do wzoru wchodzi tylko przy braku kondygnacji w BDOT10k.

## Jak działa pętla

Pętla to eksperyment z dodatkowym sygnałem: spisem NSP 2021. Spis liczy osoby przypisane do adresów w 2021 roku, a my szacujemy, ile osób naprawdę mieszka w budynku dziś. We Wrocławiu wiele osób mieszka bez meldunku (studenci, pracownicy, nowe osiedla), więc spis jest niemal na pewno niższy od naszego szacunku. Agent dostaje to w prompcie wprost i nie traktuje spisu jako wartości docelowej; nadwyżka przy akademikach i nowych osiedlach jest spodziewana, a bardziej podejrzany jest szacunek wyraźnie niższy od spisu.

Mieszkańców budynku dzielimy między kwadraty spisu według tego, jaka część obrysu leży w każdym, i porównujemy tylko kwadraty, w których szacunek ma każdy budynek mieszkalny. Kwadrat dostaje flagę, gdy suma szacunków różni się od spisu ponad 1,5 raza w dowolną stronę i o co najmniej 25 osób. Pętla rusza przy fladze albo gdy świadek przeczy BDOT10k, np. pisze, że nikt nie mieszka w budynku mieszkalnym.

Agent nie widzi zdjęć. Czyta opisy budynków z takich kwadratów, stawia diagnozę i wybiera, o co zapytać świadka (`typ`, `stan`, `udzial_mieszkalny` albo `gestosc`). Liczb nie zmienia, a diagnozy trafiają tylko do zapisu. Filtr w kodzie przepuszcza jedno pytanie na budynek w rundzie, bez powtórek, najwyżej 20 z jednego wywołania agenta, i wycina z pytań cyfry, żeby świadek nie poznał liczb ze spisu. Świadek zmienia zdanie tylko wtedy, gdy uzasadnia to obraz, a wzór liczy wszystko od nowa. Rundy są najwyżej 2 (Du i in. 2024). Stan sprzed pętli to kolumna `mieszkancy_r0`. Progi i limity to wartości na start, do ustalenia z ekspertami.

## Szperacz

Większość ludzi siedzi w kilku dużych budynkach. Przy `szukaj = true` model z wyszukiwarką internetową dostaje adresy i rekord wszystkich akademików, internatów i budynków hotelowych z BDOT10k, a do tego najwyżej 4 innych budynków z każdego arkusza: najpierw zamieszkania zbiorowego, potem tych z największym szacunkiem. Hotele sprawdzamy, bo pod tą funkcją bywają prywatne akademiki i mikroapartamenty na wynajem długoterminowy: na przykład Starter przy wybrzeżu Pasteura 18 (dawny Hotel Asystenta UWr) ma 149 kawalerek po 11–27 m², a w BDOT10k jest hotelem. Zwykły hotel dla turystów szperacz zgłasza jako brak, a kawalerkę liczy jako jedno miejsce. Szuka liczby miejsc albo mieszkań podanej dla tego konkretnego budynku, najwyżej 2 zapytaniami. Liczba miejsc zastępuje szacunek, a liczbę mieszkań mnożymy przez 1,71 osoby (GUS, Wrocław, 2024). Bez źródła zostaje wynik wzoru (`mieszkancy_wzor`); stronę i zdanie z liczbą zapisujemy w `zrodlo` i `cytat`, a trafienia trzeba przejrzeć.

Ewidencja dzieli jeden budynek zamieszkania zbiorowego, np. akademik, na kilka segmentów, a liczba miejsc w sieci dotyczy całości. Stykające się segmenty z tą samą funkcją w BDOT10k szukamy więc razem, a znalezioną liczbę dzielimy między nie według powierzchni brutto. Gdy grupa obejmuje kilka akademików spiętych łącznikami (jak przy pl. Grunwaldzkim 26 i 28 i Grunwaldzkiej 59), szperacz podaje sumę ich miejsc, ale tylko gdy znajdzie liczbę dla każdego z nich. Grupy bez własnego punktu adresowego nie szukamy, bo dostałaby adres sąsiada i policzyła jego miejsca drugi raz. Gdy szperacz nic nie znajdzie, zostaje wynik wzoru.

## Co sprawdzamy

Dla pojedynczego budynku nie mamy prawdziwej liczby mieszkańców, więc sumujemy szacunki w rejonach i porównujemy z SRLM. Raport Uniwersytetu Wrocławskiego dla UMW liczy rzeczywistą liczbę mieszkańców z meldunków, lokali i miejsc w akademikach, także niezameldowanych; dla miasta wychodzi 893 506 osób na koniec 2022 roku, o ok. 33% więcej niż w spisie. SRLM nie widzi żaden agent ani prompt i oceniamy na nim raz, po przebiegu na całym mieście.

Budynek przy granicy rejonów dzieli się według obrysu. Oceniamy rejony, których co najmniej 95% powierzchni mieszkalnej z BDOT10k ma szacunek. Miary:

- poziom: suma szacunków / suma SRLM, czyli czy szacujemy tylu ludzi, ilu jest naprawdę,
- Spearman: czy kolejność rejonów od najmniej do najbardziej zaludnionego się zgadza (1 to ta sama kolejność),
- WAPE: jaką część ludzi trzeba by przesunąć między rejonami, gdyby suma szacunków równała się sumie SRLM (0 to ten sam rozkład),
- rejony z największym i najmniejszym stosunkiem szacunku do SRLM: z nich wyciągamy wnioski, gdzie i dlaczego model się rozjeżdża.

Punktem odniesienia jest sam spis rozłożony na rejony oraz baseline `objetosc_bdot`, na który rozkładamy ludność ze spisu. SRLM jest na koniec 2022 roku, a zdjęcia i BDOT10k z 2025, więc w rejonach z osiedlami oddanymi później spodziewamy się szacunku wyższego od SRLM. Możliwe wspólne źródło: SRLM liczy akademiki jako 95% miejsc z wykazów w internecie, a szperacz szuka liczby miejsc w tych samych wykazach, więc w rejonach z akademikami zgodność może częściowo wynikać ze wspólnych danych.
