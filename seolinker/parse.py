"""Discover HTML files and extract page content."""

from pathlib import Path

from bs4 import BeautifulSoup


def extract_language(html: bytes | str) -> str | None:
    """Extract the HTML document's primary two-letter language code."""
    soup = BeautifulSoup(html, "html.parser")
    html_element = soup.find("html")
    if html_element is None:
        return None

    language = html_element.get("lang")
    if not isinstance(language, str) or not language.strip():
        return None

    return language.strip().casefold().split("-", maxsplit=1)[0]


def extract_title(html: bytes | str) -> str:
    """Extract the title text from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "(title missing)"


def extract_h1(html: bytes | str) -> str:
    """Extract the page's first visible H1 heading."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if heading is None:
        return "(H1 missing)"
    return " ".join(heading.stripped_strings)


def extract_main_text(html: bytes | str) -> str:
    """Extract the visible main text used for content analysis."""
    soup = BeautifulSoup(html, "html.parser")

    for unwanted in soup.find_all(["script", "style", "noscript", "nav", "footer"]):
        unwanted.decompose()

    content = soup.find("main") or soup.find("article") or soup.body
    if content is None:
        return ""

    return " ".join(content.stripped_strings)


def find_html_files(site_dir: Path) -> list[Path]:
    """Return HTML files from a site directory in alphabetical order."""
    if not site_dir.exists():
        raise FileNotFoundError(f"Site directory not found: {site_dir}")
    if not site_dir.is_dir():
        raise NotADirectoryError(f"The provided path is not a directory: {site_dir}")

    return sorted(site_dir.rglob("*.html"))
