"""
THE APP, instrumented.

Same recipe agent as Weeks 9 and 10, with two things added for production:

  1. Every request writes a full trace to logs/requests.jsonl — per-step time,
     tokens and cost, plus which recipe sections were retrieved.
  2. The system prompt is VERSIONED. Every log line records which version
     produced it, so a regression can be pinned to a change.

    python app.py "I'm dairy-free. What can I use instead of buttermilk?"
    python app.py --prompt-version v1.2.0 "..."
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.llm import LLMError, call_json, model_name  # noqa: E402
from agent.mcp_client import MCPToolbox  # noqa: E402
from obs.flags import compute_flags  # noqa: E402
from obs.trace_log import LOG_FILE  # noqa: E402  (re-exported for callers)
from obs.trace_log import Trace  # noqa: E402

# ---------------------------------------------------------------------------
# PROMPT VERSIONS. The live one is CURRENT_VERSION.
#
# v1.1.0  what shipped in Week 10.
# v1.2.0  the fix for the dairy-free incident (see results/drill.md): any
#         ingredient suggested to a cook with a dietary restriction must be
#         checked with a tool first, and named with its allergens.
# ---------------------------------------------------------------------------

PROMPTS = {
    "v1.1.0": """You are a kitchen assistant that works in steps. These tools are available to you:

{tools}

On every turn reply with exactly ONE JSON object:
  {{"thought": "<one short sentence>", "action": "<a tool name, or final_answer>", "args": {{...}}}}
To finish: {{"thought": "...", "action": "final_answer", "args": {{"answer": "<your answer>"}}}}

Rules:
- Use only the tools listed above, with exactly the argument names shown.
- Every fact in your answer must come from a tool result. Never guess numbers.
- If a tool returns an error, read it and fix your call.
- Never repeat a tool call you already made.
- Keep the final answer short, and name the recipe or ingredient it came from.""",

    "v1.2.0": """You are a kitchen assistant that works in steps. These tools are available to you:

{tools}

On every turn reply with exactly ONE JSON object:
  {{"thought": "<one short sentence>", "action": "<a tool name, or final_answer>", "args": {{...}}}}
To finish: {{"thought": "...", "action": "final_answer", "args": {{"answer": "<your answer>"}}}}

Rules:
- Use only the tools listed above, with exactly the argument names shown.
- Every fact in your answer must come from a tool result. Never guess numbers.
- If a tool returns an error, read it and fix your call.
- Never repeat a tool call you already made.
- Keep the final answer short, and name the recipe or ingredient it came from.

DIETARY SAFETY (added in v1.2.0 after a dairy-free incident):
- If the cook states a restriction (dairy-free, vegan, gluten-free, nut allergy), then
  BEFORE you suggest any ingredient you must call ingredient_info on it and read its
  allergens.
- Never suggest a swap whose allergens clash with the stated restriction. Milk, butter
  and buttermilk are dairy. A substitute returned by a tool is NOT automatically safe:
  check it.
- If no listed substitute is safe for that restriction, say so plainly instead of
  offering one.""",
}
CURRENT_VERSION = "v1.2.0"   # bumped 2026-10-28 after the dairy-free incident

MAX_STEPS = 8

# Rough buckets for slicing the log later.
INPUT_TYPES = [
    ("substitution", r"\b(instead of|substitut|swap|replace|alternative)\b"),
    ("dietary", r"\b(dairy[- ]?free|vegan|gluten[- ]?free|allerg|coeliac|celiac|lactose)\b"),
    ("allergen", r"\b(contain|nuts?|shellfish|sesame|egg)\b"),
    ("amount", r"\b(how much|how many|grams?|\bg\b|kg|cups?)\b"),
    ("method", r"\b(how long|temperature|bake|knead|ferment|proof|cook)\b"),
]


def classify_input(question):
    for name, pattern in INPUT_TYPES:
        if re.search(pattern, question, re.IGNORECASE):
            return name
    return "other"


def tool_descriptions(toolbox):
    blocks = []
    for name, tool in toolbox.tools.items():
        schema = (tool["schema"].get("properties") or {})
        args = ", ".join(f"{a}: {s.get('type', 'any')}" for a, s in schema.items())
        blocks.append(f"{name}({args})\n    {tool['description']}")
    return "\n\n".join(blocks)


def _context_ids(tool_name, args, result):
    """Which recipe sections this tool call actually served."""
    ids = []
    if isinstance(result, dict):
        recipe_id = result.get("recipe_id")
        section = result.get("section")
        if recipe_id and section:
            ids.append(f"{recipe_id}::{str(section).lower().replace(' ', '_')}")
        elif recipe_id:
            ids.append(f"{recipe_id}::{tool_name}")
        for hit in (result.get("results") or []):
            if isinstance(hit, dict) and hit.get("recipe_id"):
                ids.append(f"{hit['recipe_id']}::search_hit")
        if result.get("ingredient"):
            ids.append(f"ingredient-db::{result['ingredient']}")
    return ids


def answer_question(question, toolbox, prompt_version=CURRENT_VERSION, user_id="u-0001",
                    channel="web", verbose=False, log=print, guard_enabled=True):
    """Answer one question and write one complete trace."""
    trace = Trace(question, prompt_version=prompt_version, user_id=user_id, channel=channel,
                  input_type=classify_input(question), model=model_name())
    system = PROMPTS[prompt_version].format(tools=tool_descriptions(toolbox))
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"USER TASK: {question}"}]
    answer, status, seen = "", "finished", set()

    for step in range(MAX_STEPS):
        try:
            with trace.span(f"llm_call_{step + 1}", "generation") as span:
                decision, raw, usage = call_json(messages)
                span.tokens(usage["input_tokens"], usage["output_tokens"])
        except LLMError as error:
            status, answer = f"error: {error}", f"I couldn't finish this task ({error})."
            break

        if not decision or "action" not in decision:
            messages.append({"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."})
            continue
        action = str(decision.get("action", ""))
        args = decision.get("args") or {}

        if action == "final_answer":
            answer = str(args.get("answer", "")) if isinstance(args, dict) else str(args)
            break

        key = action + json.dumps(args, sort_keys=True)
        if key in seen:
            status = f"stopped: repeated the same tool call ({action})"
            answer = f"I couldn't finish this task ({status})."
            break
        seen.add(key)

        kind = "retrieval" if action in ("search_recipes", "get_recipe_section") else "tools"
        with trace.span(action, kind, args=args) as span:
            result = toolbox.call(action, args)
        trace.saw_context(_context_ids(action, args, result))
        observation = json.dumps(result, ensure_ascii=False)[:900]
        if verbose:
            log(f"   {action}({json.dumps(args)}) -> {observation[:110]}")
        messages.append({"role": "assistant", "content": json.dumps(decision)})
        messages.append({"role": "user", "content": f"Result of {action}: {observation}\n"
                                                    "If this answers the task, reply with final_answer."})
    else:
        status = f"stopped: step limit ({MAX_STEPS}) reached"
        answer = answer or f"I couldn't finish this task ({status})."

    # The field whose absence cost two queries in the drill (see results/drill.md).
    flags = compute_flags(question, answer)

    # SAFETY GUARD diet_conflict_v1, added 2026-10-28.
    #
    # The prompt rule in v1.2.0 and the allergen data now returned by substitutes_for
    # were BOTH ignored by the model: suite_fix1_prompt_only.json shows DF-01 still
    # failing with "use milk plus lemon juice". So the last word is taken away from the
    # model. This check is code: if the cook stated a restriction and the answer
    # recommends a clashing ingredient without warning, the answer does not go out.
    guard = None
    if guard_enabled and flags["diet_conflict"]:
        guard = {"name": "diet_conflict_v1", "conflicts": flags["conflicts"],
                 "suppressed_answer": answer}
        answer = ("I can't recommend that: it contains "
                  + " and ".join(sorted({c.split(" vs ")[1] for c in flags["conflicts"]}))
                  + ", which clashes with the "
                  + " and ".join(sorted({c.split(" vs ")[0] for c in flags["conflicts"]}))
                  + " requirement you gave me. The recipe cards record no safe substitute for this, "
                    "so I would rather say so than suggest something unsafe.")
        flags = compute_flags(question, answer)
        status = "finished (safety guard)"

    record = trace.finish(answer, status=status, flags=flags, safety_guard=guard,
                          env=os.environ.get("APP_ENV", "dev"))
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="+")
    parser.add_argument("--prompt-version", default=CURRENT_VERSION, choices=list(PROMPTS))
    parser.add_argument("--user", default="u-0001")
    parser.add_argument("--no-guard", action="store_true",
                        help="disable the diet_conflict guard (used to reproduce pre-fix behaviour)")
    args = parser.parse_args()

    with MCPToolbox() as toolbox:
        record = answer_question(" ".join(args.question), toolbox,
                                 prompt_version=args.prompt_version, user_id=args.user,
                                 verbose=True, guard_enabled=not args.no_guard)
    print(f"\ntrace_id: {record['trace_id']}  prompt {record['prompt_version']}")
    print(f"answer:   {record['answer']}")
    t = record["totals"]
    print(f"totals:   {t['ms']:.0f} ms | {t['tokens']} tokens | ${t['cost_usd']:.6f} | "
          f"{t['llm_calls']} model calls, {t['tool_calls']} tool calls")
    print(f"context:  {', '.join(record['context_ids']) or '(none)'}")


if __name__ == "__main__":
    main()
