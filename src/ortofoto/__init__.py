"""Przygotowanie danych z ortofotomapy skośnej (nalot 2025, Wrocław) dla agentów VLM.

Moduły:
    arkusze  - pliki GeoTIFF z data/ i czytanie z nich wycinków
    budynki  - obrysy budynków z OSM i ich wysokość
    wycinki  - wycinek budynku z każdego kierunku, wyprostowana fasada, eksport dla agenta
"""

import os
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]  # katalog repozytorium
DATA = Path(os.environ.get("ORTOFOTO_DATA", KORZEN / "data"))
WYNIKI = Path(os.environ.get("ORTOFOTO_WYNIKI", KORZEN / "wyniki"))
