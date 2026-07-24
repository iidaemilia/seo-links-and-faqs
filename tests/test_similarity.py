"""Tests for page similarity calculations."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from seolinker.models import Page
from seolinker.similarity import calculate_embedding_similarities


def make_page(location: str, text: str, analyze_content: bool = True) -> Page:
    """Create a minimal page fixture for similarity tests."""
    return Page(
        location=location,
        url=f"https://example.com/{location}",
        title=f"Title {location}",
        heading=f"Heading {location}",
        text=text,
        internal_links=(),
        analyze_content=analyze_content,
    )


class CalculateEmbeddingSimilaritiesTests(unittest.TestCase):
    """Verify semantic similarity calculation without live API requests."""

    def test_ranks_most_similar_page_pair_first(self) -> None:
        pages = [
            make_page("one", "First topic"),
            make_page("two", "Related topic"),
            make_page("three", "Different topic"),
        ]
        client = MagicMock()
        client.embeddings.create.return_value.data = [
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
            SimpleNamespace(index=1, embedding=[0.8, 0.2]),
            SimpleNamespace(index=2, embedding=[0.0, 1.0]),
        ]

        results = calculate_embedding_similarities(pages, client=client)

        self.assertEqual(
            (results[0].source.location, results[0].target.location),
            ("one", "two"),
        )
        self.assertGreater(results[0].score, results[1].score)
        client.embeddings.create.assert_called_once()

    def test_excludes_ineligible_pages_before_api_request(self) -> None:
        pages = [
            make_page("one", "Included"),
            make_page("excluded", "Not included", analyze_content=False),
            make_page("empty", "   "),
            make_page("two", "Also included"),
        ]
        client = MagicMock()
        client.embeddings.create.return_value.data = [
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
        ]

        calculate_embedding_similarities(pages, client=client)

        requested_documents = client.embeddings.create.call_args.kwargs["input"]
        self.assertEqual(len(requested_documents), 2)
        self.assertIn("Included", requested_documents[0])
        self.assertIn("Also included", requested_documents[1])

    def test_skips_api_request_when_fewer_than_two_pages_are_eligible(self) -> None:
        client = MagicMock()

        results = calculate_embedding_similarities(
            [make_page("one", "Only page")],
            client=client,
        )

        self.assertEqual(results, [])
        client.embeddings.create.assert_not_called()

    def test_rejects_wrong_number_of_embedding_vectors(self) -> None:
        pages = [
            make_page("one", "First"),
            make_page("two", "Second"),
        ]
        client = MagicMock()
        client.embeddings.create.return_value.data = [
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
        ]

        with self.assertRaisesRegex(ValueError, "different number of vectors"):
            calculate_embedding_similarities(pages, client=client)

    def test_requests_only_embeddings_missing_from_cache(self) -> None:
        pages = [
            make_page("one", "Cached topic"),
            make_page("two", "New related topic"),
            make_page("three", "Another new topic"),
        ]
        cached_embeddings = {
            pages[0].url: (1.0, 0.0),
        }
        client = MagicMock()
        client.embeddings.create.return_value.data = [
            SimpleNamespace(index=0, embedding=[0.8, 0.2]),
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
        ]

        calculate_embedding_similarities(
            pages,
            client=client,
            cached_embeddings=cached_embeddings,
        )

        requested_documents = client.embeddings.create.call_args.kwargs["input"]
        self.assertEqual(len(requested_documents), 2)
        self.assertEqual(set(cached_embeddings), {page.url for page in pages})


if __name__ == "__main__":
    unittest.main()
