### **1\. Temat i problem**

Głównym celem projektu jest stworzenie agentowego systemu LLM estymującego populację rejonu wewnątrz pojedynczych budynków we Wrocławiu. Wynik ma zasilić modele ruchu jako dokładny rozkład źródeł podróży.

* **Problem badawczy:** Publiczne dane są zagregowane w skali makro (dla miasta KBR podaje 600–675 tys. mieszkańców, podczas gdy ekspertyzy miejskie szacują ją na ok. 893,5 tys.). Dane nie są dostarczane na poziomie pojedynczych budynków.  
* **Cel wdrożeniowy:** Stworzenie narzędzia demonstracyjnego zmieniającego skalę analiz miejskich (z okręgu na konkretny budynek) i inicjującego dyskusję nad realnym zaludnieniem, bez konieczności arbitralnej optymalizacji pod niepewne dane twarde.

### **2\. Architektura i Hipotezy Badawcze**

Badamy wpływ źródła danych ($S$) oraz poziomu architektury agentowej ($A$) na jakość, stabilność oraz koszt rozkładu w stosunku do prostej heurystyki ($V=powierzchnia\times wysokość$).

#### **Hipotezy:**

* **H1:** Dołączenie danych obrazowych (ortofotomapy pionowe i ukośne) poprawia trafność rozkładu populacji w stosunku do danych nieobrazowych, w szczególności dla zabudowy jednorodzinnej, budynków mieszanych oraz akademików.  
* **H2:** Wprowadzenie reguł na poziomie rejonu oraz agentowej iteracji bilansującej poprawia stabilność i jakość predykcji w porównaniu do pojedynczego wywołania modelu.

#### **Przestrzeń Zmiennych ($S\times A$):**

* **Źródła informacji ($S$):**  
  * ${S}_{0}$: Dane GIS/wektorowe (BDOT10k, OSM, powierzchnia, wysokość z NMPT).  
  * ${S}_{1}$: ${S}_{0}$ \+ wycinanie ortofotomapy pionowej.  
  * ${S}_{2}$: ${S}_{1}$ \+ wycinki z ortofotomap ukośnych (N, E, S, W).  
  * ${S}_{3}$: ${S}_{2}$  ze zwiększonym regionem otaczającym   
* **Architektura agentowa ($A$):**  
  * ${L}_{0}$: Heurystyka wysokość \* powierzchnia \* współczynnik (Baseline).  
  * ${L}_{1}$: Wielomodalna obserwacja pojedynczego budynku przez agentów.  
  * ${L}_{2}$: Generowanie reguł klasyfikacji na poziomie całego rejonu.  
  * ${L}_{3}$: Iteracyjny proces bilansowania sumy mieszkańców w rejonie (2–3 rundy uzgadniania wyników).

### 

### **3\. Dane wejściowe**

* **Nalot 2025 Wrocław (PZGiK):** Ortofotomapy pionowe i ukośne RGB ($0,05m/px$).  
* **Dane wektorowe i statystyczne:** BDOT10k (przeliczone do EPSG:2177), KBR, siatki NSP 2021 ($125m$ – $1km$),

### **4\. Ocena i obserwacje**

* **Wymiary oceny**  
  * **Koszt:** Koszt API (\$), liczba tokenów, czas odpowiedzi, liczba kroków/wywołań**.**  
  * **Stabilność:** Wariancja kolejnych powtórzen.  
  * **Jakość:** Współczynnik korelacji Spearmana (z danymi MPWiK), MAE i WAPE (dla siatek NSP), F1-score klasyfikacji budynku (mieszkalny / mieszany / niemieszkalny na próbie 150 obiektów).  
* **Ewaluacja pomocnicza:** Zużycie wody z MPWiK na poziomie klatki schodowej (dane niepubliczne).