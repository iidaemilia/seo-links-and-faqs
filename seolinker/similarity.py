"""Sivujen TF-IDF-samankaltaisuuden laskenta."""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from seolinker.models import Page


@dataclass
class SimilarityResult:
    """Yhden sivuparin laskettu samankaltaisuus."""

    source: Page
    target: Page
    score: float


def select_stop_words(pages: list[Page]) -> str | None:
    """Valitse turvallinen scikit-learnin stop-sanalista sivujen kielistä."""
    content_languages = {
        page.language
        for page in pages
        if page.analyze_content and page.text.strip() and page.language
    }
    if content_languages == {"en"}:
        return "english"
    return None


def calculate_tfidf_similarities(pages: list[Page]) -> list[SimilarityResult]:
    """Laske sisältösivujen kaikki TF-IDF-samankaltaisuudet."""
    content_pages = [
        page for page in pages if page.analyze_content and page.text.strip()
    ]
    if len(content_pages) < 2:
        return []

    documents = [f"{page.title} {page.text}" for page in content_pages]
    vectors = TfidfVectorizer(stop_words=select_stop_words(content_pages)).fit_transform(
        documents
    )
    similarity_matrix = cosine_similarity(vectors)

    results = []
    for source_index, source_page in enumerate(content_pages):
        for target_index in range(source_index + 1, len(content_pages)):
            results.append(
                SimilarityResult(
                    source=source_page,
                    target=content_pages[target_index],
                    score=float(similarity_matrix[source_index, target_index]),
                )
            )

    return sorted(results, key=lambda result: result.score, reverse=True)
