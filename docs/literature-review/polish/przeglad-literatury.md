# Wstępny przegląd literatury

Wersja robocza na 4. zajęcia. Cel: rozeznać się, w co warto się wgłębić. Opisy są krótkie i oparte na abstraktach oraz streszczeniach z wyszukiwarki. Istnienie wszystkich pozycji, autorów, tytułów i numerów arXiv sprawdzono 2026-11-05 w API arXiv i Crossref. Pełne teksty przeczytano (w zakresie podanych liczb) dla: Science of Scaling, MAST, GenWorld, GeoLLM, Singapuru i Mozambiku oraz Pirowski, Bartoś (2018). Pozostałe liczby pochodzą ze streszczeń i trzeba je sprawdzić przed cytowaniem. Pozycje oznaczone ⚠ mają dodatkowe zastrzeżenie.

Skróty odnoszą się do projektu: H1 (obrazy poprawiają trafność), H2 (reguły rejonu i bilansowanie poprawiają stabilność i jakość), S0–S3 (źródła danych), L0–L3 (architektura).

---

## 1. Szacowanie populacji na poziomie budynku i siatek

Tu leży główna luka, którą wypełniamy: większość prac działa na siatkach, a nie na budynkach.

### 1.1 Metody dasymetryczne na danych polskich (najbliższe naszemu baseline'owi)

- **Pirowski, Szypuła (2024)**, Annals of the AAG 114(5). Populacja z budynków mieszkalnych z BDOT10k (Kraków), lokalizacja budynku jako zmienna ograniczająca, powierzchnia (zabudowa × kondygnacje) jako wiążąca, 19 map. Na siatce 1 × 1 km: baseline z samych jednostek urbanistycznych 310,8% MAPE; dasymetria z objętości 21,9%; **najlepszy wariant (2,88 os. na dom jednorodzinny, 37,1 m²/os. dla wielorodzinnych) 19,2% MAPE**. **Dlaczego ważne:** gotowy punkt odniesienia dla L0 i prior dla rubryki gęstości (L2). ⚠ Czytany tylko abstrakt (paywall). Szczegóły i korekta wcześniejszego opisu w [notatka-pirowski.md](notatka-pirowski.md).
- **Całka, Bielecka, Zdunkiewicz (2016)**, Geodesy and Cartography 65(2). Populacja z objętości budynków (BDOT) i typu zabudowy oraz średniej powierzchni mieszkania, agregowana do siatki 1 km. Obszar: powiat opatowski, rejon wiejski (nie Kraków). Poprzednik naszego baseline'u `objetosc` (powierzchnia × wysokość). Wg abstraktu RMSE średnio 9 osób.
- **Pirowski, Bartoś (2018)**, Geodetski vestnik 62(3). Poprzednik wersji z 2024; **przeczytany w całości**. Kraków, 141 jednostek, kalibracja powierzchni na osobę metodą najmniejszych kwadratów, korekta K zachowująca sumy jednostek. Podział jedno-/wielorodzinne zmniejsza MAPE z 48% do 31%. Brak niezależnej walidacji i problem parterów usługowych (autorzy sami wskazują). Szczegóły w [notatka-pirowski.md](notatka-pirowski.md).
- **Pirowski, Timek (2019)** i **Pirowski, Berka (2019)**, Geoinformatica Polonica 18, s. 57–69 i 45–55 (Kraków, siatka GUS 1 km z 2011 r.). Porównanie wariantów mapy populacji opartych na land use i land cover, w tym OBIA. Wnioski ze streszczenia wyszukiwarki: najlepiej wypadły metody oparte na pokryciu terenu, a estymacja z danych OBIA wypadła słabo. DOI: 10.4467/21995923gp.19.004.10888 i 10.4467/21995923gp.19.003.10887. ⚠ Wnioski niezweryfikowane w tekście.

### 1.2 Produkty globalne (WorldPop, GHS-POP, HRSL, LandScan)

- Wspólny wniosek porównań: **GHS-POP i HRSL używają podejścia binarnego** (ludzie tylko w komórkach uznanych za zabudowę), więc jakość zależy od detekcji budynków. GHS-POP zaniża populację na obszarach gęstych i zawyża na rzadkich. Dla Polski i Portugalii błędy względem statystyk krajowych były małe w agregacie (MAPE rzędu 1,5–4,5%), ale agregat nie mówi nic o trafności w komórce. [Soton, sustainability 11/6056](https://eprints.soton.ac.uk/435474/1/sustainability_11_06056.pdf); [Remote Sensing 12(7)](https://www.mdpi.com/2072-4292/12/7/1105).
- **Walidacja na poziomie komórki jest rzadka**, a produkty wrażliwe na wiek spisu. [PLOS ONE (Soton)](https://eprints.soton.ac.uk/468941/1/journal.pone.0271504.pdf). Argument za naszym projektem: potrzebujemy lepszego rozkładu wewnątrz agregatu, a nie tylko lepszego agregatu.
- Przy okazji: błąd z założenia „wszystkie budynki są zamieszkane" jest znany w literaturze. Odpowiada to naszej rubryce udziału mieszkalnego.

### 1.3 Estymacja na poziomie budynku z obrazów

- **Gandhinagar (2025, preprint, arXiv 2509.12926)**. Obrazy 0,3 m, DEM 0,5 m i wektory dają populację na budynek. Autorzy zauważają, że wiele prac działa na siatkach albo traktuje wysokość budynku jako zewnętrzne wejście. [arXiv](https://arxiv.org/abs/2509.12926v1). ⚠ Preprint, wynik sumaryczny miasta do sprawdzenia.
- **Mapping Vulnerable Populations with AI** (arXiv 2107.14123). Potok: U-Net do obrysów, osobna sieć fuzji do gęstości, funkcja budynku ze zdjęć ulicznych i mediów społecznościowych. [arXiv](https://arxiv.org/pdf/2107.14123). ⚠ Raczej propozycja niż pełne wyniki.
- **Mozambik (arXiv 2104.12696)**. Neal i in. Estymacja bez spisu (mikrospis UNICEF z 2019 r., dwa dystrykty), kafelki 100 m, obrysy budynków z uczenia transferowego. Poprawa predykcji dzięki powierzchni obrysów względem samych publicznych cech (potwierdzone w tekście). Pokazuje, że obrysy to krok pośredni. [arXiv](https://arxiv.org/pdf/2104.12696).
- **Guo, Cao, Wang (2017)**, Singapur, ISPRS Archives XLII-2/W7, s. 1181–1187 (referat konferencyjny). Teledetekcja i dane otwarte, metoda jednostek mieszkaniowych (LiDAR, wysokość i kondygnacje). Abstrakt podaje dokładność do 92,5% (potwierdzone w tekście). DOI: 10.5194/isprs-archives-xlii-2-w7-1181-2017.
- **Luka do sprawdzenia:** nie znaleźliśmy pracy, która z liczby kondygnacji dochodzi do liczby mieszkań na budynek (to wymaga założeń o powierzchni mieszkania).

---

## 2. Modele wizualno-językowe do atrybutów budynków (L1, H1)

- **Pan i in.** Zero-shot: CLIP i SAM do wyciągania atrybutów budynków bez treningu. [arXiv 2312.12479](https://arxiv.org/pdf/2312.12479.pdf).
- **Yang i in. (2024)**. Ocena Gemini Pro na funkcji budynku, wysokości i konstrukcji ze zdjęć ulicznych. [arXiv 2408.12821](https://arxiv.org/html/2408.12821v1). Najbliższe temu, co robi nasz świadek wizualny, choć na obrazach ulicznych, a nie z lotu ptaka.
- **OpenFACADES (2025)**. Otwarte VLM do wieloatrybutowego opisu budynków ze zdjęć ulicznych. [opis](https://fugumt.com/fugumt/paper_check/2504.02866v2_enmode).
- **Sun i in. (2025), Monachium (arXiv 2505.18021)**. Liczba kondygnacji z crowdsourcowanych zdjęć ulicznych: 81,2% trafień dokładnych, 97,9% w granicach ±1 piętro. Dobry **baseline nie-VLM** dla kondygnacji i zbiór do ewentualnej walidacji. [arXiv](https://arxiv.org/html/2505.18021v1).
- **ELEV-VISION-SAM (2024)**. SAM z VLM do segmentacji fasad i wysokości progu. [arXiv 2404.12606](https://arxiv.org/html/2404.12606v1).
- **Przeglądy VLM dla teledetekcji**: Zhou i in., *Towards Vision-Language Geo-Foundation Model: A Survey* [arXiv 2406.09385](https://arxiv.org/pdf/2406.09385v2); benchmark OmniEarth (2026) z 28 zadaniami [arXiv 2603.09471](https://arxiv.org/html/2603.09471). Autorzy OmniEarth piszą, że systematycznego benchmarku brakowało. GeoChat, RemoteCLIP i EarthGPT to modele z tej rodziny, ale ich oryginalnych prac nie przeglądaliśmy.
- **Luka:** nie znaleźliśmy pracy, która mierzy VLM jednocześnie na kondygnacjach, wysokości i funkcji z **ortofotomapy ukośnej**. To dobry argument za nowością H1.

---

## 3. LLM jako estymator geoprzestrzenny

- **GeoLLM (Manvi i in., ICLR 2024, arXiv 2310.06213)**. Prompt zbudowany z danych OSM (sąsiedztwo, współrzędne) wydobywa wiedzę geoprzestrzenną z LLM. Etykiety gęstości z WorldPop 1 km. Potwierdzone w tekście (tab. 2, gęstość WorldPop, 1000 próbek): pełny prompt r² = 0,73 (GPT-3.5), same współrzędne 0,22, bez opisu najbliższych miejsc 0,58 (Llama 2: 0,63 → 0,47). Tab. 1: dla 1000 próbek GPT-3.5 0,73, a baseline nightlight 0,62. [ICLR](https://proceedings.iclr.cc/paper_files/paper/2024/hash/a87f2df7c4ab0213c6ea228e7b7f0a4d-Abstract-Conference.html), [arXiv](https://arxiv.org/abs/2310.06213). **Dlaczego ważne:** punkt odniesienia dla „LLM z samą wiedzą" i wzór ablacji źródeł kontekstu. 

---

## 4. LLM w symulacji miejskiej i mobilności (po co populacja)

Uzasadnienie zastosowania: modele ruchu potrzebują rozkładu źródeł podróży.

- **MobiVerse (arXiv 2506.21784)**. Synteza populacji i łańcuchy aktywności plus LLM do zmian zachowań, integracja z SUMO, ok. 53 tys. agentów. [arXiv](https://arxiv.org/pdf/2506.21784).
- **GATSim (arXiv 2506.23306)**. Agenci generatywni z pamięcią i planowaniem w symulacji transportu. [arXiv](https://arxiv.org/html/2506.23306v1).
- **Song i in. (arXiv 2505.21880)**. LLM z modelowaniem agentowym, Tajpej. Autorzy przyznają, że walidacja jest niewystarczająca. [arXiv](https://arxiv.org/pdf/2505.21880).
- **GenWorld (arXiv 2606.27650)**. Infrastruktura symulacji: syntetyczne miasto na poziomie budynku (Higashihiroshima, 196 608 mieszkańców, spis i dane geoprzestrzenne), argumentuje, że istniejące platformy zwykle nie łączą syntezy populacji na skalę miasta z ugruntowaniem w danych (potwierdzone w tekście). Populację bierze ze spisu, nie szacuje jej z obrazów, więc to raczej uzasadnienie zastosowania niż konkurent. [arXiv](https://arxiv.org/pdf/2606.27650).
- **Wspólna luka:** walidacja. Nasza ocena (MPWiK, obwody wyborcze) odpowiada na nią bezpośrednio.

---

## 5. Architektura agentowa (L1–L3, H2)

- **Multiagent Debate (Du i in., ICML 2024, arXiv 2305.14325)**. Kilka instancji proponuje odpowiedzi i poprawia je po lekturze innych w kilku rundach. Zyski w rozumowaniu i faktach (abstrakt i wstęp mówią o wielu instancjach i rundach). [arXiv](https://arxiv.org/pdf/2305.14325). Wzorzec dla naszej pętli uzgadniania (2–3 rundy).
- **Self-Refine (Madaan i in., NeurIPS 2023, arXiv 2303.17651)**. Szkic, krytyka, poprawka tym samym modelem, bez treningu. [arXiv](https://arxiv.org/pdf/2303.17651). Alternatywa dla rozmowy dwóch agentów: pojedynczy agent z samokrytyką jako dodatkowy punkt odniesienia dla L3.
- **Reflexion (Shinn i in., NeurIPS 2023, arXiv 2303.11366)**. Werbalna refleksja trzymana w pamięci epizodycznej między próbami. [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract.html). Powiązane z naszą „sondą pamięci".
- **ReAct (Yao i in., ICLR 2023, arXiv 2210.03629)**. Potwierdzone w pełnym tekście (v3, marzec 2023). Model generuje na przemian myśli (rozumowanie) i akcje wobec zewnętrznego środowiska; na HotpotQA i Fever (z API Wikipedii) ogranicza halucynacje względem samego chain-of-thought, a na ALFWorld i WebShop przewyższa metody imitacyjne i RL o 34 i 10 pkt. bezwzględnych przy 1–2 przykładach w prompcie. Wynik z tab. 2: CoT ma 56% porażek z halucynacji, ReAct 0%, ale ReAct częściej wpada w pętlę powtarzanych kroków. Wzorzec dla pętli świadek–agent bilansujący (agent dopytuje i dostaje obserwację). Główne eksperymenty na PaLM-540B.
- **Towards a Science of Scaling Agent Systems (Google/MIT, arXiv 2512.08296)**. Kontrolowane porównanie pojedynczego agenta i czterech architektur wieloagentowych. Wnioski (potwierdzone w tekście): 260 konfiguracji, 6 benchmarków; zmiana względem pojedynczego agenta od +80,8% (zadania rozkładalne) do −70,0% (planowanie sekwencyjne); zwroty maleją, gdy pojedynczy agent jest już silny; niezależni agenci wzmacniają błędy na śladach 17,2×, a centralna weryfikacja obniża to do 4,4×. [arXiv](https://arxiv.org/html/2512.08296). **Bardzo bliskie naszemu pytaniu** o to, kiedy dodatkowa złożoność się opłaca. ⚠ Cytujemy wersję v3 (abstrakt: R² = 0,373 modelu predykcyjnego); w starszych wersjach liczby mogą się różnić.
- **Why Do Multi-Agent LLM Systems Fail? (MAST, Cemri i in., NeurIPS 2025, arXiv 2503.13657)**. 14 trybów porażek w 3 grupach (specyfikacja, niezgodność agentów, weryfikacja i zakończenie), 1642 oznaczone ślady z 7 frameworków (potwierdzone w tekście; NeurIPS 2025, Datasets and Benchmarks). Wniosek: porażki wynikają głównie z projektu systemu. [arXiv](https://arxiv.org/html/2503.13657v3). Gotowa taksonomia do analizy naszych śladów (rozmowa w pętli).

---

## 6. Stabilność i powtarzalność wyników LLM (oś „stabilność")

- **Non-Determinism of "Deterministic" LLM Settings (arXiv 2408.04667)**. Przy temperaturze 0 dokładność wahała się do 15% między 10 przebiegami, a żaden model nie dawał identycznych wyjść. Proponuje metryki zgodności przebiegów. [arXiv](https://arxiv.org/abs/2408.04667).
- **Numeryczne źródła niedeterminizmu (arXiv 2506.09501)**. Rozmiar partii, liczba GPU i model GPU zmieniają wynik zachłannego dekodowania. [arXiv](https://arxiv.org/pdf/2506.09501v2).
- **Eureka (arXiv 2409.10566)**. Microsoft Research, framework ewaluacji modeli bazowych (potwierdzone w pełnym tekście). Dla niedeterminizmu (sekcja 6) powtarza każdą instancję 3 razy przy temperaturze 0, top p = 0,95, i raportuje entropię wyników na instancję (cechy kategorialne), odchylenie standardowe (liczbowe) oraz odsetek instancji z niezgodnymi wynikami; np. Gemini 1.5 Pro 26% niezgodności na MMMU. Ważne dla nas: błąd standardowy średniej z powtórzeń zaniża niedeterminizm na poziomie instancji, więc trzeba raportować zgodność per instancja. Wyniki z modeli Claude 3 i GPT-4, więc nie przenosić liczb na nasze modele.
- **Do uzupełnienia:** self-consistency (Wang i in.) i wariancja odpowiedzi liczbowych. Nie znaleźliśmy tego w tym przebiegu.

---

## Co z tego wynika dla projektu

| Temat | Wniosek | Gdzie dalej |
|---|---|---|
| Baseline L0 | Pirowski i współautorzy dają gotowe wartości (2,88 os. na dom jednorodzinny, 37 m²/os. wielorodzinne) i miarę błędu (MAPE); mnożnik K jako baseline dla L3 | pełny tekst wersji 2024 (paywall), patrz notatka |
| Nowość H1 | Brak pracy z VLM na ortofotomapie ukośnej dla kondygnacji, wysokości i funkcji | dokończyć wyszukiwanie dla 2025–2026 |
| Pytanie H2 | „Science of Scaling" i MAST dają ramę, kiedy bilansowanie się opłaca (centralna weryfikacja ogranicza propagację błędów) | dokończyć lekturę poza sprawdzonymi liczbami |
| Walidacja | Prace o LLM w mobilności same wskazują brak walidacji | przeczytać GenWorld i Song i in. |
| Stabilność | Niedeterminizm występuje przy temp. 0, więc powtórzenia są konieczne | zaplanować liczbę powtórzeń |

## Do zrobienia (nie sprawdzone)

- Pirowski i Szypuła (2024): brak dostępu do pełnego tekstu, cytujemy wyłącznie na podstawie abstraktu i tak to zaznaczamy w artykule. Liczby z ReAct i Eureka sprawdzono w pełnym tekście. Liczby z GeoLLM, Science of Scaling, MAST i GenWorld sprawdzono w tekście.
- Znaleźć i zweryfikować: self-consistency (Wang i in., arXiv 2203.11171, cytowane w ReAct), HRSL i obrysy budynków Microsoftu jako konkurenci, metodologia siatek NSP 2021 (GUS).
- Szukać prac o estymacji liczby mieszkań z kondygnacji i powierzchni.
- Sprawdzić, czy istnieją prace o LLM jako sędzia (weryfikator) dla estymacji liczbowych, pod kątem L3.
- Szukać w polskich czasopismach (Przegląd Geograficzny, Geodeta, Geoinformatica Polonica) prac o populacji z BDOT10k po 2024.
