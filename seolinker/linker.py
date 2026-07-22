"""Puuttuvien sisäisten linkkien ehdotusten muodostaminen."""

from dataclasses import dataclass

from seolinker.models import Page
from seolinker.similarity import SimilarityResult


@dataclass
class LinkSuggestion:
    """Yksi puuttuva suunnattu linkki kahden sivun välillä."""

    source: Page
    target: Page
    similarity: float


def suggest_missing_links(
    similarities: list[SimilarityResult], min_similarity: float
) -> list[LinkSuggestion]:
    """Ehdota riittävän samankaltaisten sivujen puuttuvat linkkisuunnat."""
    suggestions = []

    for result in similarities:
        if result.score < min_similarity:
            continue

        directions = (
            (result.source, result.target),
            (result.target, result.source),
        )
        for source, target in directions:
            if target.url in source.internal_links:
                continue
            suggestions.append(
                LinkSuggestion(
                    source=source,
                    target=target,
                    similarity=result.score,
                )
            )

    return suggestions
