"""
The answer step: turns the 3 fetched chunks into an answer, or refuses.

This is the Week 3 extractive answerer. It has no LLM. It picks the single best
sentence (or ingredient-table row) out of the fetched chunks and quotes it,
citing the chunk it came from.

WEEK 6 - THE ONE CHANGE BEING MEASURED is how that sentence gets picked:

    picker="cosine"          BEFORE. Embedding similarity to the question, blended
                             with the chunk's similarity. Rewards sharing words.
    picker="cross_encoder"   AFTER. A cross-encoder reads the question and each
                             candidate TOGETHER and scores "does this answer it?".

The gates, the candidates, search and everything else are identical for both.

    GATE 1  vocabulary   - a meaningful question word that appears nowhere in the
                           whole corpus means the corpus cannot hold the answer
    GATE 2  closeness    - at least one fetched chunk must be similar enough
    GATE 3  sentence     - the chosen sentence itself must be similar enough

One small adjustment so the answerer does not depend on which retriever ran:
it measures each chunk's closeness to the question itself (cosine similarity)
instead of trusting the retriever's score. A hybrid RRF score like 0.032 and a
cosine score like 0.62 mean completely different things, and the answer step
must behave identically before and after the retrieval change, or the
before/after comparison would be measuring two changes.
"""

import re

import numpy as np

from .config import CHUNK_WEIGHT, MIN_SCORE_TO_ANSWER, MIN_SENTENCE_SCORE
from .embedder import cross_encoder, embed

PICKERS = ("cosine", "cross_encoder")

STOPWORDS = frozenset("""
about above after again against all also although always among and any are
because been before being below between both but can cannot come comes could
did does doing done down during each either else even ever every few for from
get gets give gives goes going had has have having her here hers him his how
however into its itself just keep keeps let lets like long made make makes many
may might more most much must need needs neither never next nor not now off
once only onto other others ought our ours out over own put puts rather said
same say says shall she should since some such take takes than that the their
theirs them themselves then there these they this those though through thus too
under until upon use used uses using very want wants was were what when where
whether which while who whom whose why will with within without would you your
yours
""".split())

REFUSAL = (
    "I cannot answer that from the recipe cards. "
    "They do not contain the information, and I will not guess."
)


def _words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3]


def _stem(word):
    for suffix, min_len in (("ing", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if len(word) >= min_len and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def build_vocabulary(chunks):
    return {_stem(w) for chunk in chunks for w in _words(chunk.text)}


def unknown_words(question, vocabulary):
    seen = []
    for word in _words(question):
        if word not in STOPWORDS and _stem(word) not in vocabulary and word not in seen:
            seen.append(word)
    return seen


def _candidates(chunk):
    """Break a chunk into possible answers: table rows (with header) and sentences."""
    header, prose, candidates = None, [], []
    for line in chunk.body.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            if re.fullmatch(r"\|[\s\-:|]+\|", s):
                continue
            if header is None:
                header = s
            else:
                candidates.append(header + "\n" + s)
        else:
            prose.append(line)

    for paragraph in re.split(r"\n\s*\n", "\n".join(prose)):
        flat = " ".join(paragraph.split())
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", flat):
            if len(sentence.strip()) > 20:
                candidates.append(sentence.strip())
    return candidates


def answer(question, hits, index, vocabulary, trace=None, picker="cosine"):
    """
    picker      "cosine" (before) or "cross_encoder" (after): how the answer
                sentence is chosen. See the top of this file.
    question    what the user asked
    hits        the top 3 fetched chunks (from any retriever)
    index       the SearchIndex, used to measure closeness with the embedding model
    vocabulary  every word in the corpus, for gate 1
    trace       optional dict. If given, every gate decision and the top candidate
                sentences are written into it, so the answer can be read and
                replayed later. It never changes what the answerer does.
    """
    trace = {} if trace is None else trace
    result = {"refused": True, "answer": REFUSAL, "citation": None, "reason": ""}

    missing = unknown_words(question, vocabulary)
    trace["gate1_unknown_words"] = missing
    if missing:
        result["reason"] = f"Gate 1: these words appear nowhere in the corpus: {', '.join(missing)}"
        return result

    closeness = {hit.chunk.chunk_id: index.cosine(question, hit.chunk) for hit in hits}
    trace["gate2_chunk_cosines"] = {k: round(v, 4) for k, v in closeness.items()}
    if not hits or max(closeness.values()) < MIN_SCORE_TO_ANSWER:
        result["reason"] = f"Gate 2: no fetched chunk reached similarity {MIN_SCORE_TO_ANSWER}"
        return result

    pool = [(text, hit) for hit in hits for text in _candidates(hit.chunk)]
    if not pool:
        result["reason"] = "Gate 3: no usable sentence in the fetched chunks"
        return result

    vectors = embed([question] + [text for text, _ in pool])
    sentence_scores = vectors[1:] @ vectors[0]

    if picker not in PICKERS:
        raise ValueError(f"picker must be one of {PICKERS}")

    if picker == "cosine":
        pick_scores = [
            (1 - CHUNK_WEIGHT) * float(s) + CHUNK_WEIGHT * closeness[hit.chunk.chunk_id]
            for (_, hit), s in zip(pool, sentence_scores)
        ]
    else:
        pick_scores = [float(x) for x in cross_encoder().predict([(question, text) for text, _ in pool])]

    scored = sorted(
        (
            (score, float(s), text, hit)
            for score, s, (text, hit) in zip(pick_scores, sentence_scores, pool)
        ),
        key=lambda item: -item[0],
    )
    _, best_cosine, best_text, best_hit = scored[0]
    best = (best_text, best_hit, best_cosine)

    trace["picker"] = picker
    trace["candidate_count"] = len(scored)
    trace["top_candidates"] = [
        {"pick_score": round(p, 4), "sentence_score": round(s, 4), "chunk_id": h.chunk.chunk_id, "text": t}
        for p, s, t, h in scored[:5]
    ]

    text, hit, sentence_score = best
    if sentence_score < MIN_SENTENCE_SCORE:
        result["reason"] = f"Gate 3: best sentence scored {sentence_score:.3f}, below {MIN_SENTENCE_SCORE}"
        return result

    return {
        "refused": False,
        "answer": text,
        "citation": hit.chunk.chunk_id,
        "cited_recipe_id": hit.chunk.recipe_id,
        "reason": "All gates passed",
    }
