"""Write analysis results to report files."""

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from seolinker.faq import FaqStatus, faq_status_label
from seolinker.faq_generator import GeneratedFaq
from seolinker.models import Page


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def write_json_report(
    output_dir: Path,
    pages: list[Page],
    incoming_sources: dict[str, set[str]],
    generated_faq: GeneratedFaq | None = None,
    faq_only: bool = False,
) -> Path:
    """Write analysis results as JSON and return the report path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"

    page_results = []
    for page in pages:
        incoming_links = sorted(incoming_sources[page.url])
        is_orphan = None if faq_only else page.analyze_content and not incoming_links
        page_results.append(
            {
                "location": page.location,
                "url": page.url,
                "title": page.title,
                "h1": page.heading,
                "language": page.language,
                "word_count": page.word_count,
                "analyze_content": page.analyze_content,
                "is_orphan": is_orphan,
                "faq_checked": page.analyze_content,
                "faq_status": (
                    page.faq_status.value if page.analyze_content else None
                ),
                "outgoing_internal_links": list(page.internal_links),
                "incoming_internal_links": incoming_links,
            }
        )

    settings = (
        {"faq_model": generated_faq.model if generated_faq else None}
        if faq_only
        else {}
    )
    summary = (
        {
            "pages_fetched": len(pages),
            "faq_suggestions": (
                len(generated_faq.result.items) if generated_faq else 0
            ),
        }
        if faq_only
        else {
            "pages_found": len(pages),
            "content_pages": sum(page.analyze_content for page in pages),
            "orphan_pages": sum(bool(page["is_orphan"]) for page in page_results),
            "faq_gaps": sum(
                page.analyze_content and page.faq_status != FaqStatus.BOTH
                for page in pages
            ),
        }
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "faq_only" if faq_only else "site_audit",
        "settings": settings,
        "summary": summary,
        "pages": page_results,
        "generated_faq": (
            {
                "page_url": generated_faq.page.url,
                "model": generated_faq.model,
                "items": [
                    item.model_dump() for item in generated_faq.result.items
                ],
                "visible_html": generated_faq.visible_html,
                "faq_page_schema": json.loads(generated_faq.schema_json),
                "json_ld_script": generated_faq.json_ld_script,
            }
            if generated_faq
            else None
        ),
    }

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def write_markdown_report(
    output_dir: Path,
    pages: list[Page],
    incoming_sources: dict[str, set[str]],
    generated_faq: GeneratedFaq | None = None,
    faq_only: bool = False,
) -> Path:
    """Write analysis results as a human-readable Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    orphan_pages = [
        page
        for page in pages
        if page.analyze_content and not incoming_sources[page.url]
    ]

    if faq_only:
        lines = [
            "# SEO Linker FAQ report",
            "",
            "## Summary",
            "",
            "- Mode: FAQ only",
            f"- Page fetched: {generated_faq.page.url if generated_faq else 'none'}",
            "",
            "## Generated FAQ",
            "",
        ]
        _append_generated_faq_markdown(lines, generated_faq)
        report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return report_path

    lines = [
        "# SEO Linker report",
        "",
        "## Summary",
        "",
        f"- Pages found: {len(pages)}",
        f"- Pages included in content analysis: {sum(page.analyze_content for page in pages)}",
        f"- Orphan content pages: {len(orphan_pages)}",
        f"- Pages with FAQ gaps: {sum(page.analyze_content and page.faq_status != FaqStatus.BOTH for page in pages)}",
        "",
        "## Orphan content pages",
        "",
    ]

    if orphan_pages:
        lines.extend(f"- [{page.heading}]({page.url})" for page in orphan_pages)
    else:
        lines.append("No orphan content pages found.")

    lines.extend(["## FAQ status", ""])
    for page in pages:
        if page.analyze_content:
            lines.append(
                f"- [{page.heading}]({page.url}): {faq_status_label(page.faq_status)}"
        )

    lines.extend(["", "## Generated FAQ", ""])
    _append_generated_faq_markdown(lines, generated_faq)

    lines.extend(["", "## Pages", ""])
    for page in pages:
        incoming_count = len(incoming_sources[page.url])
        analysis_status = "yes" if page.analyze_content else "no"
        lines.extend(
            [
                f"### {page.heading}",
                "",
                f"- URL: {page.url}",
                f"- Title: {page.title}",
                f"- Language: {page.language or 'not detected'}",
                f"- Words: {page.word_count}",
                f"- Included in content analysis: {analysis_status}",
                f"- Internal link targets: {len(page.internal_links)}",
                f"- Pages linking here: {incoming_count}",
                "",
            ]
        )

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def _append_generated_faq_markdown(
    lines: list[str], generated_faq: GeneratedFaq | None
) -> None:
    """Append generated FAQ content and publication-ready code blocks."""
    if generated_faq is None:
        lines.append("No FAQs were generated in this run.")
        return

    lines.extend(
        [
            f"- Page: {generated_faq.page.url}",
            f"- Model: `{generated_faq.model}`",
            "",
        ]
    )
    for item in generated_faq.result.items:
        lines.extend([f"### {item.question}", "", item.answer, ""])
    lines.extend(
        [
            "### Visible FAQ HTML",
            "",
            "```html",
            generated_faq.visible_html,
            "```",
            "",
            "### FAQPage JSON-LD",
            "",
            "```html",
            generated_faq.json_ld_script,
            "```",
        ]
    )


def write_html_report(
    output_dir: Path,
    pages: list[Page],
    incoming_sources: dict[str, set[str]],
    generated_faq: GeneratedFaq | None = None,
    faq_only: bool = False,
) -> Path:
    """Write analysis results as a self-contained HTML report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.html"
    orphan_pages = [] if faq_only else [
        page
        for page in pages
        if page.analyze_content and not incoming_sources[page.url]
    ]
    content_pages = [page for page in pages if page.analyze_content]

    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.get_template("report.html.j2")
    rendered = template.render(
        generated_at=datetime.now(timezone.utc),
        pages=pages,
        content_pages=content_pages,
        orphan_pages=orphan_pages,
        incoming_sources=incoming_sources,
        faq_status_label=faq_status_label,
        faq_gaps=[
            page for page in content_pages if page.faq_status != FaqStatus.BOTH
        ],
        generated_faq=generated_faq,
        faq_only=faq_only,
    )
    report_path.write_text(rendered, encoding="utf-8")
    return report_path


def write_faq_only_reports(
    output_dir: Path, generated_faq: GeneratedFaq
) -> tuple[Path, Path, Path]:
    """Write JSON, Markdown and HTML reports for a single-page FAQ run."""
    page = generated_faq.page
    common = {
        "output_dir": output_dir,
        "pages": [page],
        "incoming_sources": {page.url: set()},
        "generated_faq": generated_faq,
        "faq_only": True,
    }
    json_path = write_json_report(**common)
    markdown_path = write_markdown_report(**common)
    html_path = write_html_report(**common)
    return json_path, markdown_path, html_path
