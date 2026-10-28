# Shipping the fix: version bump, canary, rollback

## What changed

| | before | after |
|---|---|---|
| **Prompt version** | `v1.1.0` | **`v1.2.0`** — adds the DIETARY SAFETY rule: check `ingredient_info` before suggesting anything to a cook with a restriction |
| **Retrieval layer** | `substitutes_for` returned `{"use": "milk plus lemon juice", "how": "..."}` | returns each substitute's **own allergens** plus a warning that a substitute is not automatically safe |
| **App layer** | nothing checked the answer | **safety guard `diet_conflict_v1`**: an answer that recommends an allergen clashing with a stated restriction is not sent |

The third one exists because the first two were not enough, and I have the run that
proves it: with v1.2.0 and the allergen data, the suite still failed DF-01 with "use milk
plus lemon juice" (`results/suite_fix1_prompt_only.json`). A prompt asks the model
nicely; the guard is code, and code does not get talked round.

## Canary plan (two lines)

Ship `v1.2.0` + the guard to **10% of traffic for 24 hours**, keeping `v1.1.0` on the rest, and watch
three numbers side by side per version: `flags.diet_conflict` rate (target: zero on the canary), the
`safety_guard` trigger rate (expected: small and non-zero — if it is zero, the guard is not wired up),
and the refusal rate (if the guard is over-firing, this climbs and cooks get unhelpful answers).

## Rollback plan (two lines)

Rollback is a config change, not a deploy: set the prompt version back to `v1.1.0` and
`guard_enabled=false`, because both are read per request rather than baked in. Trigger it if the
refusal rate on the canary rises by more than 5 percentage points over the control, or any cook
reports a *correct* dairy-free answer being blocked — the guard failing safe is still a failure.
