# Fixed connections, variable idle subscriptions

## Design

- **Question**: how much idle state is added by 0–4 distinct track
  subscriptions when the Publisher and Subscriber each keep one connection?
- **Implementations**: the pinned aiomoqt, imquic and MOQtail relays from
  the [draft-22 qualification](2026-11-20-draft22-qualification.md).
  Publisher and Subscriber both use aiomoqt 0.14.1 / aiopquic 0.7.1.
- **Network and TLS**: raw QUIC, strict draft-22, trusted test certificate,
  private Linux loopback network namespace. Two client connections per trial.
- **States**: SETUP and namespace publication completed; then the requested
  tracks subscribed and acknowledged by both endpoints. No Objects are
  sent, so the terminal Object issue is not exercised here.
- **Measurement**: each state settles for 0.5 s before a 1 s CPU window.
  PSS/RSS are sampled at its end. Per-role deltas subtract the first
  phase from the second phase within a fresh-process trial. The
  zero-subscription condition measures drift over the same two windows.
- **Schedule**: six blocks per count, all six relay orders, seed 22;
  90 trials in total. Counts and order are fixed before the run.
- **Scope**: each subscription refers to a different track. The added state
  includes track bookkeeping and subscription bookkeeping. This pilot
  does not isolate multiple subscriptions to the same track.

## Preparation

The 0- and 4-subscription smoke checks succeeded on all three relays.
The finite-transfer harness was reused for relay launch, process cleanup
and procfs resource counters. The endpoint code acknowledges upstream
SUBSCRIBE requests without sending Objects. Upstream acknowledgment and
Subscriber completion counts are checked before collecting the second
phase.

[Reproduction procedure](../subscriptions/README.md)
## Results

All 90 scheduled trials completed with matching upstream and downstream
subscription counts. Values below are medians of within-process PSS
changes from SETUP/publication to the second observation phase.

| Subscriptions | aiomoqt Relay (KiB) | imquic Relay (KiB) | MOQtail Relay (KiB) |
| ---: | ---: | ---: | ---: |
| 0 | 0.0 | 0.0 | 0.0 |
| 1 | 20.0 | 97.5 | 274.0 |
| 2 | 52.5 | 144.0 | 382.0 |
| 3 | 77.0 | 80.0 | 300.0 |
| 4 | 104.0 | 154.0 | 398.0 |

The 0-subscription row estimates observation drift; raw changes above
have not been corrected by subtracting another trial. The endpoints use
the same Python implementation in every arm. Detailed ranges, endpoint
metrics, and CPU deltas are in the summary. These are exploratory
descriptive statistics, with no confidence interval or scalability claim.

- [Trial observations](2026-11-21-idle-subscriptions.jsonl)
- [Per-role summary](2026-11-21-idle-subscriptions-summary.json)

## Interpretation and limits

- With four subscriptions, Publisher PSS changes had medians of 44–48 KiB
  across relay arms; Subscriber medians were 44–63.5 KiB. One Subscriber
  observation in each of the aiomoqt and MOQtail arms was near 2 MiB;
  those observations were retained.
- Relay four-subscription PSS ranges were 104–104 KiB for aiomoqt,
  84–172 KiB for imquic and 252–588 KiB for MOQtail. The zero-subscription
  Relay changes were between -1 and +1 KiB.
- imquic and MOQtail medians are not monotonic across the five levels.
  These snapshots do not justify a constant per-subscription memory cost.
- CPU windows remain short and do not resolve startup CPU from idle CPU.
  A main measurement should lengthen the window and investigate memory
  outliers before making claims about small differences.
