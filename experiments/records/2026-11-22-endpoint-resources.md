# Small-payload Publisher/Subscriber implementation pilot

All 36 balanced trials completed with 50 correct Objects each. The measured role changes between imquic, MOQtail and aiomoqt; the external aiomoqt Relay and opposite aiomoqt endpoint remain fixed. This measures existing Linux implementations, not firmware or an intrinsic MoQT memory floor.

## Conditions

- IETF MoQT draft-22 over raw QUIC; one track; 50 Objects of 64 bytes at 100 ms intervals.
- Verified TLS with a dedicated CA and server leaf; no global trust-store changes. All three Publisher negative-trust checks rejected an unrelated CA.
- Six fresh-process trials per implementation/role, all six balanced orders; 2-second connected-idle and approximately 5-second transfer windows.
- Memory maxima are sampled every 100 ms. CPU is process CPU time per actual observed wall second, including exited threads. Startup peaks and transport-only endpoint controls are not measured.
- [Admission and failed attempts](2026-11-22-endpoint-admission.md), [conditions and procedure](../endpoints/README.md), [build commands](../endpoints/BUILD.md).

## Publisher

PSS values are MiB. Transfer PSS is the median of each trial's sampled maximum; brackets show observed min–max across six independent trials, not a confidence interval. CPU is ms/s (10 ms/s is about 1% of one CPU core).

| Implementation | Idle PSS | Transfer PSS [range] | Transfer CPU [range] | Threads |
| --- | ---: | ---: | ---: | ---: |
| imquic | 3.54 | 3.63 [3.62, 3.67] | 3.72 [3.54, 4.06] | 3 |
| moqtail | 5.77 | 6.06 [5.86, 6.07] | 2.48 [2.11, 3.01] | 18 |
| aiomoqt | 26.54 | 26.56 [26.47, 26.81] | 6.83 [5.93, 6.93] | 2 |

## Subscriber

PSS values are MiB. Transfer PSS is the median of each trial's sampled maximum; brackets show observed min–max across six independent trials, not a confidence interval. CPU is ms/s (10 ms/s is about 1% of one CPU core).

| Implementation | Idle PSS | Transfer PSS [range] | Transfer CPU [range] | Threads |
| --- | ---: | ---: | ---: | ---: |
| imquic | 3.57 | 3.62 [3.52, 3.67] | 13.99 [13.29, 15.62] | 2 |
| moqtail | 5.88 | 6.00 [5.94, 6.13] | 2.37 [2.31, 2.58] | 18 |
| aiomoqt | 25.38 | 25.47 [25.44, 25.54] | 6.99 [6.48, 7.18] | 3 |

## Memory categories: six trials per implementation and role

An additional balanced series measured anonymous and file-backed PSS using Linux smaps_rollup. Values are medians of each trial's final transfer-window sample; brackets show the observed range across six independent trials. All 36 transfers verified 50 correct Objects.

| Role | Implementation | Anonymous PSS (MiB) | File-backed PSS (MiB) |
| --- | --- | ---: | ---: |
| publisher | imquic | 1.54 [1.53, 1.54] | 2.08 [2.05, 2.13] |
| publisher | moqtail | 0.94 [0.93, 0.95] | 5.11 [4.92, 5.11] |
| publisher | aiomoqt | 21.96 [21.96, 21.97] | 1.51 [1.49, 1.53] |
| subscriber | imquic | 1.52 [1.52, 1.52] | 2.05 [1.99, 2.10] |
| subscriber | moqtail | 0.95 [0.94, 0.96] | 5.04 [4.98, 5.11] |
| subscriber | aiomoqt | 22.04 [22.03, 22.05] | 1.51 [1.47, 1.51] |

## Interpretation

- Existing C/Rust endpoints do run with substantially smaller total PSS than the Python reference in this small workload: imquic is approximately one-seventh and MOQtail roughly one-quarter of the Python footprint. These are implementation/configuration differences, not isolated language effects.
- Total PSS and anonymous PSS answer different questions. The repeated category series has lower anonymous PSS for MOQtail than imquic despite the reverse total-PSS order. Anonymous PSS includes more than application heap, and file-backed code cannot simply be subtracted to derive MCU RAM requirements.
- CPU does not follow the memory ranking. imquic Subscriber uses more CPU during transfer than the Python reference in this pilot. The attribution is unresolved; source inspection found a 100 ms outer application sleep, which alone does not explain the difference. No pure protocol or MCU energy claim follows.
- Small payloads and short windows do not characterize media-rate buffers, handshake peaks, long-term retention or failure recovery. All role adapters use existing full libraries; this is not a minimal embedded port.
- No matched active QUIC-only endpoint control was measured, so these absolute values do not isolate MoQT overhead from QUIC/TLS, runtime and application logic.
- moxygen and libquicr were included in candidate inspection but do not have role-isolated draft-22 resource results in this pilot. Their absence is not a negative resource finding.

## Artifacts

- [Balanced events](2026-11-22-endpoint-resources.jsonl), [summary and paired differences](2026-11-22-endpoint-summary.json).
- [Balanced memory-category events](2026-11-22-endpoint-memory-categories-balanced.jsonl), [category summary](2026-11-22-endpoint-memory-categories-balanced-summary.json), [original one-run diagnostic](2026-11-22-endpoint-memory-categories.jsonl), [collector and binary hashes](2026-11-22-endpoint-provenance.json).
- [Figure](../../reports/blog/figures/endpoint-implementation-memory.png), [plot script](../endpoints/plot.py).

## Validation

The summarizer checked all 36 declared role/implementation/block cases,
all six implementation orders per role, two resource phases per case,
recorded observation durations, monotonic CPU counters, and validated
receipt counts. Regeneration matched the stored summary exactly. The
collector and four native artifacts matched the hashes fixed before the
balanced collection. Publication links and targeted credential/host-path
scans passed. The original six-case category diagnostic is retained; the balanced category series completed all 36 cases.

Six trials provide observed variability, not a guarantee of statistical
power or a universal ranking. No firmware build, flash, external issue
operation or publication was performed.
