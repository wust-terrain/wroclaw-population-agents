###  **https\://bit.ly/zmgsn2026**

### 

### **Cel kursu**

Celem kursu jest zapoznanie studentów z metodologią projektowania, budowy i eksperymentalnej oceny **systemów agentowych**, w szczególności systemów wykorzystujących duże modele językowe i wnioskujące (LLM/RLM), narzędzia, pamięć, mechanizmy planowania, formułowania zadań i ograniczeń, ocena autonomiczności, bezpieczeństwa (przekraczanie dopuszczalnych granic, wartości), weryfikacji i współpracy wielu agentów.

**Kluczowe** jest to, by projekt był **ambitny**, **ciekawy**, który będzie **inspirował innych** i dostarczał wyników **ważnych dla społeczności**. 

Podstawową formą zaliczenia jest realizacja **grupowego projektu badawczego**, którego wyniki zostaną opracowane w postaci draftu publikacji naukowej zgodnego z [wytycznymi ACL](https://aclrollingreview.org/cfp#long-papers) (maks. 8 stron bez bibliografii i załączników) lub [NeurIPS](https://neurips.cc/Conferences/2025/CallForPapers) (maks. 9 stron bez bibliografii i załączników).

Projekt powinien być realizowany w grupach liczących **od 2 do 4 osób**. Temat projektu może zostać zaproponowany przez studentów, pod warunkiem jego akceptacji przez prowadzącego oraz zgodności z tematyką kursu.

Projekt może mieć charakter:

* **metodologiczny** – jego głównym przedmiotem jest analiza określonego elementu systemu agentowego;  
* **naukowo-wdrożeniowy** – system agentowy służy rozwiązaniu rzeczywistego problemu, a jednocześnie jego wybrane elementy są przedmiotem systematycznych eksperymentów;  
* **badawczo-aplikacyjny** – punktem wyjścia jest konkretna dziedzina zastosowań, jednak głównym celem pozostaje postawienie i weryfikacja hipotezy badawczej dotyczącej działania systemu agentowego.

Niezależnie od wybranego tematu **samo zastosowanie istniejącego systemu agentowego, biblioteki lub gotowego środowiska nie jest wystarczające do realizacji projektu**. Projekt musi zawierać jasno sformułowane pytanie badawcze lub hipotezę oraz kontrolowane eksperymenty pozwalające określić wpływ wybranych elementów systemu na jego działanie.

---

### **Alternatywa**

Alternatywą jest realizacja [list zadań](https://drive.google.com/drive/folders/1rHp7dLHFPTV0ssmNXACqx0IS43lIr1TV?usp=drive_link) (zasady zaliczania podane w [karcie kursu](https://drive.google.com/file/d/1HiNhm5ukm0RWcrvMlJpPxlX32pMeqWPA/view?usp=sharing)) lub – w przypadku problemów z wyborem grupy – możliwość realizowania projektu indywidualnie (obowiązują te same zasady zaliczenia co w grupie).

---

### **Struktura projektu**

Projekt realizowany będzie etapami, z krótką prezentacją (7–10 minut) na każdym z sześciu etapów, co umożliwi systematyczne monitorowanie postępów i konsultacje z prowadzącymi.

Każdy etap kończy się oddaniem odpowiednich materiałów, obejmujących w szczególności kod źródłowy, wyniki eksperymentów oraz aktualizację artykułu w Overleaf. Etap oceniany będzie na podstawie jakości prezentacji oraz dostarczonych materiałów.

Szablon ACL: [https\://github.com/acl-org/acl-style-files](https://github.com/acl-org/acl-style-files)

Szablon NeurIPS: [https\://media.neurips.cc/Conferences/NeurIPS2025/Styles.zip](https://media.neurips.cc/Conferences/NeurIPS2025/Styles.zip)

**Dodatkowo na koniec semestru przewidziane jest przygotowanie plakatu jako rezultat projektu, który będzie prezentowany na AI Forum\! Plakat jest również elementem oceny\!**

**Uwaga\!** Możliwa jest realizacja istniejącego projektu naukowo-wdrożeniowego, pod warunkiem rozszerzenia go o **nowy komponent badawczy dotyczący systemów agentowych**. Zakres takiego projektu musi zostać wcześniej uzgodniony z prowadzącym. Grupa realizująca wspólny projekt powinna uczęszczać na jeden termin zajęć do jednego prowadzącego.

---

### **Wymagania badawcze**

Każdy projekt powinien umożliwiać udzielenie odpowiedzi na konkretne pytanie badawcze dotyczące działania systemu agentowego.

Projekt powinien obejmować:

* co najmniej dwie jasno zdefiniowane **zmienne eksperymentalne** dotyczące modelu, architektury agenta, jego środowiska wykonawczego lub sposobu działania;  
* co najmniej jeden odpowiednio dobrany **punkt odniesienia (baseline)**;  
* ilościową ocenę jakości działania systemu;  
* analizę kosztu działania systemu, o ile korzystanie z modeli lub narzędzi wiąże się z mierzalnym kosztem;  
* analizę co najmniej części parametrów związanych z efektywnością działania, takich jak czas odpowiedzi, liczba tokenów, liczba kroków, liczba wywołań narzędzi lub liczba prób rozwiązania zadania;  
* analizę uzyskanych wyników, ograniczeń rozwiązania oraz możliwych źródeł błędów.

W miarę możliwości eksperyment powinien umożliwiać określenie **przyczynowego wpływu badanego elementu systemu**, a nie jedynie porównanie dwóch kompletnych rozwiązań różniących się wieloma właściwościami jednocześnie.

---

### **Przykładowe obszary badawcze**

Poniższa lista nie jest zamkniętym katalogiem tematów. Studenci mogą zaproponować inne zagadnienia po konsultacji z prowadzącym.

#### **1\. Architektura i orkiestracja systemu wieloagentowego**

Badaniu może podlegać sposób organizacji współpracy wielu agentów.

Możliwe jest porównanie m.in.:

* pojedynczego agenta,  
* architektury planista–wykonawca,  
* architektury planista–wykonawca–weryfikator,  
* dynamiczne identyfikowanie ról w roju agentów,  
* kilku wyspecjalizowanych agentów,  
* wykonywania zadań sekwencyjnie i równolegle,  
* można wyjść również do podejścia badań interakcji międzyludzkich, np.: przykładowo można użyć środowisk, np.: [https\://docs.sotopia.world/concepts/agents](https://docs.sotopia.world/concepts/agents),  
* podmiana agenta na człowieka,  
* przykładowe systemy orkiestracji agentów (ADE \- agentic development environment) :  
  * [https\://herdr.dev/](https://herdr.dev/)  
  * [https\://www\.onorca.dev/](https://www.onorca.dev/)  
  * [https\://openchamber.dev/](https://openchamber.dev/)  
  * [https\://www\.conductor.build/](https://www.conductor.build/)  
  * [https\://superset.sh/](https://superset.sh/)  
* przykładowe harnessy:  
  * [https\://opencode.ai/](https://opencode.ai/)  
  * [https\://pi.dev/](https://pi.dev/)  
  * [https\://omp.sh/](https://omp.sh/)  
  * [https\://hermes-agent.nousresearch.com/](https://hermes-agent.nousresearch.com/)  
  * [https\://claude.com/product/claude-code](https://claude.com/product/claude-code)  
  * [https\://openai.com/pl-PL/codex/](https://openai.com/pl-PL/codex/)  
* przykładowe benchmarki:  
  * [https\://appworld.dev/appworld/](https://appworld.dev/appworld/)  
  * [https\://osu-nlp-group.github.io/TravelPlanner/](https://osu-nlp-group.github.io/TravelPlanner/)  
  * [https\://github.com/sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench)  
  * [https\://github.com/swe-bench/SWE-bench](https://github.com/swe-bench/SWE-bench)  
  * [https\://github.com/ServiceNow/WorkArena](https://github.com/ServiceNow/WorkArena)  
  * [https\://agentdojo.spylab.ai/](https://agentdojo.spylab.ai/)

Istotnym pytaniem jest określenie, **w którym momencie korzyść wynikająca z dodatkowej specjalizacji lub liczby agentów przestaje rekompensować koszt komunikacji i koordynacji**.

#### **2\. Wpływ środowiska wykonawczego agenta**

Przedmiotem projektu może być analiza wpływu **środowiska wykonawczego agenta (agent harness)** na jakość i koszt działania tego samego modelu.

W szczególności możliwe jest oszacowanie **narzutu środowiska (harness tax)**, czyli dodatkowego kosztu wynikającego m.in. z:

* dodatkowych instrukcji systemowych,  
* zarządzania kontekstem,  
* wykonywania dodatkowych kroków,  
* wywołań narzędzi,  
* mechanizmów ponawiania prób,  
* mechanizmów planowania i weryfikacji.

Analizowany powinien być zarówno dodatkowy koszt środowiska, jak i uzyskiwana dzięki niemu poprawa jakości działania.

#### **3\. Dostosowanie środowiska do konkretnego problemu**

Projekt może polegać na zaprojektowaniu i eksperymentalnej ocenie modyfikacji środowiska wykonawczego dostosowanej do konkretnego problemu.

Przykładowe elementy podlegające modyfikacji obejmują:

* sposób planowania,  
* zarządzanie kontekstem,  
* sposób wyboru narzędzi,  
* mechanizm weryfikacji wyników,  
* strategię ponawiania prób,  
* sposób przekazywania informacji pomiędzy krokami,  
* strategie formułowania zadań i ograniczeń (i konsekwencje tych decyzji), np. czy model wymyka się spod kontroli,   
* sposób delegowania zadań do innych agentów.

Istotną częścią projektu powinna być analiza, **który element modyfikacji odpowiada za obserwowaną zmianę jakości lub kosztu działania systemu**.

#### **4\. Łączenie różnych środowisk agentowych**

Możliwe jest badanie **kompozycji lub fuzji środowisk agentowych (harness fusion)**.

Celem może być określenie, czy połączenie wybranych mechanizmów pochodzących z różnych środowisk prowadzi do poprawy działania systemu.

Przedmiotem eksperymentu mogą być przykładowo:

* mechanizm zarządzania kontekstem z jednego środowiska,  
* mechanizm planowania z drugiego,  
* sposób obsługi narzędzi z trzeciego,  
* dodatkowy moduł weryfikacji wyników.

#### **5\. Samodoskonalące się środowiska agentowe**

Badaniu mogą podlegać systemy zdolne do automatycznej modyfikacji własnego sposobu działania.

Agent może na podstawie wcześniejszych eksperymentów:

* modyfikować instrukcje,  
* zmieniać sposób korzystania z narzędzi,  
* tworzyć nowe procedury,  
* modyfikować strategię planowania,  
* zmieniać sposób zarządzania kontekstem,  
* tworzyć nowe umiejętności lub procedury wielokrotnego użytku.

Przykładem tego kierunku jest [SoL-Pi](https://nvlabs.github.io/SoL-Pi/).

Szczególnie istotne jest sprawdzenie, czy automatycznie wypracowane ulepszenia **generalizują na nowe zadania**, a nie jedynie poprawiają wyniki na przykładach wykorzystanych podczas optymalizacji.

#### **6\. Zarządzanie kontekstem i pamięcią**

Badanie sposobów przechowywania, selekcji i kompresji informacji wykorzystywanych przez agenta.

Przykładowe pytania badawcze:

* Co powinno być przechowywane w pamięci?  
* Kiedy informacje powinny być usuwane lub kompresowane?  
* Jaki wpływ ma wielkość kontekstu na jakość rozwiązania?  
* Czy pamięć poprawia jakość działania również na nowych zadaniach?  
* Jaki jest koszt obsługi pamięci w stosunku do uzyskiwanej poprawy jakości?

#### **7\. Projektowanie narzędzi dla agentów**

Przedmiotem badania może być wpływ sposobu udostępniania narzędzi na działanie agenta.

Można porównywać m.in.:

* niewielką liczbę narzędzi wysokiego poziomu z dużą liczbą prostych operacji;  
* różne opisy i interfejsy narzędzi;  
* różne sposoby organizacji przestrzeni dostępnych narzędzi;  
* odporność agenta na obecność narzędzi nieprzydatnych dla danego zadania;  
* automatyczne tworzenie nowych narzędzi lub procedur na podstawie powtarzających się sekwencji działań.

#### **8\. Dynamiczny dobór modeli i zasobów obliczeniowych**

System agentowy może dynamicznie wybierać sposób rozwiązania zadania zależnie od jego trudności.

Możliwe jest badanie:

* wyboru modelu,  
* poziomu intensywności rozumowania,  
* liczby agentów,  
* długości procesu planowania,  
* liczby iteracji,  
* momentu uruchomienia dodatkowej weryfikacji.

Celem może być znalezienie kompromisu pomiędzy jakością rozwiązania, kosztem i czasem działania systemu.

#### **9\. Analiza przebiegu działania agenta w trakcie działania i po**

Ocena systemu nie musi ograniczać się do sprawdzenia końcowej odpowiedzi.

Przedmiotem analizy może być również **przebieg wykonania zadania (trajectory)**, w tym:

* jakość kolejnych decyzji,  
* poprawność wyboru narzędzi,  
* moment powstania błędu,  
* skuteczność wykrywania i naprawiania błędów,  
* liczba niepotrzebnych kroków,  
* sposób wykorzystania informacji z wcześniejszych etapów działania.  
* ocena / porównanie różnych strategii kontroli w trakcie działania (wykrywanie niepożądanych działań i/lub działań nieefektywnych)  
* agenty kontrolujące  
* strategie korygujące działanie w trakcie

Pozwala to odpowiedzieć nie tylko na pytanie, **czy agent rozwiązał zadanie**, lecz również **dlaczego zakończył się sukcesem lub porażką**.

#### **10\. Mechanizmy weryfikacji wyników**

Badaniu może podlegać sposób oceny częściowych lub końcowych wyników działania agenta.

Możliwe jest porównanie:

* weryfikacji wykonywanej przez model językowy,  
* deterministycznych testów,  
* programowych funkcji oceny,  
* niezależnego agenta-weryfikatora,  
* kilku kolejnych etapów weryfikacji.

Ważnym zagadnieniem jest również odporność systemu na sytuacje, w których agent znajduje sposób uzyskania wysokiego wyniku w przyjętej metryce bez rzeczywistego rozwiązania problemu.

#### **11\. Odporność na zmiany środowiska**

Możliwe jest badanie zachowania agenta w sytuacji zmiany warunków, w których działa.

Przykładowe zmiany obejmują:

* zmianę interfejsu API,  
* zmianę nazw lub argumentów narzędzi,  
* usunięcie jednego z narzędzi,  
* pojawienie się nowych narzędzi,  
* zmianę formatu danych,  
* częściową niedostępność usług.

Projekt może badać zarówno spadek jakości, jak i zdolność systemu do samodzielnego dostosowania się do nowych warunków.

#### **12\. Odporność na błędy**

Systemy agentowe mogą być badane pod kątem odporności na:

* błędne wyniki narzędzi,  
* niepełne dane,  
* nieudane wywołania usług,  
* błędne decyzje pojedynczego agenta,  
* błędy komunikacji pomiędzy agentami.

Można analizować zdolność do wykrywania błędów, ponownego planowania oraz stopniowego pogarszania jakości zamiast całkowitego niepowodzenia systemu.

#### **13\. Bezpieczeństwo systemów agentowych**

Możliwa jest również realizacja projektów dotyczących bezpieczeństwa, m.in.:

* ataków typu *prompt injection*,  
* manipulowania wynikami narzędzi,  
* zatruwania pamięci agenta,  
* nadmiernych uprawnień,  
* propagacji błędnych lub złośliwych informacji pomiędzy agentami,  
* różne strategie wprowadzania bezpieczników (czego nie powinien robić).

W takich projektach należy analizować kompromis pomiędzy bezpieczeństwem, użytecznością systemu i kosztem zastosowanych zabezpieczeń.

#### **14\. Minimalna wystarczająca architektura agenta**

Interesującym kierunkiem jest badanie, które elementy architektury agentowej rzeczywiście są potrzebne do rozwiązania danego problemu.

Możliwe jest stopniowe rozbudowywanie systemu:

`model → narzędzia → pętla działania → weryfikacja → pamięć → planowanie → system wieloagentowy`

i mierzenie dla każdego kolejnego elementu:

* zmiany jakości,  
* zmiany kosztu,  
* zmiany czasu wykonania,  
* zmiany liczby tokenów.

Pozwala to określić **narzut wynikający ze zwiększania złożoności systemu agentowego** oraz znaleźć najprostszą architekturę wystarczającą do rozwiązania danego problemu.

#### **15\. Działanie w świecie rzeczywistym**

- wynajmowanie ludzi przez AI w autonomiczny sposób (API) \- ***rent a human*** \- [https\://rentahuman.ai/](https://rentahuman.ai/)   
  - testowanie, badania i współpraca z Krzysztofem Majewskim z Radia Wrocław  
- współpraca z robotami i systemami autonomicznymi

#### **16\. Uczestnictwo w [SemEval 2027](https://semeval.github.io/SemEval2027/tasks.html) \- Agents and AI Tools**

* **Task 11: VAKRA-Advanced**: Evaluating Multi-Hop Multi-Source tool-calling capabilities in Executable Environments \- [https\://sites.google.com/view/vakrasemeval2027?pli=1\&authuser=0](https://sites.google.com/view/vakrasemeval2027?pli=1&authuser=0)   
* **Task 10: AgentRisk**: Risk Evaluation, Identification, and Policy-Guided Response in Agentic Multi-Turn Interactions \- [https\://agentrisk-semeval.lovable.app/](https://agentrisk-semeval.lovable.app/) 

---

### **Etapy projektu i punkty**

1. **Wybór tematu i plan projektu (2., 3\. zajęcia, 10 pkt.)**  
   * Zgłoszenie tematu projektu.  
   * Sformułowanie problemu oraz wstępnego pytania badawczego lub hipotezy.  
   * Określenie badanego systemu agentowego oraz głównych elementów jego architektury.  
   * Określenie zmiennej lub zmiennych, które będą przedmiotem eksperymentów.  
   * Wskazanie wstępnego punktu odniesienia (*baseline*).  
   * Przygotowanie skróconego planu realizacji projektu.  
   * Przygotowanie szablonu artykułu na Overleaf z nazwiskami osób z grupy, tematem i roboczym abstraktem.  
   * Dodanie prowadzącego do projektu w Overleaf.  
2. **Przegląd literatury i prototyp implementacji (4., 5\. zajęcia, 10 pkt.)**  
   * Przegląd literatury dotyczącej wybranego problemu oraz odpowiednich metod budowy i oceny systemów agentowych.  
   * Identyfikacja najważniejszych wcześniejszych prac oraz określenie różnic pomiędzy nimi a planowanym projektem.  
   * Przygotowanie prototypu rozwiązania.  
   * Określenie wykorzystywanych modeli, narzędzi, bibliotek oraz środowiska wykonawczego.  
   * Określenie struktury projektu i przypisanie ról w grupie.  
   * Wstępne określenie sposobu ewaluacji.  
   * Napisanie rozdziałów „Wstęp” oraz „Przegląd literatury” w artykule.  
   * Alternatywa: lista 1\.  
3. **Opis danych, środowiska i metody badawczej (6., 7\. zajęcia, 10 pkt.)**  
   * Opis zbiorów danych, zestawów zadań lub środowiska, na którym prowadzona będzie ewaluacja.  
   * Szczegółowy opis architektury systemu agentowego.  
   * Opis wykorzystywanych modeli, narzędzi, pamięci, mechanizmów planowania, weryfikacji lub komunikacji – zależnie od charakteru projektu.  
   * Określenie zmiennych niezależnych i zależnych w eksperymencie.  
   * Wybór metryk jakościowych i efektywnościowych.  
   * Przygotowanie rozdziałów „Dane” / „Środowisko”, „Metody” oraz „Plan eksperymentów” w artykule.  
   * Implementacja podstawowej wersji systemu oraz punktu odniesienia.  
   * Alternatywa: lista 2\.  
4. **Przygotowanie środowiska eksperymentalnego (8., 9\. zajęcia, 20 pkt.)**  
   * Przygotowanie kompletnego środowiska umożliwiającego powtarzalne wykonywanie eksperymentów.  
   * Implementacja metod ewaluacji i przetwarzania wyników.  
   * Implementacja rejestrowania podstawowych parametrów działania systemu, w szczególności jakości, czasu wykonania, kosztu i liczby tokenów, o ile są one istotne dla projektu.  
   * W zależności od charakteru projektu: rejestrowanie liczby kroków, wywołań narzędzi, ponownych prób, komunikatów pomiędzy agentami lub innych parametrów przebiegu działania.  
   * Implementacja badanych wariantów systemu.  
   * Przeprowadzenie eksperymentów pilotażowych i weryfikacja poprawności środowiska.  
   * Alternatywa: lista 3\.  
5. **Eksperymenty i opracowanie wyników cz. 1 (10., 11\. zajęcia, 20 pkt.)**  
   * Wykonanie głównych eksperymentów.  
   * Porównanie rozwiązania z przyjętym punktem odniesienia.  
   * Przeprowadzenie zaplanowanych badań ablacyjnych lub porównań wariantów systemu.  
   * Analiza jakości rozwiązania.  
   * Analiza kosztu, czasu wykonania, liczby tokenów oraz innych istotnych parametrów działania.  
   * Analiza typowych przypadków sukcesu i niepowodzeń systemu.  
   * Przygotowanie wstępnych tabel i wykresów do artykułu.  
   * Alternatywa: lista 4\.  
6. **Eksperymenty i opracowanie wyników cz. 2 (12., 13\. zajęcia, 30 pkt.)**  
   * Uzupełnienie eksperymentów wynikających z wcześniejszej analizy rezultatów.  
   * W miarę możliwości zbadanie generalizacji rozwiązania na nowych zadaniach, danych lub warunkach.  
   * Analiza ograniczeń zaproponowanego rozwiązania.  
   * Dyskusja wyników w odniesieniu do postawionego pytania badawczego lub hipotezy.  
   * Napisanie rozdziałów „Wyniki badań”, „Dyskusja”, „Ograniczenia” oraz „Wnioski i dalsze prace”.  
   * Finalizacja artykułu i sformułowanie propozycji dalszych badań.  
   * **Przygotowanie plakatu podsumowującego projekt**  
   * Alternatywa: lista 5\.  
7. **Finalizacja prac (14., 15\. zajęcia)**  
   * Oddawanie zaległości.  
   * Dopracowanie artykułów do postaci możliwie zbliżonej do publikacyjnej.  
   * Uporządkowanie kodu oraz materiałów umożliwiających odtworzenie najważniejszych eksperymentów.  
   * Końcowa prezentacja najważniejszych wyników projektu.

---

### **Przykładowe artykuły**

Prace z maksymalną liczbą punktów, które dostały się na punktowane konferencje naukowe, zrealizowane w poprzednich latach:

1. Kopeć, D., Kozłowski, W., Wizerkaniuk, M., Krutul, D., Kocoń, J., & Zięba, M. (2025, July). *SupResDiffGAN a new approach for the Super-Resolution task*. In International Conference on Computational Science (pp. 66–80). Cham: Springer Nature Switzerland. [\[link1\]](https://arxiv.org/pdf/2504.13622) [\[link2\]](https://www.iccs-meeting.org/archive/iccs2025/papers/159090060.pdf)  
2. Matys, P., Eliasz, J., Kiełczyński, K., Langner, M., Ferdinan, T., Kocoń, J., & Kazienko, P. (2025, July). *AggTruth: Contextual Hallucination Detection Using Aggregated Attention Scores in LLMs*. In International Conference on Computational Science (pp. 227–243). Cham: Springer Nature Switzerland. [\[link1\]](https://arxiv.org/pdf/2506.18628) [\[link2\]](https://www.iccs-meeting.org/archive/iccs2025/papers/159110220.pdf)

---

### **Kryteria oceniania**

* 50% – 3.0  
* 60% – 3.5  
* 70% – 4.0  
* 80% – 4.5  
* 90% – 5.0

---

### **Zasady oddawania i prezentacji**

* Każde spóźnienie o 1 zajęcia skutkuje obniżeniem punktacji o 30% za dany etap, o 2 zajęcia – o 60%, powyżej 2 zajęć – niezaliczeniem etapu.  
* Produkty etapu (prezentacja, kody, aktualizacja artykułu w Overleaf, **na końcu plakat**) należy wysłać mailowo lub inną ustaloną metodą **przed rozpoczęciem zajęć**, aby móc zaprezentować etap.  
* Obecność na wszystkich zajęciach jest obowiązkowa.  
* Dozwolona jest jedna nieusprawiedliwiona nieobecność w terminie oddania (w przypadku nieobecności całej grupy stosowane są zasady dotyczące spóźnienia) oraz jedna nieusprawiedliwiona nieobecność w dowolnym innym terminie.  
* Każda dodatkowa nieobecność nieusprawiedliwiona skutkuje obniżeniem końcowej oceny o jeden stopień dla danej osoby.

---

### **Uwagi dodatkowe**

Grupa ma możliwość kontaktu z prowadzącym w celu konsultacji merytorycznych oraz technicznych podczas trwania zajęć.

Prowadzący może zaakceptować projekt wykorzystujący istniejący system, środowisko agentowe lub wcześniejszy projekt studentów, jeżeli nowy zakres prac zawiera **samodzielny i odpowiednio szeroki komponent badawczy** związany z systemami agentowymi.

W szczególności nie jest wymagane stworzenie całego systemu od podstaw. Dopuszczalne jest wykorzystanie istniejących modeli, bibliotek, środowisk agentowych, narzędzi oraz otwartych implementacji, jeżeli służą one przeprowadzeniu poprawnie zaprojektowanego eksperymentu.

Ocenie podlega przede wszystkim:

* jakość sformułowanego problemu badawczego;  
* poprawność metodologii eksperymentalnej;  
* jakość i powtarzalność eksperymentów;  
* trafność zastosowanych punktów odniesienia;  
* jakość analizy i interpretacji wyników;  
* świadomość ograniczeń przeprowadzonego badania;  
* jakość przygotowanego artykułu naukowego.

Na zakończenie kursu każda grupa przedstawi pełny przegląd swojego projektu, a finalny artykuł zostanie oceniony również pod kątem możliwości dalszego rozwinięcia i publikacji.

**Publikacja artykułu nie jest obligatoryjna.**

