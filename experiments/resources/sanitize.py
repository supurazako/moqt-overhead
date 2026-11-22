"""Replace absolute host-monotonic event times with per-trial relative times."""
import argparse
import json
from pathlib import Path


def sanitize(source, target):
    rows = [json.loads(line) for line in Path(source).read_text().splitlines()]
    origins = {}
    for row in rows:
        if 'relay' in row and 'ns' in row:
            key = tuple(row[k] for k in ('mode','level','block','relay'))
            origins[key] = min(origins.get(key, row['ns']), row['ns'])
    for row in rows:
        if row['event'] == 'configuration':
            row['event_timestamps'] = 'nanoseconds since first event in each trial'
        if 'relay' not in row:
            continue
        key = tuple(row[k] for k in ('mode','level','block','relay'))
        for field in ('ns','first_ns'):
            if row.get(field) is not None:
                row[field] -= origins[key]
    Path(target).write_text(''.join(json.dumps(row)+'\n' for row in rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('target')
    args = parser.parse_args()
    sanitize(args.source, args.target)
