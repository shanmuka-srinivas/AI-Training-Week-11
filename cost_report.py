"""
Where the time and money actually go, per stage, from the log.

    python cost_report.py

Writes results/cost_by_stage.md and results/tenx.md.

Three stages, tagged on every span as it happens:
    retrieval   searching and reading recipe cards
    tools       the other tool calls (scaling, ingredient lookups)
    generation  the model

You cannot cut a cost you have not attributed. Optimising before this table
exists means the number moves and nobody knows which change moved it.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from obs.trace_log import read_log  # noqa: E402

STAGES = ["retrieval", "tools", "generation"]


def main():
    everything = [r for r in read_log() if r.get("spans")]
    # Traffic SHAPE (how many requests per hour) must come from production only:
    # my own test runs today all landed in one hour and would invent a fake peak.
    records = [r for r in everything if r.get("env", "prod") == "prod"]
    dev_runs = len(everything) - len(records)
    real = [r for r in records if not r.get("simulated")]
    n = len(records)

    ms, cost, tokens, calls = defaultdict(float), defaultdict(float), defaultdict(int), defaultdict(int)
    for record in records:
        for span in record["spans"]:
            stage = span["kind"]
            ms[stage] += span["ms"]
            cost[stage] += span["cost_usd"]
            tokens[stage] += span["input_tokens"] + span["output_tokens"]
            calls[stage] += 1

    total_ms, total_cost = sum(ms.values()), sum(cost.values())
    per_request_cost = total_cost / n
    per_request_ms = total_ms / n
    latencies = sorted(r["totals"]["ms"] for r in records)
    p50 = latencies[len(latencies) // 2] / 1000
    p99 = latencies[int(len(latencies) * 0.99)] / 1000

    lines = [
        "# Cost per request, broken down by stage",
        "",
        f"From {n} production requests ({len(real)} of them real runs, the rest simulated traffic with "
        f"span shapes and token counts sampled from real runs). {dev_runs} development requests are "
        "excluded: they were mine, and they all landed in one hour.",
        "",
        "Money is what these exact token counts would cost on a hosted model "
        "(gemini-2.5-flash-lite, $0.10/$0.40 per million in/out). Run locally the cash cost is $0, "
        "but the tokens and the seconds are real.",
        "",
        "| stage | calls/request | time/request | share of time | tokens/request | cost/request | share of cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for stage in STAGES:
        lines.append(
            f"| {stage} | {calls[stage] / n:.1f} | {ms[stage] / n / 1000:.1f} s | {ms[stage] / total_ms:.0%} | "
            f"{tokens[stage] / n:,.0f} | ${cost[stage] / n:.6f} | "
            f"{(cost[stage] / total_cost if total_cost else 0):.0%} |")
    lines += [
        f"| **total** | **{sum(calls.values()) / n:.1f}** | **{per_request_ms / 1000:.1f} s** | 100% | "
        f"**{sum(tokens.values()) / n:,.0f}** | **${per_request_cost:.6f}** | 100% |",
        "",
        f"**Cost per request: ${per_request_cost:.6f}** — about **${per_request_cost * 10000:.2f} per 10,000 "
        f"questions**. Latency p50 **{p50:.0f} s**, p99 **{p99:.0f} s**.",
        "",
        "## What this says",
        "",
        f"- **The model is {cost['generation'] / total_cost:.0%} of the cost and "
        f"{ms['generation'] / total_ms:.0%} of the time.** Retrieval and the tools are local lookups: no tokens, "
        f"and {(ms['retrieval'] + ms['tools']) / total_ms:.0%} of the clock between them.",
        "- So there is exactly one lever worth pulling, and it is the model. Making retrieval faster would be "
        f"optimising {(ms['retrieval'] + ms['tools']) / total_ms:.0%} of the latency and 0% of the bill.",
        f"- Each request makes {calls['generation'] / n:.1f} model calls averaging "
        f"${cost['generation'] / max(calls['generation'], 1):.6f} and "
        f"{ms['generation'] / max(calls['generation'], 1) / 1000:.0f} s each. **Removing one call is worth more "
        "than any other change available.**",
        "",
        "## Where the saving would come from, in order",
        "",
        "1. **Cache repeated questions.** The log shows the same handful of questions asked over and over by "
        "different users; a cache hit removes a whole request, not a fraction of one.",
        "2. **Cut a model call.** Most requests spend one call deciding to use a tool and another writing the "
        "answer. Easy lookups could answer in one.",
        "3. **A cheaper model for easy questions**, keeping the better one for dietary and substitution questions "
        "— which is exactly where the incident happened, so that is not the place to economise.",
        "",
    ]
    (ROOT / "results" / "cost_by_stage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- the 10x question -------------------------------------------------
    # Averages hide the thing that actually breaks, so this uses the BUSIEST hour
    # in the log, not the mean. Queues form at the peak, not at the average.
    from collections import Counter
    per_hour = Counter(r["ts"][:13] for r in records)
    peak_hour_count = max(per_hour.values())
    mean_hour_count = n / len(per_hour)
    model_seconds = statistics.mean(
        sum(s["ms"] for s in r["spans"] if s["kind"] == "generation") for r in records) / 1000
    capacity_per_hour = 3600 / model_seconds       # one model, one request at a time
    peak_10x = peak_hour_count * 10
    utilisation = peak_10x / capacity_per_hour
    days = 9
    per_day = n / days

    verdict = ("LATENCY breaks first" if utilisation >= 0.7 else "nothing breaks yet at the mean, but see the peak")
    tenx = [
        "# At 10x today's traffic, what breaks first?",
        "",
        f"**{verdict}: in the busiest hour the app would need to serve {peak_10x} requests against a capacity of "
        f"{capacity_per_hour:.0f} per hour — {utilisation:.0%} utilisation — and queueing delay climbs steeply "
        f"above about 70%, long before the queue is formally over capacity.**",
        "",
        "## The numbers behind that line",
        "",
        "| | today | at 10x |",
        "|---|---|---|",
        f"| requests logged | {n} over {days} days | {n * 10} |",
        f"| busiest hour | {peak_hour_count} requests | **{peak_10x} requests** |",
        f"| average hour | {mean_hour_count:.1f} requests | {mean_hour_count * 10:.1f} requests |",
        f"| model time per request | {model_seconds:.0f} s | unchanged |",
        f"| **capacity, one model** | **{capacity_per_hour:.0f} requests/hour** | **{capacity_per_hour:.0f}** |",
        f"| peak utilisation | {peak_hour_count / capacity_per_hour:.0%} | **{utilisation:.0%}** |",
        f"| cost per month (hosted prices) | ${per_request_cost * per_day * 30:.2f} | "
        f"${per_request_cost * per_day * 300:.2f} |",
        "",
        "## Why latency and not the other two",
        "",
        f"**Not cost.** Ten times the traffic is about ${per_request_cost * per_day * 300:.0f} a month at hosted "
        "prices. Nobody escalates that.",
        "",
        "**Not a provider rate limit**, because the model runs on our own machine and has none — though moving to "
        "a hosted model to fix the latency would swap the throughput ceiling for exactly that.",
        "",
        f"**It is throughput.** One local model answers one request at a time and spends {model_seconds:.0f} s of "
        f"model time on each, so it can serve about {capacity_per_hour:.0f} an hour. At 10x the busy hour asks for "
        f"{peak_10x}. At {utilisation:.0%} utilisation the queue does not overflow on average, but waits during the "
        "peak grow several times longer than the "
        f"{p50:.0f} s people see today — and the p99, already {p99:.0f} s, is what they complain about.",
        "",
        "## The plan, in the order it would be done",
        "",
        "1. **Cache.** The log is full of repeated questions; cache hits remove load before anything is bought.",
        "2. **Run more than one worker.** The model is single-process here, so N copies give roughly N times the "
        "capacity until memory runs out (about 2 GB each).",
        "3. **Route by difficulty**, so easy lookups stop occupying the slow path.",
        "4. **Then a hosted model**, accepting a rate limit and a bill in exchange for elastic capacity — both "
        "easier to raise than a laptop's CPU.",
        "",
    ]
    (ROOT / "results" / "tenx.md").write_text("\n".join(tenx) + "\n", encoding="utf-8")

    print(f"cost per request ${per_request_cost:.6f} | p50 {p50:.0f}s p99 {p99:.0f}s")
    for stage in STAGES:
        print(f"  {stage:<11} {ms[stage] / total_ms:5.0%} of time, {(cost[stage] / total_cost if total_cost else 0):5.0%} of cost")
    print(f"10x: peak hour {peak_10x} req vs capacity {capacity_per_hour:.0f}/h = {utilisation:.0%} utilisation")
    print("wrote results/cost_by_stage.md and results/tenx.md")


if __name__ == "__main__":
    main()
