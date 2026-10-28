"""
The eval set: 46 test cases, grouped by PROBLEM TYPE.

The first four problem types are the ranked taxonomy from Week 5. Every failure
read in Week 5 is here as a permanent regression test (source "W5 T-xxx"), so it
can never come back unnoticed. Each type also gets a few NEW cases, so a fix
can't pass just by memorising the 20 Week 5 questions.

    wrong_sentence    Quotes a sentence that shares words with the question but doesn't answer it
    false_refusal     Refuses questions the recipe cards can answer
    allergen_yes_no   Allergen questions get a hint instead of a clear yes or no
    indirect          Right information, but the cook has to work the answer out
    substitution      "Can I swap X for Y?" (Track B's focus), graded by the Gemini judge
    must_refuse       Questions the cards can't answer. A fix must NOT start answering these.
    already_working   The Week 5 passes, kept so a fix can't quietly break them

Every expected fact was copied from the recipe cards in data/recipes/.

HOW A CASE IS SCORED (all rule checks; they are free and exact)
    expect             "answer" or "refuse"
    must_contain_any   the answer must contain at least one of these
    must_contain_all   the answer must contain every one of these
    min_distinct       the answer must mention at least n of these
    recipe             the citation must come from this recipe (the "source present" check)
    judge              "substitution": the Gemini judge decides pass/fail instead of text matching.
                       The rule checks for citation and recipe still run first.
"""

VEGAN_TITLES = [
    "Rosemary Focaccia", "Neapolitan Pizza Dough", "Classic Hummus", "Two-Kilo Country Sourdough",
    "Wholegrain Rye Sourdough", "Buckwheat Sourdough", "Vegan Napa Cabbage Kimchi", "Caraway Sauerkraut",
]

CASES = [
    # ======================================================================
    # 1. wrong_sentence
    # ======================================================================
    {"id": "WS-01", "type": "wrong_sentence", "source": "W5 T-004",
     "question": "how many pancakes does the buttermilk recipe make",
     "expect": "answer", "recipe": "R-003", "must_contain_any": ["twelve"]},
    {"id": "WS-02", "type": "wrong_sentence", "source": "W5 T-034",
     "question": "how much garlic in the hummus",
     "expect": "answer", "recipe": "R-004", "must_contain_any": ["15 g"]},
    {"id": "WS-03", "type": "wrong_sentence", "source": "W5 T-048",
     "question": "how much sugar in the pancakes",
     "expect": "answer", "recipe": "R-003", "must_contain_any": ["24 g"]},
    {"id": "WS-04", "type": "wrong_sentence", "source": "W5 T-051",
     "question": "do I need to toast the caraway for the rye bread",
     "expect": "answer", "recipe": "R-102", "must_contain_any": ["Toast the caraway"]},
    {"id": "WS-05", "type": "wrong_sentence", "source": "W5 T-052",
     "question": "how warm should the water be for the rosemary focaccia",
     "expect": "answer", "recipe": "R-001", "must_contain_any": ["24 C"]},
    {"id": "WS-06", "type": "wrong_sentence", "source": "W5 T-053",
     "question": "is the hummus nut free",
     "expect": "answer", "recipe": "R-004", "must_contain_any": ["Contains sesame"]},
    {"id": "WS-07", "type": "wrong_sentence", "source": "new",
     "question": "how much yeast goes in the pizza dough",
     "expect": "answer", "recipe": "R-002", "must_contain_any": ["1.8 g"]},
    {"id": "WS-08", "type": "wrong_sentence", "source": "new",
     "question": "how much olive oil in the focaccia",
     "expect": "answer", "recipe": "R-001", "must_contain_any": ["64 g"]},
    {"id": "WS-09", "type": "wrong_sentence", "source": "new",
     "question": "how much lemon juice goes in the hummus",
     "expect": "answer", "recipe": "R-004", "must_contain_any": ["90 g"]},
    {"id": "WS-10", "type": "wrong_sentence", "source": "new",
     "question": "how many grams of salt in the buckwheat loaf",
     "expect": "answer", "recipe": "R-103", "must_contain_any": ["12 g"]},

    # ======================================================================
    # 2. false_refusal
    # ======================================================================
    {"id": "FR-01", "type": "false_refusal", "source": "W5 T-016",
     "question": "which recipes are vegan",
     "expect": "answer", "min_distinct": {"n": 2, "of": VEGAN_TITLES}},
    {"id": "FR-02", "type": "false_refusal", "source": "W5 T-023",
     "question": "is the buckwheat loaf safe for coeliacs",
     "expect": "answer", "recipe": "R-103", "must_contain_any": ["coeliac", "Free from gluten"]},
    {"id": "FR-03", "type": "false_refusal", "source": "W5 T-030",
     "question": "whats the oven temp for the rye sourdough",
     "expect": "answer", "recipe": "R-102", "must_contain_any": ["250 C", "190 C"]},
    {"id": "FR-04", "type": "false_refusal", "source": "W5 T-042",
     "question": "my country loaf came out flat and spread, what went wrong",
     "expect": "answer", "recipe": "R-101", "must_contain_any": ["bulk ferment ran long"]},
    {"id": "FR-05", "type": "false_refusal", "source": "W5 T-054",
     "question": "how much salt in the vegan kimchi compared to the traditional one",
     "expect": "answer", "must_contain_all": ["75 g", "90 g"]},
    {"id": "FR-06", "type": "false_refusal", "source": "new",
     "question": "whats the proof temp for the buckwheat bread",
     "expect": "answer", "recipe": "R-103", "must_contain_any": ["26 C"]},
    {"id": "FR-07", "type": "false_refusal", "source": "new",
     "question": "my focaccia came out dense, why",
     "expect": "answer", "recipe": "R-001", "must_contain_any": ["over-floured"]},

    # ======================================================================
    # 3. allergen_yes_no
    # ======================================================================
    {"id": "AL-01", "type": "allergen_yes_no", "source": "W5 T-017",
     "question": "does the traditional kimchi have fish in it",
     "expect": "answer", "recipe": "R-104", "must_contain_any": ["Contains fish"]},
    {"id": "AL-02", "type": "allergen_yes_no", "source": "W5 T-031",
     "question": "do the pancakes contain nuts",
     # The card never mentions nuts either way, so the only safe behaviour is to refuse.
     "expect": "refuse"},
    {"id": "AL-03", "type": "allergen_yes_no", "source": "new",
     "question": "does the focaccia have nuts in it",
     "expect": "answer", "recipe": "R-001", "must_contain_any": ["tree nuts"]},
    {"id": "AL-04", "type": "allergen_yes_no", "source": "new",
     "question": "is there egg in the buttermilk pancakes",
     "expect": "answer", "recipe": "R-003", "must_contain_any": ["hen egg"]},
    {"id": "AL-05", "type": "allergen_yes_no", "source": "new",
     "question": "does the vegan kimchi contain shellfish",
     "expect": "answer", "recipe": "R-105", "must_contain_any": ["Free from fish, shellfish"]},

    # ======================================================================
    # 4. indirect
    # ======================================================================
    {"id": "IN-01", "type": "indirect", "source": "W5 T-002",
     "question": "can I make the pizza dough the same day or does it have to go in the fridge",
     "expect": "answer", "recipe": "R-002", "must_contain_any": ["at least twenty-four hours"]},

    # ======================================================================
    # 5. substitution, graded by the Gemini judge
    #    "reference" is what the card actually says about the swap, for humans reading reports.
    #    The judge gets the full recipe card(s), not this note.
    # ======================================================================
    {"id": "SU-01", "type": "substitution", "source": "W5 log T-006",
     "question": "can I swap the tahini for peanut butter in the hummus",
     "judge": "substitution", "reference_recipes": ["R-004"],
     "reference": "The card doesn't discuss replacing tahini at all."},
    {"id": "SU-02", "type": "substitution", "source": "W5 log T-018",
     "question": "can I use dried yeast instead of fresh for the pizza dough",
     "judge": "substitution", "reference_recipes": ["R-002"],
     "reference": "The card doesn't discuss dried yeast. It only stresses the tiny fresh yeast weight is deliberate."},
    {"id": "SU-03", "type": "substitution", "source": "W5 log T-047",
     "question": "what can I use instead of glutinous rice flour in kimchi",
     "judge": "substitution", "reference_recipes": ["R-104", "R-105"],
     "reference": "No substitute is given. The porridge feeds the lactobacilli and helps the paste cling."},
    {"id": "SU-04", "type": "substitution", "source": "new",
     "question": "can I use psyllium powder instead of whole husk in the buckwheat loaf",
     "judge": "substitution", "reference_recipes": ["R-103"],
     "reference": "Whole husk is specified. Powder gels faster, sets tighter, and gives a rubbery crumb."},
    {"id": "SU-05", "type": "substitution", "source": "new",
     "question": "can I leave the psyllium out of the gluten-free sourdough",
     "judge": "substitution", "reference_recipes": ["R-103"],
     "reference": "No. It can't be substituted; without it the loaf bakes into gravel."},
    {"id": "SU-06", "type": "substitution", "source": "new",
     "question": "can I use plain flour instead of Tipo 00 for the pizza",
     "judge": "substitution", "reference_recipes": ["R-002"],
     "reference": "The card doesn't discuss other flours."},
    {"id": "SU-07", "type": "substitution", "source": "new",
     "question": "can I use regular milk instead of buttermilk in the pancakes",
     "judge": "substitution", "reference_recipes": ["R-003"],
     "reference": "Not directly covered, but the card says buttermilk is there for its acid, which reacts with the bicarbonate of soda."},
    {"id": "SU-08", "type": "substitution", "source": "new",
     "question": "can I use table salt instead of fine sea salt in the sauerkraut",
     "judge": "substitution", "reference_recipes": ["R-106"],
     "reference": "The card doesn't discuss salt types. It stresses the 2% salt weight."},
    {"id": "SU-09", "type": "substitution", "source": "new",
     "question": "can I replace the fish sauce with kelp and shiitake stock in kimchi",
     "judge": "substitution", "reference_recipes": ["R-104", "R-105"],
     "reference": "Yes, that's the vegan card's approach, but as a separate formula with its own weights, and it ferments a day longer."},
    {"id": "SU-10", "type": "substitution", "source": "new",
     "question": "can I use a cheaper oil instead of extra virgin olive oil on the focaccia",
     "judge": "substitution", "reference_recipes": ["R-001"],
     "reference": "The card says to use an oil you'd happily put on a salad, because you'll taste it."},
    {"id": "SU-11", "type": "substitution", "source": "new",
     "question": "can I make the traditional kimchi vegan by just leaving out the fish sauce and shrimp",
     "judge": "substitution", "reference_recipes": ["R-104", "R-105"],
     "reference": "No. The vegan card is a separate formula; removing them and putting nothing back gives a thin kimchi that sours more slowly."},

    # ======================================================================
    # 6. must_refuse: the cards cannot answer these
    # ======================================================================
    {"id": "MR-01", "type": "must_refuse", "source": "W5 log T-007",
     "question": "how many calories in a slice of the country sourdough", "expect": "refuse"},
    {"id": "MR-02", "type": "must_refuse", "source": "W5 log T-020",
     "question": "what wine goes with the rosemary focaccia", "expect": "refuse"},
    {"id": "MR-03", "type": "must_refuse", "source": "W5 log T-035",
     "question": "where can I buy gochugaru", "expect": "refuse"},
    {"id": "MR-04", "type": "must_refuse", "source": "W5 log T-057",
     "question": "can kids eat kimchi", "expect": "refuse"},
    {"id": "MR-05", "type": "must_refuse", "source": "W5 log T-059",
     "question": "how do I make a sourdough starter from scratch", "expect": "refuse"},
    {"id": "MR-06", "type": "must_refuse", "source": "new",
     "question": "how much sodium per serving is in the sauerkraut", "expect": "refuse"},

    # ======================================================================
    # 7. already_working: the Week 5 passes
    # ======================================================================
    {"id": "OK-01", "type": "already_working", "source": "W5 T-008",
     "question": "how long should I knead the neapolitan dough",
     "expect": "answer", "recipe": "R-002", "must_contain_any": ["ten minutes"]},
    {"id": "OK-02", "type": "already_working", "source": "W5 T-011",
     "question": "my sauerkraut smells like sulphur, is it ruined?",
     "expect": "answer", "recipe": "R-106", "must_contain_any": ["first three days"]},
    {"id": "OK-03", "type": "already_working", "source": "W5 T-024",
     "question": "how do i make the kelp stock for the vegan kimchi",
     "expect": "answer", "recipe": "R-105", "must_contain_any": ["dried kelp"]},
    {"id": "OK-04", "type": "already_working", "source": "W5 T-040",
     "question": "what's the starter percentage in the rye",
     "expect": "answer", "recipe": "R-102", "must_contain_any": ["thirty percent", "30%"]},
    {"id": "OK-05", "type": "already_working", "source": "W5 T-045",
     "question": "how much ginger in the vegan kimchi",
     "expect": "answer", "recipe": "R-105", "must_contain_any": ["17 g"]},
    {"id": "OK-06", "type": "already_working", "source": "W5 T-058",
     "question": "how long to cook the chickpeas",
     "expect": "answer", "recipe": "R-004", "must_contain_any": ["fifty minutes"]},
]

PROBLEM_TYPES = [
    ("wrong_sentence", "Quotes a sentence that shares words with the question but doesn't answer it"),
    ("false_refusal", "Refuses questions the recipe cards can answer"),
    ("allergen_yes_no", "Allergen questions get a hint instead of a clear yes or no"),
    ("indirect", "Right information, but the cook has to work the answer out"),
    ("substitution", "Substitution questions (graded by the Gemini judge)"),
    ("must_refuse", "Questions the cards can't answer (the app must refuse)"),
    ("already_working", "Week 5 passes (regression guard)"),
]
