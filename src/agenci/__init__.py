"""System agentowy szacujący liczbę mieszkańców budynków. Opis całości: docs/architektura.md.

Moduły (w kolejności przepływu danych):
    karta        - karta budynku: rekord z BDOT10k, wysokość i wycinki ortofotomapy (bez modelu)
    llm          - wywołania modelu (Claude albo vLLM) z pamięcią odpowiedzi w SQLite
    swiadkowie   - świadek wizualny (VLM): typ budynku, stan, udział mieszkalny i gęstość
    estymatory   - liczba mieszkańców: baseline'y, rubryka (stałe z literatury) i wzór
    statystyka   - NSP 2021 w kwadratach 125 m i przypisanie budynków do kwadratów
    srlm         - rejony SRLM i udziały budynków w rejonach
    petla        - pętla uzgadniania: agent bilansujący dopytuje świadka o rozjazdy ze spisem
    szperacz     - agent z wyszukiwarką: liczba miejsc albo mieszkań dla największych budynków
    eksperyment  - konfiguracja przebiegu (TOML) i uruchomienie na zbiorze budynków
    ewaluacja    - ocena na rejonach SRLM
"""

from ortofoto import KORZEN, WYNIKI

BAZA = WYNIKI / "eksperymenty.sqlite"  # log wywołań modelu i pamięć odpowiedzi
EKSPERYMENTY = KORZEN / "eksperymenty"  # konfiguracje przebiegów
PRZEBIEGI = WYNIKI / "eksperymenty"  # wyniki przebiegów: <nazwa>.csv, <nazwa>__dialog.csv, <nazwa>__bilans.csv
MAX_PX = 768  # dłuższy bok obrazu wysyłanego do modelu
