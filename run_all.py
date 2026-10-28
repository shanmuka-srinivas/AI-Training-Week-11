"""
Run the week:

    python run_all.py --reports     recompute the reports from the existing log (instant)
    python run_all.py --drill       replay both support drills (instant)
    python run_all.py --suite       re-run the eval suite RED and GREEN (~20 min, local model)

The log in logs/requests.jsonl is kept, because the drills and the cost report are
about a log that already exists. Rebuilding it from scratch would need
`python app.py "..."` runs plus `python traffic.py`.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(title, command):
    print("=" * 78)
    print(title)
    print("=" * 78)
    code = subprocess.run([sys.executable, *command], cwd=ROOT).returncode
    print()
    return code


if "--suite" in sys.argv:
    run("eval suite, RED (prompt v1.1.0, no guard)", ["suite.py", "--tag", "red_replay",
                                                      "--prompt-version", "v1.1.0", "--no-guard"])
    run("eval suite, GREEN (prompt v1.2.0 + diet_conflict guard)", ["suite.py", "--tag", "green_replay",
                                                                    "--prompt-version", "v1.2.0"])

if "--drill" in sys.argv or len(sys.argv) == 1:
    run("drill 1, as it was run before the flag existed (4 queries)",
        ["logsearch.py", "--answer-contains", "milk"])
    run("drill 2, with the flag added (1 query)", ["logsearch.py", "--flag", "diet_conflict"])

run("cost per stage, and the 10x question", ["cost_report.py"])
print("Read RESULTS.md, then results/drill.md, results/cost_by_stage.md, results/tenx.md.")
