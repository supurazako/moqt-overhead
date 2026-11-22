# Connection and sustained-transfer follow-up

This series returns to the Linux fixed-resource investigation. It does not
measure MCU feasibility or compare different Publisher/Subscriber libraries.
All endpoint processes use aiomoqt; only the relay implementation varies.

## Conditions fixed before collection

- Pinned implementations and dependencies: the same versions as the
  [qualification](../records/2026-11-20-draft22-qualification.md).
- IETF MoQT draft-22, raw QUIC, loopback in a private network namespace.
  Ephemeral EC P-256 self-signed certificate, explicitly trusted by clients.
- One publishing connection, one subscribing connection, one relay process.
- Idle series: one acknowledged track subscription, plus 0/1/2/3 extra
  SETUP-only clients. Total relay connections are therefore 2/3/4/5.
  Observe 5 seconds after a 0.5-second settling interval.
- Active series: fixed two connections, 1 or 4 distinct track subscriptions;
  1,500 Objects of 8,192 payload bytes per track, paced at 20 ms intervals.
  Each track uses one subgroup stream. Observe 30 seconds after subscriptions
  are acknowledged and a 0.5-second settling interval. Aggregate payload rate
  increases with track count; this series does not isolate subscription-state
  memory from data-rate-dependent buffering.
- Six blocks per level balance all six relay orders. Seed 22022 randomizes
  block/level order. Independent processes and a fresh connection for each
  trial; each run uses a temporary certificate. Idle and active series run
  sequentially, not concurrently.
- A 250 ms loop samples process PSS/RSS and CPU runtime. The completed idle
  series used the original per-thread counter; its two invalid extra-client
  CPU rows are retained and excluded from CPU estimates. The final active
  series uses a Linux process CPU clock via `clock_getcpuclockid` and
  `clock_gettime_ns`, which retains CPU time from exited threads.
  Report all samples, sampled maximum, start/end snapshots, total-window CPU
  rate and (active only) CPU rate after 5 seconds. A sampled maximum can miss
  shorter peaks. Polling overhead is part of the measurement environment.
  The original thread-counter active attempt was stopped because MOQtail
  changed its thread set about 9 seconds into the window. Its partial data
  are preserved separately and excluded from final estimates. The process
  clock removes this source of undercounting; it excludes child processes.
  To recover the original collector, reverse `process-clock.patch`.
- Packet capture covers setup, measured activity and teardown. Report UDP
  payload bytes per endpoint/link; relay totals reverse endpoint directions
  and sum links once. GSO can affect captured datagram counts.
- The receiver validates track/group/Object identity and full payload before
  the Publisher closes the subgroup and sends PUBLISH_DONE. This keeps the
  known terminal-message race outside the active measurement. It is a
  different lifecycle from the original finite-stream pilot; it neither
  fixes imquic nor proves its original termination path correct.
- Teardown is not part of the resource window. Captured traffic includes it.
  All new failures are retained. Compare complete-delivery trials separately
  and disclose denominators.
- PSS can change when extra Python processes share mappings. Report RSS too;
  PSS differences at a fixed process count are easier to interpret than
  endpoint PSS differences across numbers of extra clients.

These are balanced follow-up measurements, not a guarantee of statistical
power. Show block-level differences and 95% percentile bootstrap intervals
(resampling whole blocks, seed 22, 10,000 draws). With six blocks, intervals
are exploratory. Interpret widths against 128 KiB memory and 1 ms/s CPU
resolution targets; if unresolved, explicitly report uncertainty rather than
claiming equality. Pilot smoke runs are separate from this series.

## Reproduce

Use the Python environment and native executables described in
[fanout](../fanout/README.md); replace the interpreter path if needed.

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec /tmp/moq-overhead-venv/bin/python experiments/resources/measure.py --mode idle --balanced --capture' \
  > idle.jsonl 2> idle.log
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec /tmp/moq-overhead-venv/bin/python experiments/resources/measure.py --mode active --balanced --capture' \
  > active.jsonl 2> active.log
python3 experiments/resources/summarize.py idle.jsonl active.jsonl > summary.json
```

Raw local stderr can contain environment details and stays in `.scratch`.
Committed JSONL contains only synthetic experiment events, counters and
resource measurements; no keys or packet captures are retained there.

## Interpretation after collection

The 30-second active windows did not establish steady-state memory: PSS
continued to rise. The `post5_cpu_ms_per_s` field is the CPU average after
five seconds, and `post5_pss_change_kib` is the PSS change over that interval.
Neither label asserts equilibrium. Main results are finite-window resource
observations; further plateau/leak attribution remains an open question.

Before sharing a run, convert absolute host-monotonic event times to
per-trial relative times while keeping the original locally:

```sh
python3 experiments/resources/sanitize.py raw.jsonl shared.jsonl
```

Analysis accepts raw or relative event times. The series' `elapsed_ns` and
CPU durations are already relative and remain unchanged. The corrected
collector is used by the current reproduction commands; the original idle
counter can be recovered using the reverse patch described above.

Publication figures use matplotlib 3.10.7. Run `reports/blog/plot.py` with
that dependency available. After the article and figures are built, run
`python3 experiments/resources/verify.py` for the final coverage, resource,
link and targeted secret checks. These checks complement reading the
article and inspecting the plots; they do not establish causal attribution.
