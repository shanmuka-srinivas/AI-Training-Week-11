"""
The eval suite: the Week-6 cases plus every case born from a real failure.

    python suite.py --tag red                      # current prompt version
    python suite.py --tag green --prompt-version v1.2.0

Two kinds of case run side by side:
  * Week-6 cases, graded by evals/checks.py (unchanged since Week 6)
  * incident cases, each with its own check function, added when something
    broke in production

Prints the pass count, so a fix that quietly breaks something else shows up.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.mcp_client import MCPToolbox  # noqa: E402
from app import CURRENT_VERSION, answer_question  # noqa: E402
from evals.case_dairy_free import CASE as DAIRY_CASE  # noqa: E402
from evals.cases import CASES  # noqa: E402
from evals.checks import rule_checks  # noqa: E402

TYPES = ["wrong_sentence", "false_refusal", "allergen_yes_no", "must_refuse", "already_working"]
REFUSAL_WORDS = ("cannot", "can't", "could not", "couldn't", "do not contain", "don't contain",
                 "not contain", "no information", "does not say", "doesn't say", "not available",
                 "unable", "not provided", "no record", "do not record", "don't record")

INCIDENT_CASES = [DAIRY_CASE]


def week6_cases():
    by_type = {}
    for case in CASES:
        by_type.setdefault(case["type"], []).append(case)
    return [case for t in TYPES for case in by_type[t][:2]]


def grade_week6(case, answer):
    refused = any(w in answer.lower() for w in REFUSAL_WORDS)
    result = {"answer": answer, "refused": refused, "refusal_reason": "",
              "citation": None if refused else "app", "cited_recipe_id": case.get("recipe"), "context": []}
    checks = rule_checks(case, result)
    failed = [n for n, ok, _ in checks if not ok]
    return all(ok for _, ok, _ in checks), ("; ".join(failed) or "all checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--prompt-version", default=CURRENT_VERSION)
    parser.add_argument("--no-guard", action="store_true", help="disable the diet_conflict guard")
    args = parser.parse_args()

    cases = week6_cases()
    rows, started = [], time.perf_counter()
    print(f"suite: {len(cases)} Week-6 cases + {len(INCIDENT_CASES)} incident case(s) | "
          f"prompt {args.prompt_version}\n")

    with MCPToolbox() as toolbox:
        for case in cases:
            record = answer_question(case["question"], toolbox, prompt_version=args.prompt_version,
                                     guard_enabled=not args.no_guard)
            passed, why = grade_week6(case, record["answer"])
            rows.append({"id": case["id"], "kind": "week6", "question": case["question"],
                         "answer": record["answer"], "passed": passed, "why": why,
                         "trace_id": record["trace_id"], "cost_usd": record["totals"]["cost_usd"]})
            print(f"  {case['id']:7} {'PASS' if passed else 'FAIL'}  {why[:60]}")
        for case in INCIDENT_CASES:
            record = answer_question(case["question"], toolbox, prompt_version=args.prompt_version,
                                     guard_enabled=not args.no_guard)
            passed, why = case["check"](record["answer"])
            rows.append({"id": case["id"], "kind": "incident", "question": case["question"],
                         "answer": record["answer"], "passed": passed, "why": why,
                         "trace_id": record["trace_id"], "cost_usd": record["totals"]["cost_usd"]})
            print(f"  {case['id']:7} {'PASS' if passed else 'FAIL'}  {why[:60]}")

    passed = sum(r["passed"] for r in rows)
    out = {"tag": args.tag, "prompt_version": args.prompt_version, "guard": not args.no_guard,
           "passed": passed, "total": len(rows), "rows": rows,
           "seconds": round(time.perf_counter() - started, 1)}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"suite_{args.tag}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSUITE {args.tag.upper()}: {passed}/{len(rows)} passed  (prompt {args.prompt_version})")
    incident = [r for r in rows if r["kind"] == "incident"]
    print("incident cases: " + ", ".join(f"{r['id']} {'PASS' if r['passed'] else 'FAIL'}" for r in incident))


if __name__ == "__main__":
    main()
