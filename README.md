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

Ortofotomapa skośna z [geoportal.gov.pl](https://www.geoportal.gov.pl), arkusz 6.148.12.04.2: pliki `*_N.tif`, `*_E.tif`, `*_S.tif`, `*_W.tif` wrzuć do `data/` bez zmiany nazw. Obrysy budynków z OSM pobierają się same. Dane nie trafiają do gita.

## Użycie

```bash
uv run python -m ortofoto.wycinki 101207542    # wycinki budynku o danym osm_id do wyniki/wycinki/
```

Demo: `notebooks/demo_ortofotomapa_skosna.ipynb`.

Nowa zależność: `uv add <pakiet>`, potem `uv export --format requirements-txt --no-hashes -o requirements.txt`.
