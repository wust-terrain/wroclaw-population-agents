"""Wywołania modelu: jeden klient z pamięcią odpowiedzi w SQLite.

Model `claude-*` idzie do API Anthropic (klucz w ANTHROPIC_API_KEY). Każdy inny model (np. Qwen/Qwen3.8-27B) idzie do
serwera zgodnego z API OpenAI pod adresem LOKALNY_URL (domyślnie vLLM na http://localhost:8000/v1); odpowiedź jest
ograniczona schematem JSON, a koszt to 0 USD.

Każde wywołanie (prompt, odpowiedź, tokeny, koszt) trafia do tabeli `wywolania`. Identyczne zapytanie nie idzie drugi raz
do API, więc powtórka przebiegu jest darmowa, o ile prompty i obrazy się nie zmieniły. Wywołanie bez poprawnego JSON-a (odmowa,
limit tokenów, zepsuty JSON) zostaje w logu, ale nie w pamięci: klient ponawia je do PROBY razy, a powtórka przebiegu znowu.

Tryb na sucho nie łączy się z API i niczego nie zapisuje: zwraca odpowiedź zgodną ze schematem i szacuje koszt z rozmiaru
promptu. Służy do sprawdzenia, czy kod działa, i do wyceny przebiegu przed uruchomieniem.
"""

import base64
import hashlib
import io
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass

import anthropic
import openai
from PIL import Image

from agenci import BAZA, MAX_PX

CENY = {  # USD za 1 mln tokenów (wejście, wyjście); cennik Anthropic z 2026-10, sprawdź przed dużym przebiegiem
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
WYSZUKANIE_USD = 0.01  # cena jednego zapytania do wyszukiwarki (10 USD za 1000); sprawdź przed dużym przebiegiem
Z_FALLBACKIEM = {"claude-opus-5-5", "claude-sonnet-5-5"}  # modele, dla których włączamy fallbacks: "default"
EFFORT = "medium"
MAX_TOKENS = 16000
PROBY = 5  # tyle razy najwyżej wysyłamy zapytanie, zanim uznamy, że model nie da odpowiedzi
ROWNOLEGLE = int(os.environ.get("ROWNOLEGLE", 4))  # tyle wywołań modelu naraz; dla lokalnego serwera więcej, np. 32
LOKALNY_URL = os.environ.get("LOKALNY_URL", "http://localhost:8000/v1")  # serwer zgodny z API OpenAI dla modeli spoza Claude


@dataclass
class Odpowiedz:
    dane: dict | None  # JSON zgodny ze schematem albo None, gdy po PROBY próbach nie było poprawnej odpowiedzi
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


def _json(t):
    """JSON z odpowiedzi modelu albo None, gdy się nie parsuje (np. ucięty)."""
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


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
        self.lokalny = not model.startswith("claude-")
        if not na_sucho:
            self.api = (openai.OpenAI(base_url=LOKALNY_URL, api_key=os.environ.get("LOKALNY_KLUCZ", "brak"), timeout=3600, max_retries=4)
                        if self.lokalny else anthropic.Anthropic(max_retries=4))
            BAZA.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(BAZA, check_same_thread=False)
            self.db.execute("""CREATE TABLE IF NOT EXISTS wywolania (
                id INTEGER PRIMARY KEY, klucz TEXT, czas TEXT DEFAULT CURRENT_TIMESTAMP,
                eksperyment TEXT, budynek TEXT, rola TEXT, model TEXT, model_odpowiedzi TEXT,
                system TEXT, prompt TEXT, odpowiedz TEXT, stop TEXT, tokeny_we INTEGER, tokeny_wy INTEGER, koszt_usd REAL, czas_s REAL)""")
            self.db.execute("CREATE INDEX IF NOT EXISTS wywolania_klucz ON wywolania (klucz)")

    def zapytaj(self, *, rola, system, tresc, schemat, budynek=None, wyszukiwan=0):
        """Wysyła prompt (lista bloków tekst/obraz) i zwraca Odpowiedz z JSON-em zgodnym ze schematem.

        wyszukiwan > 0 daje modelowi wyszukiwarkę internetową z takim limitem zapytań.
        """
        if self.na_sucho:
            odp = self._na_sucho(system, tresc, schemat, wyszukiwan)
        else:
            odp = self._z_pamieci_albo_api(rola, system, tresc, schemat, budynek, wyszukiwan)
        with self.blokada:
            self.koszt += odp.koszt_usd
        return odp

    def _z_pamieci_albo_api(self, rola, system, tresc, schemat, budynek, wyszukiwan):
        # na_sucho i powtorzenie są stałe, ale klucze odpowiedzi już zapisanych w bazie je zawierają
        klucz = hashlib.sha256(json.dumps(
            {"model": self.model, "effort": EFFORT, "na_sucho": False, "system": system, "tresc": tresc, "schemat": schemat,
             "powtorzenie": 0} | ({"wyszukiwan": wyszukiwan} if wyszukiwan else {}), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.blokada:
            zapisana = self.db.execute("SELECT odpowiedz, koszt_usd, stop FROM wywolania WHERE klucz = ? AND odpowiedz IS NOT NULL "
                                       "LIMIT 1", (klucz,)).fetchone()
        if zapisana:
            odpowiedz, koszt, stop = zapisana
            return Odpowiedz(json.loads(odpowiedz), koszt, stop)

        wyslij = self._wyslij_lokalnie if self.lokalny else self._wyslij
        suma = 0.0
        for _ in range(PROBY):  # model losuje, więc ponowione zapytanie zwykle daje poprawną odpowiedź
            start = time.perf_counter()
            dane, we, wy, model_odp, stop, szukan = wyslij(system, tresc, schemat, wyszukiwan)
            czas = time.perf_counter() - start
            cena_we, cena_wy = CENY.get(model_odp, CENY.get(self.model, (0.0, 0.0)))
            koszt = (we * cena_we + wy * cena_wy) / 1e6 + szukan * WYSZUKANIE_USD
            suma += koszt
            with self.blokada:
                self.db.execute("""INSERT INTO wywolania (klucz, eksperyment, budynek, rola, model, model_odpowiedzi, system, prompt,
                                   odpowiedz, stop, tokeny_we, tokeny_wy, koszt_usd, czas_s) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (klucz, self.eksperyment, budynek, rola, self.model, model_odp, system, _do_logu(tresc),
                                 json.dumps(dane, ensure_ascii=False) if dane is not None else None, stop, we, wy, koszt, czas))
                self.db.commit()
            if dane is not None:
                break
        return Odpowiedz(dane, suma, stop)

    def _na_sucho(self, system, tresc, schemat, wyszukiwan=0):
        """Szacunek: ok. 3 znaki na token, ok. 800 tokenów na obraz, 1500 tokenów wyjścia z zapasem na myślenie, 10 tys. tokenów na wynik wyszukiwania."""
        znaki = len(system) + sum(len(b["text"]) for b in tresc if b["type"] == "text")
        we = znaki // 3 + 800 * sum(b["type"] == "image" for b in tresc) + 10000 * wyszukiwan
        cena_we, cena_wy = CENY.get(self.model, (0.0, 0.0))
        return Odpowiedz(_przyklad(schemat), (we * cena_we + 1500 * cena_wy) / 1e6 + wyszukiwan * WYSZUKANIE_USD, "na_sucho")

    def _wyslij(self, system, tresc, schemat, wyszukiwan=0):
        zapytanie = {"model": self.model, "max_tokens": MAX_TOKENS, "system": system, "messages": [{"role": "user", "content": tresc}],
                     "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": schemat}}}
        if wyszukiwan:  # nowsza wersja narzędzia działa tylko na Opusie i Sonnecie
            wersja = "web_search_20260209" if self.model in Z_FALLBACKIEM else "web_search_20250305"
            zapytanie["tools"] = [{"type": wersja, "name": "web_search", "max_uses": wyszukiwan}]
        we = wy = szukan = 0
        for _ in range(4):  # pause_turn: serwer przerwał długą turę z narzędziem, odsyłamy ją bez zmian i serwer ją kończy
            if self.model in Z_FALLBACKIEM:  # przy odmowie API samo ponawia zapytanie na innym modelu
                odp = self.api.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **zapytanie)
            else:
                odp = self.api.messages.create(**zapytanie)
            we, wy = we + odp.usage.input_tokens, wy + odp.usage.output_tokens
            szukan += getattr(getattr(odp.usage, "server_tool_use", None), "web_search_requests", 0) or 0
            if odp.stop_reason != "pause_turn":
                break
            zapytanie["messages"] = [{"role": "user", "content": tresc}, {"role": "assistant", "content": odp.content}]
        dane = _json([b.text for b in odp.content if b.type == "text"][-1]) if odp.stop_reason == "end_turn" else None
        return dane, we, wy, odp.model, odp.stop_reason, szukan

    def _wyslij_lokalnie(self, system, tresc, schemat, wyszukiwan=0):
        """To samo zapytanie do serwera zgodnego z API OpenAI (vLLM): obrazy jako data URL, odpowiedź ograniczona schematem."""
        if wyszukiwan:
            raise ValueError("Wyszukiwarka działa tylko z modelami Claude; ustaw model_szperacza = \"claude-...\"")
        bloki = [{"type": "text", "text": b["text"]} if b["type"] == "text" else
                 {"type": "image_url", "image_url": {"url": f"data:{b['source']['media_type']};base64,{b['source']['data']}"}} for b in tresc]
        odp = self.api.chat.completions.create(
            model=self.model, max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": bloki}],
            response_format={"type": "json_schema", "json_schema": {"name": "odpowiedz", "schema": schemat}},
            extra_body={"chat_template_kwargs": {"reasoning_effort": EFFORT}})
        wybor = odp.choices[0]
        dane = _json(wybor.message.content) if wybor.finish_reason == "stop" and wybor.message.content else None
        return dane, odp.usage.prompt_tokens, odp.usage.completion_tokens, odp.model, wybor.finish_reason, 0
