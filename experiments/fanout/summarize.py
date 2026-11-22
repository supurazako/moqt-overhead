"""Validate fanout pilot blocks and summarize complete-delivery trials."""

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

RELAYS = ("aiomoqt", "imquic", "moqtail")
PHASES = ("disconnected", "subscribed", "transfer")


def load_trials(source):
    trials = defaultdict(list)
    with source.open() as stream:
        for line in stream:
            row = json.loads(line)
            key = row["subscribers"], row["block"], row["relay"]
            trials[key].append(row)
    return trials


def sanitize(trials, path):
    with path.open("w") as output:
        for rows in trials.values():
            start = min((r["ns"] for r in rows if "ns" in r), default=0)
            for row in rows:
                item = row.copy()
                if "ns" in item:
                    item["elapsed_ns"] = item.pop("ns") - start
                if "error" in item and item["error"] != "Object delivery validation failed":
                    item["error"] = "See trial notes"
                output.write(json.dumps(item, separators=(",", ":")) + "\n")


def describe(values):
    if not values:
        return None
    return {"n": len(values), "median": round(median(values), 3),
            "min": round(min(values), 3), "max": round(max(values), 3)}


def summarize(trials):
    expected = set(itertools.product(range(1, 5), range(1, 7), RELAYS))
    if trials.keys() != expected:
        raise ValueError("Expected 72 distinct trials")
    report = []
    for count in range(1, 5):
        orders = set()
        for block in range(1, 7):
            positions = {trials[count, block, name][0]["position"]: name for name in RELAYS}
            orders.add(tuple(positions.get(pos) for pos in (1, 2, 3)))
        if orders != set(itertools.permutations(RELAYS)):
            raise ValueError(f"Order is not balanced at subscriber count {count}")
        for name in RELAYS:
            passed = 0
            received = 0
            missing_locations = defaultdict(int)
            measured = defaultdict(list)
            before_transfer = defaultdict(list)
            incomplete_transfer = defaultdict(list)
            for block in range(1, 7):
                rows = trials[count, block, name]
                terminals = [r for r in rows if r["event"] in ("trial_completed", "trial_failed")]
                if not terminals:
                    raise ValueError(f"Incomplete trial {count}/{block}/{name}")
                received_rows = [r for r in rows if r["event"] == "received"]
                received += sum(r["objects"] for r in received_rows)
                for row in received_rows:
                    for group, obj in row["missing"]:
                        missing_locations[f"{group}.{obj}"] += 1
                success = terminals[-1]["event"] == "trial_completed" and terminals[-1]["passed"]
                passed += int(success)
                if success and (len(received_rows) != count or any(r["objects"] != 120 for r in received_rows)):
                    raise ValueError("A passing trial did not deliver every Object")
                for phase in PHASES:
                    samples = [r for r in rows if r["event"] == "sample" and r["phase"] == phase]
                    if not samples and not success:
                        continue
                    target = (before_transfer if phase != "transfer" else
                              measured if success else incomplete_transfer)
                    for key in ("publisher", "relay", "subscriber"):
                        metrics = [r for r in samples if r["role"].split("-")[0] == key]
                        if len(metrics) != (count if key == "subscriber" else 1):
                            raise ValueError(f"Missing role or phase samples: {name}/{phase}/{key}")
                        for metric in ("pss_kib", "rss_kib"):
                            target[f"{phase}.{key}.{metric}"].append(sum(r[metric] for r in metrics))
                        if all(r["cpu_ns"] is not None for r in metrics):
                            target[f"{phase}.{key}.cpu_ms_per_s"].append(
                                sum(1000 * r["cpu_ns"] / r["window_ns"] for r in metrics))
                if not success:
                    continue
                send_start = next(r["elapsed_ns"] for r in rows if r["event"] == "send_start")
                first = [r["elapsed_ns"] for r in rows if r["event"] == "first_object"]
                if len(first) != count:
                    raise ValueError("Missing first-object event")
                measured["slowest_first_object_ms"].append((max(first) - send_start) / 1e6)
                for role in ["publisher", *(f"subscriber-{i}" for i in range(1, count + 1))]:
                    times = {r["event"]: r["elapsed_ns"] for r in rows
                             if r.get("role") == role and "elapsed_ns" in r}
                    kind = role.split("-")[0]
                    checkpoints = [("connect_start", "quic_connected"), ("quic_connected", "setup_done")]
                    checkpoints.append(("setup_done", "published" if kind == "publisher" else "subscribed"))
                    if kind == "subscriber":
                        checkpoints.append(("connect_start", "first_object"))
                    for start, end in checkpoints:
                        measured[f"startup.{kind}.{start}_to_{end}_ms"].append(
                            (times[end] - times[start]) / 1e6)
                wires = [r for r in rows if r["event"] == "wire"]
                for key in ("publisher", "subscriber"):
                    links = [r for r in wires if r["role"].split("-")[0] == key]
                    if len(links) != (count if key == "subscriber" else 1):
                        raise ValueError("Missing UDP link data")
                    for metric in ("tx_udp_bytes", "rx_udp_bytes", "tx_datagrams", "rx_datagrams"):
                        measured[f"wire.{key}.{metric}"].append(sum(r[metric] for r in links))
                for direction, peer_direction in (("tx", "rx"), ("rx", "tx")):
                    for unit in ("udp_bytes", "datagrams"):
                        measured[f"wire.relay.{direction}_{unit}"].append(
                            sum(r[f"{peer_direction}_{unit}"] for r in wires))
            report.append({"relay": name, "subscribers": count, "passed": passed,
                           "trials": 6, "objects_received": received,
                           "objects_expected": 6 * count * 120,
                           "missing_locations": dict(missing_locations),
                           "pretransfer": {key: describe(vals) for key, vals in before_transfer.items()},
                           "incomplete_transfer": {key: describe(vals) for key, vals in incomplete_transfer.items()},
                           "successful_trials": {key: describe(vals) for key, vals in measured.items()}})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--sanitize", type=Path)
    args = parser.parse_args()
    trials = load_trials(args.source)
    if args.sanitize:
        sanitize(trials, args.sanitize)
        trials = load_trials(args.sanitize)
    print(json.dumps(summarize(trials), indent=2))


if __name__ == "__main__":
    main()
