"""Extract an allowlisted qualification result from two aiomoqt TAP cases."""

import argparse
import csv
import re
import sys
from pathlib import Path

EXPECTED = ("setup-only", "data-subgroup-basic")


def extract(path):
    contents = path.read_text()
    matches = list(re.finditer(r"^(ok|not ok) 1 - ([\w-]+)$", contents, re.M))
    if tuple(match[2] for match in matches) != EXPECTED:
        raise ValueError("Expected one completed TAP result for each qualification case")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(contents)
        diagnostic = contents[match.end():end]
        protocols = sorted(set(re.findall(r'^\s+alpn: "(moqt-\d+)"$', diagnostic, re.M)))
        counts = re.search(
            r"(\d+) objects received; Stream Count upstream (\d+), downstream (\d+)",
            diagnostic,
        )
        outcome = "pass" if match[1] == "ok" else "fail"
        yield [match[2], outcome, " ".join(protocols), *(counts.groups() if counts else ("", "", ""))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", help="Entries in the form relay=path")
    args = parser.parse_args()
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["relay", "case", "outcome", "alpn", "objects_received",
                     "upstream_streams", "downstream_streams"])
    for entry in args.results:
        relay, path = entry.split("=", 1)
        for row in extract(Path(path)):
            writer.writerow([relay, *row])


if __name__ == "__main__":
    main()
