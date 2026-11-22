# Small-payload Publisher/Subscriber implementation pilot

## Question and scope

How much resource usage do existing Linux Publisher/Subscriber implementations
achieve in a small, controlled workload? This is a PC process measurement,
not a firmware build, MCU memory requirement, intrinsic protocol minimum,
or proof that a microcontroller can run the same programs.

## Candidates

- imquic C examples at `d93d18141b0db5f167290a6b162b059dc964015e`:
  `imquic-moq-test` for publishing and `imquic-moq-sub` for subscribing.
- MOQtail Rust test client 0.17.0 at
  `2c3efc60659fec3dfda5ded56581236a4035e8f1` (`client@0.17.0`).
- aiomoqt 0.14.1 / aiopquic 0.7.1, with the same small Python adapter.
- Additional candidates inspected: moxygen and libquicr. moxygen's current
  source includes partial draft-22 with a Meta-specific ALPN; its retrieved
  interop executable exposes control test cases rather than standalone
  50-Object Pub/Sub roles; some cases create multiple sessions in one process. It is not
  admitted as a role-isolated resource arm. libquicr's inspected current
  source targets draft-18, outside the primary series. No resource ranking
  is made for either project.

The C and Rust programs are existing upstream test applications with small,
recorded measurement adapters. They are not newly optimized MCU clients.
Unused features can still contribute to their footprint.

## Conditions fixed after admission checks, before balanced collection

- IETF MoQT draft-22 over raw QUIC; private Linux loopback namespace.
- One fixed aiomoqt relay process; one fixed aiomoqt counterpart process.
  Only the measured endpoint implementation changes, one role at a time.
- One connection to the relay, one subscribed track, 50 Objects of 64 bytes
  each, every 100 ms. Group 0, Object IDs 0–49, one subgroup stream.
- All payload bytes are `t`. Receiver adapters validate count, location /
  sequence and payload, without retaining full payload history. aiomoqt
  retains a small ID set for duplicate detection; native clients retain
  counters or their existing test statistics.
- Publisher idle state: namespace accepted, no Subscriber connected.
  Subscriber idle state: subscription accepted, common Publisher gated.
  Observe each for two seconds, then measure about five seconds of transfer.
- These idle states differ by role; do not subtract them as a pure Pub/Sub
  protocol difference. A Publisher's active window starts just after its
  counterpart process launch; a Subscriber's begins when the gated peer is
  released. Actual sampled durations are recorded.
- PSS/RSS every 100 ms, Linux process CPU clock retaining exited-thread
  runtime. Record sampled maxima and CPU duration/window. Sampling can miss
  shorter peaks. This pilot does not measure startup allocation peaks or
  allocator-only RAM. The main metrics describe complete Linux processes.
- Six blocks, all six permutations of the three implementations, seed
  22023. New processes and connections each trial; two roles in each block,
  36 trials total. The same within-block order supports paired differences.
- Encrypted, verified TLS: local test CA signs a separate leaf with CA:FALSE,
  serverAuth and localhost/127.0.0.1 names. Clients trust that CA explicitly.
  No machine trust store is modified. No resumption, qlog or media codec.
- Runtime defaults are retained, including Tokio's worker count. Logging is
  suppressed except small readiness/receipt instrumentation events. This is
  not a one-thread-tuned Rust configuration.
- The common Publisher defers PUBLISH_DONE until cleanup so the candidate
  Subscriber remains alive for resource sampling. The comparison therefore
  does not claim to validate early-termination race handling.

## Adapters and build

Patches in this directory document all native changes: readiness/receipt
markers, validation, a common constant payload instead of Rust's PRNG,
certificate verification enabled in the imquic samples, and explicit
single-root trust configuration. Protocol library behavior is otherwise
unchanged. The imquic core patch exposes a test root file through the
existing picoquic configuration; it does not disable verification.

The imquic tools/library were rebuilt inside the existing pinned
`moqt-overhead-imquic:d93d181` image. MOQtail was built with
`CC=clang CXX=clang++ cargo build --release --locked -p client -j 4`.
`prepare.py` generates most adapters from fresh source checkouts; apply
`connection.rs.patch` and `quic.c.patch` as well. Source/binary hashes and
compiler/runtime versions are recorded with the results.

## Reproduce

[Exact adapter build commands](BUILD.md).

Install the [existing dependencies](../interop/README.md). Obtain and build
the pinned native sources, apply the patches, and place these files under
`.scratch/endpoint-built`: `imquic-bench-pub`, `imquic-bench-sub`,
`libimquic.so.0`, and `moqtail-bench-client`.

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec /tmp/moq-overhead-venv/bin/python experiments/endpoints/measure.py --balanced' \
  > endpoint-events.jsonl 2> endpoint-diagnostics.log
python3 experiments/endpoints/summarize.py endpoint-events.jsonl > endpoint-summary.json
```

An unrelated-root negative check is available as
`--negative-trust --roles publisher`. It expects no READY marker; confirm
certificate rejection in the separate diagnostic log. Successful trusted
runs and the enabled-verifier source settings are also required evidence.

## Exclusions and limits

Initial smoke checks exposed CA-as-leaf rejection and wtransport ignoring
SSL_CERT_FILE when loading native roots. Both checks remain separate from
balanced estimates. A custom trusted-root adapter resolved this without
using a no-verify switch.

Public event files contain synthetic counts, samples and relative durations.
Private keys, packet captures and local stderr are not published. No firmware
was built or flashed for this study; the briefly started ESP-IDF image pull
was cancelled when the scope was clarified.

## Repeated memory categories

To repeat anonymous/file-backed memory observations with six independent
trials per implementation and role (36 trials, balanced order):

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec /tmp/moq-overhead-venv/bin/python experiments/endpoints/memory-categories.py --balanced' \
  > category-events.jsonl 2> category-diagnostics.log
python3 experiments/endpoints/summarize-categories.py category-events.jsonl > category-summary.json
```

For each trial, use the final transfer-window sample, then report the
median and observed range across six trials. The main endpoint memory
comparison uses each trial's sampled maximum, so these are distinct
statistics. Without `--balanced`, the wrapper retains the original
one-run-per-role diagnostic mode.
