# Artykuł (Overleaf, szablon ACL)

Pliki: `main.tex`, `references.bib`, `acl.sty`, `acl_natbib.bst` (szablon z https://github.com/acl-org/acl-style-files).

Wgranie: Overleaf → New Project → Upload Project → `artykul.zip`. Kompilator pdfLaTeX, plik główny `main.tex`.
Dodaj prowadzącego w Share. Brakujące miejsca są oznaczone czerwonym `[TODO: ...]` (makro `\todo`).
Przed oddaniem etapu: `\renewcommand{\todo}[1]{}` usuwa wszystkie znaczniki.

Kompilacja lokalnie: pdflatex + bibtex + pdflatex x2 (potrzebny pakiet inconsolata z texlive-fonts-extra; na Overleafie jest domyślnie).
