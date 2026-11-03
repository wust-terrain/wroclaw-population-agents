"""Wywołania Claude: jeden klient z pamięcią odpowiedzi w SQLite.

Każde wywołanie (prompt, odpowiedź, tokeny, koszt) trafia do tabeli `wywolania`. Identyczne zapytanie nie idzie drugi raz
do API, więc powtórka przebiegu jest darmowa, o ile prompty i obrazy się nie zmieniły.

Tryb na sucho nie łączy się z API i niczego nie zapisuje: zwraca odpowiedź zgodną ze schematem i szacuje koszt z rozmiaru
promptu. Służy do sprawdzenia, czy kod działa, i do wyceny przebiegu przed uruchomieniem.
"""

import base64
import hashlib
import io
import json
import sqlite3
import threading
import time
from dataclasses import dataclass

import anthropic
from PIL import Image

from agenci import BAZA, MAX_PX

CENY = {  # USD za 1 mln tokenów (wejście, wyjście); cennik Anthropic z 2026-10, sprawdź przed dużym przebiegiem
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
Z_FALLBACKIEM = {"claude-opus-5-5", "claude-sonnet-5-5"}  # modele, dla których włączamy fallbacks: "default"
EFFORT = "medium"
MAX_TOKENS = 16000
ROWNOLEGLE = 4  # tyle wywołań modelu naraz


@dataclass
class Odpowiedz:
    dane: dict | None  # JSON zgodny ze schematem albo None, gdy model odmówił
    koszt_usd: float
    stop: str


def obraz(img):
    """Blok obrazu dla API z tablicy RGB: zmniejszony do MAX_PX na dłuższym boku, JPEG w base64."""
    pil = Image.fromarray(img)
    pil.thumbnail((MAX_PX, MAX_PX))
    bufor = io.BytesIO()
    pil.save(bufor, format="JPEG", quality=85)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.standard_b64encode(bufor.getvalue()).decode()}}


def tekst(t):
    return {"type": "text", "text": t}


def _do_logu(tresc):
    """Prompt w logu: tekst w całości, obrazy jako skrót (żeby baza nie puchła)."""
    return "\n".join(b["text"] if b["type"] == "text" else f"[obraz, sha1 {hashlib.sha1(b['source']['data'].encode()).hexdigest()[:10]}]"
                     for b in tresc)


def _przyklad(schemat):
    """Najprostsza wartość zgodna ze schematem (dla trybu na sucho)."""
    if "enum" in schemat:
        return schemat["enum"][0]
    typ = schemat.get("type")
    if typ == "object":
        return {k: _przyklad(v) for k, v in schemat.get("properties", {}).items()}
    if typ == "array":
        return []
    return {"string": "", "integer": 1, "number": 0.5, "boolean": False}.get(typ)


class Klient:
    """Jedno miejsce, przez które przechodzą wszystkie wywołania modelu w przebiegu."""

    def __init__(self, model, eksperyment, na_sucho=False):
        self.model, self.eksperyment, self.na_sucho = model, eksperyment, na_sucho
        self.koszt = 0.0  # suma z przebiegu; odpowiedź z pamięci liczy się tak, jakby przyszła z API
        self.blokada = threading.Lock()  # wywołania idą z wielu wątków
        if not na_sucho:
            self.api = anthropic.Anthropic(max_retries=4)
            BAZA.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(BAZA, check_same_thread=False)
            self.db.execute("""CREATE TABLE IF NOT EXISTS wywolania (
                id INTEGER PRIMARY KEY, klucz TEXT, czas TEXT DEFAULT CURRENT_TIMESTAMP,
                eksperyment TEXT, budynek TEXT, rola TEXT, model TEXT, model_odpowiedzi TEXT,
                system TEXT, prompt TEXT, odpowiedz TEXT, stop TEXT, tokeny_we INTEGER, tokeny_wy INTEGER, koszt_usd REAL, czas_s REAL)""")
            self.db.execute("CREATE INDEX IF NOT EXISTS wywolania_klucz ON wywolania (klucz)")

    def zapytaj(self, *, rola, system, tresc, schemat, budynek=None):
        """Wysyła prompt (lista bloków tekst/obraz) i zwraca Odpowiedz z JSON-em zgodnym ze schematem."""
        if self.na_sucho:
            odp = self._na_sucho(system, tresc, schemat)
        else:
            odp = self._z_pamieci_albo_api(rola, system, tresc, schemat, budynek)
        with self.blokada:
            self.koszt += odp.koszt_usd
        return odp

    def _z_pamieci_albo_api(self, rola, system, tresc, schemat, budynek):
        # na_sucho i powtorzenie są stałe, ale klucze odpowiedzi już zapisanych w bazie je zawierają
        klucz = hashlib.sha256(json.dumps(
            {"model": self.model, "effort": EFFORT, "na_sucho": False, "system": system, "tresc": tresc, "schemat": schemat,
             "powtorzenie": 0}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.blokada:
            zapisana = self.db.execute("SELECT odpowiedz, koszt_usd, stop FROM wywolania WHERE klucz = ? LIMIT 1", (klucz,)).fetchone()
        if zapisana:
            odpowiedz, koszt, stop = zapisana
            return Odpowiedz(json.loads(odpowiedz) if odpowiedz else None, koszt, stop)

        start = time.perf_counter()
        dane, we, wy, model_odp, stop = self._wyslij(system, tresc, schemat)
        czas = time.perf_counter() - start
        cena_we, cena_wy = CENY.get(model_odp, CENY[self.model])
        koszt = (we * cena_we + wy * cena_wy) / 1e6
        with self.blokada:
            self.db.execute("""INSERT INTO wywolania (klucz, eksperyment, budynek, rola, model, model_odpowiedzi, system, prompt,
                               odpowiedz, stop, tokeny_we, tokeny_wy, koszt_usd, czas_s) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (klucz, self.eksperyment, budynek, rola, self.model, model_odp, system, _do_logu(tresc),
                             json.dumps(dane, ensure_ascii=False) if dane is not None else None, stop, we, wy, koszt, czas))
            self.db.commit()
        return Odpowiedz(dane, koszt, stop)

    def _na_sucho(self, system, tresc, schemat):
        """Szacunek: ok. 3 znaki na token, ok. 800 tokenów na obraz, 1500 tokenów wyjścia z zapasem na myślenie."""
        znaki = len(system) + sum(len(b["text"]) for b in tresc if b["type"] == "text")
        we = znaki // 3 + 800 * sum(b["type"] == "image" for b in tresc)
        cena_we, cena_wy = CENY[self.model]
        return Odpowiedz(_przyklad(schemat), (we * cena_we + 1500 * cena_wy) / 1e6, "na_sucho")

    def _wyslij(self, system, tresc, schemat):
        zapytanie = {"model": self.model, "max_tokens": MAX_TOKENS, "system": system, "messages": [{"role": "user", "content": tresc}],
                     "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": schemat}}}
        if self.model in Z_FALLBACKIEM:  # przy odmowie API samo ponawia zapytanie na innym modelu
            odp = self.api.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **zapytanie)
        else:
            odp = self.api.messages.create(**zapytanie)
        dane = None
        if odp.stop_reason not in ("refusal", "max_tokens"):
            dane = json.loads(next(b.text for b in odp.content if b.type == "text"))
        return dane, odp.usage.input_tokens, odp.usage.output_tokens, odp.model, odp.stop_reason
