# 2026-11-20 · Draft-22 fanout pilot

## Question

How do connected-idle resources, delivery, and active transfer resources
change when the same publisher and synthetic track feed one to four
subscribers through different draft-22 relays?

## Conditions

- **Host**: Linux 6.12.90 x86_64, AMD Ryzen 7 2700, Python 3.13.5.
  All roles ran as native processes over IPv4 loopback in a private
  network namespace. Endpoints trusted the shared test certificate.
- **Relays**: aiomoqt 0.14.1, imquic 0.0.3/alpha
  (`d93d18141b0db5f167290a6b162b059dc964015e`), and MOQtail relay
  0.17.0 (`2c3efc6`). The imquic executable used the extracted shared
  imquic library plus host GLib 2.84.4-3~deb13u3, Jansson 2.14-2+b3,
  and OpenSSL 3.5.7-1~deb13u2.
- **Workload**: aiomoqt 0.14.1 / aiopquic 0.7.1 endpoints, one
  publisher, one track, four subgroup streams, 120 synthetic 8 KiB
  Objects in total, 20 ms between Objects, 1–4 subscribers. Each
  subscriber was expected to receive 983,040 payload bytes.
- **Design**: six blocks per subscriber count, all six relay orders,
  seeded condition order, fresh processes at each trial. The
  measurement and capture tools were the same in all arms.
- **Provisional sensitivity**: the earlier idle pilot used 1 MiB PSS,
  1 ms CPU per second, and 1 ms startup as practical differences.
  This series is descriptive and retains observations for selecting
  main-measurement repetitions. See the [workload and commands](../fanout/README.md).

## Attempts and changes

1. The first functional check used all three relays with four
   subscribers and delivered all Objects. The check revealed that
   the test tuple put the pacing argument into the Objects-per-group
   field. The corrected workload puts the 20 ms interval in the
   pacing field. The functional check is excluded from the pilot.
2. The first pilot attempt used native host networking. The MOQtail
   executable opened a wildcard UDP socket. That attempt was stopped
   and its data was set aside. The reported run uses a private
   namespace, so the wildcard listener is reachable only within
   that namespace.
3. The first capture check reported fewer UDP payload bytes than
   the client had verified. The retry enabled tcpdump immediate
   mode, allowed a short drain before stopping capture, and added
   a lower-bound payload validation. The check then passed. Pilot
   runs use the revised collector.
4. The slower workload exposed intermittent final-Object loss in
   an imquic arm. Missing Object IDs and the trial outcome are
   recorded. Pre-transfer metrics use all available trials. Complete and incomplete
   transfers have separate resource summaries.

## Outcomes

All 72 scheduled trials reached the delivery check. The runner exited
nonzero after recording the 20 unsuccessful imquic trials.

| Subscribers | aiomoqt full trials | imquic full trials | MOQtail full trials | imquic Objects received / expected |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 6/6 | 0/6 | 6/6 | 714/720 |
| 2 | 6/6 | 0/6 | 6/6 | 1,428/1,440 |
| 3 | 6/6 | 2/6 | 6/6 | 2,148/2,160 |
| 4 | 6/6 | 2/6 | 6/6 | 2,864/2,880 |

All 46 missing deliveries in the imquic arm were Group 3, Object 29,
the final Object. Each affected subscriber observed all four subgroup
stream endings and a termination message. These observations describe
the tested relay/endpoint/workload combination. The root cause remains
unconfirmed.

## Resource and startup observations

Subscribed-idle PSS medians use the six observations in each cell.
PSS apportions shared memory. Adding endpoint processes can change
a process's share of shared mappings.

| Subscribers | aiomoqt relay PSS (MiB) | imquic relay PSS (MiB) | MOQtail relay PSS (MiB) |
| ---: | ---: | ---: | ---: |
| 1 | 24.82 | 3.61 | 12.94 |
| 2 | 24.24 | 3.53 | 13.77 |
| 3 | 24.06 | 3.63 | 14.52 |
| 4 | 23.78 | 3.59 | 15.52 |

- **Endpoint PSS with four subscribers**: subscribed-idle Publisher
  medians were 23.94–24.17 MiB across relay arms. The four Subscribers'
  summed medians were 95.56–96.66 MiB. All endpoints used the same
  Python implementation.
- **Transfer CPU with four subscribers**: median scheduled CPU time
  in ms per elapsed second was 25.6 / 71.3 / 119.1 for Publisher /
  Relay / Subscriber total through aiomoqt, and 26.9 / 63.2 / 95.3
  through MOQtail. Each uses six complete trials. For imquic, only
  two complete trials were available at this fanout.
- **Transfer timing with four subscribers**: median send-invocation
  to slowest Subscriber first Object was 13.68 ms for aiomoqt and
  14.51 ms for MOQtail. This is a loopback workload measurement.
- **Wire traffic with four subscribers**: median Relay transmissions
  were about 4.06 MB for aiomoqt and 4.07 MB for MOQtail, summing links
  in the Relay's transmit direction. The 3,932,160 bytes of delivered
  application payload equal four copies of 983,040 bytes. The UDP
  totals also cover connection and subscription setup and ACKs.

The resource observations describe complete implementations for this
configuration. The matched idle controls are a separate comparison.

## Artifacts

- [Sanitized trial events](2026-11-20-draft22-fanout-pilot.jsonl)
- [Machine-readable descriptive summary](2026-11-20-draft22-fanout-summary.json)
