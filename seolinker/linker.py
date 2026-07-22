"""Build suggestions for missing internal links."""

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from seolinker.models import Page
from seolinker.similarity import SimilarityResult


WORD_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
GENERIC_TARGET_WORDS = {
    "article",
    "articles",
    "page",
    "pages",
    "site",
    "sites",
    "website",
    "websites",
}


@dataclass
class LinkSuggestion:
    """One missing directed link between two pages."""

    source: Page
    target: Page
    similarity: float
    placement_type: str
    anchor_text: str
    context_sentence: str | None
    read_more_label: str | None


def _target_keywords(page: Page) -> set[str]:
    """Return meaningful words from the target page's H1 heading."""
    keywords = {
        match.group(0).casefold()
        for match in WORD_PATTERN.finditer(page.heading)
        if not match.group(0).isdigit()
    }
    if page.language == "en":
        keywords -= ENGLISH_STOP_WORDS
        keywords -= GENERIC_TARGET_WORDS
    return keywords


def _find_contextual_placement(source: Page, target: Page) -> tuple[str, str] | None:
    """Find a compact source passage containing two target heading words."""
    target_keywords = _target_keywords(target)
    if len(target_keywords) < 2:
        return None

    best_match = None
    for sentence in SENTENCE_BOUNDARY.split(source.text):
        words = list(WORD_PATTERN.finditer(sentence))
        matching_indexes = [
            index
            for index, word in enumerate(words)
            if word.group(0).casefold() in target_keywords
        ]

        for start_position, start_index in enumerate(matching_indexes):
            for end_index in matching_indexes[start_position + 1 :]:
                if end_index - start_index > 5:
                    break

                match_count = sum(
                    start_index <= index <= end_index for index in matching_indexes
                )
                word_span = end_index - start_index
                candidate_score = (match_count, -word_span)
                anchor = sentence[
                    words[start_index].start() : words[end_index].end()
                ]
                candidate = (candidate_score, anchor, sentence.strip())
                if best_match is None or candidate_score > best_match[0]:
                    best_match = candidate

    if best_match is None:
        return None
    return best_match[1], best_match[2]


def suggest_missing_links(
    similarities: list[SimilarityResult], min_similarity: float
) -> list[LinkSuggestion]:
    """Suggest missing link directions between sufficiently similar pages."""
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
            contextual_placement = _find_contextual_placement(source, target)
            if contextual_placement:
                anchor_text, context_sentence = contextual_placement
                placement_type = "contextual"
                read_more_label = None
            else:
                anchor_text = target.heading
                context_sentence = None
                placement_type = "read_more"
                read_more_label = "Lue myös" if target.language == "fi" else "Related reading"
            suggestions.append(
                LinkSuggestion(
                    source=source,
                    target=target,
                    similarity=result.score,
                    placement_type=placement_type,
                    anchor_text=anchor_text,
                    context_sentence=context_sentence,
                    read_more_label=read_more_label,
                )
            )

    return suggestions
