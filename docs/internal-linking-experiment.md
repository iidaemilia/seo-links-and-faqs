# Archived internal-linking experiment

This document preserves the design and lessons from an earlier SEO Linker
experiment. The production tool no longer calculates page similarity or
suggests internal links.

## What the experiment did

The original audit:

1. extracted each page's title, H1, main text and existing internal links;
2. compared every eligible page pair;
3. used either local TF-IDF cosine similarity or optional OpenAI embeddings;
4. removed directions where the target was already linked;
5. searched the source text for a possible contextual anchor;
6. fell back to a related-reading link when no contextual placement existed.

Embedding vectors were cached by URL, content and model so unchanged pages did
not need another API request.

The old command-line controls included:

```text
--similarity tfidf|embeddings
--min-similarity SCORE
OPENAI_EMBEDDING_MODEL
```

## Why it was removed

Whole-page similarity was useful for retrieving possible candidates, but it
was not a strong enough reason to recommend a link. A site with many closely
related pages produced too many plausible-looking pairs and too little
prioritisation.

The experiment exposed several important limitations:

- Similar pages may compete for the same search intent instead of helping each
  other.
- A valuable next-step link can connect pages that are not globally similar.
- Comparing every page pair grows quadratically.
- A similarity score does not explain the user's next information need.
- A matching target heading does not guarantee a natural source passage.
- Producing a suggestion in both directions creates noise.
- A global threshold cannot provide consistent quality across different sites.

## A stronger future direction

If internal-link recommendations are revisited, use similarity only for
candidate retrieval. A more credible pipeline would be:

1. Build the existing internal-link graph and identify orphaned or weakly
   linked pages.
2. Describe each eligible page with structured fields such as page type,
   primary topic, search intent, audience, journey stage and business priority.
3. Prefer real URL-to-query data from Google Search Console when available.
4. Search at paragraph level so every candidate has a concrete placement.
5. Retrieve a small candidate set with embeddings or lexical search.
6. Remove existing links, conflicting intents and illogical journey
   transitions.
7. Rerank only the shortlist using the structured page data.
8. Return zero to two suggestions with a target URL, source passage, anchor and
   user-centred rationale.

The page map and embeddings should be cached by content hash. An LLM should
evaluate only a small shortlist, never every possible page pair.

## Suggested data model

A future content inventory could use:

```csv
url,primary_query,intent,journey_stage,page_type,priority
/guides/example/,example question,informational,awareness,article,medium
/products/example/,example product,commercial,consideration,product,high
```

This archived design is intentionally separate from the active product. The
current SEO Linker scope is orphan-page detection, FAQ coverage auditing and
FAQ generation for a selected URL.
