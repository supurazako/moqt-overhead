#!/usr/bin/env bash
# Run the draft-22 admission checks against local loopback relays.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
relay=${1:?Usage: run.sh aiomoqt|moqtail|imquic|mlmrel}
python=${PYTHON:-"$root/.venv/bin/python"}
port=${MOQ_PORT:-45443}
work=$(mktemp -d)
pid=
container=
cleanup() {
    if [[ -n "$container" ]]; then
        docker rm -f "$container" >/dev/null 2>&1 || true
    fi
    if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    rm -rf -- "$work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$python" - "$port" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind(("127.0.0.1", int(sys.argv[1])))
PY
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -noenc -days 1 \
    -subj /CN=localhost -addext subjectAltName=DNS:localhost,IP:127.0.0.1 \
    -keyout "$work/key.pem" -out "$work/cert.pem" >/dev/null 2>&1

case "$relay" in
    aiomoqt)
        command=("$python" -m aiomoqt.tools.moq_interop_relay
            --bind 127.0.0.1 --port "$port" --quic --draft 22
            --cert "$work/cert.pem" --key "$work/key.pem" --log-level WARNING)
        ;;
    moqtail)
        container="moqt-overhead-interop-$$"
        command=(docker run --rm --name "$container"
            -p "127.0.0.1:$port:$port/udp" --user "$(id -u):$(id -g)"
            --tmpfs /tmp:rw,mode=1777
            -v "$work:/certs:ro"
            ghcr.io/moqtail/relay@sha256:e6d28fc9dbbe295e4a7e6780b6d61383deab994785a87d01cfef0e18701719d5
            --host 0.0.0.0 --port "$port" --cert-file /certs/cert.pem
            --key-file /certs/key.pem)
        ;;
    imquic)
        container="moqt-overhead-interop-$$"
        command=(docker run --rm --name "$container"
            -p "127.0.0.1:$port:$port/udp" --user "$(id -u):$(id -g)"
            -v "$work:/certs:ro" moqt-overhead-imquic:d93d181
            -b 0.0.0.0 -p "$port" -M 22 -q -c /certs/cert.pem -k /certs/key.pem)
        ;;
    mlmrel)
        command=("${MLMREL:-"$root/.scratch/mlmrel"}"
            -addr "127.0.0.1:$port" -cert "$work/cert.pem" -key "$work/key.pem"
            -loglevel warning)
        ;;
    *)
        printf 'Unknown relay: %s\n' "$relay" >&2
        exit 2
        ;;
esac

(cd "$work" && exec "${command[@]}") >"$work/relay.log" 2>&1 &
pid=$!
for attempt in {1..100}; do
    if [[ "$relay" == moqtail ]] && rg -q "is running on" "$work/relay.log"; then
        break
    fi
    if [[ "$relay" == imquic ]] && docker exec "$container" awk \
        -v address="00000000:$(printf '%04X' "$port")" \
        '$2 == address {found=1} END {exit !found}' /proc/net/udp 2>/dev/null; then
        break
    fi
    if [[ -z "$container" ]] && ss -Hlun | awk -v address="127.0.0.1:$port" '$4 == address {found=1} END {exit !found}'; then
        break
    fi
    if ! kill -0 "$pid" 2>/dev/null || [[ "$attempt" == 100 ]]; then
        cat "$work/relay.log" >&2
        exit 1
    fi
    sleep 0.1
done

if [[ "${MOQ_SPLIT_ENDPOINTS:-0}" == 1 ]]; then
    "$python" "$root/experiments/interop/endpoints.py" "$port" "$work/cert.pem"
    exit
fi

status=0
for test in setup-only data-subgroup-basic; do
    # Disabling verification is only for this loopback smoke test.
    timeout 30 "$python" -m aiomoqt.tools.moq_interop_client \
        --relay "moqt://127.0.0.1:$port" --draft 22 \
        --test "$test" --tls-disable-verify --log-level error || status=1
done
if (( status )); then
    cat "$work/relay.log" >&2
fi
exit "$status"
