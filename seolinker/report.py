"""Write analysis results to report files."""

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from seolinker.faq import faq_status_label
from seolinker.linker import LinkSuggestion
from seolinker.models import Page
from seolinker.similarity import SimilarityResult


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def write_json_report(
    output_dir: Path,
    pages: list[Page],
    incoming_sources: dict[str, set[str]],
    similarities: list[SimilarityResult],
    suggestions: list[LinkSuggestion],
    min_similarity: float,
    preprocessing: str,
) -> Path:
    """Write analysis results as JSON and return the report path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"

    page_results = []
    for page in pages:
        incoming_links = sorted(incoming_sources[page.url])
        is_orphan = page.analyze_content and not incoming_links
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

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "min_similarity": min_similarity,
            "tfidf_preprocessing": preprocessing,
        },
        "summary": {
            "pages_found": len(pages),
            "content_pages": sum(page.analyze_content for page in pages),
            "orphan_pages": sum(page["is_orphan"] for page in page_results),
            "link_suggestions": len(suggestions),
        },
        "pages": page_results,
        "similarities": [
            {
                "source": result.source.url,
                "target": result.target.url,
                "score": round(result.score, 6),
            }
            for result in similarities
        ],
        "link_suggestions": [
            {
                "source": suggestion.source.url,
                "target": suggestion.target.url,
                "similarity": round(suggestion.similarity, 6),
                "placement_type": suggestion.placement_type,
                "anchor_text": suggestion.anchor_text,
                "context_sentence": suggestion.context_sentence,
                "read_more_text": (
                    f"{suggestion.read_more_label}: {suggestion.anchor_text}"
                    if suggestion.placement_type == "read_more"
                    else None
                ),
            }
            for suggestion in suggestions
        ],
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
    similarities: list[SimilarityResult],
    suggestions: list[LinkSuggestion],
    min_similarity: float,
    preprocessing: str,
) -> Path:
    """Write analysis results as a human-readable Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    orphan_pages = [
        page
        for page in pages
        if page.analyze_content and not incoming_sources[page.url]
    ]

    lines = [
        "# SEO Linker report",
        "",
        "## Summary",
        "",
        f"- Pages found: {len(pages)}",
        f"- Pages included in content analysis: {sum(page.analyze_content for page in pages)}",
        f"- Orphan content pages: {len(orphan_pages)}",
        f"- Link suggestions: {len(suggestions)}",
        f"- Minimum similarity: {min_similarity:.3f}",
        f"- TF-IDF preprocessing: {preprocessing}",
        "",
        "## Orphan content pages",
        "",
    ]

    if orphan_pages:
        lines.extend(f"- [{page.heading}]({page.url})" for page in orphan_pages)
    else:
        lines.append("No orphan content pages found.")

    lines.extend(["", "## Link suggestions", ""])
    if not suggestions:
        lines.append("No new link suggestions found at the current threshold.")
    else:
        for index, suggestion in enumerate(suggestions, start=1):
            lines.extend(
                [
                    f"### {index}. {suggestion.source.heading} → {suggestion.target.heading}",
                    "",
                    f"- Source: {suggestion.source.url}",
                    f"- Target: {suggestion.target.url}",
                    f"- Similarity: {suggestion.similarity:.3f}",
                ]
            )
            if suggestion.placement_type == "contextual":
                lines.extend(
                    [
                        "- Suggestion type: contextual link",
                        f"- Anchor text: `{suggestion.anchor_text}`",
                        f"- Placement sentence: {suggestion.context_sentence}",
                    ]
                )
            else:
                lines.extend(
                    [
                        "- Suggestion type: related-reading link",
                        f"- Suggested text: **{suggestion.read_more_label}:** [{suggestion.anchor_text}]({suggestion.target.url})",
                    ]
                )
            lines.append("")

    lines.extend(["## FAQ status", ""])
    for page in pages:
        if page.analyze_content:
            lines.append(
                f"- [{page.heading}]({page.url}): {faq_status_label(page.faq_status)}"
            )

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

    lines.extend(["## All TF-IDF comparisons", ""])
    if not similarities:
        lines.append("At least two content pages are required for comparison.")
    else:
        for result in similarities:
            lines.append(
                f"- {result.source.heading} ↔ {result.target.heading}: "
                f"{result.score:.3f}"
            )

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def write_html_report(
    output_dir: Path,
    pages: list[Page],
    incoming_sources: dict[str, set[str]],
    suggestions: list[LinkSuggestion],
    min_similarity: float,
    preprocessing: str,
) -> Path:
    """Write analysis results as a self-contained HTML report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.html"
    orphan_pages = [
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
        suggestions=suggestions,
        incoming_sources=incoming_sources,
        faq_status_label=faq_status_label,
        min_similarity=min_similarity,
        preprocessing=preprocessing,
    )
    report_path.write_text(rendered, encoding="utf-8")
    return report_path
