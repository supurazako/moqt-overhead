"""Summarize the fixed zero-connection and first-connection follow-up."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median

from summarize import summarize

PROFILES = ("aiomoqt", "imquic", "moqtail")


def interval(values):
    ordered = sorted(values)
    index = {6: 0, 12: 2}[len(ordered)]
    return {"n": len(ordered), "median": median(ordered), "low": ordered[index],
            "high": ordered[-(index + 1)]}


def profile_summary(directory, profile):
    output = {}
    for series, blocks, count in (("cpu", 6, 0), ("startup", 12, 1)):
        path = directory / f"{profile}-{series}.csv"
        summarize(path, blocks, [count])  # check trials and order before analysis
        with path.open(newline="") as source:
            rows = {(int(r["block"]), r["server"]): r for r in csv.DictReader(source)}

        for key, metric in (("pss_kib", lambda r: int(r["pss_kib"])),
                            ("cpu_ms_per_s", lambda r: int(r["scheduled_cpu_ns"]) /
                             1e6 / float(r["idle_window_s"]))):
            delta = [metric(rows[block, "moqt"]) - metric(rows[block, "quic"])
                     for block in range(1, blocks + 1)]
            output[f"{series}_{key}_delta"] = interval(delta)
        if series == "startup":
            output["setup_ms"] = interval(
                [float(rows[block, "moqt"]["first_moqt_setup_us"]) / 1000
                 for block in range(1, blocks + 1)])
            totals = [[sum(int(rows[block, server][f"{side}_udp_bytes"])
                           for side in ("client", "server")) for server in ("quic", "moqt")]
                      for block in range(1, blocks + 1)]
            output["udp_bytes_delta"] = interval([moqt - quic for quic, moqt in totals])
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps({p: profile_summary(args.directory, p) for p in PROFILES}, indent=2))
