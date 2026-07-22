"""Generate page-specific FAQ suggestions with the OpenAI Responses API."""

import json
from dataclasses import dataclass
from html import escape

from openai import OpenAI
from pydantic import BaseModel, Field

from seolinker.models import Page


MAX_CONTENT_CHARACTERS = 8_000


class FaqItem(BaseModel):
    """One generated FAQ question and answer."""

    question: str
    answer: str


class FaqResult(BaseModel):
    """A validated collection of three to five FAQ suggestions."""

    items: list[FaqItem] = Field(min_length=3, max_length=5)


@dataclass(frozen=True)
class GeneratedFaq:
    """Generated FAQs and reusable publication-ready output."""

    page: Page
    result: FaqResult
    model: str

    @property
    def visible_html(self) -> str:
        """Return a visible FAQ section ready to copy into a page."""
        items = []
        for item in self.result.items:
            items.extend(
                [
                    "  <details>",
                    f"    <summary>{escape(item.question)}</summary>",
                    f"    <p>{escape(item.answer)}</p>",
                    "  </details>",
                ]
            )
        return "\n".join(
            [
                '<section class="faq">',
                "  <h2>Frequently asked questions</h2>",
                *items,
                "</section>",
            ]
        )

    @property
    def schema_json(self) -> str:
        """Return FAQPage structured data as safe, formatted JSON."""
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item.question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item.answer,
                    },
                }
                for item in self.result.items
            ],
        }
        return (
            json.dumps(schema, ensure_ascii=False, indent=2)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )

    @property
    def json_ld_script(self) -> str:
        """Return a complete FAQPage JSON-LD script element."""
        return (
            '<script type="application/ld+json">\n'
            f"{self.schema_json}\n"
            "</script>"
        )


def generate_faqs(page: Page, model: str) -> GeneratedFaq:
    """Generate grounded FAQ suggestions for one page."""
    client = OpenAI()
    page_content = page.text[:MAX_CONTENT_CHARACTERS]
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Generate useful FAQ suggestions based only on the supplied "
                    "web page content. Do not add facts, claims, services or advice "
                    "that the page does not support. Use the same language as the "
                    "page. Write three to five natural questions with concise, "
                    "self-contained answers suitable for visible website content."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"URL: {page.url}\n"
                    f"Title: {page.title}\n"
                    f"H1: {page.heading}\n"
                    f"Language: {page.language or 'not detected'}\n\n"
                    f"Page content:\n{page_content}"
                ),
            },
        ],
        text_format=FaqResult,
    )
    if response.output_parsed is None:
        raise ValueError("The API response did not contain parsed FAQ data.")
    return GeneratedFaq(page=page, result=response.output_parsed, model=model)
