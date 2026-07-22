# SEO Linker

A Python command-line tool for finding internal linking opportunities,
checking FAQ coverage and generating page-specific FAQ suggestions.

The tool can analyze a public website through its XML sitemap, read a local
directory of HTML files or fetch a single page for fast FAQ generation. It
never modifies the website: all results are written to reviewable reports.

## Current capabilities

- Fetch and analyze URLs from an XML sitemap
- Fetch only one page with `--faq-only`
- Read local HTML files recursively
- Extract titles, H1 headings, main content and internal links
- Exclude selected utility or listing pages from content comparison
- Identify orphan content pages
- Detect visible FAQ content and `FAQPage` JSON-LD
- Compare content pages with TF-IDF and cosine similarity
- Suggest missing internal link directions and placements
- Fall back to a language-aware related-reading link
- Generate grounded FAQs with the OpenAI Responses API
- Validate generated FAQ data with Structured Outputs
- Produce visible FAQ HTML and matching `FAQPage` JSON-LD
- Export JSON, Markdown and self-contained HTML reports

## Requirements

- Python 3.10 or newer
- An OpenAI API key only for FAQ generation

## Installation

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

The virtual environment keeps this project's packages separate from the rest
of your computer.

## Usage modes

### 1. Audit a public website

```bash
./.venv/bin/python main.py \
  --url https://iidalehtonen.com \
  --out-dir output/site-audit
```

The tool reads `/sitemap.xml`, fetches the listed pages and analyzes internal
links, orphan pages, FAQ coverage and TF-IDF content similarity.

This command makes no OpenAI API request unless `--faq-page` is also provided.

### 2. Audit a website and generate FAQs for one sitemap page

```bash
./.venv/bin/python main.py \
  --url https://iidalehtonen.com \
  --faq-page https://iidalehtonen.com/writing/should-you-build-your-website-with-ai/ \
  --out-dir output/site-audit-with-faq
```

This performs the full sitemap audit and makes one OpenAI API request for the
exact page selected with `--faq-page`.

### 3. Generate FAQs for one page without a site audit

```bash
./.venv/bin/python main.py \
  --faq-only https://iidalehtonen.com/writing/should-you-build-your-website-with-ai/ \
  --out-dir output/ai-website-faq
```

This fetches only the selected page and makes one OpenAI API request. It skips
the sitemap, orphan-page checks, TF-IDF and internal-link analysis.

Use this mode when you need FAQs for one page and do not need a fresh sitewide
audit.

### 4. Analyze local HTML files

```bash
./.venv/bin/python main.py \
  --site sample_site \
  --out-dir output/sample
```

The Finnish sample site is intentional: it acts as a small test fixture for
Unicode text and language-aware link labels. This command makes no OpenAI API
request.

## OpenAI API setup

Copy the example configuration:

```bash
cp .env.example .env
```

Then replace `your_api_key_here` in `.env` with your own API key. The real
`.env` file is excluded from Git and must never be committed.

The default FAQ model is configured in `.env`:

```text
OPENAI_FAQ_MODEL=gpt-5.6-luna
```

FAQ generation sends the selected page's title, H1 and up to 8,000 characters
of visible page text to the OpenAI API. Review all generated content before
publishing it.

## Output

Each run creates the following files in the selected `--out-dir`:

- `report.json` for machine-readable data
- `report.md` for easy text review and copying
- `report.html` for visual review in a browser

When FAQs are generated, all three reports include:

- Three to five question-and-answer suggestions
- Visible FAQ HTML
- Matching `FAQPage` JSON-LD
- Copy buttons in the HTML report

Generated reports are excluded from Git because they are run-specific output.

## Options

```bash
./.venv/bin/python main.py --help
```

Use `--min-similarity` to change the minimum TF-IDF similarity score required
for a link suggestion. Use `--out-dir` to keep reports from different runs in
separate directories.

## Current limitations

- Full public-site analysis requires a readable XML sitemap.
- Pages are currently fetched sequentially during a full audit.
- Results are not cached between runs.
- TF-IDF recognizes shared words, but not synonyms or broader meaning.
- Anchor suggestions are deliberately conservative.
- FAQ generation is currently limited to one explicitly selected page per run.
- The tool excludes the exact `/privacy/` and `/writing/` paths from content
  comparison while still including their links in the site graph.
