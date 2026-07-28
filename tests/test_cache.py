"""Tests for the persistent page analysis cache."""

import json
import tempfile
import unittest
from pathlib import Path

from seolinker.cache import (
    CACHE_VERSION,
    CachedPage,
    calculate_content_hash,
    load_page_cache,
    save_page_cache,
)
from seolinker.faq import FaqStatus
from seolinker.models import Page


def make_cached_page() -> CachedPage:
    """Create a complete cache entry fixture."""
    return CachedPage(
        page=Page(
            location="/article/",
            url="https://example.com/article/",
            title="Cached article",
            heading="Article heading",
            text="Cached page content.",
            internal_links=("https://example.com/other/",),
            language="en",
            analyze_content=True,
            faq_status=FaqStatus.VISIBLE_ONLY,
        ),
        content_hash=calculate_content_hash(b"<html>content</html>"),
        etag='"page-v1"',
        last_modified="Wed, 23 Jul 2026 12:00:00 GMT",
    )


class PageCacheTests(unittest.TestCase):
    """Verify cache persistence and safe invalidation."""

    def test_round_trips_complete_page_data(self) -> None:
        entry = make_cached_page()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "pages.json"

            save_page_cache({entry.page.url: entry}, path)
            loaded = load_page_cache(path)

        self.assertEqual(loaded, {entry.page.url: entry})

    def test_returns_empty_cache_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "missing.json"

            self.assertEqual(load_page_cache(path), {})

    def test_returns_empty_cache_when_json_is_broken(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "pages.json"
            path.write_text("{broken", encoding="utf-8")

            self.assertEqual(load_page_cache(path), {})

    def test_returns_empty_cache_for_another_cache_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "pages.json"
            path.write_text(
                json.dumps({"version": CACHE_VERSION + 1, "pages": {}}),
                encoding="utf-8",
            )

            self.assertEqual(load_page_cache(path), {})


if __name__ == "__main__":
    unittest.main()
