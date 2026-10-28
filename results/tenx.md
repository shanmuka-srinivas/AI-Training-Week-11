# At 10x today's traffic, what breaks first?

**LATENCY breaks first: in the busiest hour the app would need to serve 100 requests against a capacity of 90 per hour — 111% utilisation — and queueing delay climbs steeply above about 70%, long before the queue is formally over capacity.**

## The numbers behind that line

| | today | at 10x |
|---|---|---|
| requests logged | 502 over 9 days | 5020 |
| busiest hour | 10 requests | **100 requests** |
| average hour | 4.1 requests | 40.8 requests |
| model time per request | 40 s | unchanged |
| **capacity, one model** | **90 requests/hour** | **90** |
| peak utilisation | 11% | **111%** |
| cost per month (hosted prices) | $0.53 | $5.33 |

## Why latency and not the other two

**Not cost.** Ten times the traffic is about $5 a month at hosted prices. Nobody escalates that.

**Not a provider rate limit**, because the model runs on our own machine and has none — though moving to a hosted model to fix the latency would swap the throughput ceiling for exactly that.

**It is throughput.** One local model answers one request at a time and spends 40 s of model time on each, so it can serve about 90 an hour. At 10x the busy hour asks for 100. At 111% utilisation the queue does not overflow on average, but waits during the peak grow several times longer than the 41 s people see today — and the p99, already 61 s, is what they complain about.

## The plan, in the order it would be done

1. **Cache.** The log is full of repeated questions; cache hits remove load before anything is bought.
2. **Run more than one worker.** The model is single-process here, so N copies give roughly N times the capacity until memory runs out (about 2 GB each).
3. **Route by difficulty**, so easy lookups stop occupying the slow path.
4. **Then a hosted model**, accepting a rate limit and a bill in exchange for elastic capacity — both easier to raise than a laptop's CPU.

