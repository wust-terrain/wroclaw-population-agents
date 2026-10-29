# wroclaw-population-agents

System agentów VLM do szacowania liczby mieszkańców pojedynczych budynków we Wrocławiu na podstawie danych przestrzennych i zdjęć lotniczych.

Na razie działa część dla jednego arkusza ortofotomapy: karta budynku (wycinki z czterech stron, fasady, rekord BDOT10k), świadek wizualny (VLM), estymator ze wzoru i konfiguracje ablacji. Pętla uzgadniania, w której agenci rozmawiają, jest w planie. Przegląd całości: `notebooks/proof_of_concept.ipynb`.

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

Dane nie trafiają do gita. Wszystko wrzuć do `data/` bez zmiany nazw.

Ortofotomapa skośna z [geoportal.gov.pl](https://www.geoportal.gov.pl) (nalot 2025, arkusz 6.148.12.04.2, okolice pl. Grunwaldzkiego, ok. 80 MB każdy plik):

```text
84055_1599419_6.148.12.04.2_N.tif
84055_1598619_6.148.12.04.2_E.tif
84055_1600219_6.148.12.04.2_S.tif
84055_1601019_6.148.12.04.2_W.tif
```

BDOT10k dla Wrocławia (powiat 0264, GML, ok. 320 MB po rozpakowaniu) z tego samego geoportalu. Rozpakuj go tak, żeby istniał plik:

```text
data/0264_powiat_m.Wrocław/BDOT10K/PL.PZGiK.337.0264__OT_BUBD_A.xml
```

Dane statystyczne rozpakuj do `data/populacja/`:

```text
Grid_125_1.xlsx, Grid_125_2.xlsx   NSP 2021 w siatce 125 m, cała Polska (GUS, Grid_125_XLS.zip, 47 MB)
obwody_glosowania_utf8.csv         obwody głosowania 2025 (PKW, obwody_glosowania_csv.zip, 2,9 MB)
```

Źródła: [usługa ATOM GRID w GUS](https://geo.stat.gov.pl/atom-web/atom/GRID?spatial_dataset_identifier_code=GRID_2021_125m_xls&spatial_dataset_identifier_namespace=GRID) i [dane w arkuszach PKW](https://prezydent2025.pkw.gov.pl/prezydent2025/data/csv/obwody_glosowania_csv.1758650309.zip). Pierwsze uruchomienie czyta arkusze NSP ok. 1,5 min i zapisuje kwadraty Wrocławia w `data/populacja/`.

Obrysy z OSM (adres, zmierzona wysokość) pobierają się same przy pierwszym uruchomieniu.

## Użycie

Notatniki: `notebooks/proof_of_concept.ipynb` (przegląd), `notebooks/demo_ortofotomapa_skosna.ipynb` (szczegóły ortofotomapy skośnej) i `notebooks/swiadek_statystyczny.ipynb` (NSP 2021 i obwody głosowania).

Eksperymenty z `eksperymenty/*.toml`; wyniki i log wywołań trafiają do `wyniki/eksperymenty.sqlite`:

```bash
uv run python -m agenci.eksperyment eksperymenty/*.toml --na-sucho    # bez API: test i wycena
export ANTHROPIC_API_KEY=...                                          # prawdziwy przebieg
uv run python -m agenci.eksperyment eksperymenty/swiadek_s2.toml
uv run python -m agenci.ewaluacja                                      # porównanie przebiegów
uv run pytest
```

Wycinki jednego budynku (numer z OSM albo id z BDOT10k): `uv run python -m ortofoto.wycinki 101207542`.

Z pip te same polecenia bez `uv run`. Nowa zależność: `uv add <pakiet>`, potem `uv export --format requirements-txt --no-hashes -o requirements.txt`.
