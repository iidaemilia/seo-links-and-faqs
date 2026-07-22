"""Command-line entry point for SEO Linker."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from seolinker import __version__
from seolinker.faq import detect_faq_status, faq_status_label
from seolinker.fetch import fetch_page_html, fetch_sitemap_urls
from seolinker.linker import suggest_missing_links
from seolinker.links import (
    extract_internal_links,
    find_incoming_link_sources,
    normalize_url,
)
from seolinker.models import Page
from seolinker.parse import (
    extract_h1,
    extract_language,
    extract_main_text,
    extract_title,
    find_html_files,
)
from seolinker.report import write_json_report, write_markdown_report
from seolinker.similarity import calculate_tfidf_similarities, select_stop_words


EXCLUDED_CONTENT_PATHS = {"/privacy/", "/writing/"}


def print_page_results(
    heading: str, pages: list[Page], min_similarity: float, output_dir: Path
) -> None:
    """Print page-level link data and write the analysis reports."""
    incoming_sources = find_incoming_link_sources(pages)
    print(heading)

    for page in pages:
        incoming_count = len(incoming_sources[page.url])
        analysis_status = (
            "content page" if page.analyze_content else "excluded from content analysis"
        )
        orphan_status = (
            ", orphan page"
            if page.analyze_content and incoming_count == 0
            else ""
        )
        faq_status = (
            faq_status_label(page.faq_status)
            if page.analyze_content
            else "not checked"
        )
        print(
            f"- {page.location} — {page.title} "
            f"({page.word_count} words, "
            f"internal link targets: {len(page.internal_links)}, "
            f"pages linking here: {incoming_count}, "
            f"{analysis_status}{orphan_status}, "
            f"FAQ: {faq_status})"
        )

    similarities = calculate_tfidf_similarities(pages)
    stop_words = select_stop_words(pages)
    preprocessing = "english_stop_words" if stop_words == "english" else "none"
    preprocessing_label = (
        "English stop words removed"
        if preprocessing == "english_stop_words"
        else "no stop-word list"
    )
    print(f"\nTF-IDF similarities ({preprocessing_label}):")
    if not similarities:
        print("- At least two content pages are required for comparison.")
    else:
        for result in similarities:
            print(
                f"- {result.source.location} ↔ {result.target.location}: "
                f"{result.score:.3f}"
            )

    suggestions = suggest_missing_links(similarities, min_similarity=min_similarity)
    print(f"\nSuggested missing link directions (threshold {min_similarity:.3f}):")
    if not suggestions:
        print("- No new link directions found at the current threshold.")
    else:
        for suggestion in suggestions:
            print(
                f"- {suggestion.source.location} → {suggestion.target.location} "
                f"({suggestion.similarity:.3f})"
            )
            if suggestion.placement_type == "contextual":
                print(f'  Anchor: "{suggestion.anchor_text}"')
                print(f'  Placement sentence: "{suggestion.context_sentence}"')
            else:
                print(f"  {suggestion.read_more_label}: {suggestion.anchor_text}")

    report_path = write_json_report(
        output_dir=output_dir,
        pages=pages,
        incoming_sources=incoming_sources,
        similarities=similarities,
        suggestions=suggestions,
        min_similarity=min_similarity,
        preprocessing=preprocessing,
    )
    print(f"\nJSON report saved: {report_path}")
    markdown_path = write_markdown_report(
        output_dir=output_dir,
        pages=pages,
        incoming_sources=incoming_sources,
        similarities=similarities,
        suggestions=suggestions,
        min_similarity=min_similarity,
        preprocessing=preprocessing,
    )
    print(f"Markdown report saved: {markdown_path}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Analyze internal linking on a static HTML website."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"SEO Linker {__version__}",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--site",
        type=Path,
        help="Path to a local website directory to analyze.",
    )
    source.add_argument(
        "--url",
        help="Public website URL to analyze through its sitemap.",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.15,
        help="Minimum similarity score for a link suggestion (default: 0.15).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated reports (default: output).",
    )
    return parser


def main() -> None:
    """Run the command-line tool."""
    parser = build_parser()
    args = parser.parse_args()
    if not 0 <= args.min_similarity <= 1:
        parser.error("--min-similarity must be between 0 and 1.")

    if args.site:
        try:
            html_files = find_html_files(args.site)
        except (FileNotFoundError, NotADirectoryError) as error:
            parser.error(str(error))

        pages = []
        for html_file in html_files:
            html = html_file.read_bytes()
            relative_path = html_file.relative_to(args.site)
            page_url = f"https://local.test/{relative_path.as_posix()}"
            pages.append(
                Page(
                    location=str(relative_path),
                    url=normalize_url(page_url),
                    title=extract_title(html),
                    heading=extract_h1(html),
                    text=extract_main_text(html),
                    internal_links=tuple(extract_internal_links(html, page_url)),
                    language=extract_language(html),
                    faq_status=detect_faq_status(html),
                )
            )
        print_page_results(
            f"Found {len(pages)} HTML files:",
            pages,
            args.min_similarity,
            args.out_dir,
        )
        return

    try:
        urls = fetch_sitemap_urls(args.url)
    except ValueError as error:
        parser.error(str(error))

    pages = []
    for url in urls:
        try:
            html = fetch_page_html(url)
        except ValueError as error:
            parser.error(str(error))
        path = urlsplit(url).path
        pages.append(
            Page(
                location=url,
                url=normalize_url(url),
                title=extract_title(html),
                heading=extract_h1(html),
                text=extract_main_text(html),
                internal_links=tuple(extract_internal_links(html, url)),
                language=extract_language(html),
                analyze_content=path not in EXCLUDED_CONTENT_PATHS,
                faq_status=detect_faq_status(html),
            )
        )
    print_page_results(
        f"Found {len(pages)} URLs in the sitemap:",
        pages,
        args.min_similarity,
        args.out_dir,
    )


if __name__ == "__main__":
    main()
