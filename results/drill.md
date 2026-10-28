# The support drill: finding one bad answer in 501

## The complaint, in full

> "A cook said it suggested a dairy swap that wasn't actually dairy-free. Maybe Tuesday?"

No trace id. No recipe. No user. No exact time. That is everything, and in production
that really is everything you get.

## Result

| | |
|---|---|
| **Found** | `t-20261020-ed8e7b` — 2026-10-20 16:40 UTC, user `u-0017`, mobile, prompt `v1.1.0` |
| **Time to find (machine)** | **00:01** — the four queries below run in under a second |
| **Queries needed** | **4** |
| **The slice that found it** | **free text over the ANSWER field** (`--answer-contains milk`) |
| **Haystack** | 501 logged requests over 9 days |
| **Verified against** | `logs/.answer_key.json`, sealed by the planting script and opened only after the find |

**The honest caveat on the clock.** 00:01 is the machine time for the four queries. It does
not include a human reading the output and deciding what to try next, which is the real
cost of a drill; a person doing this from scratch would take two to four minutes. The
number I would defend is **four queries, and the slice that found it**, because that is
the part the tooling determines. I also knew the *shape* of the bug, having planted it —
mitigated by the planting script choosing the time, user and trace id at random and
sealing them, so the search could not be short-circuited by memory.

## The four queries

| # | Query | Result | What it told me |
|---|---|---|---|
| 1 | `--count` | 501 | the size of the haystack |
| 2 | `--input-type dietary --count` | 100 | too coarse: a fifth of all traffic is dietary |
| 3 | `--contains "dairy-free" --count` | 48 | still too many to read |
| 4 | **`--answer-contains milk`** | **4** | readable. Three were correct answers *warning* about dairy; the fourth recommended it |

The fourth query is the one that worked, and the reason is worth keeping: **the complaint
described the answer, not the question.** The cook did not say "I asked about buttermilk",
they said "it suggested something with dairy in it". A log that only indexed inputs would
have been useless here, and three of my four queries were spent before I used the answer
text.

The four candidates, for honesty about how close the near-misses were:

```
t-20261020-ed8e7b  Q: I'm dairy-free. What can I use instead of the buttermilk in the pancakes?
                   A: For your pancakes, you can use milk plus lemon juice...        <-- the bad one
t-20261023-86952b  A: Not as written: the Buttermilk Pancakes contain ... both dairy.   (correct)
t-20261025-7e43a7  A: Not as written: the Buttermilk Pancakes contain ... both dairy.   (correct)
t-20261028-f98f5d  A: Not as written: the Buttermilk Pancakes contain ... both dairy.   (correct)
```

## The log field whose absence cost the time

Queries 2 and 3 were wasted because nothing in the log says **"this answer recommended an
ingredient that clashes with a restriction the cook stated"**. The app had both halves of
that at the time — the question said "dairy-free", the tool result named milk — and wrote
neither down as a flag.

The missing field: **`flags.diet_conflict`**, set when a stated restriction and a suggested
ingredient's allergens disagree. With it, query 1 is
`logsearch.py --flag diet_conflict` and returns exactly one row. See
[bonus_second_drill.md](bonus_second_drill.md) for that field added and the drill re-run.
