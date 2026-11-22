# Draft-22 fanout pilot

## Workload

- One publisher, one relay, and 1–4 subscribers. The same aiomoqt
  endpoint processes appear in each trial. The relay is the comparison
  variable. All three roles run as native Linux processes in one private
  loopback network namespace.
- A single track carries 4 groups of 30 synthetic 8 KiB Objects, one
  subgroup stream per group, with a 20 ms interval between objects.
  Each subscriber verifies group and Object IDs, payloads, the four
  stream endings, and the termination message.
- Six blocks for each subscriber count balance all permutations of the
  three relay implementations. Seed 22 determines block order. A new
  process is started for every role in every trial.

## Measurements

- PSS and RSS are snapshots at the end of each phase. CPU time is the
  change in the sum of the threads' scheduled runtime from Linux
  `schedstat`. A thread set change invalidates that CPU sample.
- The phases are disconnected, subscribed without Objects, and
  transfer. Each idle phase uses a 0.35 s settle and a 1 s sample
  window. Transfer measurements run until sending and receipt reporting
  complete. The transfer-end memory snapshot may miss transient peaks.
- Endpoint events use the host monotonic clock. First Object time is
  measured from the publisher's send invocation. Subscription setup
  and the start delay intentionally imposed by the controller are
  also visible in the event data.
- Tcpdump in immediate mode captures IPv4 UDP on loopback from before
  endpoint connections through completion plus a short settling interval.
  The tool assigns traffic to the endpoint's local UDP socket, checks
  that captured byte counts cover the verified payload, and discards
  the temporary packet captures. Kernel drop counters are checked.
  Loopback GSO can affect the datagram count. These counts describe
  captured UDP records.
- Transfer failures remain in delivery totals. Transfer comparisons
  are conditional on complete delivery. Pre-transfer resource summaries
  use all trials with samples for that phase. This can yield different
  sample sizes across implementations. All measurement rows remain in
  the sanitized data for further analysis.

## Reproduce

Follow the [qualification setup](../interop/README.md) to install the
Python dependencies and obtain the two native relay executables.
Extract their native files from the same pinned images:

```sh
mkdir -p .scratch/native
imquic=$(docker create moqt-overhead-imquic:d93d181)
docker cp "$imquic:/build/imquic/examples/.libs/imquic-moq-relay" .scratch/native/
docker cp "$imquic:/build/imquic/src/.libs/libimquic.so.0.0.2" .scratch/native/libimquic.so.0
docker rm "$imquic"
moqtail=$(docker create ghcr.io/moqtail/relay@sha256:e6d28fc9dbbe295e4a7e6780b6d61383deab994785a87d01cfef0e18701719d5)
docker cp "$moqtail:/usr/local/bin/relay" .scratch/native/moqtail
docker rm "$moqtail"
```

Host libraries are used when running the extracted binaries. Run with
unprivileged user and network namespaces enabled:

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec .venv/bin/python experiments/fanout/measure.py --capture --pilot' \
  > .scratch/fanout-pilot.jsonl 2> .scratch/fanout-pilot.log
python3 experiments/fanout/summarize.py .scratch/fanout-pilot.jsonl \
    --sanitize fanout-pilot-sanitized.jsonl > fanout-pilot-summary.json
```

The runner exits nonzero if any trial fails, after attempting all
scheduled trials. The summarizer checks completeness separately.

## Terminal Object diagnostic

The [imquic final Object follow-up](../records/2026-11-20-imquic-final-object.md)
records a separate intervention that changes the Publisher's
`PUBLISH_DONE` send timing and enables endpoint and relay event tracing.
