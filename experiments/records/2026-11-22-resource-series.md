# Role-resource follow-up: collection plan and provenance

This record was created before the balanced series began. Conditions and
interpretation rules are in [resources/README](../resources/README.md).

- Existing pinned relay binaries and aiomoqt endpoints are reused.
- Runner: `experiments/resources/measure.py`; summarizer:
  `experiments/resources/summarize.py`.
- Idle: 72 scheduled trials (4 levels × 6 blocks × 3 relays).
- Active: 36 scheduled trials (2 levels × 6 blocks × 3 relays).
- Six blocks contain all levels and relays. One relay permutation is used
  within each block, with level order randomized inside the block.
  This balances relay positions and supports within-block increments.
- Initial harness checks: idle zero extras, active 1/4 tracks for 3 seconds,
  and idle three extras. These are smoke checks and excluded from estimates.
- Exact collector hash and run outcomes are recorded below after collection.
- All new failures remain in the dataset. No hardware purchasing, external
  issue operations, or publishing is part of this collection run.

## Collector provenance

- `experiments/resources/measure.py`: SHA-256 `1f0a3fed9b8a6f5b376599c40791e00a23b02e15816df9809a9dcc035278854d`.
- `experiments/resources/README.md`: SHA-256 `5651cec4efaa0db9a57618d5dc39f1f57eaa64019a82f61977811d78a3b99993`.
- Host kernel/architecture: 6.12.90+deb13.1-amd64 / x86_64.

## Counter correction before the replacement active series

The original active attempt was stopped after nine completed trials because
MOQtail's thread set changed about nine seconds into transfer. Three Relay
CPU rows were invalid, so the per-thread method could not support the
planned longer-window comparison. The completed idle series is retained;
its two invalid CPU rows affect only additional idle clients.

- [Aborted active attempt](2026-11-22-active-resources-aborted-thread-counter.jsonl): preserve all completed rows and the interrupted partial trial; exclude this attempt from the final resource estimates.
- The replacement uses a Linux process CPU clock, retaining exited-thread CPU time. An exited 80 ms worker check retained 80.529 ms, and the three-relay 11-second transfer smoke check completed.
- The replacement retains the same payloads, pacing, levels, order seed, six blocks, observation interval and receipt-before-termination policy. Only the CPU counter changed.
- [Counter patch](../resources/process-clock.patch) preserves the exact change. Reverse it to reconstruct the original collector from the corrected source.
- The original collector/README hashes above describe the first attempt. Replacement hashes follow.
- `experiments/resources/measure.py`: SHA-256 `71430c38a7fdc6fcbad44af7b00f3a2cdb06c72e5e35fd31ba424e22c0178e25`.
- `experiments/resources/README.md`: SHA-256 `7f2393052f54062ac288e8d6d0c99fcc4b02503d0fa53258225aad5e1c5dd71b`.

## Results

Validated 108 scheduled cases. Cases with failure events: 0.

### Active transfer by role

PSS values are medians of sampled maxima (MiB). CPU values are medians of scheduled runtime after 5 seconds (ms/s). These are total process resources, not matched-control increments.

- 1 track(s):
  - aiomoqt: publisher: 29.68 MiB / 23.14 ms/s; relay: 49.76 MiB / 38.90 ms/s; subscriber: 38.03 MiB / 27.48 ms/s.
  - imquic: publisher: 30.64 MiB / 26.73 ms/s; relay: 15.64 MiB / 81.49 ms/s; subscriber: 39.16 MiB / 34.05 ms/s.
  - moqtail: publisher: 30.82 MiB / 19.73 ms/s; relay: 24.81 MiB / 30.16 ms/s; subscriber: 39.05 MiB / 23.31 ms/s.
- 4 track(s):
  - aiomoqt: publisher: 41.81 MiB / 37.44 ms/s; relay: 128.24 MiB / 84.53 ms/s; subscriber: 75.51 MiB / 50.30 ms/s.
  - imquic: publisher: 42.76 MiB / 43.67 ms/s; relay: 51.40 MiB / 101.92 ms/s; subscriber: 76.88 MiB / 80.96 ms/s.
  - moqtail: publisher: 42.82 MiB / 29.98 ms/s; relay: 61.79 MiB / 80.44 ms/s; subscriber: 76.60 MiB / 51.94 ms/s.

### Incremental relay resources

Each value is a median within-block difference; brackets show exploratory 95% block-bootstrap intervals. Six blocks are a small sample.

- idle, level 1 minus 0:
  - aiomoqt: -433.5 [-1541.5, -265.5] KiB.
  - imquic: -26.0 [-111.5, -6.0] KiB.
  - moqtail: 684.0 [499.5, 902.0] KiB.
- idle, level 2 minus 0:
  - aiomoqt: -631.0 [-1750.5, 348.0] KiB.
  - imquic: -36.0 [-117.0, 23.5] KiB.
  - moqtail: 1525.0 [1323.5, 1602.0] KiB.
- idle, level 3 minus 0:
  - aiomoqt: -1010.0 [-1941.5, -812.5] KiB.
  - imquic: -29.0 [-119.5, 10.0] KiB.
  - moqtail: 2225.0 [2076.5, 2608.0] KiB.
- active, level 4 minus 1:
  - aiomoqt: 80382.0 [77040.5, 82682.0] KiB.
  - imquic: 36638.5 [36592.5, 36709.0] KiB.
  - moqtail: 37886.5 [37623.0, 39706.5] KiB.

### Data and limitations

- [Idle observations](2026-11-22-idle-resources.jsonl), [active observations](2026-11-22-active-resources.jsonl), [validated summary](2026-11-22-resource-summary.json).
- The active stream lifecycle differs from the finite-transfer pilot: all data are verified before FIN/PUBLISH_DONE. This does not demonstrate correct handling of the earlier terminal-message race.
- Traffic covers setup and teardown as well as the resource window. Relay transmit/receive bytes sum link counters in the reversed endpoint direction.
- [Memory growth investigation](2026-11-22-memory-growth.md): the Relay and Subscriber did not establish a memory plateau. Post-five-second averages do not assert equilibrium.
- More active tracks also mean more aggregate traffic. Extra idle processes alter PSS sharing. No MCU feasibility, intrinsic protocol minimum, or constant per-client slope is inferred.
- The six-block intervals do not guarantee the prespecified resolution targets. Inspect widths; small differences and long-term stability can remain unresolved.
- PSS maxima are sampled every 250 ms and can miss shorter peaks. No allocation-level peak, application startup peak, kernel socket memory, or energy measurement is claimed.
