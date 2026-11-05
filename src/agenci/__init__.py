"""System agentowy szacujący liczbę mieszkańców budynków. Opis całości: docs/architektura.md.

Moduły (w kolejności przepływu danych):
    karta        - karta budynku: rekord z BDOT10k, wysokość i wycinki ortofotomapy (bez modelu)
    llm          - wywołania Claude z pamięcią odpowiedzi w SQLite
    swiadkowie   - świadek wizualny (VLM): typ budynku, kondygnacje, udział mieszkalny, stan
    estymatory   - liczba mieszkańców: baseline'y, rubryka (stałe z literatury) i wzór
    statystyka   - NSP 2021 w kwadratach 125 m i przypisanie budynków do kwadratów
    petla        - pętla uzgadniania: agent bilansujący dopytuje świadka o rozjazdy ze spisem
    eksperyment  - konfiguracja przebiegu (TOML) i uruchomienie na zbiorze budynków
    ewaluacja    - zgodność z BDOT10k i sumy w kwadratach NSP 2021
"""

from ortofoto import KORZEN, WYNIKI

BAZA = WYNIKI / "eksperymenty.sqlite"  # log wywołań modelu i pamięć odpowiedzi
EKSPERYMENTY = KORZEN / "eksperymenty"  # konfiguracje przebiegów
PRZEBIEGI = WYNIKI / "eksperymenty"  # wyniki przebiegów: <nazwa>.csv, <nazwa>__dialog.csv, <nazwa>__bilans.csv
MAX_PX = 768  # dłuższy bok obrazu wysyłanego do modelu
