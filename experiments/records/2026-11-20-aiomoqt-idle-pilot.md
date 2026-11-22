# 2026-11-20 · aiomoqt draft-22 idle pilot

## Scope and run order

- **Comparison**: aiomoqt 0.14.1 relay and bare aiopquic 0.7.1 listener.
  Both use aiopquic, BBR, ALPN `moqt-22`, a trusted local P-256
  certificate, a 64 KiB datagram frame limit, a 1 MiB stream ring cap,
  and a 4,096-connection listener limit. The two arms use their native
  Python protocol factories and listener startup paths.
- **Host**: Linux x86_64 6.12.90, AMD Ryzen 7 2700, Python 3.13.5,
  OpenSSL 3.5.7 for certificate generation. Wire capture used tcpdump
  4.99.5 and libpcap 1.10.5.
- **Conditions**: 0–4 held connections, six paired blocks per connection
  count, three starts in each order, seed 22. Each arm starts a fresh
  listener. The relay completes SETUP on each connection. No track or
  subscription is created. The captured run uses a separate namespace
  and is analyzed separately.
- **Timing**: 0.5 s settling before a 1 s idle window. Startup intervals
  are observed in the client process for the first connection of each
  listener. PSS and CPU refer to the listener process. See
  [reproduction instructions](../idle/README.md) for commands and
  provisional sensitivity targets.

## No-capture pilot

All 60 scheduled trials completed. The quoted PSS difference is the
median of the six within-block differences per connection count.

| Held connections | Bare QUIC PSS, median (KiB) | Relay PSS, median (KiB) | Paired difference, median (KiB) | Observed difference range (KiB) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 21,139.5 | 26,693.0 | 5,537 | 5,507–5,652 |
| 1 | 21,403.5 | 26,948.5 | 5,570 | 5,454–5,737 |
| 2 | 21,494.0 | 27,023.5 | 5,606 | 5,421–5,691 |
| 3 | 21,575.0 | 27,106.0 | 5,516 | 5,465–5,784 |
| 4 | 21,588.5 | 27,278.5 | 5,682 | 5,530–7,701 |

- **Memory**: at zero connections, the paired difference was 5.41 MiB.
  Across 0–4 held connections, group medians ranged from 5.39 to
  5.55 MiB. The sign was positive in all 30 pairs and the median was
  positive in both orders at every connection count. The four-connection
  group had one 7,701 KiB difference, retained in the data.
- **Startup**: across the 24 trials with connections per arm, first
  QUIC-ready time had medians of 4.25 ms for the bare listener and 5.53 ms
  for the relay. The 24 relay SETUP intervals had a median of 1.89 ms
  and ranged from 1.64–2.00 ms. These intervals include client-side
  work and loopback scheduling. They do not estimate WAN startup.
- **Idle CPU**: each one-second window showed zero or one process CPU tick.
  At 100 Hz, one tick is 10 ms of CPU time, above the provisional
  target of 1 ms/s. This run cannot resolve a practical CPU difference.
  A longer observation window or a finer-resolution process or cgroup
  CPU counter is needed.

The observed ranges are descriptive. Final confidence intervals and
inference require the planned main measurement. The PSS difference
covers the whole relay process relative to its bare-listener baseline,
including imports and relay functions.

## UDP payload on loopback

All 60 scheduled trials completed in the isolated namespace. Counts
cover both directions from before the first connection to the end of
the idle window, excluding connection teardown. The capture aggregates
QUIC, TLS, ACKs and MoQT activity.

| Held connections | Bare QUIC, median (bytes) | Relay, median (bytes) | Paired difference, median (bytes) | Observed difference range (bytes) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 |
| 1 | 6,307 | 6,445 | 138 | -82–194 |
| 2 | 12,448 | 12,689.5 | 241 | 94–317 |
| 3 | 18,452.5 | 18,927.5 | 476 | 124–550 |
| 4 | 24,567 | 25,293 | 722.5 | 522–908 |

The one-connection block differences include a negative value. These
are whole-exchange deltas that include differences in packetization
and ACKs. The UDP size of the MoQT messages themselves is not inferred
from this comparison.

## Attempts and measurement changes

1. The first invocation stopped before any trial because the script
   name shadowed the installed `aiomoqt` package. Renaming the script
   resolved the import error.
2. Direct capture on the host loopback socket failed for lack of capture
   rights. A user-owned network namespace provided a private loopback
   socket. In that namespace, tcpdump's default privilege drop failed
   because its usual UID was unmapped. Both the capture and decoder now
   explicitly run as the namespace's mapped root.
3. The first wire run stopped before producing a data row because the
   decoder still attempted the privilege drop. The retry applies the
   same namespace UID to both tcpdump commands.

## Artifacts

- [No-capture pilot rows](2026-11-20-aiomoqt-idle-pilot.csv)
- [Wire pilot rows](2026-11-20-aiomoqt-idle-wire.csv)
