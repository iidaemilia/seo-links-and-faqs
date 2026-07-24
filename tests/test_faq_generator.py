"""Tests for grounded FAQ generation."""

import unittest
from unittest.mock import patch

from seolinker.faq_generator import (
    FAQ_SYSTEM_PROMPT,
    FaqItem,
    FaqResult,
    generate_faqs,
)
from seolinker.models import Page


class GenerateFaqsTests(unittest.TestCase):
    """Verify the FAQ API request contains reader- and search-focused guidance."""

    @patch("seolinker.faq_generator.OpenAI")
    def test_uses_reader_need_prompt_and_page_context(
        self,
        mock_openai,
    ) -> None:
        page = Page(
            location="article",
            url="https://example.com/article",
            title="Article title",
            heading="Article heading",
            text="Supported article content.",
            internal_links=(),
            language="en",
        )
        mock_openai.return_value.responses.parse.return_value.output_parsed = (
            FaqResult(
                items=[
                    FaqItem(question="Question one?", answer="Answer one."),
                    FaqItem(question="Question two?", answer="Answer two."),
                    FaqItem(question="Question three?", answer="Answer three."),
                ]
            )
        )

        generate_faqs(page, model="test-model")

        request = mock_openai.return_value.responses.parse.call_args.kwargs
        self.assertEqual(request["input"][0]["content"], FAQ_SYSTEM_PROMPT)
        self.assertIn(
            "reader's likely information needs",
            request["input"][0]["content"],
        )
        self.assertIn(
            "distinct search intent",
            request["input"][0]["content"],
        )
        self.assertIn(
            "Supported article content.",
            request["input"][1]["content"],
        )
