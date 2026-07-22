"""SEO Linker -komentorivin sisäänkäynti."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from seolinker import __version__
from seolinker.faq import detect_faq_status
from seolinker.fetch import fetch_page_html, fetch_sitemap_urls
from seolinker.linker import suggest_missing_links
from seolinker.links import (
    extract_internal_links,
    find_incoming_link_sources,
    normalize_url,
)
from seolinker.models import Page
from seolinker.parse import (
    extract_language,
    extract_main_text,
    extract_title,
    find_html_files,
)
from seolinker.similarity import calculate_tfidf_similarities, select_stop_words


EXCLUDED_CONTENT_PATHS = {"/privacy/", "/writing/"}


def print_page_results(
    heading: str, pages: list[Page], min_similarity: float
) -> None:
    """Tulosta sivukohtaiset linkkiverkon yhteenvetotiedot."""
    incoming_sources = find_incoming_link_sources(pages)
    print(heading)

    for page in pages:
        incoming_count = len(incoming_sources[page.url])
        analysis_status = (
            "sisältösivu" if page.analyze_content else "ei sisältöanalyysissä"
        )
        orphan_status = (
            ", orpo sivu"
            if page.analyze_content and incoming_count == 0
            else ""
        )
        faq_status = page.faq_status.value if page.analyze_content else "ei tarkisteta"
        print(
            f"- {page.location} — {page.title} "
            f"({page.word_count} sanaa, "
            f"sisäisiä kohteita: {len(page.internal_links)}, "
            f"sisääntulevia sivuja: {incoming_count}, "
            f"{analysis_status}{orphan_status}, "
            f"FAQ: {faq_status})"
        )

    similarities = calculate_tfidf_similarities(pages)
    stop_words = select_stop_words(pages)
    preprocessing = (
        "englannin stop-sanat poistettu"
        if stop_words == "english"
        else "ei stop-sanalistaa"
    )
    print(f"\nTF-IDF-samankaltaisuudet ({preprocessing}):")
    if not similarities:
        print("- Vertailuun tarvitaan vähintään kaksi sisältösivua.")
        return

    for result in similarities:
        print(
            f"- {result.source.location} ↔ {result.target.location}: "
            f"{result.score:.3f}"
        )

    suggestions = suggest_missing_links(similarities, min_similarity=min_similarity)
    print(f"\nAlustavat puuttuvat linkkisuunnat (raja {min_similarity:.3f}):")
    if not suggestions:
        print("- Ei uusia linkkisuuntia nykyisellä rajalla.")
        return

    for suggestion in suggestions:
        print(
            f"- {suggestion.source.location} → {suggestion.target.location} "
            f"({suggestion.similarity:.3f})"
        )


def build_parser() -> argparse.ArgumentParser:
    """Luo komentorivin argumenttien käsittelijä."""
    parser = argparse.ArgumentParser(
        description="Analysoi staattisen HTML-sivuston sisäistä linkitystä."
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
        help="Polku analysoitavan sivuston kansioon.",
    )
    source.add_argument(
        "--url",
        help="Analysoitavan sivuston julkinen verkko-osoite.",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.15,
        help="Linkkiehdotuksen pienin sallittu samankaltaisuus (oletus: 0.15).",
    )
    return parser


def main() -> None:
    """Käynnistä komentorivityökalu."""
    parser = build_parser()
    args = parser.parse_args()
    if not 0 <= args.min_similarity <= 1:
        parser.error("--min-similarity-arvon pitää olla välillä 0–1.")

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
                    text=extract_main_text(html),
                    internal_links=tuple(extract_internal_links(html, page_url)),
                    language=extract_language(html),
                    faq_status=detect_faq_status(html),
                )
            )
        print_page_results(
            f"Löytyi {len(pages)} HTML-tiedostoa:",
            pages,
            args.min_similarity,
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
                text=extract_main_text(html),
                internal_links=tuple(extract_internal_links(html, url)),
                language=extract_language(html),
                analyze_content=path not in EXCLUDED_CONTENT_PATHS,
                faq_status=detect_faq_status(html),
            )
        )
    print_page_results(
        f"Sitemapista löytyi {len(pages)} URLia:",
        pages,
        args.min_similarity,
    )


if __name__ == "__main__":
    main()
