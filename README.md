# wroclaw-population-agents

System agentów VLM do szacowania liczby mieszkańców pojedynczych budynków we Wrocławiu na podstawie danych przestrzennych i zdjęć lotniczych.

Agentów jeszcze nie ma. Na razie jest pakiet `ortofoto`, który z ortofotomapy skośnej robi wycinki budynku z czterech stron dla przyszłego agenta wizualnego, oraz notatnik demo.

## Instalacja

Python 3.12+.

```bash
git clone https://github.com/wust-terrain/wroclaw-population-agents.git
cd wroclaw-population-agents

# uv
uv sync && uv run nbstripout --install

# albo pip
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt && nbstripout --install
```

`nbstripout` usuwa wyniki komórek z notatników przy commicie.

## Dane

Notatnik potrzebuje czterech plików ortofotomapy skośnej z [geoportal.gov.pl](https://www.geoportal.gov.pl) (nalot 2025, arkusz 6.148.12.04.2, okolice pl. Grunwaldzkiego, ok. 80 MB każdy). Wrzuć je do `data/` bez zmiany nazw:

```
84055_1599419_6.148.12.04.2_N.tif
84055_1598619_6.148.12.04.2_E.tif
84055_1600219_6.148.12.04.2_S.tif
84055_1601019_6.148.12.04.2_W.tif
```

Bez któregoś kierunku notatnik też zadziała, tylko ten widok będzie pusty. Obrysy budynków z OSM pobierają się same. Dane nie trafiają do gita.

## Użycie

```bash
uv run python -m ortofoto.wycinki 101207542    # wycinki budynku o danym osm_id do wyniki/wycinki/
```

Demo: `notebooks/demo_ortofotomapa_skosna.ipynb`.

Nowa zależność: `uv add <pakiet>`, potem `uv export --format requirements-txt --no-hashes -o requirements.txt`.
