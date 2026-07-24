"""Calculate TF-IDF similarity between pages."""

from dataclasses import dataclass

from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from seolinker.models import Page

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
MAX_EMBEDDING_CHARACTERS = 8_000


@dataclass
class SimilarityResult:
    """Calculated similarity for one page pair."""

    source: Page
    target: Page
    score: float


def select_stop_words(pages: list[Page]) -> str | None:
    """Select a safe scikit-learn stop-word list from page languages."""
    content_languages = {
        page.language
        for page in pages
        if page.analyze_content and page.text.strip() and page.language
    }
    if content_languages == {"en"}:
        return "english"
    return None


def calculate_tfidf_similarities(pages: list[Page]) -> list[SimilarityResult]:
    """Calculate all TF-IDF similarities between eligible content pages."""
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


def calculate_embedding_similarities(
    pages: list[Page],
    model: str = DEFAULT_EMBEDDING_MODEL,
    client: OpenAI | None = None,
    cached_embeddings: dict[str, tuple[float, ...]] | None = None,
) -> list[SimilarityResult]:
    """Calculate semantic similarities with OpenAI embedding vectors."""
    content_pages = [
        page for page in pages if page.analyze_content and page.text.strip()
    ]
    if len(content_pages) < 2:
        return []

    embeddings = cached_embeddings if cached_embeddings is not None else {}
    missing_pages = [page for page in content_pages if page.url not in embeddings]
    if missing_pages:
        documents = [
            f"{page.title}\n{page.heading}\n{page.text}"[
                :MAX_EMBEDDING_CHARACTERS
            ].replace("\n", " ")
            for page in missing_pages
        ]
        openai_client = client or OpenAI()
        response = openai_client.embeddings.create(
            model=model,
            input=documents,
            encoding_format="float",
        )
        ordered_embeddings = [
            item.embedding
            for item in sorted(response.data, key=lambda item: item.index)
        ]
        if len(ordered_embeddings) != len(missing_pages):
            raise ValueError(
                "The embeddings API returned a different number of vectors "
                "than requested."
            )
        for page, embedding in zip(
            missing_pages,
            ordered_embeddings,
            strict=True,
        ):
            embeddings[page.url] = tuple(embedding)

    similarity_matrix = cosine_similarity(
        [embeddings[page.url] for page in content_pages]
    )
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
