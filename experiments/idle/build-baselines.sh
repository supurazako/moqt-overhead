#!/usr/bin/env bash
# Build native listener controls for the native imquic and MOQtail relays.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
native="$root/.scratch/native"
quinn="$root/.scratch/quinn-build"
mkdir -p "$native" "$quinn/src"

cp "$root/experiments/idle/quinn/Cargo.toml" "$quinn/"
cp "$root/experiments/idle/quinn/src/main.rs" "$quinn/src/"
curl -fsSL https://raw.githubusercontent.com/moqtail/moqtail/2c3efc60659fec3dfda5ded56581236a4035e8f1/Cargo.lock \
    -o "$quinn/Cargo.lock"
# Build from the relay's dependency lock, allowing Cargo to drop unrelated crates.
cargo build --release --manifest-path "$quinn/Cargo.toml" -j 4
python3 - "$quinn/Cargo.lock" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as f:
    packages = {p["name"]: p["version"] for p in tomllib.load(f)["package"]}
expected = {"quinn": "0.11.12", "quinn-proto": "0.11.19", "rustls": "0.23.46",
            "tokio": "1.53.2", "wtransport": "0.7.2"}
for name, version in expected.items():
    if packages.get(name) != version:
        raise SystemExit(f"Unexpected {name} version: {packages.get(name)}")
PY
cp "$quinn/target/release/moqtail-quic-baseline" "$native/"

docker build -f "$root/experiments/idle/imquic-echo.Dockerfile" \
    -t moqt-overhead-imquic-echo:d93d181 "$root/experiments/idle"
container=$(docker create moqt-overhead-imquic-echo:d93d181)
trap 'docker rm "$container" >/dev/null' EXIT
docker cp "$container:/build/imquic/examples/.libs/imquic-echo-server" "$native/"
