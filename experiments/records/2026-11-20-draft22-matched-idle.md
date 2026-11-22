# 2026-11-20 · Draft-22 matched idle pilots

## Comparison

Each relay is paired with a local listener using its QUIC and TLS
dependencies. Every arm uses the same Python client, ALPN `moqt-22`,
and trusted P-256 test certificate. The relay arm completes SETUP.
No tracks, subscriptions or Objects are created.

- **aiomoqt**: relay 0.14.1 and an aiopquic 0.7.1 listener with BBR,
  matching flow-control defaults, datagram limit, stream ring cap,
  and connection limit.
- **imquic**: relay and raw QUIC echo server from commit `d93d181`,
  sharing the same extracted imquic library, picoquic, picotls and
  host dependencies. The test client sends no application stream data
  to the echo server.
- **MOQtail**: relay 0.17.0 and a minimal listener built with Quinn
  0.11.12, Quinn protocol 0.11.19, rustls 0.23.46, Tokio 1.53.2 and
  wtransport 0.7.2. BBR, 7 s idle timeout, 3 s keep-alive and the
  10,000 bidi stream limit match the relay. The control is compiled
  separately from the release relay binary.

The resulting differences describe the two measured programs and
their configurations. They include their distinct initialization,
application behavior and, where applicable, build differences.

## Procedure

- Same Linux host and native binaries as the fanout pilot.
- One private network namespace per profile, from before the first
  trial through the last, with IPv4 loopback capture.
- Six fresh-process pairs at each of 0–4 held connections. Three
  pairs in each execution order, seeded condition order with seed 22.
- 0.5 s settling and a 1 s idle observation. PSS/RSS at the end of
  the idle interval. Scheduled CPU time is summed across stable
  process threads and divided by the observed wall time.
- Byte counts cover both directions from before the first connection
  through the idle window, excluding teardown. QUIC, TLS, ACKs and
  SETUP can share those windows.
- The program reports elapsed connection and SETUP calls using the
  same client clock. The statistics below are paired descriptive
  medians and observed ranges.

See [build and reproduction commands](../idle/README.md).

## Results

All 180 trials completed. Each cell reports the median paired PSS
difference in KiB, with the relay minus its matched QUIC control.

| Held connections | aiomoqt | imquic | MOQtail |
| ---: | ---: | ---: | ---: |
| 0 | 5,426 | 119.5 | 7,127.5 |
| 1 | 5,423 | 309 | 7,640 |
| 2 | 5,433 | 360 | 7,714.5 |
| 3 | 5,534.5 | 359 | 7,830 |
| 4 | 5,578 | 371 | 7,792 |

- **Memory**: the zero-connection paired differences are approximately
  5.30 MiB for aiomoqt, 0.12 MiB for imquic, and 6.96 MiB for MOQtail.
- **Idle CPU**: the magnitude of every median within-profile
  difference was below the provisional 1 ms/s threshold. These
  short windows describe idle scheduled CPU time. The ranges and
  individual observations remain available.
- **Initial SETUP**: in the one-connection case, median SETUP times
  after the QUIC call returned were 1.72 ms for aiomoqt, 0.46 ms for
  imquic, and 1.09 ms for MOQtail. These are local client observations.
- **UDP payload**: in the one-connection case, the median of the
  paired deltas across both directions was 138 bytes for aiomoqt,
  168.5 bytes for imquic, and 134 bytes for MOQtail. These deltas
  measure the entire exchange through the idle window.

The aiomoqt repeat uses immediate capture and scheduled-runtime
counters. The first aiomoqt pilot remains in the record as a separate
series.

## Artifacts

- [aiomoqt observations](2026-11-20-aiomoqt-matched-idle.csv)
- [imquic observations](2026-11-20-imquic-matched-idle.csv)
- [MOQtail observations](2026-11-20-moqtail-matched-idle.csv)
- [Machine-readable summary](2026-11-20-draft22-matched-idle-summary.json)
