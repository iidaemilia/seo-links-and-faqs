"""Näkyvän FAQ-sisällön ja FAQPage-scheman tunnistus."""

import json
from enum import Enum
from typing import Any

from bs4 import BeautifulSoup


class FaqStatus(str, Enum):
    """Sivulta tunnistettu FAQ-sisällön ja scheman yhdistelmä."""

    NONE = "ei näkyvää FAQ:ta eikä schemaa"
    VISIBLE_ONLY = "näkyvä FAQ, schema puuttuu"
    SCHEMA_ONLY = "FAQPage-schema, näkyvä FAQ puuttuu"
    BOTH = "näkyvä FAQ ja FAQPage-schema"


def _has_visible_faq(soup: BeautifulSoup) -> bool:
    """Tunnista selvästi FAQ:ksi merkitty näkyvä sisältö."""
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
    """Etsi FAQPage-tyyppi sisäkkäisestä JSON-LD-rakenteesta."""
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
    """Tunnista kelvollisesta JSON-LD:stä FAQPage-tyyppi."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            structured_data = json.loads(script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        if _contains_faq_page_type(structured_data):
            return True

    return False


def detect_faq_status(html: bytes | str) -> FaqStatus:
    """Palauta sivun näkyvän FAQ-sisällön ja FAQPage-scheman tila."""
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
