# Week 11, Track B (Recipes & food) — production: logging, the drill, cost, and the failure→test loop

**Task:** make the app observable, find a planted bad answer from a vague complaint, measure
and improve cost per request, and turn the failure into a permanent test.

| Mentor check | Answer |
|---|---|
| Can they find a specific past answer quickly? | **Yes: 4 queries over 501 requests**, trace `t-20261020-ed8e7b`, verified against a sealed answer key — §2 |
| Do the logs show time and cost **per step**? | **Yes**, every span: see [results/trace.json](results/trace.json) and §1 |
| Did they measure cost per request and improve it? | Measured **$0.000318/request**, split by stage; the improvement is named and sized in §5 |
| Did they turn a real failure into a test that guards it? | **Yes: DF-01, seen RED (1/11) then GREEN (6/11)** — §4 |

Everything runs offline on the local Qwen model. Real cash cost: **$0**.

---

## 1. What every request now records

One JSON object per request in `logs/requests.jsonl` ([obs/trace_log.py](obs/trace_log.py)).
The real trace of the incident, abbreviated:

```json
{ "trace_id": "t-20261020-ed8e7b",
  "ts": "2026-10-20T16:40:37+00:00",
  "user_id": "u-0017", "channel": "mobile",
  "input_type": "substitution",
  "prompt_version": "v1.1.0",
  "question": "I'm dairy-free. What can I use instead of the buttermilk in the pancakes?",
  "answer":   "For your pancakes, you can use milk plus lemon juice: 1 cup milk + 1 tbsp lemon...",
  "context_ids": ["ingredient-db::cultured buttermilk"],
  "spans": [
    {"name": "llm_call_1",      "kind": "generation", "ms": 42299, "input_tokens": 752, "output_tokens": 39, "cost_usd": 0.000091},
    {"name": "substitutes_for", "kind": "tools",      "ms":     8, "input_tokens":   0, "output_tokens":  0, "cost_usd": 0.0},
    {"name": "llm_call_2",      "kind": "generation", "ms": 12110, "input_tokens": 862, "output_tokens": 59, "cost_usd": 0.000110}
  ],
  "totals": {"ms": 54416, "tokens": 1712, "cost_usd": 0.000201, "llm_calls": 2, "tool_calls": 1} }
```

Three fields earn their place more than the rest:

- **`prompt_version`** — without it you cannot tell a regression from bad luck.
- **`context_ids`** — this one says `ingredient-db::cultured buttermilk`, so we know in one hop
  that retrieval served the substitutes list and the model read it correctly. The data was
  wrong, not the retrieval. Without this field that is a two-day mystery.
- **per-span cost and time** — one lump total would have hidden that 98% of the time and 100%
  of the money is the model (§5).

## 2. The support drill

> "A cook said it suggested a dairy swap that wasn't actually dairy-free. Maybe Tuesday?"

**Found in 4 queries: `t-20261020-ed8e7b`** (and it genuinely was a Tuesday). Full account in
[results/drill.md](results/drill.md).

| query | rows | |
|---|---|---|
| `--count` | 501 | the haystack |
| `--input-type dietary` | 100 | too coarse |
| `--contains "dairy-free"` | 48 | still too many |
| **`--answer-contains milk`** | **4** | found it |

**The lesson is in which query worked.** The complaint described the **answer**, not the
question — the cook never said "I asked about buttermilk", they said "it told me to use
something with dairy in it". A log that indexed only inputs would have been useless.

**Honesty about the clock.** The four queries run in under a second, so I am not claiming a
human mm:ss; a person reading between queries would take two to four minutes. The number I
defend is **four queries, and the slice that found it**. The plant was randomised and sealed
by the script so the search could not be short-circuited by my knowing where it was.

**The missing field that cost two queries:** nothing recorded that *the cook stated a
restriction and the answer recommended something that clashes with it*. The app had both
halves and joined neither. Added as `flags.diet_conflict` — see §6.

## 3. The bug, and why it is not the model's fault

`substitutes_for("cultured buttermilk")` returned `{"use": "milk plus lemon juice"}` with no
allergen information at all. The ingredient database really does record that swap; it just
isn't dairy-free, and nothing checked. The model repeated what the tool told it.

## 4. The failure → test loop: RED, then GREEN

A new eval case, [evals/case_dairy_free.py](evals/case_dairy_free.py) (`DF-01`), written from
the incident and added to the Week-6 suite. **It was run before the fix, so it has been seen
failing** — a test that has only ever been green is a test you have not tested.

| run | prompt | guard | suite | DF-01 |
|---|---|---|---|---|
| **RED** | v1.1.0 | off | **1/11** | **FAIL** — "offers 'milk' with no dairy warning" |
| fix attempt 1 | v1.2.0 | off | 5/11 | **FAIL** — "recommends 'milk' … to a dairy-free cook" |
| **GREEN** | v1.2.0 | on | **6/11** | **PASS** |

**Nothing regressed:** the only case passing in RED (AL-02) still passes in GREEN.

**The middle row is the interesting one.** Fix attempt 1 did the sensible things — a prompt
rule forbidding unsafe swaps, and a retrieval-layer change so `substitutes_for` now returns
each substitute's own allergens (`"use": "milk plus lemon juice", "allergens": ["milk"]`) — and
the model **still** recommended milk. A 3B model cannot be argued into safety.

So the fix that shipped takes the last word away from the model: a deterministic guard
(`diet_conflict_v1`) in [app.py](app.py) that refuses to emit an answer recommending an
allergen which clashes with a stated restriction. Prompt and data changes make the right
answer *likely*; the guard makes the wrong answer *impossible to emit*.

Version bump, canary and rollback: [results/canary_rollback.md](results/canary_rollback.md).

## 5. Cost per request, by stage

From 502 production requests ([results/cost_by_stage.md](results/cost_by_stage.md)):

| stage | time/request | share of time | tokens/request | cost/request | share of cost |
|---|---|---|---|---|---|
| retrieval | 0.8 s | 2% | 0 | $0 | 0% |
| tools | 0.1 s | 0% | 0 | $0 | 0% |
| **generation** | **40 s** | **98%** | **2,650** | **$0.000318** | **100%** |

**Cost per request $0.000318, about $3.18 per 10,000 questions.** p50 41 s, p99 61 s.

So there is exactly one lever and it is the model. Speeding up retrieval would optimise 2% of
the clock and 0% of the bill. The improvement worth making, in order: **cache repeated
questions** (the log is full of them), **remove one of the two model calls** on easy lookups
(worth ~$0.00016 and ~20 s each), then route easy questions to a smaller model — but *not*
dietary or substitution questions, which is exactly where this week's incident happened.

## 6. At 10× traffic, what breaks first

**Latency, and the number is the busiest hour:** [results/tenx.md](results/tenx.md)

> At 10× today's traffic the busiest hour needs **100 requests** against a capacity of
> **90/hour** (one local model, ~40 s of model time each) — **111% utilisation**, so the queue
> grows faster than it drains.

Not cost: 10× is about **$10/month** at hosted prices. Not a rate limit: the model is local and
has none — though moving to a hosted model to fix the latency would swap the throughput
ceiling for exactly that. The plan, in order: cache, run more workers, route by difficulty,
and only then go hosted.

## 7. Bonus: wiring the drill shut

Added `flags.diet_conflict`, backfilled over history, then had a second bad answer planted and
re-ran the drill ([results/bonus_second_drill.md](results/bonus_second_drill.md)):

| | drill 1 | drill 2 |
|---|---|---|
| queries | **4** | **1** |
| rows at the first query | 501 | **5** |
| found | `t-20261020-ed8e7b` | `t-20261019-c59850` (first row) |

**But the flag has a precision of 3/5.** Two of the five rows it returned are false positives:
"buckwheat **flour** is safe for coeliacs" (correct, but *flour* maps to gluten) and "use a
non-dairy **milk** alternative" (correct, but *milk* matched). It is a triage aid that turns
501 rows into 5, and it must never become an automatic gate.

## 8. What I would not claim

- **The haystack is mostly simulated.** 500 of the 502 production records were generated by
  [traffic.py](traffic.py) with span shapes and token counts sampled from real runs; the two
  planted failures and the rest are real app runs. Running 500 real questions through a local
  model would take eight hours.
- **I planted the failures myself.** Mitigated by the script randomising the timestamp, user
  and trace id and sealing them in a file not opened until after the find — but a squadmate
  planting it would be a stronger test.
- **The suite is weak in absolute terms** (6/11). This week measured a loop closing, not a
  good app.
- **The guard is narrow.** It knows five restrictions and a keyword list of allergens. It would
  not catch "this contains casein" or a restriction phrased in a way the pattern misses.

## Reproduce

```bash
python run_all.py --reports     # cost + 10x from the existing log (instant)
python run_all.py --drill       # replay both drills (instant)
python run_all.py --suite       # re-run RED and GREEN (~20 min, local model)
python logsearch.py --flag diet_conflict
```
