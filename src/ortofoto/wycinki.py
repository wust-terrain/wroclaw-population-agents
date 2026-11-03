"""Wycinki budynku z każdego kierunku i wyprostowane fasady.

Na ortofotomapie skośnej podstawa budynku leży pod obrysem, a dach jest przesunięty o K · h
w kierunku patrzenia kamery. Między nimi widać fasadę zwróconą do kamery.
"""

import numpy as np
from shapely.affinity import translate
from shapely.geometry import box
from shapely.geometry.polygon import orient

from ortofoto.arkusze import KIERUNKI, KOLEJNOSC, czytaj, pokrywa

K = 0.85  # przesunięcie dachu / wysokość budynku; sprawdzone wzrokowo dla N, E, S i W (kamera ok. 40° od pionu)


def dach(b, kier, k=K):
    """Obrys dachu budynku b w widoku kier: obrys podstawy przesunięty o k · h."""
    dx, dy = KIERUNKI[kier]
    return translate(b.geometry, dx * k * b.h, dy * k * b.h)


def kadr(b, kier, k=K, margines=5):
    """Prostokąt (minx, miny, maxx, maxy) obejmujący podstawę i dach budynku b w widoku kier."""
    return box(*b.geometry.union(dach(b, kier, k)).bounds).buffer(margines, join_style="mitre").bounds


def dostepne_kierunki(b):
    """Kierunki, z których arkusze pokrywają cały kadr budynku b."""
    return [kier for kier in KOLEJNOSC if pokrywa(kier, kadr(b, kier))]


def elewacja(b, kier, res=0.05):
    """Wyprostowana fasada zwrócona do kamery (najdłuższa taka krawędź obrysu).

    Zwraca obraz w metrach (szerokość = długość krawędzi, wysokość = h) i szerokość [m],
    albo None, gdy żadna krawędź nie jest zwrócona do kamery.
    """
    v = np.array(KIERUNKI[kier], float)
    xy = np.array(orient(b.geometry, 1).exterior.coords)  # obrys przeciwnie do wskazówek zegara
    krawedzie = []
    for p1, p2 in zip(xy[:-1], xy[1:]):
        L = np.hypot(*(p2 - p1))
        normalna = np.array([p2[1] - p1[1], p1[0] - p2[0]]) / L  # na zewnątrz budynku
        if normalna @ -v > 0.5:
            krawedzie.append((L, p1, p2))
    if not krawedzie:
        return None
    L, p1, p2 = max(krawedzie, key=lambda t: t[0])
    u = (np.arange(int(L / res)) + 0.5) / int(L / res)  # 0..1 wzdłuż krawędzi
    w = 1 - (np.arange(int(b.h / res)) + 0.5) / int(b.h / res)  # 1 = dach (góra obrazu), 0 = grunt
    P = p1 + u[None, :, None] * (p2 - p1) + w[:, None, None] * (K * b.h * v)  # punkt fasady na ortofotomapie
    (x0, y0), (x1, y1) = P.reshape(-1, 2).min(0) - 1, P.reshape(-1, 2).max(0) + 1
    img, _ = czytaj(kier, (x0, y0, x1, y1), res)
    kol = ((P[..., 0] - x0) / res).astype(int).clip(0, img.shape[1] - 1)
    wie = ((y1 - P[..., 1]) / res).astype(int).clip(0, img.shape[0] - 1)
    return img[wie, kol], L


