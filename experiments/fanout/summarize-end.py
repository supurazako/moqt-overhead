"""Extract terminal event order from local diagnostic logs."""

import argparse
import csv
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory", type=Path)
args = parser.parse_args()
out = csv.writer(sys.stdout, lineterminator="\n")
out.writerow(["block", "delay_ms", "objects_received", "relay_done_line",
              "relay_track_removed_line", "relay_final_object_line", "relay_track_missing_line",
              "publisher_done_after_fin_ms", "subscriber_done_after_final_object_ms"])
for block in range(1, 7):
    for delay in ((0, 100) if block % 2 else (100, 0)):
        base = args.directory / f"block-{block}-delay-{delay}"
        events = {row["event"]: row for row in map(json.loads, base.with_suffix(".jsonl").read_text().splitlines())}
        lines = base.with_suffix(".log").read_text().splitlines()
        done = next(i for i, line in enumerate(lines, 1) if "Subscription via ID" in line and "is done" in line)
        final = next(i for i, line in enumerate(lines, 1)
                     if "Incoming object:" in line and "group=3," in line and " id=29," in line)
        removed = next(i for i, line in enumerate(lines, 1) if "Removing track 'track'" in line)
        missing = final + 1 if "No track found for that subscription" in lines[final] else ""
        queued = (events["publish_done_queued"]["ns"] - events["data_and_fin_queued"]["ns"]) / 1e6
        final_received = events.get("final_object_received")
        received = ((events["publish_done_received"]["ns"] - final_received["ns"]) / 1e6
                    if final_received else "")
        out.writerow([block, delay, events["received"]["objects"], done, removed, final, missing,
                      round(queued, 3), round(received, 3) if final_received else ""])
