"""Command-line entry point for SEO Linker."""

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from openai import OpenAIError

from seolinker import __version__
from seolinker.cache import (
    CachedPage,
    calculate_content_hash,
    load_page_cache,
    save_page_cache,
)
from seolinker.faq import detect_faq_status, faq_status_label
from seolinker.faq_generator import GeneratedFaq, generate_faqs
from seolinker.fetch import (
    RobotsDeniedError,
    fetch_page,
    fetch_page_html,
    fetch_robots_policy,
    fetch_sitemap_urls,
    get_crawl_delay,
)
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
from seolinker.report import (
    write_faq_only_reports,
    write_html_report,
    write_json_report,
    write_markdown_report,
)
EXCLUDED_CONTENT_PATHS = {"/privacy/", "/writing/"}


def print_page_results(
    heading: str,
    pages: list[Page],
    output_dir: Path,
    generated_faq: GeneratedFaq | None = None,
) -> None:
    """Print orphan and FAQ data and write the audit reports."""
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

    report_path = write_json_report(
        output_dir=output_dir,
        pages=pages,
        incoming_sources=incoming_sources,
        generated_faq=generated_faq,
    )
    print(f"\nJSON report saved: {report_path}")
    markdown_path = write_markdown_report(
        output_dir=output_dir,
        pages=pages,
        incoming_sources=incoming_sources,
        generated_faq=generated_faq,
    )
    print(f"Markdown report saved: {markdown_path}")
    html_path = write_html_report(
        output_dir=output_dir,
        pages=pages,
        incoming_sources=incoming_sources,
        generated_faq=generated_faq,
    )
    print(f"HTML report saved: {html_path}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Audit orphan pages and FAQ coverage on a website."
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
    source.add_argument(
        "--faq-only",
        help=(
            "Fetch only this page URL, generate FAQs and skip the full site audit."
        ),
    )
    parser.add_argument(
        "--faq-page",
        help=(
            "Generate FAQs with the OpenAI API for this exact page URL. "
            "No API call is made when this option is omitted."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated reports (default: output).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="Maximum sitemap URLs to audit (default: 100).",
    )
    parser.add_argument(
        "--include-path",
        action="append",
        default=[],
        help=(
            "Include only a URL path prefix before crawling. "
            "Repeat the option to include multiple paths."
        ),
    )
    parser.add_argument(
        "--exclude-path",
        action="append",
        default=[],
        help=(
            "Exclude a URL path prefix before crawling. "
            "Repeat the option to exclude multiple paths."
        ),
    )
    parser.add_argument(
        "--list-urls",
        action="store_true",
        help=(
            "List and group sitemap URLs after path exclusions without "
            "downloading page HTML."
        ),
    )
    return parser


def main() -> None:
    """Run the command-line tool."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error("--max-pages must be at least 1.")
    if args.list_urls and not args.url:
        parser.error("--list-urls can be used only together with --url.")
    included_paths = []
    for path in args.include_path:
        if not path.startswith("/"):
            parser.error("--include-path values must start with '/'.")
        normalized_path = path if path.endswith("/") else f"{path}/"
        included_paths.append(normalized_path)
    excluded_paths = []
    for path in args.exclude_path:
        if not path.startswith("/"):
            parser.error("--exclude-path values must start with '/'.")
        normalized_path = path if path.endswith("/") else f"{path}/"
        excluded_paths.append(normalized_path)
    if args.faq_page and not args.url:
        parser.error("--faq-page can currently be used only together with --url.")
    if args.faq_only:
        if not os.getenv("OPENAI_API_KEY"):
            parser.error("OPENAI_API_KEY is missing. Add it to the local .env file.")
        try:
            robots_policy = fetch_robots_policy(args.faq_only)
            crawl_delay = get_crawl_delay(robots_policy)
            print(f"Using crawl delay: {crawl_delay:g} seconds")
            html = fetch_page_html(
                args.faq_only,
                robots_policy,
                crawl_delay=crawl_delay,
            )
        except ValueError as error:
            parser.error(str(error))

        page_url = normalize_url(args.faq_only)
        page = Page(
            location=page_url,
            url=page_url,
            title=extract_title(html),
            heading=extract_h1(html),
            text=extract_main_text(html),
            internal_links=tuple(extract_internal_links(html, page_url)),
            language=extract_language(html),
            faq_status=detect_faq_status(html),
        )
        model = os.getenv("OPENAI_FAQ_MODEL", "gpt-5.6-luna")
        print(f"Generating FAQs for one page: {page.url}")
        print(f"Model: {model}")
        try:
            generated_faq = generate_faqs(page, model=model)
        except (OpenAIError, ValueError) as error:
            parser.error(f"OpenAI API request failed: {error}")

        for index, item in enumerate(generated_faq.result.items, start=1):
            print(f"\n{index}. {item.question}")
            print(item.answer)

        json_path, markdown_path, html_path = write_faq_only_reports(
            args.out_dir, generated_faq
        )
        print(f"\nJSON report saved: {json_path}")
        print(f"Markdown report saved: {markdown_path}")
        print(f"HTML report saved: {html_path}")
        return

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
        try:
            print_page_results(
                f"Found {len(pages)} HTML files:",
                pages,
                args.out_dir,
            )
        except ValueError as error:
            parser.error(str(error))
        return

    try:
        robots_policy = fetch_robots_policy(args.url)
        crawl_delay = get_crawl_delay(robots_policy)
        print(f"Using crawl delay: {crawl_delay:g} seconds")
        urls = fetch_sitemap_urls(
            args.url,
            robots_policy,
            crawl_delay=crawl_delay,
            max_pages=None if args.list_urls else args.max_pages,
            included_paths=tuple(included_paths),
            excluded_paths=tuple(excluded_paths),
        )
    except ValueError as error:
        parser.error(str(error))

    if args.list_urls:
        path_groups: dict[str, int] = {}
        for url in urls:
            path_parts = [part for part in urlsplit(url).path.split("/") if part]
            group = f"/{path_parts[0]}/" if path_parts else "/"
            path_groups[group] = path_groups.get(group, 0) + 1

        print(f"\nFound {len(urls)} sitemap URLs after exclusions.")
        print("\nURL groups:")
        for group, count in sorted(path_groups.items()):
            print(f"- {group}: {count}")
        print("\nURLs:")
        for url in urls:
            print(f"- {url}")
        return

    cached_pages = load_page_cache()
    current_domain = urlsplit(args.url).netloc
    updated_cache = {
        url: entry
        for url, entry in cached_pages.items()
        if urlsplit(url).netloc != current_domain
    }
    pages = []
    reused_page_count = 0
    for url in urls:
        normalized_url = normalize_url(url)
        cached_page = cached_pages.get(normalized_url)
        try:
            fetched_page = fetch_page(
                url,
                robots_policy,
                crawl_delay=crawl_delay,
                etag=cached_page.etag if cached_page else None,
                last_modified=(
                    cached_page.last_modified if cached_page else None
                ),
            )
        except RobotsDeniedError:
            print(f"Skipping URL forbidden by robots.txt: {url}")
            continue
        except ValueError as error:
            parser.error(str(error))

        if fetched_page.not_modified:
            if cached_page is None:
                parser.error(
                    f"Page returned 304 Not Modified without cached data: {url}"
                )
            pages.append(cached_page.page)
            updated_cache[normalized_url] = cached_page
            reused_page_count += 1
            continue

        if fetched_page.content is None:
            parser.error(f"Page returned no HTML content: {url}")
        html = fetched_page.content
        path = urlsplit(url).path
        page = Page(
            location=url,
            url=normalized_url,
            title=extract_title(html),
            heading=extract_h1(html),
            text=extract_main_text(html),
            internal_links=tuple(extract_internal_links(html, url)),
            language=extract_language(html),
            analyze_content=path not in EXCLUDED_CONTENT_PATHS,
            faq_status=detect_faq_status(html),
        )
        pages.append(page)
        updated_cache[normalized_url] = CachedPage(
            page=page,
            content_hash=calculate_content_hash(html),
            etag=fetched_page.etag,
            last_modified=fetched_page.last_modified,
        )

    save_page_cache(updated_cache)
    print(
        f"Reused {reused_page_count} unchanged pages from cache; "
        f"analyzed {len(pages) - reused_page_count} downloaded pages."
    )
    generated_faq = None
    if args.faq_page:
        requested_url = normalize_url(args.faq_page)
        page = next((item for item in pages if item.url == requested_url), None)
        if page is None:
            parser.error("--faq-page must match a URL found in the sitemap.")
        if not page.analyze_content:
            parser.error("The selected FAQ page is excluded from content analysis.")
        if not os.getenv("OPENAI_API_KEY"):
            parser.error("OPENAI_API_KEY is missing. Add it to the local .env file.")

        model = os.getenv("OPENAI_FAQ_MODEL", "gpt-5.6-luna")
        print(f"\nGenerating FAQs for: {page.url}")
        print(f"Model: {model}")
        try:
            generated_faq = generate_faqs(page, model=model)
        except (OpenAIError, ValueError) as error:
            parser.error(f"OpenAI API request failed: {error}")

        print("\nGenerated FAQ suggestions:")
        for index, item in enumerate(generated_faq.result.items, start=1):
            print(f"\n{index}. {item.question}")
            print(item.answer)

    print_page_results(
        f"\nFound {len(pages)} URLs in the sitemap:",
        pages,
        args.out_dir,
        generated_faq=generated_faq,
    )


if __name__ == "__main__":
    main()
