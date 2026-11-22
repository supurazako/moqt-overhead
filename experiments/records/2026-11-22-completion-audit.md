# Completion audit: fixed-resource study and English article draft

## Scope and evidence

- Existing matched QUIC/TLS controls: the idle/startup follow-up was
  regenerated from its six CSV files using `summarize-followup.py` and
  matched the stored summary exactly. This supports the zero-client
  implementation increment and initial SETUP observations, not a universal
  MoQT minimum.
- Fixed subscription with additional connections: all 72 scheduled cases
  in `2026-11-22-idle-resources.jsonl` completed; one subscribed track and
  0–3 additional SETUP-only clients. Role-specific resources and link bytes
  are present. Two invalid CPU rows affect only additional idle clients.
- Fixed connections with multiple active tracks: all 36 scheduled cases
  in `2026-11-22-active-resources.jsonl` completed. Each verifies 1,500
  Objects per track and payload correctness. Publisher, Relay and
  Subscriber each have six valid process-clock CPU observations for each
  relay/track condition and at least 100 memory samples per trial.
- Longer transfer and selected repeated conditions: six balanced blocks
  per condition, 30-second windows, one and four tracks. Relay/Subscriber
  memory did not reach a plateau; this negative finding is retained rather
  than calling the resulting maxima steady-state requirements. The study
  does not claim precision beyond its exploratory six-block intervals.
- Cause checks: thread-set changes invalidated the original long-window
  CPU method; an exited-worker check verified the replacement process
  clock. Original/corrected source reconstruction matched recorded hashes.
  The existing imquic termination investigation remains separate.
- Memory attribution: pinned-source inspection confirmed retained-Object
  features in aiomoqt/imquic relays. Three separate instrumented trials
  and six Python heap snapshots were retained. They do not decompose all
  native memory growth or establish an unbounded leak. See
  [memory investigation](2026-11-22-memory-growth.md).
- Reproducibility: collector, summarizer, sanitizer, counter check, report
  generator, plot generator, pinned plotting requirements, environment
  metadata, raw observations in relative time, and original-counter patch
  are available. Original unsanitized data stay in `.scratch`.
- Sanitization: regenerating all three main/aborted publication files from
  their local originals produced byte-identical output. Every resource row
  remained unchanged. Executable/collector hashes matched the environment
  record. Targeted key/token and host-path checks passed.
- English article: [draft](../../reports/blog/moqt-fixed-costs.md), with
  five PNG/SVG figure pairs. Local links and figures were checked, and
  representative figures were visually inspected. It includes methods,
  role-specific measurements, intervals, failed/interrupted attempts,
  counter correction, retention limitations, and reproducibility links.

## Final validation

`python3 experiments/resources/verify.py` passed checks for all 108 cases,
role coverage, observation windows, monotonic event/CPU data, valid
post-five-second CPU measurements, local links, figures, and targeted
secret patterns. `git diff --check` passed. Scheduled order permutations,
block differences, first/last-half diagnostics and position medians are
retained in the machine-readable summary.

## Boundaries

The deliverable is a local English blog draft with reproducibility
artifacts. No blog was externally published and no issue operations were
performed. MCU experiments, alternative protocol comparisons, alternative
endpoint-library rankings, active QUIC-only attribution, cache-disabled
controls and longer memory-plateau experiments remain outside the completed
article's claims. These limitations are explicit rather than treated as
measured conclusions.
