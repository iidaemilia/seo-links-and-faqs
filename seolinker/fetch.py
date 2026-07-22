"""Verkkosivuston URLien hakemiseen liittyvät toiminnot."""

from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


def fetch_page_html(url: str) -> bytes:
    """Lataa verkkosivu ja palauta sen HTML-sisältö."""
    request = Request(url, headers={"User-Agent": "SEO-Linker/0.1"})

    try:
        with urlopen(request, timeout=15) as response:
            html = response.read()
    except HTTPError as error:
        raise ValueError(
            f"Sivun haku epäonnistui: HTTP {error.code} ({url})"
        ) from error
    except URLError as error:
        raise ValueError(f"Sivun haku epäonnistui ({url}): {error.reason}") from error

    return html


def fetch_sitemap_urls(base_url: str) -> list[str]:
    """Hae sivuston sitemap.xml ja palauta sen saman domainin URLit."""
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        raise ValueError(f"Virheellinen sivuston URL: {base_url}")

    sitemap_url = urljoin(base_url, "/sitemap.xml")
    request = Request(sitemap_url, headers={"User-Agent": "SEO-Linker/0.1"})

    try:
        with urlopen(request, timeout=15) as response:
            sitemap_xml = response.read()
    except HTTPError as error:
        raise ValueError(
            f"Sitemapin haku epäonnistui: HTTP {error.code} ({sitemap_url})"
        ) from error
    except URLError as error:
        raise ValueError(f"Sitemapin haku epäonnistui: {error.reason}") from error

    try:
        root = ElementTree.fromstring(sitemap_xml)
    except ElementTree.ParseError as error:
        raise ValueError(f"Sitemap ei ole kelvollista XML:ää: {sitemap_url}") from error

    urls = []
    for location in root.findall("{*}url/{*}loc"):
        if location.text:
            url = location.text.strip()
            if urlparse(url).netloc == parsed_base_url.netloc:
                urls.append(url)

    return sorted(urls)
