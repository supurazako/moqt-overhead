# imquic final Object loss · follow-up

## Question and design

Can deferring the upstream `PUBLISH_DONE` change delivery of the last
Object through imquic? The diagnostic repeats the draft-22 one-subscriber
fanout workload with the same endpoints, relay commit and Object pacing.
Six independent pairs alternate the order of 0 ms and 100 ms of additional
delay. Both arms log endpoint events and upstream object/termination
processing in the relay. Logging can change scheduling; this series
therefore estimates behavior under tracing.

The intervention delays the control send after the data and subgroup FIN
are queued by the same Publisher. It does not wait for a delivery
acknowledgment. The actual instrumented enqueue gap is recorded.

## Outcome

- Immediate: 3/6 trials delivered 120/120 Objects. The other three each
  delivered 119 Objects and omitted Group 3, Object 29.
- Deferred: 6/6 trials delivered 120/120 Objects.
- In all three failing traces, the relay processed `PUBLISH_DONE`, received
  the final 8,192-byte Object afterward, and logged that it could not find
  the track. The Subscriber received the termination notification and four
  stream endings. All nine complete traces logged the final Object before
  the relay processed `PUBLISH_DONE`.

Representative relay log order from the first immediate trial:

1. Line 273: upstream subscription ended with Stream Count 4.
2. Line 275: the relay removed the track.
3. Line 277: final Object arrived, Group 3/Object 29, with end-of-stream.
4. Line 278: the relay reported that the track could not be found.

## Mechanism

The trace identifies where the Object was lost. The demo relay's
`imquic_demo_publish_done` callback forwards termination and removes the
track immediately. The track destructor removes the publisher's alias
lookup. A late data callback then reaches `imquic_demo_incoming_object`,
fails the alias lookup, and returns before forwarding. The upstream
control and data streams can be processed in different orders even when
the Publisher queued the data and FIN first.

The 100 ms delay is a diagnostic intervention. These tests do not establish
a portable grace period. An implementation fix would need to coordinate
track teardown with outstanding upstream data streams according to the
termination and delivery rules. No upstream code was changed.

- [Pinned imquic relay source](https://github.com/meetecho/imquic/blob/d93d18141b0db5f167290a6b162b059dc964015e/examples/moq-relay.c#L1938)
- [Alias cleanup in the track destructor](https://github.com/meetecho/imquic/blob/d93d18141b0db5f167290a6b162b059dc964015e/examples/moq-relay.c#L252)
- [Late data lookup and return](https://github.com/meetecho/imquic/blob/d93d18141b0db5f167290a6b162b059dc964015e/examples/moq-relay.c#L2414)
- [MoQT draft-22 termination handling](https://datatracker.ietf.org/doc/html/draft-ietf-moq-transport-22#section-9.9)

## Reproduce

Use the native preparation in [the fanout procedure](../fanout/README.md).

```sh
experiments/fanout/recheck-end.sh > .scratch/end-recheck-status.csv
python3 experiments/fanout/summarize-end.py .scratch/end-recheck
```

[Sanitized per-trial evidence](2026-11-20-imquic-final-object.csv)
contains trace line positions, outcomes and relative event timings.
Full local relay logs stay in the scratch directory.
