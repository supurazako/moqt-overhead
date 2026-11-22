# Idle follow-up design

- **Idle CPU and process memory**: zero connections, 5 s observation
  after the original 0.5 s settling period, six independent paired
  blocks per implementation. Scheduled-runtime counters replace tick
  rounding. Each arm runs in the same network namespace as its pair.
- **Startup and UDP**: one connection, original 1 s observation,
  twelve independent paired blocks per implementation, immediate
  capture. Doubling the six pilot pairs is a fixed follow-up size.
  The pilot showed more variability in startup than idle memory. The
  follow-up reports precision as observed and does not guarantee
  that the pilot's sensitivity targets will be met.
- **Orders**: balanced AB and BA in both series. The runner fixes
  assignments in advance using seed 22. Implementation profiles run
  sequentially. Estimates are within-profile contrasts.
- **Analysis**: report the median of paired differences for PSS,
  scheduled CPU and UDP payload. Report the median of the relay's
  first SETUP intervals. For independent continuous observations of
  a common median, the six-observation min–max interval has 96.875%
  coverage and the twelve-observation third–tenth order statistic
  interval has about 96.1% coverage. Report these intervals as
  exploratory across the several endpoints. Rounded metrics and
  ties can make intervals conservative.

See [baseline setup](README.md). Run `experiments/idle/recheck.sh`
to repeat the fixed matrix. Raw process logs remain in the scratch
directory.

Generate the checked summary after all six CSVs exist:

```sh
python3 experiments/idle/summarize-followup.py .scratch/idle-recheck
```
