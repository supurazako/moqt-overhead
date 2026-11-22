# One- and two-relay comparison

Both arms use aiomoqt 0.14.1 / aiopquic 0.7.1 and the draft-22
[fanout workload](README.md). In the two-relay arm the Publisher
connects to the upstream relay, Subscribers connect to the edge, and
the edge uses the upstream relay as its origin. Both relays are
separate processes. The edge starts its upstream session at launch.
The endpoint connections validate the test certificate. The built-in
edge-to-origin connector does not validate it. All traffic runs in an
isolated loopback namespace.

Measure one and four Subscribers, with six independent pairs per
count. Each order appears three times per count, with seeded ordering.
Report complete-delivery trials, paired differences in aggregate relay
PSS and CPU, and the slowest first Object arrival across Subscribers.
CPU covers the finite transfer window. The phase labeled disconnected
means Publisher and Subscribers have not connected. The two relays may
already be connected in that phase.

Count UDP payload separately on Publisher, Subscriber and inter-relay
links. The inter-relay link can already be established when capture
begins. Its measured bytes describe opening subscriptions and transfer
over an existing inter-relay session. Sum the links once.

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec .venv/bin/python experiments/fanout/measure.py --topology --subscribers 1 4 --capture' \
  > .scratch/topology.jsonl 2> .scratch/topology.log
```

The analysis checks schedule completeness and order balance. It keeps
the success count per arm and calculates paired differences from
blocks where both arms delivered every Object.

```sh
python3 experiments/fanout/summarize-topology.py .scratch/topology.jsonl \
  --sanitize .scratch/topology-sanitized.jsonl
```
