"""Detect visible FAQ content and FAQPage structured data."""

import json
from enum import Enum
from typing import Any

from bs4 import BeautifulSoup


class FaqStatus(str, Enum):
    """Possible combinations of visible FAQ content and FAQPage schema."""

    NONE = "none"
    VISIBLE_ONLY = "visible_only"
    SCHEMA_ONLY = "schema_only"
    BOTH = "both"


FAQ_STATUS_LABELS = {
    FaqStatus.NONE: "No visible FAQ or FAQPage schema",
    FaqStatus.VISIBLE_ONLY: "Visible FAQ found; FAQPage schema is missing",
    FaqStatus.SCHEMA_ONLY: "FAQPage schema found; visible FAQ is missing",
    FaqStatus.BOTH: "Visible FAQ and FAQPage schema found",
}


def faq_status_label(status: FaqStatus) -> str:
    """Return a human-readable English label for an FAQ status."""
    return FAQ_STATUS_LABELS[status]


def _has_visible_faq(soup: BeautifulSoup) -> bool:
    """Detect content that is explicitly presented as a visible FAQ."""
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        heading_text = " ".join(heading.stripped_strings).casefold()
        if (
            "faq" in heading_text.split()
            or heading_text == "ukk"
            or "usein kysytyt kysymykset" in heading_text
            or "frequently asked questions" in heading_text
        ):
            return True

    for summary in soup.select("details > summary"):
        if summary.get_text(" ", strip=True).endswith("?"):
            return True

    return False


def _contains_faq_page_type(value: Any) -> bool:
    """Find an FAQPage type inside a nested JSON-LD structure."""
    if isinstance(value, dict):
        schema_type = value.get("@type")
        if schema_type == "FAQPage":
            return True
        if isinstance(schema_type, list) and "FAQPage" in schema_type:
            return True
        return any(_contains_faq_page_type(item) for item in value.values())

    if isinstance(value, list):
        return any(_contains_faq_page_type(item) for item in value)

    return False


def _has_faq_schema(soup: BeautifulSoup) -> bool:
    """Detect an FAQPage type in valid JSON-LD blocks."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            structured_data = json.loads(script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        if _contains_faq_page_type(structured_data):
            return True

    return False


def detect_faq_status(html: bytes | str) -> FaqStatus:
    """Return the page's visible FAQ and FAQPage schema status."""
    soup = BeautifulSoup(html, "html.parser")
    has_visible_faq = _has_visible_faq(soup)
    has_faq_schema = _has_faq_schema(soup)

    if has_visible_faq and has_faq_schema:
        return FaqStatus.BOTH
    if has_visible_faq:
        return FaqStatus.VISIBLE_ONLY
    if has_faq_schema:
        return FaqStatus.SCHEMA_ONLY
    return FaqStatus.NONE
