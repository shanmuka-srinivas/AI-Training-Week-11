"""
Add the flags field to every log record written before the field existed.

    python backfill_flags.py

The drill showed the gap: nothing in the log said "this answer recommended something
that clashes with a restriction the cook stated". The app records it now. This fills it
in for the history, so the index is useful on day one instead of in nine days' time.

Re-stamping old records is a judgement call: the flag is computed from the question and
answer that were already stored, so nothing is invented, but a reader should know the
field was derived later. That is what "backfilled": true records.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from obs.flags import compute_flags  # noqa: E402
from obs.trace_log import LOG_FILE  # noqa: E402

records = [json.loads(line) for line in LOG_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
added = 0
for record in records:
    if "flags" not in record:
        record["flags"] = compute_flags(record.get("question", ""), record.get("answer", ""))
        record["flags"]["backfilled"] = True
        added += 1

with LOG_FILE.open("w", encoding="utf-8") as handle:
    for record in records:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

conflicts = [r for r in records if (r.get("flags") or {}).get("diet_conflict")]
print(f"{len(records)} records, flags added to {added}")
print(f"diet_conflict = true on {len(conflicts)}:")
for record in conflicts:
    print(f"   {record['trace_id']}  {record['ts']}  {record['flags']['conflicts']}")
