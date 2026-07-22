"""SEO Linkerin yhteiset tietorakenteet."""

from dataclasses import dataclass

from seolinker.faq import FaqStatus


@dataclass
class Page:
    """Yhdeltä HTML-sivulta analyysia varten kerätyt tiedot."""

    location: str
    url: str
    title: str
    text: str
    internal_links: tuple[str, ...]
    analyze_content: bool = True
    faq_status: FaqStatus = FaqStatus.NONE

    @property
    def word_count(self) -> int:
        """Palauta päätekstin sanamäärä."""
        return len(self.text.split())
