# Sustained-transfer memory growth: evidence and limits

## Observation

The [balanced 30-second series](2026-11-22-resource-series.md) did not
establish steady-state memory for the Relay or Subscriber. Four-track
Relay PSS grew between the first sample after five seconds and the last
sample by median 82,600 KiB (aiomoqt), 40,444 KiB (imquic), and 40,696 KiB
(MOQtail). Publisher curves largely flattened after their initial steps;
Subscriber curves continued to step upward. See the [time-series figure](../../reports/blog/figures/active-memory-over-time.png).

These observations replace the intended assumption of a stationary active
window. The CPU average after five seconds and finite-window memory maxima
remain reported, but are not labeled equilibrium requirements.

## Confirmed source behavior

- aiomoqt 0.14.1's `tools/moq_interop_relay.py` defines a recent-object cache
  with `CACHE_BYTES = 32 MiB` per track and `CACHE_BUDGET_BYTES = 256 MiB`
  relay-wide. `_cache_bytes` is charged when incoming Objects are cached;
  trimming acts on groups/limits. The main series sends only about
  11.72 MiB per track, below that per-track byte bound.
- In pinned imquic `d93d181`, `examples/moq-relay.c`,
  `imquic_demo_incoming_object` duplicates incoming Objects into
  `track->objects` for subsequent FETCH. The inspected local file was
  byte-for-byte equal to the source extracted using `git show` inside the
  pinned build image. [Pinned source](https://github.com/meetecho/imquic/blob/d93d18141b0db5f167290a6b162b059dc964015e/examples/moq-relay.c).
- [Source hashes](2026-11-22-memory-source-hashes.json) identify the two
  inspected files. These facts establish retained-object features, not
  an allocation-level decomposition of all observed PSS growth.
- The endpoint parser's `StreamChain.commit()` drops consumed chunks;
  this source fact alone cannot exclude retention elsewhere in the
  native transport, ring buffers, allocator or application bookkeeping.

## Separate instrumented diagnostic

After the main measurements, a separate non-balanced diagnostic ran each
relay once with four tracks, 600 Objects per track, 8 KiB payloads and
20 ms pacing for a 12-second resource window. Python `tracemalloc` was
enabled in Publisher/Subscriber processes using a startup hook. A snapshot
was taken ten seconds after hook initialization, which is **not** ten
seconds after transfer readiness.

- All three diagnostic trials verified 2,400 Objects with no payload errors.
- Six endpoint snapshots were collected. Traced current memory at snapshot
  time was approximately 14–15 MiB, with import-related allocations largest.
- This is a single snapshot per endpoint, not a before/after allocation
  difference. It cannot quantify the cause of native RSS/PSS growth.
- Tracing changes overhead and timing; plot generation also ran during this
  diagnostic. Its CPU/memory values are excluded from the main estimates
  and should not be compared as performance measurements.
- [Diagnostic events](2026-11-22-memory-diagnostic.jsonl),
  [heap snapshots](2026-11-22-memory-heaps.json),
  [startup hook](../resources/heap-sitecustomize.py).

Reproduce the diagnostic after the normal setup:

```sh
mkdir -p .scratch/heap-site
cp experiments/resources/heap-sitecustomize.py .scratch/heap-site/sitecustomize.py
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec env PYTHONPATH=.scratch/heap-site /tmp/moq-overhead-venv/bin/python experiments/resources/measure.py --mode active --levels 4 --objects 600 --duration 12 --capture' \
  > diagnostic.jsonl 2> diagnostic.log
```

## Remaining attribution

No active QUIC-only control or cache-disabled paired measurement was
performed. The fraction due to MoQT bookkeeping versus caches, transport
buffers and allocator retention remains unresolved. The data do not
establish an unbounded leak, a protocol requirement, or a universal
steady-state footprint. Cache/stream-lifecycle controls and longer plateau
measurements are separate future work rather than silently extrapolated
from these windows.
