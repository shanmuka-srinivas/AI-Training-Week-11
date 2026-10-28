"""
The log field that was missing on 2026-10-20.

During the drill, two queries were wasted because nothing in the log recorded the
one thing that actually defines the incident: the cook stated a restriction, and
the answer recommended an ingredient that clashes with it. The app knew both
halves at the time and wrote down neither.

This computes that flag on every request, so the same incident is one query away.
"""

import re

RESTRICTIONS = {
    "dairy-free": ["milk"],
    "vegan": ["milk", "egg", "fish", "crustacean shellfish"],
    "gluten-free": ["gluten"],
    "nut allergy": ["tree nuts", "peanut"],
    "sesame allergy": ["sesame"],
}

RESTRICTION_PATTERNS = {
    "dairy-free": r"dairy[- ]?free|no dairy|lactose",
    "vegan": r"\bvegan\b",
    "gluten-free": r"gluten[- ]?free|coeliac|celiac",
    "nut allergy": r"nut[- ]?free|nut allerg",
    "sesame allergy": r"sesame[- ]?free|sesame allerg",
}

ALLERGEN_WORDS = {
    "milk": "milk", "buttermilk": "milk", "butter": "milk", "cream": "milk", "yoghurt": "milk",
    "yogurt": "milk", "ghee": "milk", "cheese": "milk",
    "flour": "gluten", "wheat": "gluten", "rye": "gluten", "barley": "gluten",
    "peanut": "peanut", "almond": "tree nuts", "cashew": "tree nuts", "hazelnut": "tree nuts",
    "tahini": "sesame", "sesame": "sesame",
    "anchovy": "fish", "fish sauce": "fish", "shrimp": "crustacean shellfish", "egg": "egg",
}

# Phrases that show an allergen is being named as a WARNING, not a recommendation.
WARNING = r"(not|avoid|isn'?t|cannot|can'?t|contains?|free from|unsuitable|instead of|no safe|unfortunately|do not)"


def allergens_in(text):
    lowered = " ".join(str(text).lower().split())
    found = []
    for word, allergen in ALLERGEN_WORDS.items():
        if not re.search(rf"\b{word}", lowered):
            continue
        if word == "butter" and re.search(r"(seed|nut|peanut|almond|sunflower)\s+butter", lowered):
            continue
        if allergen not in found:
            found.append(allergen)
    return found


def restrictions_in(text):
    lowered = str(text).lower()
    return [name for name, pattern in RESTRICTION_PATTERNS.items() if re.search(pattern, lowered)]


def compute_flags(question, answer):
    """
    Returns the flags block for one request.

    diet_conflict is True when the cook stated a restriction AND the answer names an
    ingredient carrying a clashing allergen without warning about it.
    """
    asked = restrictions_in(question)
    in_answer = allergens_in(answer)
    conflicts = []
    lowered = " ".join(str(answer).lower().split())
    for restriction in asked:
        for allergen in RESTRICTIONS.get(restriction, []):
            if allergen not in in_answer:
                continue
            word = next((w for w, a in ALLERGEN_WORDS.items() if a == allergen and re.search(rf"\b{w}", lowered)), None)
            if not word:
                continue
            hit = re.search(rf"\b{word}", lowered)
            window = lowered[max(0, hit.start() - 70): hit.end() + 70]
            if not re.search(WARNING, window):
                conflicts.append(f"{restriction} vs {allergen}")
    return {
        "diet_requested": asked,
        "allergens_in_answer": in_answer,
        "diet_conflict": bool(conflicts),
        "conflicts": conflicts,
    }
