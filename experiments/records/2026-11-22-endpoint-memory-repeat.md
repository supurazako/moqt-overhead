# Balanced repetition of endpoint memory categories

## Reason and design, fixed before collection

The article's author requested repeated memory-category measurements in
place of treating the earlier single-run diagnostic as the endpoint of
validation. Preserve the original six diagnostic trials separately.

- Same three implementations, binaries, verified TLS, fixed external relay
  and opposite endpoint, 64-byte payload, 50 Objects at 100 ms intervals.
- Six independent trials per implementation and role, 36 trials total.
  Balance all six implementation permutations with the existing seed 22023.
- Fresh processes and connections. Same two-second idle and approximately
  five-second active windows as the endpoint implementation pilot.
- Read PSS, RSS, anonymous/file-backed PSS and private clean/dirty memory
  from the same smaps_rollup read for category coherence.
- For each category, take the final active-window sample per trial; report
  the median and observed range across six trials. Do not substitute
  within-process samples for independent trials.
- Keep failed trials and reasons, check all 50 Objects for each completed
  transfer, and validate complete role/order coverage before reporting.
- Update the Japanese article's category table and explanation from these
  observations. These trials address repeatability of the Linux category
  measurement; they are not firmware or handshake-peak measurements.

## Results and validation

All 36 scheduled transfers completed with 50 correct Objects each. All six implementation orders and both resource phases were validated for each role. Every reported category contains six independent final-window observations.

| Implementation | Publisher anonymous PSS, MiB [range] | Subscriber anonymous PSS, MiB [range] |
| --- | ---: | ---: |
| imquic | 1.54 [1.53, 1.54] | 1.52 [1.52, 1.52] |
| moqtail | 0.94 [0.93, 0.95] | 0.95 [0.94, 0.96] |
| aiomoqt | 21.96 [21.96, 21.97] | 22.04 [22.03, 22.05] |

The original diagnostic is retained. The Japanese draft now uses six-trial medians instead of one-run category values, and its single-run caution was replaced with the observed ranking.

During analysis, a check initially assumed total PSS equals anonymous plus file-backed PSS. Linux also reports shared-memory PSS, so that check rejected valid Python observations. The check was corrected to allow a nonnegative remaining contribution. `other_pss_residual_kib` records total minus anonymous minus file-backed PSS, including rounding; it is derived, not a separately sampled shared-memory counter. Anonymous/file-backed measurements were not changed.

- [Events](2026-11-22-endpoint-memory-categories-balanced.jsonl), [summary](2026-11-22-endpoint-memory-categories-balanced-summary.json), [provenance](2026-11-22-endpoint-memory-repeat-provenance.json).
