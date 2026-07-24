"""Fetch website URLs and HTML over HTTP."""

import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

HTTP_USER_AGENT = "SEO-Linker/0.1"
ROBOTS_USER_AGENT = "SEO-Linker"
DEFAULT_CRAWL_DELAY = 1.0
DEFAULT_MAX_PAGES = 100
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_SITEMAP_BYTES = 5 * 1024 * 1024
MAX_ROBOTS_BYTES = 512 * 1024
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
SITEMAP_CONTENT_TYPES = {
    "application/xml",
    "text/xml",
    "application/rss+xml",
}
ROBOTS_CONTENT_TYPES = {"text/plain"}


class RobotsDeniedError(ValueError):
    """A URL is disallowed by the website's robots.txt rules."""


class UnsafeRedirectError(ValueError):
    """A redirect would leave the approved website boundary."""


@dataclass(frozen=True)
class FetchedPage:
    """Downloaded page content and HTTP cache validation metadata."""

    content: bytes | None
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


class SafeRedirectHandler(HTTPRedirectHandler):
    """Allow redirects only within one domain and its robots.txt rules."""

    def __init__(
        self,
        allowed_netloc: str,
        policy: RobotFileParser | None = None,
    ) -> None:
        super().__init__()
        self.allowed_netloc = allowed_netloc
        self.policy = policy

    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> Request | None:
        parsed_url = urlparse(newurl)
        if (
            parsed_url.scheme not in {"http", "https"}
            or parsed_url.netloc != self.allowed_netloc
        ):
            raise UnsafeRedirectError(
                f"Redirect blocked because it leaves "
                f"{self.allowed_netloc}: {newurl}"
            )
        ensure_robots_allowed(newurl, self.policy)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_safely(
    request: Request,
    policy: RobotFileParser | None = None,
) -> object:
    """Open a request without allowing unsafe redirects."""
    request_netloc = urlparse(request.full_url).netloc
    opener = build_opener(SafeRedirectHandler(request_netloc, policy))
    return opener.open(request, timeout=15)


def read_limited(
    response: object,
    max_bytes: int,
    resource_name: str,
    url: str,
) -> bytes:
    """Read a response without allowing it to exceed a memory safety limit."""
    content = response.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError(
            f"{resource_name} exceeds the {max_bytes}-byte download "
            f"safety limit: {url}"
        )
    return content


def ensure_content_type(
    response: object,
    allowed_types: set[str],
    resource_name: str,
    url: str,
) -> None:
    """Reject a response whose declared media type is unexpected."""
    content_type = response.headers.get_content_type().lower()
    if content_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(
            f"{resource_name} returned unsupported content type "
            f"'{content_type}' ({url}). Expected one of: {allowed}."
        )


def fetch_robots_policy(base_url: str) -> RobotFileParser:
    """Download and parse robots.txt for a website."""
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        raise ValueError(f"Invalid website URL: {base_url}")

    robots_url = urljoin(base_url, "/robots.txt")
    request = Request(robots_url, headers={"User-Agent": HTTP_USER_AGENT})
    policy = RobotFileParser()
    policy.set_url(robots_url)

    try:
        with open_safely(request) as response:
            ensure_content_type(
                response,
                ROBOTS_CONTENT_TYPES,
                "robots.txt",
                robots_url,
            )
            robots_text = read_limited(
                response,
                MAX_ROBOTS_BYTES,
                "robots.txt",
                robots_url,
            ).decode("utf-8", errors="replace")
    except HTTPError as error:
        if error.code in {404, 410}:
            policy.parse([])
            return policy
        raise ValueError(
            f"Robots.txt request failed: HTTP {error.code} ({robots_url})"
        ) from error
    except URLError as error:
        raise ValueError(
            f"Robots.txt request failed ({robots_url}): {error.reason}"
        ) from error

    policy.parse(robots_text.splitlines())
    return policy


def ensure_robots_allowed(url: str, policy: RobotFileParser | None) -> None:
    """Raise an error when robots.txt forbids fetching a URL."""
    if policy is not None and not policy.can_fetch(ROBOTS_USER_AGENT, url):
        raise RobotsDeniedError(
            f"robots.txt forbids SEO-Linker from fetching: {url}"
        )


def get_crawl_delay(
    policy: RobotFileParser, default: float = DEFAULT_CRAWL_DELAY
) -> float:
    """Return the website's crawl delay or a polite default."""
    configured_delay = policy.crawl_delay(ROBOTS_USER_AGENT)
    return float(configured_delay) if configured_delay is not None else default


def fetch_page_html(
    url: str,
    policy: RobotFileParser | None = None,
    crawl_delay: float = 0,
) -> bytes:
    """Download a web page and return its HTML content."""
    result = fetch_page(url, policy=policy, crawl_delay=crawl_delay)
    if result.content is None:
        raise ValueError(f"Page returned no HTML content: {url}")
    return result.content


def fetch_page(
    url: str,
    policy: RobotFileParser | None = None,
    crawl_delay: float = 0,
    etag: str | None = None,
    last_modified: str | None = None,
) -> FetchedPage:
    """Download a page or report that its cached version is still current."""
    ensure_robots_allowed(url, policy)
    if crawl_delay > 0:
        time.sleep(crawl_delay)
    headers = {"User-Agent": HTTP_USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    request = Request(url, headers=headers)

    try:
        with open_safely(request, policy) as response:
            ensure_content_type(
                response,
                HTML_CONTENT_TYPES,
                "Page",
                url,
            )
            html = read_limited(
                response,
                MAX_PAGE_BYTES,
                "Page",
                url,
            )
            response_etag = response.headers.get("ETag")
            response_last_modified = response.headers.get("Last-Modified")
    except HTTPError as error:
        if error.code == 304:
            return FetchedPage(
                content=None,
                etag=error.headers.get("ETag") or etag,
                last_modified=(
                    error.headers.get("Last-Modified") or last_modified
                ),
                not_modified=True,
            )
        raise ValueError(
            f"Page request failed: HTTP {error.code} ({url})"
        ) from error
    except URLError as error:
        raise ValueError(f"Page request failed ({url}): {error.reason}") from error

    return FetchedPage(
        content=html,
        etag=response_etag,
        last_modified=response_last_modified,
    )


def fetch_sitemap_urls(
    base_url: str,
    policy: RobotFileParser | None = None,
    crawl_delay: float = 0,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[str]:
    """Fetch sitemap.xml and return URLs from the same domain."""
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        raise ValueError(f"Invalid website URL: {base_url}")

    sitemap_url = urljoin(base_url, "/sitemap.xml")
    ensure_robots_allowed(sitemap_url, policy)
    if crawl_delay > 0:
        time.sleep(crawl_delay)
    request = Request(sitemap_url, headers={"User-Agent": HTTP_USER_AGENT})

    try:
        with open_safely(request, policy) as response:
            ensure_content_type(
                response,
                SITEMAP_CONTENT_TYPES,
                "Sitemap",
                sitemap_url,
            )
            sitemap_xml = read_limited(
                response,
                MAX_SITEMAP_BYTES,
                "Sitemap",
                sitemap_url,
            )
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

    if len(urls) > max_pages:
        raise ValueError(
            f"Sitemap contains {len(urls)} same-domain URLs, exceeding the "
            f"safety limit of {max_pages}. Use --max-pages to raise the limit "
            "deliberately."
        )

    return sorted(urls)
