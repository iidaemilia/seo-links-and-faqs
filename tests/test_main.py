"""Tests for command-line analysis modes."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import main


class SiteAuditCliTests(unittest.TestCase):
    """Verify site audits report orphan and FAQ data."""

    def test_site_audit_reports_orphan_and_faq_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            arguments = [
                "main.py",
                "--site",
                "sample_site",
                "--out-dir",
                str(output_dir),
            ]
            with patch.object(sys, "argv", arguments):
                main.main()

            report = json.loads(
                (output_dir / "report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["mode"], "site_audit")
        self.assertIn("orphan_pages", report["summary"])
        self.assertIn("faq_gaps", report["summary"])
        self.assertEqual(
            set(report),
            {
                "generated_at",
                "mode",
                "settings",
                "summary",
                "pages",
                "generated_faq",
            },
        )


class ListUrlsCliTests(unittest.TestCase):
    """Verify sitemap inventory mode does not download page HTML."""

    @patch("main.fetch_page")
    @patch(
        "main.fetch_sitemap_urls",
        return_value=[
            "https://example.com/",
            "https://example.com/products/one/",
            "https://example.com/products/two/",
        ],
    )
    @patch("main.get_crawl_delay", return_value=1.0)
    @patch("main.fetch_robots_policy", return_value=MagicMock())
    def test_lists_grouped_urls_without_fetching_pages(
        self,
        mock_fetch_robots_policy,
        mock_get_crawl_delay,
        mock_fetch_sitemap_urls,
        mock_fetch_page,
    ) -> None:
        arguments = [
            "main.py",
            "--url",
            "https://example.com",
            "--list-urls",
            "--include-path",
            "/products/",
            "--exclude-path",
            "/en/",
        ]

        with (
            patch.object(sys, "argv", arguments),
            patch("builtins.print") as mock_print,
        ):
            main.main()

        mock_fetch_sitemap_urls.assert_called_once_with(
            "https://example.com",
            mock_fetch_robots_policy.return_value,
            crawl_delay=1.0,
            max_pages=None,
            included_paths=("/products/",),
            excluded_paths=("/en/",),
        )
        mock_fetch_page.assert_not_called()
        printed_lines = [call.args[0] for call in mock_print.call_args_list]
        self.assertIn("- /products/: 2", printed_lines)


if __name__ == "__main__":
    unittest.main()
