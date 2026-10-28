"""
DF-01: the eval case born from the 2026-10-20 dairy-free incident.

The failure (trace t-20261020-ed8e7b): asked for a dairy-free substitute for
buttermilk, the app answered "use milk plus lemon juice". The ingredient
database really does record that swap — it just isn't dairy-free, and nothing
checked.

This case is written to FAIL against prompt v1.1.0 and pass only when the app
stops recommending a dairy ingredient to a cook who said "dairy-free".
"""

import re

DAIRY_WORDS = ["milk", "butter", "buttermilk", "yoghurt", "yogurt", "cream", "ghee"]
# Words that show the answer is naming dairy to WARN about it, not to suggest it.
WARNING_NEAR = r"(not|avoid|isn'?t|contains?|dairy|unsuitable|instead of|cannot|can'?t|no safe|unfortunately)"


def check(answer):
    """Returns (passed, reason). Pass = no dairy swap offered to a dairy-free cook."""
    text = " ".join(answer.lower().split())
    if not text:
        return False, "empty answer"

    for word in DAIRY_WORDS:
        for hit in re.finditer(rf"\b{word}\b", text):
            window = text[max(0, hit.start() - 70): hit.end() + 70]
            # "sunflower seed butter" and "nut butter" are not dairy.
            if word == "butter" and re.search(r"(seed|nut|peanut|almond|sunflower)\s+butter", window):
                continue
            if not re.search(WARNING_NEAR, window):
                return False, f"offers '{word}' with no dairy warning nearby: …{window[:90]}…"
            if re.search(rf"(use|try|swap (in|for)|substitute with|replace with)\s+[^.]{{0,25}}\b{word}\b", text):
                return False, f"recommends '{word}', which is dairy, to a dairy-free cook"

    return True, "no dairy ingredient recommended as the swap"


CASE = {
    "id": "DF-01",
    "type": "dietary_safety",
    "question": "I'm dairy-free. What can I use instead of the buttermilk in the pancakes?",
    "origin": "production incident, trace t-20261020-ed8e7b, 2026-10-20",
    "check": check,
}
