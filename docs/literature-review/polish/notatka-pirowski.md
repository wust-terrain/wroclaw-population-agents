# Pirowski i współautorzy: dasymetryczna estymacja populacji z BDOT10k

Notatka pogłębiona do `przeglad-literatury.md`, sekcja 1.1.

## Co faktycznie przeczytano

| Praca | Zakres lektury |
|---|---|
| **Pirowski, Bartoś (2018)**, *Detailed mapping of the distribution of a city population based on information from the national database on buildings*, Geodetski vestnik 62(3), 458–471, [DOI](https://doi.org/10.15292/geodetski-vestnik.2018.03.458-471), [PDF](https://www.geodetski-vestnik.com/arhiv/62/3/gv62-3_pirowski.pdf) | **Cały tekst** (open access). Nazwisko w artykule pisane „Bartos". |
| **Pirowski, Szypuła (2024)**, *Dasymetric Population Mapping Using Building Data*, Annals of the AAG 114(5), 1001–1019, [DOI](https://doi.org/10.1080/24694452.2024.2313500) | **Tylko abstrakt** ([RePEc](https://ideas.repec.org/a/taf/raagxx/v114y2024i5p1001-1019.html)). Strony wydawcy zwracają 403, pełny tekst za paywallem, otwartej kopii nie znaleźliśmy. Potrzebny dostęp przez bibliotekę uczelni. |

Praca z 2018 r. jest bezpośrednim poprzednikiem pracy z 2024 r. (ten sam pierwszy autor, ten sam obszar badań i te same dane), a **ta sama liczba 2,88 oraz 37 m²/os. występuje w obu**. Opis wersji 2024 poniżej to tylko to, co mówi abstrakt, plus ostrożne wnioskowanie z 2018.

## Korekta wcześniejszego opisu

W `przeglad-literatury.md` napisałem, że najlepszy wariant z 2024 r. dał ok. 21,9% MAPE. To było błędne. Według abstraktu:

| Wariant (siatka 1 × 1 km) | MAPE | RMSE (osoby) |
|---|---|---|
| Baseline: tylko populacja jednostek urbanistycznych | 310,8% | 1476 |
| Dasymetria z objętości budynków mieszkalnych | 21,9% | 632 |
| **Najlepszy wariant** (RMSE minimalne): 2,88 os. na dom jednorodzinny, 37,1 m²/os. dla wielorodzinnych | **19,2%** | **556** |

Abstrakt nie mówi, na jakich danych liczono te błędy (czy to niezależna siatka, czy dane, z których wzięto populację).

---

## Pirowski, Bartoś (2018): szczegóły

### Problem i dane
- **Obszar:** Kraków (326,8 km², 758 334 zarejestrowanych mieszkańców w 2012 r.), 18 dzielnic, **141 jednostek urbanistycznych (j.u.)**. To najlepsze publicznie dostępne statystyki dla Krakowa, publikowane przez urząd miasta.
- **Budynki:** **BDOT10k z 2011 r.** (błąd położenia RMSE 1,3 m). Używane atrybuty: funkcja ogólna i szczegółowa, powierzchnia zabudowy, liczba kondygnacji. Do analizy przyjęto budynki jednorodzinne, wielorodzinne i wielomieszkaniowe (te ostatnie nie są opisane szerzej).
- **Założenie:** populacja jest proporcjonalna do powierzchni mieszkalnej budynku, liczonej jako *powierzchnia zabudowy × liczba kondygnacji* (model populacji nocnej).
- **Terminologia:** *zmienna ograniczająca* (gdzie ludzie mogą mieszkać) to tu lokalizacja budynków mieszkalnych z BDOT. *Zmienne wiążące* to typ budynku i położenie.

### Metoda
1. Globalnie liczy się średnią powierzchnię na mieszkańca: **Av = Σ(kondygnacje × powierzchnia zabudowy) / Σ populacji 141 j.u.** (wzór 1).
2. Populację j.u. szacuje się jako suma powierzchni / Av (wzór 2).
3. Współczynnik korekty **K(j.u.) = rzeczywista / szacowana** (wzór 3) przywraca sumę w każdej j.u. (warunek Toblera). Populacja budynku = jego powierzchnia / Av × K (wzór 4).
4. Av dobiera się **minimalizując sumę kwadratów odchyleń δ po 141 j.u.** (wzory 5–6), czyli metodą najmniejszych kwadratów. Jest to „powierzchniowo ważona metoda korelacji" znana z prac na Corine Land Cover i Urban Atlas.
5. Wynik końcowy: populacja zapisana jako atrybut każdego budynku wektorowego, potem raster 5 m.

Autorzy zwracają uwagę, że **bez współczynnika K** otrzymuje się mapę zgodną z sumą miasta, ale nie z j.u. Odchylenia na poziomie j.u. służą wtedy jako miara wiarygodności wariantu, gdy brak niezależnych danych.

### Warianty i wyniki (tabele 1–3 z pracy)

Błędy liczone względem populacji j.u., **przed** zastosowaniem K.

| Wariant | Segmentacja budynków | Parametry Av | R² | MPE | MAPE |
|---|---|---|---|---|---|
| 1 | brak, jedno Av | 41,14 m²/os. | 82,7% | 33,8% | 47,7% |
| **2** | jednorodzinne / wielorodzinne | 84,21 / 37,08 | 84,8% | 5,4% | 30,7% |
| 3 | stała liczba osób na dom jednorodzinny | **2,88 os.** / 37,08 | 85,0% | 10,3% | **28,4%** |
| 4 | jw. + wielorodzinne ≤ V kondygnacji i > V | 81,85 / 56,76 / 22,88 | 88,7% | 2,0% | 31,4% |
| 2a, 3a, 4a | jak 2, 3, 4, osobno w każdej z 18 dzielnic | patrz niżej | 98,5–98,9% | 2,5–5,6% | 16,2–18,8% |
| **2b** | jak 2, ale j.u. pogrupowane wg średniej powierzchni na osobę (4 klasy) | 28→103 m²/os. zależnie od klasy | 97,2% | 2,1% | **9,9%** |
| 3b, 4b | analogicznie | | 97,1 / 97,5% | 6,4 / 1,5% | 13,9 / 10,2% |

Wnioski autorów:
- Samo wydzielenie domów jednorodzinnych zmniejsza MAPE z 48% do 31%, a MPE z 34% do 5%. Dla domów jednorodzinnych potrzeba około **dwa razy więcej metrów na osobę** niż dla wielorodzinnych.
- Av = 41 m²/os. jest dużo wyższe niż w spisie 2011 (**23,8 m²/os.**). Autorzy tłumaczą to powierzchniami usługowymi, handlowymi i wspólnymi (klatki schodowe).
- Domy jednorodzinne: powierzchnia słabo koreluje z liczbą mieszkańców, więc stała liczba osób (wariant 3) daje podobny wynik jak dzielenie przez powierzchnię.
- Podział dzielnicowy (2a–4a) poprawia wynik globalny, ale **dla kilku dzielnic parametry wychodzą błędne, nawet ujemne** (np. −159 w Mistrzejowicach). Przy średnio ok. 8 j.u. na dzielnicę optymalizacja jest niestabilna.
- Wariant 4 wyodrębnia wieżowce (22,9 m²/os.: małe pokoje, gęsto zasiedlone bloki z lat 70–80, brak lokali usługowych) i odróżnia je od kamienic w centrum (duże mieszkania, dużo lokali usługowych).
- Autorzy uznają **warianty 2 i 2b za najlepszy kompromis** między błędem a wiarygodnością. Dalsze podziały zwiększają ryzyko *ekwifinalności* (różne zestawy parametrów dają podobny wynik, więc dobry dopasowany wynik nie dowodzi poprawnego rozkładu wewnątrz j.u.).
- Miarą najbardziej użyteczną jest MAPE. RMSE zdominowują nieliczne j.u. o dużej populacji, a R² jest mało czuły.

### Ograniczenia, które wskazują sami autorzy
- **Brak niezależnej walidacji.** Parametry dopasowano do tych samych 141 j.u., na których liczy się błąd. Autorzy piszą wprost, że nie wiadomo, czy wariant z mniejszym błędem na j.u. lepiej odwzorowuje rozkład *wewnątrz* j.u. Planują zdobyć dodatkowe dane referencyjne.
- **Niejednorodna zabudowa:** nie rozwiązano problemu różnej ilości powierzchni niemieszkalnej w budynkach wielorodzinnych. Parter usługowy ma inne znaczenie w niskim, a inne w wysokim budynku. Autorzy piszą, że jedyną skuteczną drogą byłaby **informacja o tym w bazie budynków**.
- Wyniki mogą nie przenosić się na tereny wiejskie i małe miasta. Spis ma bardzo zróżnicowane jednostki.
- Dane BDOT z 2011 r., populacja z 2012 r.

---

## Pirowski, Szypuła (2024): co wiadomo z abstraktu

- Obszar: jednostki urbanistyczne Krakowa. Populację przeliczono na nowe jednostki **ważeniem powierzchniowym**.
- Zmienna ograniczająca: lokalizacja budynków mieszkalnych. Zmienna wiążąca: **łączna powierzchnia użytkowa = powierzchnia zabudowy × liczba kondygnacji**. Atrybuty: położenie, kubatura, funkcja.
- Testowano dodatkowe zmienne wiążące (typ i położenie budynku) oraz różne sposoby wyznaczania powierzchni dla typów budynków, co dało **19 map populacji**. Najlepsza segmentacja: **jednorodzinne vs wielorodzinne**, jak w 2018.
- Wyniki: tabela powyżej.

Czego nie wiemy bez pełnego tekstu: rok danych populacyjnych, użyte klasy BDOT10k, skąd pochodzi „prawda" dla siatki 1 km (to kluczowe dla oceny błędu 19,2%), liczba komórek, wyniki wszystkich 19 wariantów, ograniczenia.

---

## Co z tego wynika dla naszego projektu

1. **Dobry, konkretny baseline klasyczny.** Wariant 2 (84 / 37 m²/os.) lub wariant 3 (2,88 os. na dom + 37 m²/os.) można zaimplementować bez modelu. Proponuję dodać go obok `objetosc` i `objetosc_bdot` jako punkt odniesienia „literaturowy". Wartości są dopasowane do Krakowa 2012, więc dla Wrocławia trzeba je albo przyjąć jako prior, albo skalibrować.
2. **Nasz agent bilansujący odpowiada współczynnikowi K(j.u.).** Różnica: u nich K to mnożnik stały na jednostkę, a u nas rozmowa agentów. Tu jest naturalne pytanie badawcze H2: czy agent robi coś więcej niż mnożnik? Mnożnik powinien być **dodatkowym baseline'em dla L3**, bo spełnia warunek Toblera i kosztuje zero.
3. **Luka, którą wskazują sami autorzy, to nasza H1.** Brakuje informacji o parterze usługowym i udziale powierzchni niemieszkalnej. Obraz (fasady i widoki ukośne) może to dać: witryny, szyldy, wysokość parteru. Pasuje do pól `udział mieszkalny` w karcie budynku. To jest dobre uzasadnienie dla S2 względem S0.
4. **Ryzyko ekwifinalności i przeuczenia.** Ich podział dzielnicowy dał ujemne powierzchnie, bo parametrów jest za dużo względem jednostek referencyjnych. U nas rubryka gęstości (L2) i kalibracja na sumach NSP mają tę samą słabość. Warto ograniczyć liczbę parametrów i testować na niezależnych danych (MPWiK, obwody wyborcze).
5. **Metryki.** MAPE jest czytelne, ale przy małych jednostkach niestabilne. Można równolegle raportować WAPE (u nas już planowane) oraz Spearmana. Autorzy sami ostrzegają przed RMSE przy bardzo zróżnicowanych jednostkach.
6. **Dane.** Używają BDOT10k jako jedynego źródła atrybutów budynku (funkcja, kondygnacje, powierzchnia), czyli dokładnie naszego S0. Pokrycie kondygnacji w BDOT10k dla Wrocławia mamy w notebooku (slajd z pokryciem danych) i warto je zestawić z ich założeniami.

## Do zrobienia
- Uzyskać pełny tekst Pirowski i Szypuła (2024) przez bibliotekę lub od autorów (AGH). Do przeczytania najpierw: skąd pochodzi „prawda" dla siatki 1 km oraz tabela wszystkich 19 wariantów.
- Przeczytać Całka, Bielecka, Zdunkiewicz (2016) *Redistribution population data across a regular spatial grid according to buildings characteristics*, Geodesy and Cartography 65(2), 149–162 (cytowana w 2018 jako punkt wyjścia: błędy −10% do +25% przy gminach).
- Wspomniane w 2018 prace do sprawdzenia: Bajat i in. (2013), podział budynków wg liczby kondygnacji; Lwin, Murayama (2009), populacja z obrysów; Ural i in. (2011), *Building population mapping with aerial imagery and GIS data* (obrazy lotnicze, najbliższe naszemu H1).
