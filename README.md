# SEO Linker

Komentorivityökalu staattisen HTML-sivuston sisäisen linkityksen analysointiin.

## Nykytila

Projektirunko ja ensimmäinen käynnistyvä komentorivi.

## Asennus

```bash
python3.13 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## Kokeile

```bash
./.venv/bin/python main.py --url https://iidalehtonen.com
```

Paikallisen HTML-kansion voi edelleen analysoida näin:

```bash
./.venv/bin/python main.py --site sample_site
```
