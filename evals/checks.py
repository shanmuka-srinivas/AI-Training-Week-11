"""
Rule checks (assertions). Free, instant, exact. They run first, and the AI
judge is only used where a rule genuinely can't decide.

Also three RAGAS-style numbers, computed with simple rules instead of the RAGAS
library, because this app quotes its answers word for word:

    faithfulness       is the answer really in the fetched text? For an
                       extractive app this should always be yes, and the check
                       proves it instead of assuming it.
    context recall     was the expected fact inside the 3 fetched chunks?
                       (Did search give the answer step a chance?)
    context precision  what share of the 3 fetched chunks came from the
                       expected recipe? (How much noise came with it?)

RAGAS's own versions of these use an LLM to decide what "supported" means. We
don't need that here, and that keeps this part free and deterministic.
"""

import re

from rag.answerer import REFUSAL


def contains(text, fact):
    """Case-insensitive, whole-token match, so "17 g" never counts as "7 g"."""
    pattern = re.escape(fact)
    if re.match(r"\w", fact):
        pattern = r"(?<![\w.])" + pattern
    if re.search(r"\w$", fact):
        pattern += r"\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _flat(text):
    return " ".join(text.split())


def rule_checks(case, result):
    """
    Returns a list of (check name, passed, detail). A case passes the rules only
    if every check passes.
    """
    checks = []
    answer = _flat(result["answer"])
    refused = result["refused"]

    expect = case.get("expect")
    if expect == "refuse":
        checks.append(("refused when it should", refused, "" if refused else f"answered: {answer[:80]}"))
        return checks
    if expect == "answer":
        checks.append(("did not refuse", not refused, result["refusal_reason"]))
        if refused:
            return checks

    # Substitution cases have no expect: refusing CAN be right. The judge decides that.
    if refused:
        return checks

    checks.append(("source present", bool(result["citation"]), ""))
    if case.get("recipe"):
        ok = result["cited_recipe_id"] == case["recipe"]
        checks.append(("cites the right recipe", ok, f"cited {result['cited_recipe_id']}, expected {case['recipe']}"))

    if case.get("must_contain_any"):
        ok = any(contains(answer, f) for f in case["must_contain_any"])
        checks.append(("contains the fact", ok, f"needs one of {case['must_contain_any']}"))
    if case.get("must_contain_all"):
        missing = [f for f in case["must_contain_all"] if not contains(answer, f)]
        checks.append(("contains every fact", not missing, f"missing {missing}" if missing else ""))
    if case.get("min_distinct"):
        rule = case["min_distinct"]
        found = [t for t in rule["of"] if contains(answer, t)]
        checks.append((f"names at least {rule['n']}", len(found) >= rule["n"], f"found {found}"))

    return checks


def rag_metrics(case, result):
    """Faithfulness, context recall and context precision for one case (None = not applicable)."""
    context_text = _flat(" ".join(c["body"] for c in result["context"]))
    facts = case.get("must_contain_any") or case.get("must_contain_all") or []

    faithfulness = None
    if not result["refused"]:
        # Table-row answers are quoted as "header\nrow", so check each line separately.
        lines = [_flat(line) for line in result["answer"].splitlines() if line.strip()]
        faithfulness = all(line in context_text for line in lines)

    recall = None
    if facts:
        recall = any(contains(context_text, f) for f in facts)

    precision = None
    if case.get("recipe"):
        ids = [c["recipe_id"] for c in result["context"]]
        precision = sum(i == case["recipe"] for i in ids) / len(ids) if ids else 0.0

    return {"faithfulness": faithfulness, "context_recall": recall, "context_precision": precision}


def is_refusal(answer_text):
    return answer_text.strip() == REFUSAL
