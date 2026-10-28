"""
PER-REQUEST LOGGING: what the app writes down about every single answer.

The rule this week: if it isn't logged, it didn't happen. When someone says
"it gave a bad answer on Tuesday", the log is the only thing you have.

One JSON object per line in logs/requests.jsonl. One line = one request.

WHAT EVERY RECORD HOLDS, and why each field earns its place:

    trace_id         so a complaint can name one exact request
    ts               when (the complaint is always "some time on Tuesday")
    user_id, channel who asked and from where, for slicing
    input_type       what kind of question it was, for slicing
    prompt_version   which version of the instructions produced this answer.
                     Without it you cannot tell a regression from bad luck.
    question, answer BOTH are indexed. A complaint usually describes the ANSWER
                     ("it suggested milk"), not the question.
    spans            every step: retrieval, each tool call, each model call,
                     with its own time, tokens and cost. Not one lump total.
    context_ids      exactly which recipe sections were retrieved. Without this
                     you can see a wrong answer but not whether retrieval served
                     the wrong text or the model misread the right text.
    totals           time, tokens and cost for the whole request

A span is one step inside a request. Together the spans are the trace.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "logs" / "requests.jsonl"

# Prices used to turn tokens into money. The local model is free to run, so the
# money figure is what these exact token counts WOULD cost on a hosted model.
PRICE_IN, PRICE_OUT = 0.10, 0.40   # $ per 1M tokens, gemini-2.5-flash-lite list price


def token_cost(input_tokens, output_tokens):
    return input_tokens / 1e6 * PRICE_IN + output_tokens / 1e6 * PRICE_OUT


class Span:
    """One step inside a request, timed."""

    def __init__(self, trace, name, kind, **detail):
        self.trace, self.name, self.kind, self.detail = trace, name, kind, detail
        self.input_tokens = self.output_tokens = 0

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def tokens(self, input_tokens, output_tokens):
        self.input_tokens, self.output_tokens = input_tokens, output_tokens

    def __exit__(self, *exc):
        self.trace.spans.append({
            "name": self.name,
            "kind": self.kind,                     # retrieval | tools | generation
            "ms": round((time.perf_counter() - self.started) * 1000, 1),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(token_cost(self.input_tokens, self.output_tokens), 8),
            **self.detail,
        })


class Trace:
    """One request, from question to answer."""

    def __init__(self, question, prompt_version, user_id="u-0001", channel="web",
                 input_type="other", model="", log_file=LOG_FILE):
        self.record = {
            "trace_id": f"t-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:6]}",
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_id": user_id,
            "channel": channel,
            "input_type": input_type,
            "prompt_version": prompt_version,
            "model": model,
            "question": question,
        }
        self.spans = []
        self.context_ids = []
        self.log_file = Path(log_file)
        self.started = time.perf_counter()

    @property
    def trace_id(self):
        return self.record["trace_id"]

    def span(self, name, kind, **detail):
        return Span(self, name, kind, **detail)

    def saw_context(self, ids):
        for context_id in ids:
            if context_id and context_id not in self.context_ids:
                self.context_ids.append(context_id)

    def finish(self, answer, status="finished", **extra):
        input_tokens = sum(s["input_tokens"] for s in self.spans)
        output_tokens = sum(s["output_tokens"] for s in self.spans)
        self.record.update({
            "answer": answer,
            "status": status,
            "context_ids": self.context_ids,
            "spans": self.spans,
            "totals": {
                "ms": round((time.perf_counter() - self.started) * 1000, 1),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "tokens": input_tokens + output_tokens,
                "cost_usd": round(token_cost(input_tokens, output_tokens), 8),
                "llm_calls": sum(1 for s in self.spans if s["kind"] == "generation"),
                "tool_calls": sum(1 for s in self.spans if s["kind"] == "tools"),
            },
            **extra,
        })
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(self.record, ensure_ascii=False) + "\n")
        return self.record


def read_log(log_file=LOG_FILE):
    path = Path(log_file)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
