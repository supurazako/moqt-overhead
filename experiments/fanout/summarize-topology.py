"""Summarize balanced aiomoqt one- and two-relay trials."""

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from summarize import sanitize


def describe(values):
    return {"n": len(values), "median": median(values),
            "min": min(values), "max": max(values)} if values else None


def metrics(rows, hops):
    def relay_samples(phase):
        samples = [r for r in rows if r["event"] == "sample"
                   and r["phase"] == phase and r["role"].startswith("relay")]
        if len(samples) != hops:
            raise ValueError(f"Expected {hops} relay samples in {phase}")
        return samples

    idle = relay_samples("subscribed")
    active = relay_samples("transfer")
    start = next(r.get("ns", r.get("elapsed_ns")) for r in rows if r["event"] == "send_start")
    first = max(r.get("ns", r.get("elapsed_ns")) for r in rows if r["event"] == "first_object")
    wire = [r for r in rows if r["event"] == "wire"]
    inter_relay = [r for r in wire if r["role"] == "relay-edge"]

    def bytes_total(links):
        return sum(r["tx_udp_bytes"] + r["rx_udp_bytes"] for r in links)

    return {"idle_relay_pss_mib": sum(r["pss_kib"] for r in idle) / 1024,
            "transfer_relay_cpu_ms_per_s": (
                sum(r["cpu_ns"] / r["window_ns"] * 1000 for r in active)
                if all(r["cpu_ns"] is not None for r in active) else None),
            "slowest_first_object_ms": (first - start) / 1e6,
            "total_udp_bytes": bytes_total(wire),
            "inter_relay_udp_bytes": bytes_total(inter_relay)}


def summarize(trials):
    expected = set(itertools.product((1, 4), range(1, 7), (1, 2)))
    if trials.keys() != expected:
        raise ValueError("Expected six paired blocks per Subscriber count")
    result = []
    for count in (1, 4):
        orders = Counter()
        observed = {1: [], 2: []}
        paired = defaultdict(list)
        for block in range(1, 7):
            rows = {h: trials[count, block, h] for h in (1, 2)}
            orders[tuple(r[0]["position"] for r in rows.values())] += 1
            values = {}
            for hops, trial in rows.items():
                endpoints = [r for r in trial if r["event"] == "trial_completed"]
                if len(endpoints) == 1 and endpoints[0]["passed"]:
                    values[hops] = metrics(trial, hops)
                    observed[hops].append(values[hops])
            if len(values) == 2:
                for key, one in values[1].items():
                    two = values[2][key]
                    if one is not None and two is not None:
                        paired[key].append(two - one)
        if orders != {(1, 2): 3, (2, 1): 3}:
            raise ValueError(f"Unbalanced orders at {count} Subscribers")
        summaries = {}
        for hops, runs in observed.items():
            summaries[hops] = {
                "passed": len(runs),
                "metrics": {key: describe([r[key] for r in runs if r[key] is not None])
                            for key in runs[0]} if runs else {},
            }
        result.append({"subscribers": count, "arms": summaries,
                       "paired_delta": {key: describe(vals) for key, vals in paired.items()}})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--sanitize", type=Path)
    args = parser.parse_args()
    trials = defaultdict(list)
    with args.input.open() as source:
        for line in source:
            row = json.loads(line)
            trials[row["subscribers"], row["block"], row["hops"]].append(row)
    results = summarize(trials)
    if args.sanitize:
        sanitize(trials, args.sanitize)
    print(json.dumps(results, indent=2))
