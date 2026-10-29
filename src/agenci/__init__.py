"""System agentowy szacujący liczbę mieszkańców budynków.

Moduły (w kolejności przepływu danych):
    karta        - deterministyczna karta budynku: rekord z BDOT10k, wysokość i wycinki ortofotomapy
    swiadkowie   - świadek wizualny (VLM): typ budynku, kondygnacje, udział mieszkalny, stan
    estymatory   - liczba mieszkańców: baseline'y, jedno wywołanie, wzór z rubryką gęstości
    eksperyment  - konfiguracja ablacji (TOML) i uruchomienie na zbiorze budynków
    ewaluacja    - porównanie przebiegów: koszt, zgodność z OSM, proxy (woda, obwody wyborcze)
    llm          - wywołania Claude z logiem w SQLite i pamięcią odpowiedzi
"""

from ortofoto import KORZEN, WYNIKI

BAZA = WYNIKI / "eksperymenty.sqlite"  # log wywołań i predykcje wszystkich przebiegów
EKSPERYMENTY = KORZEN / "eksperymenty"  # konfiguracje ablacji
