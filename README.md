# wroclaw-population-agents

Budujemy system agentów VLM, który szacuje liczbę mieszkańców pojedynczych budynków we Wrocławiu. Populację znaną dla rejonu (GUS, KBR) rozdziela na budynki na podstawie danych przestrzennych i zdjęć lotniczych z nalotu 2025. Sprawdzamy, które źródła informacji i które elementy systemu dają lepszy wynik niż heurystyka powierzchnia × wysokość i ile to kosztuje.

W planowanym systemie świadkowie (statystyczny, przestrzenny, wizualni) zbierają obserwacje o budynkach. Agent rubryki układa z nich reguły dla rejonu, klasyfikator stosuje je do budynków, a recenzenci i agent bilansujący pilnują zgodności z sumą populacji rejonu. Orkiestrator zapisuje tokeny, czas i koszt każdego kroku.

Agentów jeszcze tu nie ma, dojdą, gdy ustalimy infrastrukturę. Na razie repo przygotowuje dane dla świadka wizualnego: wycinki budynku z czterech stron i wyprostowane fasady z ortofotomapy skośnej (pakiet `src/ortofoto`, demo w `notebooks/`).

## Instalacja

Potrzebny jest Python 3.12 lub nowszy.

```bash
git clone https://github.com/wust-terrain/wroclaw-population-agents.git
cd wroclaw-population-agents
```

Z uv:

```bash
uv sync
uv run nbstripout --install
```

Z pip:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
nbstripout --install
```

`nbstripout --install` uruchamiasz raz po sklonowaniu, żeby git zapisywał notatniki bez wyników komórek.

## Dane

Dane nie trafiają do gita. Ortofotomapę skośną (nalot 2025, bezpłatnie na [geoportal.gov.pl](https://www.geoportal.gov.pl)) wrzuć do `data/` z oryginalnymi nazwami plików. Teraz używamy arkusza 6.148.12.04.2 (okolice pl. Grunwaldzkiego) z czterech kierunków:

```
84055_1599419_6.148.12.04.2_N.tif
84055_1598619_6.148.12.04.2_E.tif
84055_1600219_6.148.12.04.2_S.tif
84055_1601019_6.148.12.04.2_W.tif
```

Obrysy budynków z OpenStreetMap pobierają się same przy pierwszym uruchomieniu.

## Uruchomienie

Demo to `notebooks/demo_ortofotomapa_skosna.ipynb`. W VS Code wybierz kernel z `.venv`, w przeglądarce uruchom `uv run --with jupyterlab jupyter lab`.

Wycinki dla świadka wizualnego (argumenty to identyfikatory budynków z OSM):

```bash
uv run python -m ortofoto.wycinki 101207542 101211778    # z pip: python -m ortofoto.wycinki ...
```

Dla każdego budynku powstaje `wyniki/wycinki/<osm_id>/` z plikami `N.jpg`, `E.jpg`, `S.jpg`, `W.jpg`, fasadami `fasada_*.jpg` i `meta.json`. Metadane nie zawierają adresu ani współrzędnych, bo prompty agentów nie mogą ich zawierać.

## Praca w repo

Wspólny kod, w tym przyszłych agentów, dodawaj w `src/`, eksperymenty jako notatniki w `notebooks/`. Nową zależność dodaj przez `uv add <pakiet>` i odśwież plik dla pip: `uv export --format requirements-txt --no-hashes -o requirements.txt`.
