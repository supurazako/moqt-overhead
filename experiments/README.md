# MoQT resource measurements

Methods, adapters, observations and analysis for IETF MoQT draft-22 over raw QUIC.
The study measures Linux processes: Publisher, Subscriber and Relay. These
observations are not microcontroller RAM requirements.

## Publisher and Subscriber

- [Method and reproduction](endpoints/README.md): fixed relay and counterpart,
  50 Objects of 64 bytes, six balanced trials per implementation and role.
- [Native adapter builds](endpoints/BUILD.md) and [Python dependencies](interop/README.md).
- [Results](records/2026-11-22-endpoint-resources.md).
- [Measured events](records/2026-11-22-endpoint-resources.jsonl) and
  [summary](records/2026-11-22-endpoint-summary.json).
- [Repeated memory categories](records/2026-11-22-endpoint-memory-repeat.md),
  [events](records/2026-11-22-endpoint-memory-categories-balanced.jsonl) and
  [summary](records/2026-11-22-endpoint-memory-categories-balanced-summary.json).
- [Build provenance](records/2026-11-22-endpoint-provenance.json) and
  [admission checks](records/2026-11-22-endpoint-admission.md).

## Relay and earlier experiments

- [Research plan](../experiment-plan.md) (Japanese; revised as the scope evolved).
- [Interop admission](interop/README.md).
- [Idle processes and QUIC controls](idle/README.md).
- [Fan-out and delivery checks](fanout/README.md).
- [Idle subscriptions](subscriptions/README.md).
- [Publisher/Relay/Subscriber resource series](resources/README.md) and
  [results](records/2026-11-22-resource-series.md).
- [English study report and figures](../reports/blog/moqt-fixed-costs.md).

The records directory preserves admission failures, aborted runs, counter
corrections and follow-up measurements alongside the successful series.
Use each method document to distinguish diagnostic runs from balanced trials.
Private keys, packet captures, local diagnostic logs and unpublished editorial
or issue drafts are excluded. Existing source patches retain their upstream
context; build instructions identify the source revisions.

## Validate the recorded series

These commands analyze existing data and do not start new experiments:

```sh
python3 experiments/resources/verify.py
python3 experiments/endpoints/summarize.py experiments/records/2026-11-22-endpoint-resources.jsonl
python3 experiments/endpoints/summarize-categories.py experiments/records/2026-11-22-endpoint-memory-categories-balanced.jsonl
```
