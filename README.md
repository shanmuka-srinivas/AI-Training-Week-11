# Making the Recipe App Watch Itself

*Week 11 · Module 6 (Production & Capstone) · Track B: Recipes & food*

---

## What is this project for?

Up to now the recipe app has been something we run and watch. In production nobody is
watching: it answers thousands of questions while everyone sleeps. So it has to watch
itself.

A real complaint sounds like this:

> *"A cook said it suggested a dairy swap that wasn't actually dairy-free. Maybe Tuesday?"*

No trace id. No recipe. No time. If the app didn't write down what it did, that complaint
can never be investigated — **if it isn't logged, it didn't happen.**

This project does three things that turn a demo into something you can actually run:

1. **Observable** — every request is logged in enough detail to find it later and see
   exactly what it did, step by step, with time and cost for each step.
2. **Affordable** — cost per request is measured and split by stage, so you know what to
   cut before you try to cut it.
3. **Self-improving** — the real failure becomes a permanent test, so that exact mistake
   can never quietly come back.

---

## Input

| What goes in | Details |
|---|---|
| **The recipe app** | From Weeks 9–10, now wrapped so every request writes a full trace |
| **A week of traffic** | 502 logged requests over 9 days ([traffic.py](traffic.py)) |
| **One planted bad answer** | A real failure, hidden in the log at a random time, with the answer **sealed** so the search can't cheat |
| **A vague complaint** | The one quoted above — that's all you get |
| **The Week-6 eval suite** | Reused unchanged, so a fix can't quietly break something else |

---

## Output

| What comes out | Where |
|---|---|
| **The drill**: how the bad answer was found, and in how many queries | [results/drill.md](results/drill.md) |
| **The trace**: per-step time, tokens, cost, prompt version, retrieved context | [results/trace.json](results/trace.json) |
| **The new test**, born from the failure | [evals/case_dairy_free.py](evals/case_dairy_free.py) |
| **Suite RED then GREEN**, with pass counts | [results/suite_red.json](results/suite_red.json) → [results/suite_green.json](results/suite_green.json) |
| **Cost per request, split by stage** | [results/cost_by_stage.md](results/cost_by_stage.md) |
| **What breaks first at 10× traffic** | [results/tenx.md](results/tenx.md) |
| **Shipping plan**: version bump, canary, rollback | [results/canary_rollback.md](results/canary_rollback.md) |
| **Bonus**: the missing field added, drill re-run | [results/bonus_second_drill.md](results/bonus_second_drill.md) |
| **The write-up** | [RESULTS.md](RESULTS.md) |

### The headline results

| | |
|---|---|
| Bad answer found in | **4 queries** out of 501 requests |
| The test, before the fix | **RED** — suite 1/11, DF-01 failing |
| The test, after the fix | **GREEN** — suite 6/11, DF-01 passing, nothing regressed |
| Cost per request | **$0.000318** — 100% of it the model |
| At 10× traffic | **Latency breaks first**: 100 requests needed in the busy hour vs 90/hour capacity |
| After adding one log field | the same drill takes **1 query instead of 4** |

---

## What happens between input and output

### Step 1: Log every request properly

Each request writes one line of JSON holding: who asked, when, from where, **which version
of the prompt** answered, the question, the answer, **which recipe sections were read**, and
a list of **spans** — one per step, each with its own milliseconds, tokens and cost.

```
llm_call_1        generation   42,299 ms   752 in / 39 out   $0.000091
substitutes_for   tools             8 ms     0 in /  0 out   $0.000000
llm_call_2        generation   12,110 ms   862 in / 59 out   $0.000110
```

Why per step and not one total? Because the totals hide the answer: 98% of the *time* and
100% of the *money* is the model, and the tools are free and instant. You'd optimise the
wrong thing.

### Step 2: The support drill — find one bad answer among 501

A script plants a genuinely bad answer at a random time, under a random user, and **seals
the answer in a file that isn't opened until the search is over**. Otherwise the drill
measures memory, not tooling.

Then the search, using [logsearch.py](logsearch.py):

| query | rows left |
|---|---|
| how many requests are there at all? | 501 |
| only the dietary ones | 100 |
| only ones mentioning "dairy-free" | 48 |
| **answers that mention milk** | **4** → found it |

**The query that worked searched the ANSWER, not the question.** The cook complained about
what the app *said*. If the log only indexed what was *asked*, this is unfindable.

### Step 3: What actually went wrong

The ingredient database really does record "milk plus lemon juice" as a buttermilk
substitute. It returned that with **no allergen information**, the model repeated it, and a
dairy-free cook was told to use milk. The data was wrong, not the retrieval and not really
the model.

### Step 4: Turn the failure into a test — and watch it fail first

A new eval case (`DF-01`) is written from the incident and run **before** any fix, because a
test that has only ever been green is a test you haven't tested.

| | prompt | guard | suite | DF-01 |
|---|---|---|---|---|
| **RED** | v1.1.0 | off | 1/11 | ❌ |
| fix attempt 1 | v1.2.0 | off | 5/11 | ❌ still recommends milk |
| **GREEN** | v1.2.0 | on | 6/11 | ✅ |

The middle row is the honest part: the obvious fixes — a prompt rule saying "check
allergens", and making the tool return each substitute's allergens — **were not enough**.
The small model ignored both. So the final fix is a **guard in code**: an answer that
recommends an ingredient clashing with a stated restriction is simply not sent.

> Prompts make the right answer *likely*. Code makes the wrong answer *impossible to send*.

### Step 5: Measure cost, then cut it

| stage | share of time | share of cost |
|---|---|---|
| retrieval (searching, reading cards) | 2% | 0% |
| tools (scaling, lookups) | 0% | 0% |
| **generation (the model)** | **98%** | **100%** |

$0.000318 per request. The only lever worth pulling is the model: cache repeated questions,
then remove one of the two model calls on easy lookups.

### Step 6: Plan for 10× the traffic

**Latency breaks first.** In the busiest hour, 10× traffic needs 100 requests served against
a capacity of about 90/hour (one local model, ~40 s of model time each) — 111% utilisation,
so the queue grows faster than it drains. Cost at 10× is about $10 a month; nobody escalates
that.

### Step 7 (bonus): add the missing field and re-run the drill

The drill wasted two queries because nothing recorded *"the cook stated a restriction and
the answer clashed with it"*. That's now a flag on every request, backfilled over history.
A second bad answer was planted and the drill re-run: **1 query instead of 4**.

---

## What we learned, in plain words

- **Log the answer, not just the question.** Complaints describe what the app said.
- **Per-step costs change what you'd do.** One lump total would have hidden that tools are
  free and instant and the model is everything.
- **Watch the test fail before you fix it.** My first fix looked sensible, and the test
  proved it didn't work.
- **A prompt is a request; code is a rule.** The model ignored both a safety instruction and
  the allergen data; only the code guard stopped the bad answer.
- **Record which prompt version answered.** Without it you can't tell a regression from bad
  luck.
- **A flag that finds things will also find things wrongly.** The new flag has 3/5 precision
  — fine for triage, unfit as an automatic gate, and said out loud.

---

## Tech stack

| Part | What we used | Why |
|---|---|---|
| Language | **Python 3.13** | |
| Logging | Hand-written **JSONL** traces with spans ([obs/trace_log.py](obs/trace_log.py)) | One file, greppable, no service to run. LangSmith or OpenTelemetry would do the same job with a dashboard |
| Searching | **[logsearch.py](logsearch.py)** — slice by time, user, prompt version, input type, cost, latency, free text, flags | The drill is only as fast as the slices you have |
| The app | The Week 9–10 agent over **MCP** tools | Unchanged except for instrumentation and the fix |
| The model | **Qwen2.5-3B-Instruct, quantised**, via llama.cpp on the CPU | Free, offline. Cost figures price the real token counts at hosted rates |
| Eval suite | The **Week-6** cases and grader, plus the new incident case | A ruler you change mid-measurement measures nothing |
| Safety guard | Plain Python in [app.py](app.py) | Deterministic, testable, and not up for negotiation by the model |

**Cost: nothing.** All of it runs on your own machine.

---

## Folder layout

```
obs/
  trace_log.py          the logger: traces, spans, per-step cost
  flags.py              the diet_conflict flag the drill showed was missing
app.py                  the instrumented app: prompt versions + the safety guard
traffic.py              builds the 500-request haystack and plants the bad answer
logsearch.py            the search tool the drill uses
suite.py                the eval suite: Week-6 cases + incident cases
evals/case_dairy_free.py  DF-01, written from the incident
cost_report.py          cost per stage, and the 10x analysis
backfill_flags.py       adds the new field to old records
plant_second.py         plants the second bad answer for the bonus drill
run_all.py              reports, drills, or the full suite
logs/requests.jsonl     536 logged requests (502 production, 34 development)
results/                everything listed in the Output table
```

---

## How to run it

```bash
pip install -r requirements.txt

python run_all.py --reports    # cost + 10x from the existing log (instant)
python run_all.py --drill      # replay both drills (instant)
python run_all.py --suite      # re-run RED and GREEN (~20 min, local model)
```

Poking around the log yourself:

```bash
python logsearch.py --flag diet_conflict           # the one query that now finds it
python logsearch.py --answer-contains milk         # the query that found it the first time
python logsearch.py --trace t-20261020-ed8e7b --full
python logsearch.py --cost-top 5                   # the most expensive requests
```

---

## Words you'll see, explained simply

| Term | Meaning |
|---|---|
| **Trace** | The full record of one request, from question to answer |
| **Span** | One step inside a request (a tool call, a model call), with its own time and cost |
| **trace id** | The unique name of one request, so a complaint can point at it |
| **Prompt version** | Which version of the instructions answered. Lets you pin a regression to a change. |
| **Context ids** | Exactly which recipe sections were read, so you can tell "wrong text fetched" from "right text misread" |
| **The support drill** | Practising finding one bad answer from a vague complaint, against the clock |
| **Cost per request** | What one answer costs, split by stage so you know what to cut |
| **p50 / p99** | Typical and worst-case time. Customers complain about the p99. |
| **Failure → test loop** | Every real failure becomes a permanent test case, so it can't come back |
| **RED then GREEN** | Watching the new test fail before the fix, and pass after |
| **Canary** | Shipping a change to a small slice of traffic first, and watching |
| **Rollback** | How you undo it quickly. Here it's a config change, not a deploy. |
| **Backfill** | Filling a newly added field in for old records |
