# Bonus: wire the drill shut, then run it again

## What was added

One field, `flags.diet_conflict`, computed on every request in
[obs/flags.py](../obs/flags.py) and backfilled over the history
([backfill_flags.py](../backfill_flags.py)):

> the cook stated a restriction **and** the answer names an ingredient carrying a clashing
> allergen, with no warning next to it.

Both halves were already in the log on 2026-10-20. Nothing joined them up.

## The two drills

| | drill 1 (dairy-free) | drill 2 (gluten-free) |
|---|---|---|
| Complaint | "suggested a dairy swap that wasn't dairy-free" | "suggested a swap that wasn't gluten-free" |
| **Queries needed** | **4** | **1** |
| Rows to read at the end | 4 | 5 |
| Rows to read at the *first* query | 501 | **5** |
| The slice that found it | free text over the answer (`--answer-contains milk`) | **`--flag diet_conflict`** |
| Found | `t-20261020-ed8e7b` | `t-20261019-c59850` (first row) |
| Machine time | 00:01 | 00:01 |

**The field that closed the gap: `flags.diet_conflict`.** In drill 1 the first three queries
(501 rows → 100 → 48) were spent narrowing by hand, because the log could describe *what was
asked* and *what was answered* but not *that the two disagreed*. In drill 2 the first query
returns a readable list.

Machine time is ~1 second in both cases and is not the interesting number; the honest
measure is **four queries down to one**, and 501 rows of triage down to 5.

## What the flag gets wrong, which matters more than the win

Of the 5 rows it returned, **2 are false positives**:

| trace | answer | why it fired | verdict |
|---|---|---|---|
| `t-20261028-832c98` | "Yes, buckwheat **flour** is safe for coeliacs." | the word list maps *flour → gluten* | **false positive** — buckwheat is gluten-free, and the answer is correct |
| `t-20261028-d678c6` | "No safe substitute … please use a non-dairy **milk** alternative" | "milk" appears, and "non-dairy" is not in the warning vocabulary | **false positive** — the answer is safe |

So the flag's precision here is **3/5**. That is fine for what it is — a triage aid that turns
501 rows into 5 — and wrong for anything else. It must not become an automatic gate, and
the two misses point at the obvious next fixes: treat "buckwheat flour", "rice flour" and
"non-dairy milk" as compound terms rather than keyword hits.

It is also worth saying that 3 of the 5 rows are my own development runs from today rather
than cook traffic. Real production would tag those with an environment field, and that is
the next field I would add.
