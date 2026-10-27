"""Wycinki budynku z każdego kierunku, wyprostowane fasady i eksport dla agenta wizualnego.

Na ortofotomapie skośnej podstawa budynku leży pod obrysem, a dach jest przesunięty o K · h
w kierunku patrzenia kamery. Między nimi widać fasadę zwróconą do kamery.

Uruchomienie z wiersza poleceń:
    python -m ortofoto.wycinki 101207542 101211778
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.affinity import translate
from shapely.geometry import box
from shapely.geometry.polygon import orient

from ortofoto import WYNIKI
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


def okres_kondygnacji(el, h, zakres=(2.4, 4.5)):
    """Okres pionowego wzoru okien [m]: maksimum autokorelacji profilu krawędzi poziomych w zakresie.

    Zwraca okres, siłę wzoru (wartość autokorelacji w maksimum; od ok. 0,4 okna są wyraźne,
    ściana bez okien daje ok. 0) oraz przesunięcia [m] i autokorelację do wykresu.
    """
    profil = np.abs(np.diff(el.mean(2), axis=0)).mean(1)
    profil = profil - np.convolve(profil, np.ones(81) / 81, mode="same")  # usuń trend dłuższy niż ok. 4 m
    ac = np.correlate(profil, profil, "full")[len(profil) - 1:]
    ac = ac / ac[0]
    przesuniecie = np.arange(len(ac)) * h / len(el)
    ok = np.flatnonzero((przesuniecie > zakres[0]) & (przesuniecie < zakres[1]))
    i = ok[ac[ok].argmax()]
    return przesuniecie[i], ac[i], przesuniecie, ac


def eksport_budynku(b, katalog, res=0.05):
    """Zapisuje wycinki i fasady budynku b do katalog/<osm_id>/ oraz meta.json; zwraca meta.

    meta.json celowo nie zawiera adresu ani współrzędnych (prompty agentów mają ich nie dostawać).
    """
    cel = Path(katalog) / str(b.name)
    cel.mkdir(parents=True, exist_ok=True)
    meta = {"osm_id": int(b.name), "pow_zabudowy_m2": round(b.geometry.area, 1), "h_m": round(float(b.h), 1),
            "zrodlo_h": b.zrodlo_h, "K": K, "m_na_px": res, "widoki": {}}
    dostepne = dostepne_kierunki(b)
    for kier in KIERUNKI:
        if kier not in dostepne:
            meta["widoki"][kier] = None  # brak arkusza dla tego kierunku
            continue
        img, _ = czytaj(kier, kadr(b, kier), res)
        Image.fromarray(img).save(cel / f"{kier}.jpg", quality=90)
        widok = {"wycinek": f"{kier}.jpg", "fasada": None, "szerokosc_fasady_m": None}
        fasada = elewacja(b, kier, res)
        if fasada is not None:
            Image.fromarray(fasada[0]).save(cel / f"fasada_{kier}.jpg", quality=90)
            widok.update(fasada=f"fasada_{kier}.jpg", szerokosc_fasady_m=round(float(fasada[1]), 1))
        meta["widoki"][kier] = widok
    (cel / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


if __name__ == "__main__":
    from ortofoto.budynki import wczytaj_budynki

    parser = argparse.ArgumentParser(description="Eksport wycinków budynków dla agenta wizualnego.")
    parser.add_argument("osm_id", type=int, nargs="+", help="identyfikatory budynków z OSM")
    parser.add_argument("--out", default=WYNIKI / "wycinki", help="katalog wyjściowy (domyślnie wyniki/wycinki)")
    parser.add_argument("--res", type=float, default=0.05, help="piksel wycinka w metrach (domyślnie 0.05)")
    args = parser.parse_args()

    bud = wczytaj_budynki()
    for osm_id in args.osm_id:
        meta = eksport_budynku(bud.loc[osm_id], args.out, args.res)
        widoki = [k for k, v in meta["widoki"].items() if v]
        print(f"{osm_id}: {', '.join(widoki) or 'brak arkuszy'} -> {Path(args.out) / str(osm_id)}")
