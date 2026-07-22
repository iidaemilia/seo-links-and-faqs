"""Fetch website URLs and HTML over HTTP."""

from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


def fetch_page_html(url: str) -> bytes:
    """Download a web page and return its HTML content."""
    request = Request(url, headers={"User-Agent": "SEO-Linker/0.1"})

    try:
        with urlopen(request, timeout=15) as response:
            html = response.read()
    except HTTPError as error:
        raise ValueError(
            f"Page request failed: HTTP {error.code} ({url})"
        ) from error
    except URLError as error:
        raise ValueError(f"Page request failed ({url}): {error.reason}") from error

    return html


def fetch_sitemap_urls(base_url: str) -> list[str]:
    """Fetch sitemap.xml and return URLs from the same domain."""
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        raise ValueError(f"Invalid website URL: {base_url}")

    sitemap_url = urljoin(base_url, "/sitemap.xml")
    request = Request(sitemap_url, headers={"User-Agent": "SEO-Linker/0.1"})

    try:
        with urlopen(request, timeout=15) as response:
            sitemap_xml = response.read()
    except HTTPError as error:
        raise ValueError(
            f"Sitemap request failed: HTTP {error.code} ({sitemap_url})"
        ) from error
    except URLError as error:
        raise ValueError(f"Sitemap request failed: {error.reason}") from error

    try:
        root = ElementTree.fromstring(sitemap_xml)
    except ElementTree.ParseError as error:
        raise ValueError(f"Sitemap is not valid XML: {sitemap_url}") from error

    urls = []
    for location in root.findall("{*}url/{*}loc"):
        if location.text:
            url = location.text.strip()
            if urlparse(url).netloc == parsed_base_url.netloc:
                urls.append(url)

    return sorted(urls)
