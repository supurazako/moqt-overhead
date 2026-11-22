#!/usr/bin/env bash
# Run the fixed follow-up matrix sequentially on an isolated loopback.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
python=${PYTHON:-"$root/.venv/bin/python"}
output=${1:-"$root/.scratch/idle-recheck"}
mkdir -p "$output"

for profile in aiomoqt imquic moqtail; do
    for series in cpu startup; do
        options=(--blocks 6 --connections 0 --window 5)
        if [[ "$series" == startup ]]; then
            options=(--blocks 12 --connections 1 --window 1 --capture)
        fi
        unshare --user --map-root-user --net sh -c 'ip link set lo up && exec "$@"' sh \
            "$python" "$root/experiments/idle/measure_idle.py" --profile "$profile" \
            --fine-cpu "${options[@]}" >"$output/$profile-$series.csv" \
            2>"$output/$profile-$series.log"
    done
done
