# 2026-11-20 · Draft-22 relay qualification

## Scope

- Admission checks for the draft-22 raw QUIC measurement series.
- One Linux x86_64 host (kernel 6.12.90, Python 3.13.5, Docker 29.5.3).
- Common client: aiomoqt 0.14.1 and aiopquic 0.7.1. The
  `data-subgroup-basic` test uses specification revision 2.
- Two cases per relay: `setup-only` and `data-subgroup-basic`. Each
  starts fresh client sessions. The transfer case checks synthetic Object
  content and count, and the completion of the three subgroup streams.
- These are functional checks. No resource usage or latency estimates
  are taken from these runs.

## Successful runs

- **aiomoqt 0.14.1**: native Python process. SETUP passed at ALPN
  `moqt-22`. Transfer passed, with 15 Objects and 3 streams on each leg.
- **MOQtail relay 0.17.0 (2c3efc6)**: Linux amd64 release image,
  `sha256:e6d28fc9dbbe295e4a7e6780b6d61383deab994785a87d01cfef0e18701719d5`.
  SETUP passed at ALPN `moqt-22`. Transfer passed, with 15 Objects
  and 3 streams on each leg.
- **imquic 0.0.3/alpha (d93d181)**: built with picoquic
  `f506de8f8bc92bc06b4920ca2ad5100c8b834f2e` and picotls
  `e446233b4100ebcdec60901c05bfb7f4cd369c5d`. The build recorded
  GLib 2.84.4-3~deb13u5, Jansson 2.14-2+b3, and OpenSSL
  3.5.7-1~deb13u3. SETUP passed at ALPN `moqt-22`. Transfer
  passed, with 15 Objects and 3 streams on each leg.
- **Eyevinn mlmrel v0.18.0 (7553b544)**: native Go 1.26.0 build;
  moqtransport 0.15.0, quic-go 0.62.0. SETUP passed at ALPN
  `moqt-22`. Transfer passed, with 15 Objects and 3 streams on each leg.

## Attempts and changes

1. **aiomoqt**: the first run completed both cases.
2. **MOQtail**: the image's default UID could not read the private
   temporary certificate directory. A retry under the invoking UID
   reached a second permission error when creating the log file.
3. **MOQtail**: a writable temporary filesystem allowed startup.
   The address-based readiness check still timed out because it expected
   an explicit IPv4 socket address and the host-network socket appeared
   as a wildcard. A standalone SETUP check confirmed the relay was
   running. The runner now publishes UDP on loopback and checks the
   container's startup message. Both cases passed after that change.
4. **mlmrel**: Go selected the module's 1.26.0 toolchain and the first
   run completed both cases.
5. **imquic**: GLib development files were unavailable on the host.
   A Debian build container was used to install build dependencies
   without changing the host. An early launch was attempted before
   image export finished. The first completed image pointed to
   `examples/moq-relay`, which was absent. Switching the entrypoint
   to `examples/imquic-moq-relay` resolved the launch error. Both
   cases passed on the rebuilt image.

## Separate endpoint check

All four relays passed with Publisher and Subscriber in separate
processes, an explicit trust file, and 15 Objects over three subgroup
streams. The client records events on the same host monotonic clock.
In some runs the first Object callback preceded the return of the
subscription call. Record both events independently in later timing
analysis.

## Decision

Keep draft-22 as the primary series. All three initial candidates
qualified. Eyevinn mlmrel also qualified as an additional candidate.
Before the performance pilot, align deployment conditions across
relays, implement matched QUIC baselines, and define the practical
difference and precision targets for each metric. The checks in this
record ran under native and containerized configurations.

The [reproduction instructions](../interop/README.md) contain commands.
The [sanitized CSV](2026-11-20-draft22-qualification.csv) retains case
outcomes, negotiated ALPN, and Object and stream counts.
