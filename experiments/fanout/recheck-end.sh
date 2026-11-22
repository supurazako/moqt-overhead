#!/usr/bin/env bash
# Six balanced pairs of immediate and deferred PUBLISH_DONE, one Subscriber.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
python=${PYTHON:-"$root/.venv/bin/python"}
output=${1:-"$root/.scratch/end-recheck"}
mkdir -p "$output"
for block in {1..6}; do
    order=(0 100)
    if (( block % 2 == 0 )); then order=(100 0); fi
    for delay in "${order[@]}"; do
        row="$output/block-$block-delay-$delay"
        if unshare --user --map-root-user --net sh -c 'ip link set lo up && exec "$@"' sh \
            env MOQ_END_TRACE=1 MOQ_END_DELAY_MS="$delay" MOQ_RELAY_TRACE=1 \
            "$python" "$root/experiments/fanout/measure.py" --relays imquic --subscribers 1 \
            >"$row.jsonl" 2>"$row.log"; then
            printf '%s,%s,0\n' "$block" "$delay"
        else
            printf '%s,%s,%s\n' "$block" "$delay" "$?"
        fi
    done
done
