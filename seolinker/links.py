"""Sisäisten linkkien poimintaan ja normalisointiin liittyvät toiminnot."""

from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from seolinker.models import Page


def normalize_url(url: str) -> str:
    """Poista URLista fragmentti ja kyselyparametrit vertailua varten."""
    url_without_fragment, _ = urldefrag(url)
    parsed = urlsplit(url_without_fragment)
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            "",
            "",
        )
    )


def extract_internal_links(html: bytes | str, page_url: str) -> list[str]:
    """Palauta sivun uniikit saman domainin sisäiset linkkikohteet."""
    soup = BeautifulSoup(html, "html.parser")
    normalized_page_url = normalize_url(page_url)
    page_domain = urlsplit(normalized_page_url).netloc
    internal_links = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        absolute_url = urljoin(normalized_page_url, href)
        parsed_url = urlsplit(absolute_url)

        if parsed_url.scheme not in {"http", "https"}:
            continue

        normalized_link = normalize_url(absolute_url)
        if urlsplit(normalized_link).netloc != page_domain:
            continue
        if normalized_link == normalized_page_url:
            continue

        internal_links.add(normalized_link)

    return sorted(internal_links)


def find_incoming_link_sources(pages: list[Page]) -> dict[str, set[str]]:
    """Palauta kutakin tunnettua sivua linkittävien sivujen URLit."""
    incoming_sources = {page.url: set() for page in pages}

    for page in pages:
        for target_url in page.internal_links:
            if target_url in incoming_sources:
                incoming_sources[target_url].add(page.url)

    return incoming_sources
