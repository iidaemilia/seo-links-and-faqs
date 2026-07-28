# SEO Linker

A Python command-line tool for auditing orphan pages and FAQ coverage, and for
generating page-specific FAQ suggestions.

The tool can analyze a public website through its XML sitemap, inspect a local
directory of HTML files or fetch one public page for FAQ generation. It never
modifies the website. All results are saved as local reports for human review.

## Current capabilities

- Read regular XML sitemaps and sitemap indexes
- Keep sitemap and page requests on the original domain
- Respect `robots.txt` rules and crawl delays
- Block cross-domain and robots-forbidden redirects
- Limit sitemap audits to 100 selected URLs by default
- Include or exclude URL path prefixes before crawling
- List selected sitemap URLs without downloading page HTML
- Limit page and sitemap downloads to 5 MiB and `robots.txt` to 512 KiB
- Reject unexpected response types such as PDFs, images and videos
- Reuse unchanged page analyses with `ETag` and `Last-Modified`
- Extract titles, H1 headings, main text, language and internal links
- Identify orphan content pages and list their URLs
- Detect visible FAQ content and `FAQPage` JSON-LD
- Generate grounded FAQs with the OpenAI Responses API
- Validate generated FAQ data with Structured Outputs
- Produce visible FAQ HTML and matching `FAQPage` JSON-LD
- Export JSON, Markdown and self-contained HTML reports

The earlier internal-link recommendation experiment is preserved separately in
[docs/internal-linking-experiment.md](docs/internal-linking-experiment.md).

## Requirements

- Python 3.10 or newer
- An OpenAI API key only for FAQ generation

## Installation

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## Usage

### Audit a public website

```bash
./.venv/bin/python main.py \
  --url https://example.com \
  --out-dir output/site-audit
```

The audit reads `/robots.txt` and `/sitemap.xml`, follows same-domain sitemap
indexes, fetches the selected pages and reports orphan pages and FAQ coverage.
It makes no OpenAI API request unless `--faq-page` is also used.

Public audits process at most 100 selected sitemap URLs by default. Raise the
limit only when the larger crawl is intentional:

```bash
./.venv/bin/python main.py \
  --url https://example.com \
  --max-pages 250 \
  --out-dir output/site-audit
```

Parsed pages are stored in `.seo-linker-cache/pages.json`. Later audits send
conditional requests using `ETag` and `Last-Modified`. A `304 Not Modified`
response reuses the cached analysis. The cache is excluded from Git.

### Inspect sitemap URLs before crawling

```bash
./.venv/bin/python main.py \
  --url https://example.com \
  --list-urls
```

This lists and groups sitemap URLs without downloading page HTML or writing a
report.

### Limit an audit by URL path

Include one or more path prefixes:

```bash
./.venv/bin/python main.py \
  --url https://example.com \
  --include-path /products/ \
  --include-path /services/ \
  --out-dir output/selected-sections
```

Exclude unwanted prefixes:

```bash
./.venv/bin/python main.py \
  --url https://example.com \
  --exclude-path /en/ \
  --exclude-path /privacy/ \
  --out-dir output/filtered-audit
```

Path-limited orphan results describe only the selected crawl. A page may appear
orphaned when its incoming link comes from a page outside that selection. Use a
complete site crawl when you need authoritative sitewide orphan detection.

### Audit a site and generate FAQ suggestions for one sitemap page

```bash
./.venv/bin/python main.py \
  --url https://example.com \
  --faq-page https://example.com/guides/example/ \
  --out-dir output/audit-with-faq
```

This performs the audit and makes one OpenAI API request for the exact selected
page.

### Generate FAQs for one page only

```bash
./.venv/bin/python main.py \
  --faq-only https://example.com/guides/example/ \
  --out-dir output/example-faq
```

This reads only the selected page, makes one OpenAI API request and skips the
sitemap and orphan-page audit.

### Analyze local HTML files

```bash
./.venv/bin/python main.py \
  --site sample_site \
  --out-dir output/sample
```

The bundled Finnish sample site is a small fixture for Unicode text, orphan
detection and FAQ coverage. This command makes no OpenAI API request.

## OpenAI API setup

Copy the example configuration:

```bash
cp .env.example .env
```

Replace `your_api_key_here` with your API key. The real `.env` file is excluded
from Git and must not be committed.

The FAQ model can be configured in `.env`:

```text
OPENAI_FAQ_MODEL=gpt-5.6-luna
```

FAQ generation sends the selected page's title, H1 and up to 8,000 characters
of visible text to the OpenAI API. Review every generated answer before
publishing it.

## Output

Audit and FAQ runs create:

- `report.json` for machine-readable results
- `report.md` for text review
- `report.html` for visual browser review

Site-audit reports include:

- analyzed page count
- orphan-page count and URLs
- FAQ-gap count
- per-page FAQ status
- incoming and outgoing internal-link counts

FAQ reports also include:

- three to five question-and-answer suggestions
- visible FAQ HTML
- matching `FAQPage` JSON-LD

Generated reports are excluded from Git because they are run-specific.

## Current limitations

- Public audits require a readable `/sitemap.xml`.
- Pages are fetched sequentially.
- Orphan detection is limited to the pages included in the crawl.
- FAQ detection recognizes explicit visible FAQ patterns and valid FAQPage
  JSON-LD; unusual custom implementations may need manual review.
- FAQ generation handles one explicitly selected page per run.
