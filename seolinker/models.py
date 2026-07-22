"""Shared data structures for SEO Linker."""

from dataclasses import dataclass

from seolinker.faq import FaqStatus


@dataclass
class Page:
    """Data collected from one HTML page for analysis."""

    location: str
    url: str
    title: str
    heading: str
    text: str
    internal_links: tuple[str, ...]
    language: str | None = None
    analyze_content: bool = True
    faq_status: FaqStatus = FaqStatus.NONE

    @property
    def word_count(self) -> int:
        """Return the word count of the extracted main content."""
        return len(self.text.split())
