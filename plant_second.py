"""
Plant the SECOND bad answer for the bonus drill, at a random time and user, with
the answer sealed again.

    python plant_second.py
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "logs" / "requests.jsonl"
KEY = ROOT / "logs" / ".answer_key_2.json"

rng = random.Random()
records = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
bad = next(r for r in records
           if "plain flour as a substitute" in r.get("answer", "").lower() and not r.get("safety_guard"))
records = [r for r in records if r["trace_id"] != bad["trace_id"]]

first = min(r["ts"] for r in records)
last = max(r["ts"] for r in records)
start = datetime.fromisoformat(first)
span = int((datetime.fromisoformat(last) - start).total_seconds())
when = (start + timedelta(seconds=rng.randrange(span))).replace(hour=rng.choice([9, 11, 13, 15, 18]))

bad = dict(bad)
bad.update({"trace_id": f"t-{when:%Y%m%d}-{rng.getrandbits(24):06x}", "ts": when.isoformat(timespec="seconds"),
            "user_id": f"u-{rng.randrange(1, 61):04d}", "channel": rng.choice(["web", "mobile", "api"])})
records.append(bad)
records.sort(key=lambda r: r["ts"])

with LOG.open("w", encoding="utf-8") as handle:
    for record in records:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

KEY.write_text(json.dumps({"_warning": "SEALED until the second drill is timed.",
                           "planted_trace_id": bad["trace_id"], "ts": bad["ts"],
                           "user_id": bad["user_id"], "answer": bad["answer"]}, indent=2), encoding="utf-8")
print(f"second failure re-planted among {len(records)} records; key sealed in {KEY.name}")
