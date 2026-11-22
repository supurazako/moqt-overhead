# Draft-22 relay qualification

These loopback checks qualify relay versions for the measurement matrix. The same
aiomoqt client strictly negotiates `moqt-22` and runs `setup-only` and
`data-subgroup-basic`. The latter announces a namespace, subscribes to a track,
and checks three groups of five synthetic Objects, including their contents.
The test timings include client and teardown work and are excluded from the
performance analysis.

## Reproduce

Use Linux, Python 3.13, OpenSSL, iproute2, ripgrep, and GNU coreutils.
Docker is used for the MOQtail and imquic qualification runs. Build Eyevinn
mlmrel with Go 1.26.0.

```sh
python3 -m venv .venv
.venv/bin/pip install -r experiments/interop/requirements.txt
mkdir -p .scratch
git clone --depth 1 --branch v0.18.0 https://github.com/Eyevinn/moqlivemock .scratch/moqlivemock
test "$(git -C .scratch/moqlivemock rev-parse HEAD)" = 7553b544c90b71a5acbcbf05d5b08be91273abb2
(cd .scratch/moqlivemock && GOTOOLCHAIN=go1.26.0 go build -o ../mlmrel ./cmd/mlmrel)
docker build -f experiments/interop/imquic.Dockerfile -t moqt-overhead-imquic:d93d181 experiments/interop

experiments/interop/run.sh aiomoqt > .scratch/aiomoqt.tap 2> .scratch/aiomoqt.err
experiments/interop/run.sh moqtail > .scratch/moqtail.tap 2> .scratch/moqtail.err
experiments/interop/run.sh mlmrel > .scratch/mlmrel.tap 2> .scratch/mlmrel.err
experiments/interop/run.sh imquic > .scratch/imquic.tap 2> .scratch/imquic.err
```

The runner uses one loopback UDP port per invocation. Set `MOQ_PORT` to
override the default 45443. The self-signed certificate is generated per run
and the client skips certificate verification for this check. Performance
measurements should use an explicitly trusted certificate and comparable
listener configurations. Keep raw logs in `.scratch/`. Review the results
before copying evidence into the experiment record.

## Verify separate endpoint processes

Set `MOQ_SPLIT_ENDPOINTS=1` to launch Publisher and Subscriber in separate
processes. Both validate the relay's certificate against the generated trust
file. The run emits JSON Lines with role, event name, and a host monotonic
timestamp. These timestamps validate the measurement hooks.

```sh
for relay in aiomoqt moqtail imquic mlmrel; do
    MOQ_SPLIT_ENDPOINTS=1 experiments/interop/run.sh "$relay" \
        > ".scratch/$relay-split.jsonl" 2> ".scratch/$relay-split.err"
done
python3 experiments/interop/extract.py aiomoqt=.scratch/aiomoqt.tap \
    moqtail=.scratch/moqtail.tap imquic=.scratch/imquic.tap mlmrel=.scratch/mlmrel.tap
```
