"""HTML-tiedostojen löytämiseen liittyvät toiminnot."""

from pathlib import Path

from bs4 import BeautifulSoup


def extract_title(html: bytes | str) -> str:
    """Poimi HTML-sisällön title-teksti."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "(title puuttuu)"


def extract_main_text(html: bytes | str) -> str:
    """Poimi HTML-sisällöstä analysoitava näkyvä pääteksti."""
    soup = BeautifulSoup(html, "html.parser")

    for unwanted in soup.find_all(["script", "style", "noscript", "nav", "footer"]):
        unwanted.decompose()

    content = soup.find("main") or soup.find("article") or soup.body
    if content is None:
        return ""

    return " ".join(content.stripped_strings)


def find_html_files(site_dir: Path) -> list[Path]:
    """Palauta sivustokansion HTML-tiedostot aakkosjärjestyksessä."""
    if not site_dir.exists():
        raise FileNotFoundError(f"Sivustokansiota ei löydy: {site_dir}")
    if not site_dir.is_dir():
        raise NotADirectoryError(f"Annettu polku ei ole kansio: {site_dir}")

    return sorted(site_dir.rglob("*.html"))
