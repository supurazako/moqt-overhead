# aiomoqt idle pilot

The pilot compares aiomoqt 0.14.1 against a bare aiopquic 0.7.1 listener.
For every condition, six paired blocks balance the two implementation orders.
A seeded shuffle determines condition order. Every row uses a fresh server
process. Clients hold 0–4 fresh connections open for the measurement. The
MoQT arm completes SETUP on every connection. There are no tracks or objects.

Before running this pilot, use provisional practical differences of 1 MiB
PSS, 1 ms CPU per second, and 1 ms startup time. Use half of each difference
as the provisional target for the eventual confidence interval half-width.
These targets describe measurement sensitivity for this pilot's scope.

```sh
python3 -m venv .venv
.venv/bin/pip install -r experiments/interop/requirements.txt
.venv/bin/python experiments/idle/measure_idle.py > idle-pilot.csv
```

The idle window starts after 0.5 seconds of settling. CPU ticks are counted
over one second using Linux procfs. PSS and RSS are sampled at the end of
the window. Startup times are client-observed for the first connection of
each fresh server process. The MoQT SETUP interval starts after the QUIC
connection call returns. No private keys are saved with the output.

## UDP capture

The optional capture follows IPv4 UDP payloads on loopback, by source port.
It starts before the clients connect and ends after the idle window, before
connection teardown. It combines the handshake, any SETUP, and idle
traffic. These wire runs are analyzed separately from the no-capture pilot.
A temporary capture exists for the duration of each trial and is deleted
after decoding. The CSV contains only counts and byte totals.

On Linux with unprivileged user namespaces enabled, isolate the experiment
traffic rather than granting capture rights on the host network:

```sh
unshare --user --map-root-user --net sh -c \
  'ip link set lo up && exec .venv/bin/python experiments/idle/measure_idle.py --capture' \
  > idle-wire-pilot.csv
```

Validate the no-capture result and calculate paired descriptive statistics:

```sh
python3 experiments/idle/summarize.py idle-pilot.csv
```

## Matched controls for imquic and MOQtail

First obtain the native relay binaries using the
[fanout preparation instructions](../fanout/README.md). Then build the
two additional controls:

```sh
experiments/idle/build-baselines.sh
```

The imquic control is the upstream raw QUIC echo listener, with no
application stream data sent by the client. It uses the same imquic
shared library as the relay. The MOQtail control is a small listener
using the relay's Quinn, rustls and Tokio versions, with BBR, the
same idle timeout, the same keep-alive interval, and the same bidi
stream limit. Both controls negotiate `moqt-22` to match the TLS ALPN.
The controls retain their own process initialization and application
behavior. Measured deltas apply to these pairs of programs.

```sh
for relay in imquic moqtail aiomoqt; do
    unshare --user --map-root-user --net sh -c \
        'ip link set lo up && exec "$@"' sh .venv/bin/python \
        experiments/idle/measure_idle.py --profile "$relay" --fine-cpu --capture \
        > "$relay-matched-idle.csv"
    python3 experiments/idle/summarize.py "$relay-matched-idle.csv"
done
```

The `--fine-cpu` option counts nanoseconds of Linux scheduled runtime
across a stable set of process threads. It also retains the original
tick samples. Wire capture uses immediate mode to avoid flushing
incomplete blocks at the end of a short run.
