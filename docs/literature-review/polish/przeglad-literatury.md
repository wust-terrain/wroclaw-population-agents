# Wstępny przegląd literatury

Wersja robocza na 4. zajęcia. Cel: rozeznać się, w co warto się wgłębić. Opisy są krótkie i oparte na abstraktach oraz streszczeniach z wyszukiwarki. **Żadnej pozycji nie czytaliśmy w całości, więc liczby poniżej trzeba sprawdzić w oryginałach przed cytowaniem.** Pozycje oznaczone ⚠ mają dodatkowe zastrzeżenie.

Skróty odnoszą się do projektu: H1 (obrazy poprawiają trafność), H2 (reguły rejonu i bilansowanie poprawiają stabilność i jakość), S0–S3 (źródła danych), L0–L3 (architektura).

---

## 1. Szacowanie populacji na poziomie budynku i siatek

Tu leży główna luka, którą wypełniamy: większość prac działa na siatkach, a nie na budynkach.

### 1.1 Metody dasymetryczne na danych polskich (najbliższe naszemu baseline'owi)

- **Pirowski, Szypuła (2024)**, Annals of the AAG 114(5). Populacja z budynków mieszkalnych z BDOT10k (Kraków), lokalizacja budynku jako zmienna ograniczająca, powierzchnia (zabudowa × kondygnacje) jako wiążąca, 19 map. Na siatce 1 × 1 km: baseline z samych jednostek urbanistycznych 310,8% MAPE; dasymetria z objętości 21,9%; **najlepszy wariant (2,88 os. na dom jednorodzinny, 37,1 m²/os. dla wielorodzinnych) 19,2% MAPE**. **Dlaczego ważne:** gotowy punkt odniesienia dla L0 i prior dla rubryki gęstości (L2). ⚠ Czytany tylko abstrakt (paywall). Szczegóły i korekta wcześniejszego opisu w [notatka-pirowski.md](notatka-pirowski.md).
- **Całka, Bielecka, Zdunkiewicz (2016)**. Populacja z objętości budynków i typu zabudowy, agregowana do siatki 1 km (okolice Krakowa). Poprzednik naszego baseline'u `objetosc` (powierzchnia × wysokość).
- **Pirowski, Bartoś (2018)**, Geodetski vestnik 62(3). Poprzednik wersji z 2024; **przeczytany w całości**. Kraków, 141 jednostek, kalibracja powierzchni na osobę metodą najmniejszych kwadratów, korekta K zachowująca sumy jednostek. Podział jedno-/wielorodzinne zmniejsza MAPE z 48% do 31%. Brak niezależnej walidacji i problem parterów usługowych (autorzy sami wskazują). Szczegóły w [notatka-pirowski.md](notatka-pirowski.md).
- **Seria krakowska z siatką GUS 1 km (2011)**. Porównanie wariantów, w tym land use i OBIA. Wnioski: najlepiej wypadły metody oparte na pokryciu terenu, a estymacja z danych OBIA wypadła słabo. [Geoinformatica Polonica](https://ejournals.eu/czasopismo/geoinformatica-polonica/artykul/analysis-of-the-usefulness-land-use-and-land-cover-maps-for-estimating-the-population-of-urban-areas-valorisation-of-multi-variant-population-maps-based-on-the-gus-kilometre-network).
- **Bielecka (2005)**. Dasymetryczna mapa gęstości zaludnienia Polski, kontekst historyczny.

### 1.2 Produkty globalne (WorldPop, GHS-POP, HRSL, LandScan)

- Wspólny wniosek porównań: **GHS-POP i HRSL używają podejścia binarnego** (ludzie tylko w komórkach uznanych za zabudowę), więc jakość zależy od detekcji budynków. GHS-POP zaniża populację na obszarach gęstych i zawyża na rzadkich. Dla Polski i Portugalii błędy względem statystyk krajowych były małe w agregacie (MAPE rzędu 1,5–4,5%), ale agregat nie mówi nic o trafności w komórce. [Soton, sustainability 11/6056](https://eprints.soton.ac.uk/435474/1/sustainability_11_06056.pdf); [Remote Sensing 12(7)](https://www.mdpi.com/2072-4292/12/7/1105).
- **Walidacja na poziomie komórki jest rzadka**, a produkty wrażliwe na wiek spisu. [PLOS ONE (Soton)](https://eprints.soton.ac.uk/468941/1/journal.pone.0271504.pdf). Argument za naszym projektem: potrzebujemy lepszego rozkładu wewnątrz agregatu, a nie tylko lepszego agregatu.
- Przy okazji: błąd z założenia „wszystkie budynki są zamieszkane" jest znany w literaturze. Odpowiada to naszej rubryce udziału mieszkalnego.

### 1.3 Estymacja na poziomie budynku z obrazów

- **Gandhinagar (2025, preprint, arXiv 2509.12926)**. Obrazy 0,3 m, DEM 0,5 m i wektory dają populację na budynek. Autorzy zauważają, że wiele prac działa na siatkach albo traktuje wysokość budynku jako zewnętrzne wejście. [arXiv](https://arxiv.org/abs/2509.12926v1). ⚠ Preprint, wynik sumaryczny miasta do sprawdzenia.
- **Mapping Vulnerable Populations with AI** (arXiv 2107.14123). Potok: U-Net do obrysów, osobna sieć fuzji do gęstości, funkcja budynku ze zdjęć ulicznych i mediów społecznościowych. [arXiv](https://arxiv.org/pdf/2107.14123). ⚠ Raczej propozycja niż pełne wyniki.
- **Mozambik (arXiv 2104.12696)**. Estymacja bez spisu, na siatce 100 m, z danych ankietowych. Pokazuje, że obrysy to krok pośredni. [arXiv](https://arxiv.org/pdf/2104.12696).
- **Singapur** (teledetekcja i dane otwarte). Metoda jednostek mieszkaniowych z wysokością i liczbą kondygnacji, deklarowana dokładność ok. 92,5%. [ECNU](https://pure.ecnu.edu.cn/en/publications/population-estimation-in-singapore-based-on-remote-sensing-and-op/).
- **QuickBird + LiDAR (USA)**. Informacja o kształcie z LiDAR (wysokość) znacznie poprawia estymację względem samej spektralnej. Wspiera potrzebę wysokości i kondygnacji w S0.
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

- **GeoLLM (Manvi i in., ICLR 2024, arXiv 2310.06213)**. Prompt zbudowany z danych OSM (sąsiedztwo, współrzędne) wydobywa wiedzę geoprzestrzenną z LLM. Etykiety gęstości z WorldPop 1 km. Raportowane efekty: współrzędne same słabo działają, a usunięcie opisu najbliższych miejsc obniżało r² z 0,73 do 0,58 (GPT-3.5). Wynik zbliżony do metod satelitarnych. [ICLR](https://proceedings.iclr.cc/paper_files/paper/2024/hash/a87f2df7c4ab0213c6ea228e7b7f0a4d-Abstract-Conference.html), [arXiv](https://arxiv.org/abs/2310.06213). **Dlaczego ważne:** punkt odniesienia dla „LLM z samą wiedzą" i wzór ablacji źródeł kontekstu. ⚠ Liczby ze streszczeń.

---

## 4. LLM w symulacji miejskiej i mobilności (po co populacja)

Uzasadnienie zastosowania: modele ruchu potrzebują rozkładu źródeł podróży.

- **MobiVerse (arXiv 2506.21784)**. Synteza populacji i łańcuchy aktywności plus LLM do zmian zachowań, integracja z SUMO, ok. 53 tys. agentów. [arXiv](https://arxiv.org/pdf/2506.21784).
- **GATSim (arXiv 2506.23306)**. Agenci generatywni z pamięcią i planowaniem w symulacji transportu. [arXiv](https://arxiv.org/html/2506.23306v1).
- **Song i in. (arXiv 2505.21880)**. LLM z modelowaniem agentowym, Tajpej. Autorzy przyznają, że walidacja jest niewystarczająca. [arXiv](https://arxiv.org/pdf/2505.21880).
- **GenWorld (arXiv 2606.27650)**. Argumentuje, że platformom brakuje syntezy populacji z umiejscowieniem na poziomie budynku. [arXiv](https://arxiv.org/pdf/2606.27650). ⚠ Najbardziej zbliżona do naszego problemu, ale niezweryfikowana: trzeba przeczytać.
- **Wspólna luka:** walidacja. Nasza ocena (MPWiK, obwody wyborcze) odpowiada na nią bezpośrednio.

---

## 5. Architektura agentowa (L1–L3, H2)

- **Multiagent Debate (Du i in., ICML 2024, arXiv 2305.14325)**. Kilka instancji proponuje odpowiedzi i poprawia je po lekturze innych w kilku rundach. Zyski w rozumowaniu i faktach. [arXiv](https://arxiv.org/pdf/2305.14325). Wzorzec dla naszej pętli uzgadniania (2–3 rundy).
- **Self-Refine (Madaan i in., NeurIPS 2023, arXiv 2303.17651)**. Szkic, krytyka, poprawka tym samym modelem, bez treningu. [arXiv](https://arxiv.org/pdf/2303.17651). Alternatywa dla rozmowy dwóch agentów: pojedynczy agent z samokrytyką jako dodatkowy punkt odniesienia dla L3.
- **Reflexion (Shinn i in., NeurIPS 2023, arXiv 2303.11366)**. Werbalna refleksja trzymana w pamięci epizodycznej między próbami. [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract.html). Powiązane z naszą „sondą pamięci".
- **ReAct (Yao i in., arXiv 2210.03629)**. ⚠ Wyszukiwanie nie zwróciło oryginału, a numer arXiv pochodzi z naszej wiedzy. Trzeba znaleźć i zweryfikować.
- **Towards a Science of Scaling Agent Systems (Google/MIT, arXiv 2512.08296)**. Kontrolowane porównanie pojedynczego agenta i czterech architektur wieloagentowych. Wnioski: korzyść zależy od zadania (zadania sekwencyjne tracą, równoległe zyskują), zwroty maleją, gdy pojedynczy agent jest już silny, a niezależni agenci wzmacniają błędy do 17 razy. [arXiv](https://arxiv.org/html/2512.08296). **Bardzo bliskie naszemu pytaniu** o to, kiedy dodatkowa złożoność się opłaca. ⚠ Liczby różnią się między wersjami.
- **Why Do Multi-Agent LLM Systems Fail? (MAST, Cemri i in., NeurIPS 2025, arXiv 2503.13657)**. 14 trybów porażek w 3 grupach (specyfikacja, niezgodność agentów, weryfikacja i zakończenie), 1642 oznaczone ślady. Wniosek: porażki wynikają głównie z projektu systemu. [arXiv](https://arxiv.org/html/2503.13657v3). Gotowa taksonomia do analizy naszych śladów (rozmowa w pętli).

---

## 6. Stabilność i powtarzalność wyników LLM (oś „stabilność")

- **Non-Determinism of "Deterministic" LLM Settings (arXiv 2408.04667)**. Przy temperaturze 0 dokładność wahała się do 15% między 10 przebiegami, a żaden model nie dawał identycznych wyjść. Proponuje metryki zgodności przebiegów. [arXiv](https://arxiv.org/abs/2408.04667).
- **Numeryczne źródła niedeterminizmu (arXiv 2506.09501)**. Rozmiar partii, liczba GPU i model GPU zmieniają wynik zachłannego dekodowania. [arXiv](https://arxiv.org/pdf/2506.09501v2).
- **Eureka (arXiv 2409.10566)**. Każdą instancję powtarza się 3 razy i raportuje entropię lub błąd standardowy dla etykiet i liczb. Gotowy wzór na raportowanie powtórzeń. [arXiv](https://arxiv.org/pdf/2409.10566).
- **Do uzupełnienia:** self-consistency (Wang i in.) i wariancja odpowiedzi liczbowych. Nie znaleźliśmy tego w tym przebiegu.

---

## Co z tego wynika dla projektu

| Temat | Wniosek | Gdzie dalej |
|---|---|---|
| Baseline L0 | Pirowski i współautorzy dają gotowe wartości (2,88 os. na dom jednorodzinny, 37 m²/os. wielorodzinne) i miarę błędu (MAPE); mnożnik K jako baseline dla L3 | pełny tekst wersji 2024 (paywall), patrz notatka |
| Nowość H1 | Brak pracy z VLM na ortofotomapie ukośnej dla kondygnacji, wysokości i funkcji | dokończyć wyszukiwanie dla 2025–2026 |
| Pytanie H2 | „Science of Scaling" i MAST dają ramę, kiedy bilansowanie się opłaca | przeczytać oba w całości |
| Walidacja | Prace o LLM w mobilności same wskazują brak walidacji | przeczytać GenWorld i Song i in. |
| Stabilność | Niedeterminizm występuje przy temp. 0, więc powtórzenia są konieczne | zaplanować liczbę powtórzeń |

## Do zrobienia (nie sprawdzone)

- Przeczytać w całości: Pirowski i Szypuła, GeoLLM, Science of Scaling, MAST, GenWorld.
- Znaleźć i zweryfikować: ReAct, self-consistency, HRSL i obrysy budynków Microsoftu jako konkurenci, metodologia siatek NSP 2021 (GUS).
- Szukać prac o estymacji liczby mieszkań z kondygnacji i powierzchni.
- Sprawdzić, czy istnieją prace o LLM jako sędzia (weryfikator) dla estymacji liczbowych, pod kątem L3.
- Szukać w polskich czasopismach (Przegląd Geograficzny, Geodeta, Geoinformatica Polonica) prac o populacji z BDOT10k po 2024.
