"""Przygotowanie danych z ortofotomapy skośnej (nalot 2025, Wrocław) dla agentów VLM.

Moduły:
    arkusze  - pliki GeoTIFF z data/ i czytanie z nich wycinków
    budynki  - budynki z BDOT10k, ich wysokość z LiDAR-u i adresy z punktów adresowych OSM
    wycinki  - kadr budynku z każdego kierunku, dach przesunięty od kamery, wyprostowana fasada
    pobierz  - arkusze ze skorowidza GUGiK
"""

import os
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]  # katalog repozytorium
DATA = Path(os.environ.get("ORTOFOTO_DATA", KORZEN / "data"))
WYNIKI = Path(os.environ.get("ORTOFOTO_WYNIKI", KORZEN / "wyniki"))
