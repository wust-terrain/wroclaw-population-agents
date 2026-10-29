"""Karta budynku: rekord z BDOT10k, wysokość i wycinki ortofotomapy, czyli wejście dla świadków.

Nic tu nie wywołuje modelu. Karta zawiera adres tylko po to, żeby sonda pamięci mogła go użyć;
zwykłe prompty go nie dostają.
"""

import threading
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from ortofoto.wycinki import dach, dostepne_kierunki, elewacja, kadr
from ortofoto.arkusze import czytaj

_RASTRY = threading.Lock()  # pliki rasterio nie są bezpieczne przy czytaniu z wielu wątków naraz
PODSTAWA, DACH = (255, 214, 10), (255, 45, 85)
PIKSEL_NATYWNY = 0.05  # [m], piksel ortofotomapy skośnej z nalotu 2025


@dataclass
class Karta:
    id: str  # lokalnyId budynku w BDOT10k
    pow_zabudowy_m2: float
    h_m: float
    zrodlo_h: str  # pomiar OSM / z kondygnacji / domyślna
    kondygnacje: float | None  # BDOT10k
    funkcja: str | None  # przeważająca funkcja z BDOT10k, np. budynek wielorodzinny
    funkcje: str | None  # wszystkie funkcje szczegółowe z BDOT10k, np. "budynek wielorodzinny; apteka"
    kategoria: str | None  # stan w BDOT10k: eksploatowany, w budowie, nieczynny, zniszczony
    mieszkalny_bdot: bool  # funkcja ogólna 'budynki mieszkalne'
    adres: str | None
    widoki: dict = field(default_factory=dict)  # kierunek -> obraz RGB całego budynku
    fasady: dict = field(default_factory=dict)  # kierunek -> obraz RGB wyprostowanej fasady


def _obrysuj(img, ext, res, geometrie):
    """Rysuje obrysy (geometria, kolor) na wycinku o danym extent."""
    x0, _, _, y1 = ext
    pil = Image.fromarray(img)
    rys = ImageDraw.Draw(pil)
    for geom, kolor in geometrie:
        punkty = [((x - x0) / res, (y1 - y) / res) for x, y in geom.exterior.coords]
        rys.line(punkty, fill=kolor, width=max(2, round(0.3 / res)))
    return np.asarray(pil)


def zbuduj_karte(b, max_px=768, obrys=True, widoki=True, fasady=True, obrazy_z=None):
    """Karta budynku b (wiersz z wczytaj_budynki).

    max_px    - dłuższy bok wycinka; piksel dobierany per budynek, ale nie drobniejszy niż natywne 5 cm,
                więc mały dom i duży blok dostają obraz podobnej wielkości
    widoki    - dołącza wycinki całego budynku z każdego dostępnego kierunku
    obrys     - rysuje na widokach podstawę (żółta) i dach (czerwony), żeby było wiadomo, który budynek opisać
    fasady    - dołącza wyprostowane fasady zwrócone do kamery
    obrazy_z  - inny budynek, którego obrazy trafią do karty (placebo obrazowe)
    """
    adres = f"{b['addr:street']} {b['addr:housenumber']}" if isinstance(b["addr:street"], str) else None
    karta = Karta(id=str(b.name), pow_zabudowy_m2=round(b.geometry.area, 1), h_m=round(float(b.h), 1),
                  zrodlo_h=b.zrodlo_h, kondygnacje=None if pd.isna(b.kondygnacje) else float(b.kondygnacje),
                  funkcja=b.funkcja, funkcje=b.funkcje, kategoria=b.kategoria,
                  mieszkalny_bdot=bool(b.mieszkalny_bdot), adres=adres)
    if not (widoki or fasady):
        return karta
    zrodlo = b if obrazy_z is None else obrazy_z
    with _RASTRY:
        for kier in dostepne_kierunki(zrodlo):
            if widoki:
                x0, y0, x1, y1 = kadr(zrodlo, kier)
                res = max(PIKSEL_NATYWNY, max(x1 - x0, y1 - y0) / max_px)
                img, ext = czytaj(kier, (x0, y0, x1, y1), res)
                if obrys:
                    img = _obrysuj(img, ext, res, [(zrodlo.geometry, PODSTAWA), (dach(zrodlo, kier), DACH)])
                karta.widoki[kier] = img
            if fasady and (el := elewacja(zrodlo, kier, res=PIKSEL_NATYWNY)) is not None:
                karta.fasady[kier] = el[0]
    return karta
