"""Persist page analysis data for incremental website audits."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from seolinker.faq import FaqStatus
from seolinker.models import Page


CACHE_VERSION = 1
DEFAULT_CACHE_PATH = Path(".seo-linker-cache/pages.json")


@dataclass(frozen=True)
class CachedPage:
    """One reusable page analysis and its HTTP validation metadata."""

    page: Page
    content_hash: str
    etag: str | None = None
    last_modified: str | None = None
    embedding_model: str | None = None
    embedding: tuple[float, ...] | None = None


def calculate_content_hash(content: bytes) -> str:
    """Return a stable SHA-256 hash for downloaded page content."""
    return hashlib.sha256(content).hexdigest()


def load_page_cache(path: Path = DEFAULT_CACHE_PATH) -> dict[str, CachedPage]:
    """Load a compatible cache or return an empty cache safely."""
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["version"] != CACHE_VERSION:
            return {}

        cached_pages = {}
        for url, entry in payload["pages"].items():
            page_data = entry["page"]
            cached_pages[url] = CachedPage(
                page=Page(
                    location=page_data["location"],
                    url=page_data["url"],
                    title=page_data["title"],
                    heading=page_data["heading"],
                    text=page_data["text"],
                    internal_links=tuple(page_data["internal_links"]),
                    language=page_data["language"],
                    analyze_content=page_data["analyze_content"],
                    faq_status=FaqStatus(page_data["faq_status"]),
                ),
                content_hash=entry["content_hash"],
                etag=entry.get("etag"),
                last_modified=entry.get("last_modified"),
                embedding_model=entry.get("embedding_model"),
                embedding=(
                    tuple(entry["embedding"])
                    if entry.get("embedding") is not None
                    else None
                ),
            )
        return cached_pages
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return {}


def save_page_cache(
    cached_pages: dict[str, CachedPage],
    path: Path = DEFAULT_CACHE_PATH,
) -> None:
    """Write the complete cache atomically to avoid partial files."""
    payload = {
        "version": CACHE_VERSION,
        "pages": {
            url: {
                "content_hash": entry.content_hash,
                "etag": entry.etag,
                "last_modified": entry.last_modified,
                "embedding_model": entry.embedding_model,
                "embedding": (
                    list(entry.embedding) if entry.embedding is not None else None
                ),
                "page": {
                    "location": entry.page.location,
                    "url": entry.page.url,
                    "title": entry.page.title,
                    "heading": entry.page.heading,
                    "text": entry.page.text,
                    "internal_links": list(entry.page.internal_links),
                    "language": entry.page.language,
                    "analyze_content": entry.page.analyze_content,
                    "faq_status": entry.page.faq_status.value,
                },
            }
            for url, entry in sorted(cached_pages.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
