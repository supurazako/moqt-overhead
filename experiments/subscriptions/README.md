# Idle subscriptions on fixed connections

The pilot fixes the Publisher and Subscriber to one aiomoqt process and
one raw-QUIC draft-22 connection each, and varies distinct track subscriptions
from 0 through 4 on the Subscriber's existing connection. Each track is
accepted upstream by the Publisher. No Object or PUBLISH_DONE is sent.

Each fresh trial records all three roles after SETUP and namespace
publication, then after all subscriptions are acknowledged at both ends.
Both phases settle for 0.5 s and observe scheduled CPU runtime for 1 s,
with PSS/RSS snapshots at the end. Publisher and Subscriber remain the
same implementation across relay arms. Per-process measurements are
recorded in each trial. This isolates idle subscription/track state at
fixed connection count. Distinct tracks also allocate track-level state.

There are six blocks per subscription count, one for each ordering of
aiomoqt, imquic, and MOQtail. Seed 22 shuffles the condition order.
Fresh processes and the same certificate are used throughout each
isolated-network run. The 0-subscription arm repeats the two phases
without a subscription operation, providing an observation-drift control.
This is an exploratory pilot. Short CPU windows are reported with their
observed ranges.

Use the native binaries and Python environment from
[the fanout preparation](../fanout/README.md), then run:

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec .venv/bin/python experiments/subscriptions/measure.py --pilot' \
  > .scratch/subscriptions.jsonl 2> .scratch/subscriptions.log
```
