# SEO Linker

A Python command-line tool for finding internal linking opportunities and
checking FAQ coverage on a website. It can analyze either a public website
through its sitemap or a directory of local HTML files.

The tool does not modify the website. It produces reports for human review.

## Current capabilities

- Fetch URLs from a website's XML sitemap
- Read local HTML files recursively
- Extract titles, H1 headings, main content and internal links
- Exclude selected utility or listing pages from content comparison
- Identify orphan content pages
- Detect visible FAQ content and `FAQPage` JSON-LD
- Compare content pages with TF-IDF and cosine similarity
- Suggest missing internal link directions
- Suggest a contextual anchor when a reliable phrase exists
- Fall back to a language-aware related-reading link
- Export JSON, Markdown and self-contained HTML reports

FAQ generation and the final HTML report are planned for a later phase.

## Requirements

- Python 3.10 or newer

## Installation

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

The virtual environment keeps this project's packages separate from the rest
of your computer.

## Analyze a public website

```bash
./.venv/bin/python main.py --url https://iidalehtonen.com
```

The tool looks for `/sitemap.xml`, downloads the listed pages and analyzes
their internal linking and content similarity.

## Analyze local HTML files

```bash
./.venv/bin/python main.py --site sample_site
```

The Finnish sample site is intentional: it acts as a small test fixture for
Unicode text and language-aware link labels.

## Options

```bash
./.venv/bin/python main.py --help
```

Use `--min-similarity` to change the minimum TF-IDF similarity score required
for a suggestion. Use `--out-dir` to choose where reports are saved.

## Output

Each run creates:

- `output/report.json` for machine-readable data
- `output/report.md` for easy human review
- `output/report.html` for visual review in a browser

Generated reports are excluded from Git because they are run-specific output.

## Current limitations

- Public URL analysis requires a readable XML sitemap.
- TF-IDF recognizes shared words, but not synonyms or broader meaning.
- Anchor suggestions are deliberately conservative.
- FAQ detection identifies existing content; it does not generate FAQs yet.
- The tool currently excludes the exact `/privacy/` and `/writing/` paths from
  content comparison, while still including their links in the site graph.
