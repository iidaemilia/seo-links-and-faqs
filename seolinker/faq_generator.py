"""Generate page-specific FAQ suggestions with the OpenAI Responses API."""

import json
from dataclasses import dataclass
from html import escape

from openai import OpenAI
from pydantic import BaseModel, Field

from seolinker.models import Page


MAX_CONTENT_CHARACTERS = 8_000
FAQ_SYSTEM_PROMPT = """
Generate three to five FAQ questions and answers for the supplied web page.

Choose questions based primarily on the reader's likely information needs, not
on the page's section headings or internal structure. Think about what a person
might genuinely search for before, during or after reading this page.

Prioritise questions that:
- express a concrete problem, uncertainty, comparison or decision;
- can stand alone as natural search queries;
- address useful implications, limitations or next steps;
- add value beyond simply restating the article's headings;
- can be answered accurately from the supplied page content.

You may infer a realistic reader question even when the exact question does not
appear on the page, but every factual statement in the answer must be supported
by the supplied content.

Avoid:
- questions about the article or tool's internal structure;
- near-duplicate questions;
- generic definitions unless they serve a clear reader need;
- keyword stuffing or unnatural search-engine phrasing;
- claims about rankings, citations, AI visibility or outcomes that the page
  cannot support.

Write in the same language as the page. Start each answer with a direct response,
then provide enough explanation to make it useful without the surrounding
article. Include relevant limitations or uncertainty where necessary.

Before returning the final set, select the questions that provide the strongest
combination of reader usefulness, distinct search intent and support from the
source content.
""".strip()


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
                "content": FAQ_SYSTEM_PROMPT,
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
