"""Tests for safe website fetching."""

import unittest
from email.message import Message
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request
from urllib.robotparser import RobotFileParser

from seolinker.fetch import (
    SafeRedirectHandler,
    UnsafeRedirectError,
    ensure_content_type,
    fetch_page,
    fetch_page_html,
    fetch_sitemap_urls,
    get_crawl_delay,
    read_limited,
)


class FetchPageHtmlTests(unittest.TestCase):
    """Verify that robots.txt rules are enforced before network requests."""

    def setUp(self) -> None:
        self.policy = RobotFileParser()
        self.policy.parse(
            [
                "User-agent: SEO-Linker",
                "Disallow: /private/",
                "Allow: /",
            ]
        )

    @patch("seolinker.fetch.build_opener")
    @patch("seolinker.fetch.time.sleep")
    def test_fetches_allowed_page_after_crawl_delay(
        self,
        mock_sleep: MagicMock,
        mock_build_opener: MagicMock,
    ) -> None:
        response = MagicMock()
        response.read.return_value = b"<html>Allowed</html>"
        response.headers.get_content_type.return_value = "text/html"
        mock_build_opener.return_value.open.return_value.__enter__.return_value = (
            response
        )

        html = fetch_page_html(
            "https://example.com/public/",
            self.policy,
            crawl_delay=2,
        )

        self.assertEqual(html, b"<html>Allowed</html>")
        mock_sleep.assert_called_once_with(2)
        mock_build_opener.return_value.open.assert_called_once()

    @patch("seolinker.fetch.build_opener")
    def test_does_not_fetch_disallowed_page(
        self, mock_build_opener: MagicMock
    ) -> None:
        with self.assertRaisesRegex(ValueError, "robots.txt forbids"):
            fetch_page_html("https://example.com/private/page", self.policy)

        mock_build_opener.assert_not_called()

    def test_uses_robots_crawl_delay(self) -> None:
        policy = RobotFileParser()
        policy.parse(
            [
                "User-agent: SEO-Linker",
                "Crawl-delay: 3",
            ]
        )

        self.assertEqual(get_crawl_delay(policy), 3.0)

    def test_uses_default_when_crawl_delay_is_missing(self) -> None:
        self.assertEqual(get_crawl_delay(self.policy), 1.0)

    @patch("seolinker.fetch.build_opener")
    def test_returns_not_modified_for_cached_page(
        self,
        mock_build_opener: MagicMock,
    ) -> None:
        response_headers = Message()
        response_headers["ETag"] = '"page-v1"'
        mock_build_opener.return_value.open.side_effect = HTTPError(
            "https://example.com/public/",
            304,
            "Not Modified",
            response_headers,
            None,
        )

        result = fetch_page(
            "https://example.com/public/",
            self.policy,
            etag='"page-v1"',
            last_modified="Wed, 23 Jul 2026 12:00:00 GMT",
        )

        self.assertTrue(result.not_modified)
        self.assertIsNone(result.content)
        request = mock_build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("If-none-match"), '"page-v1"')
        self.assertEqual(
            request.get_header("If-modified-since"),
            "Wed, 23 Jul 2026 12:00:00 GMT",
        )

    @patch("seolinker.fetch.build_opener")
    def test_returns_validation_metadata_for_changed_page(
        self,
        mock_build_opener: MagicMock,
    ) -> None:
        response = MagicMock()
        response.read.return_value = b"<html>Changed</html>"
        response.headers.get_content_type.return_value = "text/html"
        response.headers.get.side_effect = lambda name: {
            "ETag": '"page-v2"',
            "Last-Modified": "Thu, 24 Jul 2026 12:00:00 GMT",
        }.get(name)
        mock_build_opener.return_value.open.return_value.__enter__.return_value = (
            response
        )

        result = fetch_page(
            "https://example.com/public/",
            self.policy,
            etag='"page-v1"',
        )

        self.assertFalse(result.not_modified)
        self.assertEqual(result.content, b"<html>Changed</html>")
        self.assertEqual(result.etag, '"page-v2"')
        self.assertEqual(
            result.last_modified,
            "Thu, 24 Jul 2026 12:00:00 GMT",
        )


class FetchSitemapUrlsTests(unittest.TestCase):
    """Verify that sitemap audits stay within the configured safety limit."""

    @patch("seolinker.fetch.build_opener")
    def test_returns_urls_within_limit(
        self, mock_build_opener: MagicMock
    ) -> None:
        response = MagicMock()
        response.read.return_value = (
            b"<urlset>"
            b"<url><loc>https://example.com/one</loc></url>"
            b"<url><loc>https://example.com/two</loc></url>"
            b"</urlset>"
        )
        response.headers.get_content_type.return_value = "application/xml"
        mock_build_opener.return_value.open.return_value.__enter__.return_value = (
            response
        )

        urls = fetch_sitemap_urls("https://example.com", max_pages=2)

        self.assertEqual(
            urls,
            ["https://example.com/one", "https://example.com/two"],
        )

    @patch("seolinker.fetch.build_opener")
    def test_returns_urls_from_same_domain_sitemap_index(
        self, mock_build_opener: MagicMock
    ) -> None:
        index_response = MagicMock()
        index_response.read.return_value = (
            b"<sitemapindex>"
            b"<sitemap><loc>https://example.com/pages.xml</loc></sitemap>"
            b"<sitemap><loc>https://other.example/external.xml</loc></sitemap>"
            b"</sitemapindex>"
        )
        index_response.headers.get_content_type.return_value = "application/xml"
        pages_response = MagicMock()
        pages_response.read.return_value = (
            b"<urlset>"
            b"<url><loc>https://example.com/one</loc></url>"
            b"<url><loc>https://example.com/two</loc></url>"
            b"</urlset>"
        )
        pages_response.headers.get_content_type.return_value = "application/xml"
        mock_build_opener.return_value.open.return_value.__enter__.side_effect = [
            index_response,
            pages_response,
        ]

        urls = fetch_sitemap_urls("https://example.com", max_pages=2)

        self.assertEqual(
            urls,
            ["https://example.com/one", "https://example.com/two"],
        )
        self.assertEqual(mock_build_opener.return_value.open.call_count, 2)

    @patch("seolinker.fetch.build_opener")
    def test_excludes_paths_before_applying_page_limit(
        self, mock_build_opener: MagicMock
    ) -> None:
        response = MagicMock()
        response.read.return_value = (
            b"<urlset>"
            b"<url><loc>https://example.com/en/one</loc></url>"
            b"<url><loc>https://example.com/fi/one</loc></url>"
            b"</urlset>"
        )
        response.headers.get_content_type.return_value = "application/xml"
        mock_build_opener.return_value.open.return_value.__enter__.return_value = (
            response
        )

        urls = fetch_sitemap_urls(
            "https://example.com",
            max_pages=1,
            excluded_paths=("/en/",),
        )

        self.assertEqual(urls, ["https://example.com/fi/one"])

    @patch("seolinker.fetch.build_opener")
    def test_includes_paths_before_applying_page_limit(
        self, mock_build_opener: MagicMock
    ) -> None:
        response = MagicMock()
        response.read.return_value = (
            b"<urlset>"
            b"<url><loc>https://example.com/articles/one</loc></url>"
            b"<url><loc>https://example.com/products/one</loc></url>"
            b"<url><loc>https://example.com/products/two</loc></url>"
            b"</urlset>"
        )
        response.headers.get_content_type.return_value = "application/xml"
        mock_build_opener.return_value.open.return_value.__enter__.return_value = (
            response
        )

        urls = fetch_sitemap_urls(
            "https://example.com",
            max_pages=2,
            included_paths=("/products/",),
        )

        self.assertEqual(
            urls,
            [
                "https://example.com/products/one",
                "https://example.com/products/two",
            ],
        )

    @patch("seolinker.fetch.build_opener")
    def test_rejects_sitemap_over_limit(
        self, mock_build_opener: MagicMock
    ) -> None:
        response = MagicMock()
        response.read.return_value = (
            b"<urlset>"
            b"<url><loc>https://example.com/one</loc></url>"
            b"<url><loc>https://example.com/two</loc></url>"
            b"</urlset>"
        )
        response.headers.get_content_type.return_value = "application/xml"
        mock_build_opener.return_value.open.return_value.__enter__.return_value = (
            response
        )

        with self.assertRaisesRegex(ValueError, "exceeding the safety limit"):
            fetch_sitemap_urls("https://example.com", max_pages=1)


class SafeRedirectHandlerTests(unittest.TestCase):
    """Verify redirect boundaries before redirected pages are requested."""

    def setUp(self) -> None:
        self.request = Request("http://example.com/start")
        self.policy = RobotFileParser()
        self.policy.parse(
            [
                "User-agent: SEO-Linker",
                "Disallow: /private/",
            ]
        )
        self.handler = SafeRedirectHandler("example.com", self.policy)

    def test_allows_same_domain_redirect(self) -> None:
        redirected_request = self.handler.redirect_request(
            self.request,
            None,
            301,
            "Moved",
            {},
            "https://example.com/public/",
        )

        self.assertEqual(
            redirected_request.full_url,
            "https://example.com/public/",
        )

    def test_blocks_cross_domain_redirect(self) -> None:
        with self.assertRaisesRegex(UnsafeRedirectError, "leaves example.com"):
            self.handler.redirect_request(
                self.request,
                None,
                302,
                "Found",
                {},
                "https://other.example/private/",
            )

    def test_blocks_redirect_forbidden_by_robots(self) -> None:
        with self.assertRaisesRegex(ValueError, "robots.txt forbids"):
            self.handler.redirect_request(
                self.request,
                None,
                302,
                "Found",
                {},
                "https://example.com/private/page",
            )


class ReadLimitedTests(unittest.TestCase):
    """Verify response bodies cannot exceed their memory safety limit."""

    def test_accepts_content_at_limit(self) -> None:
        response = MagicMock()
        response.read.return_value = b"1234"

        content = read_limited(
            response,
            max_bytes=4,
            resource_name="Page",
            url="https://example.com/",
        )

        self.assertEqual(content, b"1234")
        response.read.assert_called_once_with(5)

    def test_rejects_content_over_limit(self) -> None:
        response = MagicMock()
        response.read.return_value = b"12345"

        with self.assertRaisesRegex(ValueError, "download safety limit"):
            read_limited(
                response,
                max_bytes=4,
                resource_name="Page",
                url="https://example.com/",
            )


class EnsureContentTypeTests(unittest.TestCase):
    """Verify non-HTML page responses are rejected before reading."""

    def test_accepts_html_content_type(self) -> None:
        response = MagicMock()
        response.headers.get_content_type.return_value = "text/html"

        ensure_content_type(
            response,
            {"text/html", "application/xhtml+xml"},
            "Page",
            "https://example.com/",
        )

    def test_rejects_pdf_content_type(self) -> None:
        response = MagicMock()
        response.headers.get_content_type.return_value = "application/pdf"

        with self.assertRaisesRegex(ValueError, "unsupported content type"):
            ensure_content_type(
                response,
                {"text/html", "application/xhtml+xml"},
                "Page",
                "https://example.com/file.pdf",
            )

        response.read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
