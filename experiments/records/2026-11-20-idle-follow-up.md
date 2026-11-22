# Draft-22 idle and startup follow-up

## Design

The [fixed follow-up design](../idle/FOLLOW-UP.md) was recorded before
this run. The same aiomoqt, imquic and MOQtail binaries and matched
controls from the [idle pilots](2026-11-20-draft22-matched-idle.md)
were used. Fresh listener processes ran in isolated Linux loopback
network namespaces, with balanced within-profile run order.

- **Zero connections**: six paired blocks per implementation, 5 s
  observation per arm, scheduled CPU runtime and PSS.
- **One connection**: twelve paired blocks per implementation, 1 s
  observation per arm, first SETUP interval and immediately captured
  UDP payload through the idle window, excluding teardown.
- **Intervals**: distribution-free order-statistic intervals for a
  common median under independent observations. Nominal coverage is
  96.9% at six blocks and 96.1% at twelve. The intervals are marginal
  across the reported metrics.

## Results

All 108 scheduled listener runs completed. Cells show a median
and its order-statistic interval in brackets.

| Relay | Zero-connection PSS delta (MiB) | Zero-connection CPU delta (ms/s) | First SETUP (ms) | UDP payload delta (bytes) |
| --- | ---: | ---: | ---: | ---: |
| aiomoqt | 5.26 [5.08, 5.28] | -0.21 [-0.87, 1.16] | 1.72 [1.00, 1.88] | 83.5 [13.0, 177.0] |
| imquic | 0.18 [0.11, 0.27] | 0.00 [-0.12, 0.10] | 0.50 [0.41, 0.55] | 140.5 [-12.0, 196.0] |
| moqtail | 7.09 [6.89, 7.18] | 0.00 [0.00, 0.00] | 1.26 [1.08, 2.15] | 155.5 [105.0, 156.0] |

Deltas subtract the matched baseline within each block. SETUP is
the relay-side scenario as observed by the connecting client, from
the QUIC call returning to SETUP completion. UDP payload values
include the handshake and ACKs. This follow-up covers zero and one
connection, with no track or data transfer.

## Artifacts

- [Machine-readable summary](2026-11-20-idle-follow-up/summary.json)
- [aiomoqt idle](2026-11-20-idle-follow-up/aiomoqt-cpu.csv) and [startup](2026-11-20-idle-follow-up/aiomoqt-startup.csv)
- [imquic idle](2026-11-20-idle-follow-up/imquic-cpu.csv) and [startup](2026-11-20-idle-follow-up/imquic-startup.csv)
- [MOQtail idle](2026-11-20-idle-follow-up/moqtail-cpu.csv) and [startup](2026-11-20-idle-follow-up/moqtail-startup.csv)
