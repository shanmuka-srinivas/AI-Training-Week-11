# Cost per request, broken down by stage

From 502 production requests (2 of them real runs, the rest simulated traffic with span shapes and token counts sampled from real runs). 34 development requests are excluded: they were mine, and they all landed in one hour.

Money is what these exact token counts would cost on a hosted model (gemini-2.5-flash-lite, $0.10/$0.40 per million in/out). Run locally the cash cost is $0, but the tokens and the seconds are real.

| stage | calls/request | time/request | share of time | tokens/request | cost/request | share of cost |
|---|---|---|---|---|---|---|
| retrieval | 1.7 | 0.9 s | 2% | 0 | $0.000000 | 0% |
| tools | 0.1 | 0.1 s | 0% | 0 | $0.000000 | 0% |
| generation | 2.0 | 39.8 s | 98% | 2,570 | $0.000318 | 100% |
| **total** | **3.9** | **40.7 s** | 100% | **2,570** | **$0.000318** | 100% |

**Cost per request: $0.000318** — about **$3.18 per 10,000 questions**. Latency p50 **41 s**, p99 **61 s**.

## What this says

- **The model is 100% of the cost and 98% of the time.** Retrieval and the tools are local lookups: no tokens, and 2% of the clock between them.
- So there is exactly one lever worth pulling, and it is the model. Making retrieval faster would be optimising 2% of the latency and 0% of the bill.
- Each request makes 2.0 model calls averaging $0.000159 and 20 s each. **Removing one call is worth more than any other change available.**

## Where the saving would come from, in order

1. **Cache repeated questions.** The log shows the same handful of questions asked over and over by different users; a cache hit removes a whole request, not a fraction of one.
2. **Cut a model call.** Most requests spend one call deciding to use a tool and another writing the answer. Easy lookups could answer in one.
3. **A cheaper model for easy questions**, keeping the better one for dietary and substitution questions — which is exactly where the incident happened, so that is not the place to economise.

