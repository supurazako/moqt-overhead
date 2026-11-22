"""Validate a paired idle pilot CSV and report descriptive statistics."""

import argparse
import csv
from collections import Counter
from pathlib import Path
from statistics import median


def describe(values):
    return dict(zip(("median", "min", "max"), map(lambda f: round(f(values), 3),
                                                 (median, min, max))))


def summarize(path, blocks, connections=range(5)):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    if blocks < 2 or blocks % 2:
        raise ValueError("Expected a positive, even block count")
    expected = {(count, block, server) for count in connections
                for block in range(1, blocks + 1) for server in ("quic", "moqt")}
    trials = {(int(r["connections"]), int(r["block"]), r["server"]): r for r in rows}
    if trials.keys() != expected or len(trials) != len(rows):
        raise ValueError("Missing, duplicate, or unexpected trial rows")

    wire_metrics = ("client_datagrams", "client_udp_bytes",
                    "server_datagrams", "server_udp_bytes")
    conditions = []
    for count in connections:
        pairs = [(trials[count, block, "quic"], trials[count, block, "moqt"])
                 for block in range(1, blocks + 1)]
        orders = Counter((q["position"], m["position"]) for q, m in pairs)
        if orders != {("1", "2"): blocks // 2, ("2", "1"): blocks // 2}:
            raise ValueError(f"Unbalanced execution order at {count} connections")

        def metric(*names):
            quic = [sum(float(q[name]) for name in names) for q, _ in pairs]
            moqt = [sum(float(m[name]) for name in names) for _, m in pairs]
            return {"quic": describe(quic), "moqt": describe(moqt),
                    "paired_delta": describe([m - q for q, m in zip(quic, moqt)])}

        result = {"connections": count, "pss_kib": metric("pss_kib"),
                  "rss_kib": metric("rss_kib"),
                  "cpu_nonzero_windows": {
                      kind: sum(int(pair[index]["cpu_ticks"]) > 0 for pair in pairs)
                      for index, kind in enumerate(("quic", "moqt"))
                  }}
        if "scheduled_cpu_ns" in rows[0]:
            valid_pairs = [(q, m) for q, m in pairs
                           if q["scheduled_cpu_ns"] and m["scheduled_cpu_ns"]]
            quic_cpu, moqt_cpu = (
                [float(pair[index]["scheduled_cpu_ns"]) / 1e6 / float(pair[index]["idle_window_s"])
                 for pair in valid_pairs] for index in range(2)
            )
            if valid_pairs:
                result["scheduled_cpu_ms_per_s"] = {
                    "pairs": len(valid_pairs), "quic": describe(quic_cpu),
                    "moqt": describe(moqt_cpu),
                    "paired_delta": describe([m - q for q, m in zip(quic_cpu, moqt_cpu)]),
                }
        if all(name in rows[0] for name in wire_metrics):
            for name in wire_metrics:
                result[name] = metric(name)
            result["total_udp_bytes"] = metric("client_udp_bytes", "server_udp_bytes")
            result["total_datagrams"] = metric("client_datagrams", "server_datagrams")
        if count:
            result["first_quic_ready_us"] = metric("first_quic_ready_us")
            result["first_moqt_setup_us"] = describe(
                [float(m["first_moqt_setup_us"]) for _, m in pairs])
        conditions.append(result)
    return conditions


if __name__ == "__main__":
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--blocks", type=int, default=6)
    parser.add_argument("--connections", nargs="+", type=int, choices=range(5), default=list(range(5)))
    args = parser.parse_args()
    print(json.dumps(summarize(args.csv, args.blocks, args.connections), indent=2))
