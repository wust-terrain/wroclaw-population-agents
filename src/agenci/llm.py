"""Wywołania Claude z logiem w SQLite i pamięcią odpowiedzi.

Każde wywołanie (prompt, odpowiedź, tokeny, koszt, czas) trafia do tabeli `wywolania`.
Identyczne zapytanie (ten sam model, effort, prompt, obrazy i numer powtórzenia) nie idzie
drugi raz do API: odpowiedź bierzemy z bazy, a w logu zostaje wiersz z flagą z_pamieci.
Dzięki temu ablacje dzielące część kroków nie płacą za nie dwa razy, a powtórzenia
do testu stabilności różnią się numerem powtórzenia.

Tryb na sucho nie łączy się z API: zwraca odpowiedź zgodną ze schematem i szacuje koszt
z rozmiaru promptu. Służy do testów i do wyceny przebiegu przed uruchomieniem.
"""

import base64
import hashlib
import io
import json
import sqlite3
import threading
import time
from dataclasses import dataclass

from PIL import Image

CENY = {  # USD za 1 mln tokenów (wejście, wyjście); cennik Anthropic z 2026-10, sprawdź przed dużym przebiegiem
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
Z_FALLBACKIEM = {"claude-opus-5-5", "claude-sonnet-5-5"}  # modele, dla których włączamy fallbacks: "default"


@dataclass
class Odpowiedz:
    dane: dict | None  # JSON zgodny ze schematem albo None, gdy model odmówił
    tokeny_we: int
    tokeny_wy: int
    koszt_usd: float
    czas_s: float
    z_pamieci: bool
    model: str  # model, który faktycznie odpowiedział (przy fallbacku inny niż zamówiony)
    stop: str


def obraz(img, max_px=768, jakosc=85):
    """Blok obrazu dla API z tablicy RGB: zmniejszony do max_px na dłuższym boku, JPEG w base64."""
    pil = Image.fromarray(img)
    pil.thumbnail((max_px, max_px))
    bufor = io.BytesIO()
    pil.save(bufor, format="JPEG", quality=jakosc)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.standard_b64encode(bufor.getvalue()).decode()},
            "_rozmiar": pil.size}  # pole pomocnicze, usuwane przed wysłaniem


def tekst(t):
    return {"type": "text", "text": t}


def _do_api(tresc):
    return [{k: v for k, v in blok.items() if not k.startswith("_")} for blok in tresc]


def _do_logu(tresc):
    """Prompt w logu: tekst w całości, obrazy jako opis (żeby baza nie puchła)."""
    czesci = []
    for blok in tresc:
        if blok["type"] == "text":
            czesci.append(blok["text"])
        else:
            w, h = blok["_rozmiar"]
            czesci.append(f"[obraz {w}×{h}, sha1 {hashlib.sha1(blok['source']['data'].encode()).hexdigest()[:10]}]")
    return "\n".join(czesci)


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


class Dziennik:
    """Tabela `wywolania` w SQLite; bezpieczna przy wywołaniach z wielu wątków."""

    def __init__(self, sciezka):
        sciezka.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(sciezka, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("""CREATE TABLE IF NOT EXISTS wywolania (
            id INTEGER PRIMARY KEY, klucz TEXT, czas TEXT DEFAULT CURRENT_TIMESTAMP,
            eksperyment TEXT, budynek TEXT, rola TEXT, model TEXT, model_odpowiedzi TEXT,
            system TEXT, prompt TEXT, odpowiedz TEXT, stop TEXT,
            tokeny_we INTEGER, tokeny_wy INTEGER, koszt_usd REAL, czas_s REAL, z_pamieci INTEGER)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS wywolania_klucz ON wywolania (klucz)")
        self.db.commit()

    def znajdz(self, klucz):
        with self.lock:
            return self.db.execute("""SELECT odpowiedz, tokeny_we, tokeny_wy, koszt_usd, czas_s, model_odpowiedzi, stop
                                      FROM wywolania WHERE klucz = ? AND z_pamieci = 0 LIMIT 1""", (klucz,)).fetchone()

    def zapisz(self, **wiersz):
        with self.lock:
            self.db.execute(f"INSERT INTO wywolania ({', '.join(wiersz)}) VALUES ({', '.join('?' * len(wiersz))})",
                            list(wiersz.values()))
            self.db.commit()


class Klient:
    """Jedno miejsce, przez które przechodzą wszystkie wywołania modelu w eksperymencie."""

    def __init__(self, dziennik, model="claude-opus-5-5", effort="medium", na_sucho=False, max_tokens=16000):
        self.dziennik, self.model, self.effort = dziennik, model, effort
        self.na_sucho, self.max_tokens = na_sucho, max_tokens
        self.api = None
        if not na_sucho:
            import anthropic  # import tutaj, żeby tryb na sucho i testy nie wymagały klucza

            self.api = anthropic.Anthropic(max_retries=4)

    def zapytaj(self, *, rola, system, tresc, schemat, eksperyment="", budynek=None, powtorzenie=0):
        """Wysyła prompt (lista bloków tekst/obraz) i zwraca Odpowiedz z JSON-em zgodnym ze schematem."""
        klucz = hashlib.sha256(json.dumps(
            {"model": self.model, "effort": self.effort, "na_sucho": self.na_sucho, "system": system,
             "tresc": _do_api(tresc), "schemat": schemat, "powtorzenie": powtorzenie},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        log = dict(klucz=klucz, eksperyment=eksperyment, budynek=budynek, rola=rola, model=self.model,
                   system=system, prompt=_do_logu(tresc))

        if (zapisana := self.dziennik.znajdz(klucz)) is not None:
            tekst_odp, we, wy, koszt, czas, model_odp, stop = zapisana
            self.dziennik.zapisz(**log, model_odpowiedzi=model_odp, odpowiedz=tekst_odp, stop=stop, tokeny_we=we,
                                 tokeny_wy=wy, koszt_usd=koszt, czas_s=czas, z_pamieci=1)
            dane = json.loads(tekst_odp) if tekst_odp else None
            return Odpowiedz(dane, we, wy, koszt, czas, True, model_odp, stop)

        start = time.perf_counter()
        if self.na_sucho:
            dane, model_odp, stop = _przyklad(schemat), self.model, "na_sucho"
            obrazy = [b["_rozmiar"] for b in tresc if b["type"] == "image"]
            we = (len(system) + sum(len(b["text"]) for b in tresc if b["type"] == "text")) // 3 \
                + sum(w * h // 750 for w, h in obrazy)  # ok. 3 znaki na token; obraz ok. w·h/750 tokenów
            wy = 1500  # z zapasem na myślenie adaptacyjne; prawdziwą wartość pokaże pierwszy przebieg na kilku budynkach
        else:
            dane, we, wy, model_odp, stop = self._wyslij(system, tresc, schemat)
        czas = time.perf_counter() - start
        cena_we, cena_wy = CENY.get(model_odp, CENY.get(self.model, (0.0, 0.0)))
        koszt = (we * cena_we + wy * cena_wy) / 1e6

        self.dziennik.zapisz(**log, model_odpowiedzi=model_odp, stop=stop,
                             odpowiedz=json.dumps(dane, ensure_ascii=False) if dane is not None else None,
                             tokeny_we=we, tokeny_wy=wy, koszt_usd=koszt, czas_s=czas, z_pamieci=0)
        return Odpowiedz(dane, we, wy, koszt, czas, False, model_odp, stop)

    def _wyslij(self, system, tresc, schemat):
        zapytanie = dict(model=self.model, max_tokens=self.max_tokens, system=system,
                         messages=[{"role": "user", "content": _do_api(tresc)}],
                         output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schemat}})
        if self.model in Z_FALLBACKIEM:  # przy odmowie API samo ponawia zapytanie na innym modelu
            odp = self.api.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                                **zapytanie)
        else:
            odp = self.api.messages.create(**zapytanie)
        dane = None
        if odp.stop_reason not in ("refusal", "max_tokens"):
            dane = json.loads(next(b.text for b in odp.content if b.type == "text"))
        return dane, odp.usage.input_tokens, odp.usage.output_tokens, odp.model, odp.stop_reason
