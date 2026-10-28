"""
Search the request log. This is the tool the support drill actually tests.

    python logsearch.py --contains milk                 # searches question AND answer
    python logsearch.py --input-type dietary --since 2026-10-24
    python logsearch.py --user u-0042 --slow-top 5
    python logsearch.py --cost-top 10
    python logsearch.py --trace t-20261028-e42ac6 --full

A complaint almost never describes the question. It describes the ANSWER
("it told her to use milk"), so --contains searches both.

Slices available: time, user, channel, prompt version, input type, status,
cost outliers, latency outliers, and free text.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from obs.trace_log import read_log  # noqa: E402


def match(record, args):
    if args.contains:
        needle = args.contains.lower()
        haystack = (record.get("question", "") + " " + record.get("answer", "")).lower()
        if needle not in haystack:
            return False
    if args.answer_contains and args.answer_contains.lower() not in record.get("answer", "").lower():
        return False
    if args.question_contains and args.question_contains.lower() not in record.get("question", "").lower():
        return False
    if args.user and record.get("user_id") != args.user:
        return False
    if args.channel and record.get("channel") != args.channel:
        return False
    if args.input_type and record.get("input_type") != args.input_type:
        return False
    if args.prompt_version and record.get("prompt_version") != args.prompt_version:
        return False
    if args.status and args.status not in record.get("status", ""):
        return False
    if args.context and not any(args.context.lower() in c.lower() for c in record.get("context_ids", [])):
        return False
    if args.since and record["ts"] < args.since:
        return False
    if args.until and record["ts"] > args.until:
        return False
    if args.flag and not (record.get("flags") or {}).get(args.flag):
        return False
    if args.trace and record["trace_id"] != args.trace:
        return False
    return True


def show_full(record):
    print(json.dumps(record, indent=2, ensure_ascii=False))


def show_row(record):
    totals = record.get("totals", {})
    print(f"{record['trace_id']}  {record['ts']}  {record['user_id']:<8} {record.get('input_type', ''):<12} "
          f"{record.get('prompt_version', ''):<8} {totals.get('ms', 0) / 1000:5.1f}s "
          f"{totals.get('tokens', 0):>6}tok ${totals.get('cost_usd', 0):.5f}")
    print(f"    Q: {' '.join(record.get('question', '').split())[:110]}")
    print(f"    A: {' '.join(record.get('answer', '').split())[:110]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contains", help="free text in the question OR the answer")
    parser.add_argument("--answer-contains")
    parser.add_argument("--question-contains")
    parser.add_argument("--user")
    parser.add_argument("--channel")
    parser.add_argument("--input-type")
    parser.add_argument("--prompt-version")
    parser.add_argument("--status")
    parser.add_argument("--context", help="a retrieved context id, e.g. R-003 or ingredient-db")
    parser.add_argument("--since", help="ISO timestamp, e.g. 2026-10-24")
    parser.add_argument("--until")
    parser.add_argument("--trace")
    parser.add_argument("--flag", help="a flag that must be true, e.g. diet_conflict")
    parser.add_argument("--cost-top", type=int, help="the N most expensive matching requests")
    parser.add_argument("--slow-top", type=int, help="the N slowest matching requests")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--count", action="store_true", help="just the number of matches")
    parser.add_argument("--full", action="store_true", help="print whole records")
    args = parser.parse_args()

    records = [r for r in read_log() if match(r, args)]
    if args.cost_top:
        records = sorted(records, key=lambda r: -r.get("totals", {}).get("cost_usd", 0))[:args.cost_top]
    elif args.slow_top:
        records = sorted(records, key=lambda r: -r.get("totals", {}).get("ms", 0))[:args.slow_top]

    print(f"{len(records)} matching request(s)\n")
    if args.count:
        return
    for record in records[:args.limit]:
        show_full(record) if args.full else show_row(record)
    if len(records) > args.limit and not args.full:
        print(f"\n... {len(records) - args.limit} more (use --limit)")


if __name__ == "__main__":
    main()
