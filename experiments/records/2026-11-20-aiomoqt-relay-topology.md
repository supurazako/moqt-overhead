# Draft-22 · One- and two-relay aiomoqt comparison

## Design

- **Stack**: aiomoqt 0.14.1, aiopquic 0.7.1, MoQT draft-22 over raw QUIC.
- **Host**: the same Linux loopback host as the
  [fanout pilot](2026-11-20-draft22-fanout-pilot.md), in a private network
  namespace. Each role ran in a fresh process for every trial.
- **Topology**: Publisher → Relay → Subscribers, compared with
  Publisher → upstream Relay → edge Relay → Subscribers. The built-in
  connector opens the inter-relay session at launch. Endpoint TLS
  verification is enabled. The connector does not verify the upstream
  certificate.
- **Workload**: one Publisher, one synthetic track, four Subgroups,
  120 Objects of 8 KiB each, paced at 20 ms. Subscriber counts were
  one and four. There were six balanced pairs per count.
- **Measures**: total relay PSS at subscribed idle, total relay scheduled
  CPU in the finite transfer interval, and the slowest Subscriber's
  first Object callback relative to Publisher send invocation.
  UDP totals sum the links once and exclude teardown. The inter-relay
  session may be established before capture begins.
- **Scope**: this comparison tests one added relay and link on loopback.
  It does not model inter-site network delay. Endpoint measurements
  remain in the per-trial record.

## Checks before measurement

An initial script revision stopped at a syntax error before launching
a trial. After correction, the one-Subscriber smoke check delivered
all Objects in both topologies. The four-Subscriber smoke check
validated both port captures and link attribution. The final smoke
run's teardown overlapped startup of the first scheduled run. Its
last endpoint event was before the first scheduled observation window.

See [reproduction commands and analysis](../fanout/TOPOLOGY.md).

## Results

All 24 scheduled trials delivered every Object. Each arm delivered
3,600 Objects across the two Subscriber counts and six blocks per
count. The table gives the median difference within a block as
two relays minus one relay. Ranges represent observed blocks.

| Metric | One Subscriber | Four Subscribers |
| --- | ---: | ---: |
| Subscribed-idle relay PSS (MiB) | +23.86 [23.68, 25.86] | +23.35 [23.20, 23.45] |
| Total transfer relay CPU (ms/s) | +40.30 [38.40, 42.73] | +41.71 [35.56, 45.22] |
| Total UDP payload (MB) | +1.016 [1.015, 1.017] | +1.016 [1.013, 1.018] |
| Slowest first Object (ms) | −0.87 [−2.39, −0.44] | −1.68 [−3.20, 2.19] |

The inter-relay link carried about 1.016 MB in both configurations,
with one upstream copy of the 983,040-byte track shared across
Subscribers. The measured total wire increase here is close to that
link's size. Aggregate relay memory includes the extra running
process. The first Object timing includes application scheduling
on loopback and does not estimate geographic hop latency.

- [Sanitized trial events](2026-11-20-aiomoqt-relay-topology.jsonl)
- [Machine-readable summary](2026-11-20-aiomoqt-relay-topology-summary.json)
