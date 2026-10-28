"""
Build the haystack: a log that looks like a week of real traffic, with one bad
answer hidden in it.

    python traffic.py --count 500

HONESTY ABOUT WHAT IS REAL. Running 500 questions through a local model would
take eight hours, so the bulk of this log is SIMULATED: the same schema, the
same span shapes, plausible questions and answers, timings and token counts
sampled from the real runs we measured in Weeks 9 and 10. The traces that
matter are real: the planted failure, and a handful of others, are produced by
actually running app.py.

HOW THE PLANT STAYS HONEST. The script picks the planted failure's timestamp,
user and trace id at random and writes them to logs/.answer_key.json, which is
NOT read during the drill. Otherwise the drill measures memory, not tooling.
"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "logs" / "requests.jsonl"
ANSWER_KEY = ROOT / "logs" / ".answer_key.json"

from obs.trace_log import token_cost  # noqa: E402

USERS = [f"u-{n:04d}" for n in range(1, 61)]
CHANNELS = ["web"] * 6 + ["mobile"] * 3 + ["api"]

# Ordinary traffic. Each entry: question, answer, input_type, context ids.
ORDINARY = [
    ("How much fine sea salt for the sauerkraut?", "The Small-Batch Caraway Sauerkraut uses 7 g of fine sea salt.", "amount", ["R-106::ingredients"]),
    ("How long does the sauerkraut ferment?", "Ferment at 18 C for fourteen days.", "method", ["R-106::method"]),
    ("How much flour in the pizza dough?", "The Neapolitan Pizza Dough uses 900 g of Tipo 00 flour.", "amount", ["R-002::ingredients"]),
    ("What temperature do I bake the focaccia at?", "Bake the Rosemary Focaccia at 240 C for twenty-two minutes.", "method", ["R-001::method"]),
    ("How long do I knead the pizza dough?", "Knead for ten minutes until smooth and springy.", "method", ["R-002::method"]),
    ("Does the hummus contain sesame?", "Yes. The Classic Hummus contains sesame from the tahini.", "allergen", ["R-004::allergen_note"]),
    ("How much water in the rye sourdough?", "The rye sourdough takes 810 g of water at 32 C.", "amount", ["R-102::ingredients"]),
    ("How long does the kimchi keep?", "Kimchi keeps for six months in the fridge and keeps souring.", "method", ["R-104::storage_and_troubleshooting"]),
    ("What's the hydration of the country sourdough?", "The Two-Kilo Country Sourdough runs at 75% hydration.", "amount", ["R-101::overview"]),
    ("How much psyllium in the buckwheat loaf?", "18 g of whole psyllium husk, which is 3%.", "amount", ["R-103::ingredients"]),
    ("Is the vegan kimchi free from shellfish?", "Yes. It is free from fish, shellfish, gluten, dairy, egg and nuts.", "allergen", ["R-105::allergen_note"]),
    ("How many pancakes does the recipe make?", "Twelve 12 cm pancakes.", "amount", ["R-003::overview"]),
    ("Why did my focaccia come out dense?", "A dense crumb means the dough was over-floured or under-proofed.", "method", ["R-001::storage_and_troubleshooting"]),
    ("How much gochugaru in the traditional kimchi?", "110 g of gochugaru chilli flakes, 6.1% of the cabbage weight.", "amount", ["R-104::ingredients"]),
    ("How many cups is 500 g of bread flour?", "About 3.94 cups, based on 127 g per cup.", "amount", ["ingredient-db::strong white bread flour"]),
    ("What can I use instead of tahini?", "Sunflower seed butter, 1:1. It is nut and sesame free and slightly sweeter.", "substitution", ["ingredient-db::light tahini"]),
    ("Can I use plain flour instead of Tipo 00?", "Plain flour works 1:1, giving a slacker dough with less chew.", "substitution", ["ingredient-db::tipo 00 flour"]),
    ("I'm vegan, which kimchi should I make?", "The Vegan Napa Cabbage Kimchi (R-105). It is free from fish and shellfish.", "dietary", ["R-105::allergen_note"]),
    ("I'm gluten-free, can I eat the buckwheat loaf?", "Yes. The Gluten-Free Buckwheat Sourdough is free from gluten and milled on dedicated equipment.", "dietary", ["R-103::allergen_note"]),
    ("Is the focaccia safe with a nut allergy?", "Not guaranteed: it is made in a kitchen that also handles sesame and tree nuts.", "dietary", ["R-001::allergen_note"]),
    ("I'm dairy-free, is the hummus okay?", "Yes. The Classic Hummus is free from dairy. It does contain sesame from the tahini.", "dietary", ["R-004::allergen_note"]),
    ("I'm dairy-free, can I eat the sauerkraut?", "Yes. The Small-Batch Caraway Sauerkraut is free from dairy, gluten, egg and nuts.", "dietary", ["R-106::allergen_note"]),
    ("What can I use instead of caraway seed?", "The ingredient database records no substitute for caraway seed.", "substitution", ["ingredient-db::caraway seed"]),
    ("How many calories in a slice of sourdough?", "The recipe cards do not record nutrition information, so I can't say.", "other", []),
    ("Where can I buy gochugaru?", "The cards list ingredients and weights, but name no suppliers.", "other", []),
    ("How much salt for 2 kg of cabbage in the sauerkraut?", "For 2 kg of cabbage you need 40 g of fine sea salt.", "amount", ["R-106::ingredients"]),
    ("Can I swap butter for oil in the pancakes?", "The pancake card doesn't discuss that swap, so I can't confirm it.", "substitution", ["R-003::about_this_batter"]),
    ("What's the starter percentage in the rye?", "Thirty percent, which is higher than a wheat loaf.", "amount", ["R-102::about_this_loaf"]),
]

# Questions that look like the complaint but were answered correctly, so that
# searching for "dairy" does not land on one row by luck.
NEAR_MISSES = [
    ("I'm dairy-free. Can I make the buttermilk pancakes?", "Not as written: the Buttermilk Pancakes contain cultured buttermilk and butter, both dairy.", "dietary", ["R-003::allergen_note"]),
    ("Dairy-free substitute for melted butter?", "Neutral oil at 0.8x by weight, which carries no dairy.", "substitution", ["ingredient-db::melted butter"]),
    ("Is there a dairy-free bread on the cards?", "Yes, several: the focaccia, the pizza dough and both sourdoughs are dairy-free.", "dietary", ["R-001::allergen_note", "R-002::allergen_note"]),
]


def make_spans(kind_mix, rng, total_tokens):
    """Span shapes copied from the real runs: a couple of model calls, a tool or two."""
    spans, remaining = [], total_tokens
    for index, (name, kind) in enumerate(kind_mix):
        if kind == "generation":
            share = remaining if index == len(kind_mix) - 1 else int(remaining * rng.uniform(0.35, 0.65))
            output = max(20, int(share * rng.uniform(0.04, 0.12)))
            inp = max(50, share - output)
            remaining -= share
            spans.append({"name": name, "kind": kind, "ms": round(rng.uniform(8000, 32000), 1),
                          "input_tokens": inp, "output_tokens": output,
                          "cost_usd": round(token_cost(inp, output), 8)})
        else:
            spans.append({"name": name, "kind": kind, "ms": round(rng.uniform(40, 900), 1),
                          "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
    return spans


def synthetic(rng, when, template):
    question, answer, input_type, context_ids = template
    tools = [("search_recipes", "retrieval"), ("get_recipe_section", "retrieval")]
    if input_type in ("substitution", "dietary") and context_ids and "ingredient-db" in context_ids[0]:
        tools = [("ingredient_info", "tools")] if rng.random() < 0.5 else [("substitutes_for", "tools")]
    mix = [("llm_call_1", "generation")] + [t for t in tools] + [("llm_call_2", "generation")]
    total_tokens = int(rng.gauss(2600, 900))
    total_tokens = max(700, min(9000, total_tokens))
    spans = make_spans(mix, rng, total_tokens)
    input_tokens = sum(s["input_tokens"] for s in spans)
    output_tokens = sum(s["output_tokens"] for s in spans)
    return {
        "trace_id": f"t-{when:%Y%m%d}-{rng.getrandbits(24):06x}",
        "ts": when.isoformat(timespec="seconds"),
        "user_id": rng.choice(USERS),
        "channel": rng.choice(CHANNELS),
        "input_type": input_type,
        "prompt_version": "v1.1.0",
        "model": "Qwen2.5-3B-Instruct Q4_K_M (llama.cpp, local CPU)",
        "question": question,
        "answer": answer,
        "status": "finished",
        "context_ids": context_ids,
        "spans": spans,
        "totals": {"ms": round(sum(s["ms"] for s in spans), 1),
                   "input_tokens": input_tokens, "output_tokens": output_tokens,
                   "tokens": input_tokens + output_tokens,
                   "cost_usd": round(token_cost(input_tokens, output_tokens), 8),
                   "llm_calls": sum(1 for s in spans if s["kind"] == "generation"),
                   "tool_calls": sum(1 for s in spans if s["kind"] != "generation")},
        "simulated": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None, help="leave unset so the plant is not reproducible by me")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    real = [json.loads(line) for line in LOG_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()] if LOG_FILE.exists() else []
    planted = next((r for r in real if "milk plus lemon" in r.get("answer", "").lower()), None)
    if planted is None:
        raise SystemExit("No real dairy-free failure in the log yet. Run app.py on the dairy-free "
                         "question first, so the planted trace is a real one.")

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=9)
    span_seconds = int((end - start).total_seconds())

    records = []
    templates = ORDINARY * 20 + NEAR_MISSES * 4
    for _ in range(args.count):
        when = start + timedelta(seconds=rng.randrange(span_seconds))
        # Working hours, so the timeline looks like real traffic.
        when = when.replace(hour=rng.choice([8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]))
        records.append(synthetic(rng, when, rng.choice(templates)))

    # The plant: a REAL failing trace, re-stamped with a random time and user.
    planted_when = start + timedelta(seconds=rng.randrange(span_seconds))
    planted_when = planted_when.replace(hour=rng.choice([9, 10, 11, 14, 15, 16, 17]))
    planted = dict(planted)
    planted.update({
        "trace_id": f"t-{planted_when:%Y%m%d}-{rng.getrandbits(24):06x}",
        "ts": planted_when.isoformat(timespec="seconds"),
        "user_id": rng.choice(USERS),
        "channel": rng.choice(CHANNELS),
        "simulated": False,
    })
    records.append(planted)

    records.sort(key=lambda r: r["ts"])
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    ANSWER_KEY.write_text(json.dumps({
        "_warning": "SEALED. Do not open until the drill is over and the time is recorded.",
        "planted_trace_id": planted["trace_id"], "ts": planted["ts"],
        "user_id": planted["user_id"], "answer": planted["answer"],
    }, indent=2), encoding="utf-8")

    print(f"wrote {len(records)} traces to {LOG_FILE}")
    print(f"  {len(records) - 1} simulated + 1 real planted failure")
    print(f"  window: {records[0]['ts']} .. {records[-1]['ts']}")
    print(f"  answer key sealed in {ANSWER_KEY} (do not read before the drill)")


if __name__ == "__main__":
    main()
