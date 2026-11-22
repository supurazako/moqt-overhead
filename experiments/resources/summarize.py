"""Validate balanced role-resource records and summarize paired increments."""
import argparse
import collections
import itertools
import json
import random
import statistics
from pathlib import Path


def interval(values):
    rng = random.Random(22)
    medians = sorted(statistics.median(rng.choices(values, k=len(values)))
                     for _ in range(10000))
    return {'n': len(values), 'median': statistics.median(values),
            'min': min(values), 'max': max(values),
            'ci95': [medians[249], medians[9749]]}


def summarize(paths):
    rows = [json.loads(line) for path in paths for line in Path(path).read_text().splitlines()]
    cases = collections.defaultdict(list)
    for row in rows:
        if 'relay' in row:
            cases[row['mode'], row['level'], row['block'], row['relay']].append(row)
    expected = set()
    configurations = [row for row in rows if row['event'] == 'configuration']
    if len(configurations) != 2 or {r['mode'] for r in configurations} != {'idle', 'active'}:
        raise ValueError('Expected one idle and one active configuration')
    for config in configurations:
        levels = [0, 1, 2, 3] if config['mode'] == 'idle' else [1, 4]
        if config['levels'] != levels or not config['balanced']:
            raise ValueError('Unexpected conditions')
        expected.update(itertools.product([config['mode']], levels, range(1, 7),
                                          ('aiomoqt', 'imquic', 'moqtail')))
    if cases.keys() != expected:
        raise ValueError(f'Incomplete schedule: missing {expected - cases.keys()}')
    if next(c for c in configurations if c['mode'] == 'active').get('cpu_counter') != 'linux-process-clock':
        raise ValueError('Expected corrected process-clock active series')
    output = {'trials': len(cases), 'failures': [], 'groups': {}, 'increments': {},
              'orders': {}, 'invalid_cpu_rows': [], 'diagnostics': {}}
    resources = {}
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    orders = collections.defaultdict(dict)
    for key, events in cases.items():
        mode, level, block, relay = key
        position = {e['position'] for e in events}
        if len(position) != 1:
            raise ValueError('Inconsistent position')
        orders[mode, level, block][next(iter(position))] = relay
        failed = [e for e in events if e['event'] == 'trial_failed']
        complete = [e for e in events if e['event'] == 'trial_completed' and e['passed']]
        if failed or len(complete) != 1:
            output['failures'].append({'case': key, 'errors': failed, 'completed': len(complete)})
            continue
        expected_roles = {'relay', 'publisher', 'subscriber'} | (
            {f'idle-{i}' for i in range(level)} if mode == 'idle' else set())
        samples = [e for e in events if e['event'] == 'resource']
        if {e['role'] for e in samples} != expected_roles or len(samples) != len(expected_roles):
            raise ValueError(f'Incomplete role samples: {key}')
        wire = [e for e in events if e['event'] == 'wire']
        if {e['role'] for e in wire} != expected_roles - {'relay'} or len(wire) != len(expected_roles)-1:
            raise ValueError(f'Incomplete traffic attribution: {key}')
        if mode == 'active':
            sent = next(e for e in events if e['event'] == 'sent')
            received = next(e for e in events if e['event'] == 'received')
            if sent['objects'] != 1500 * level or received['objects'] != sent['objects'] or received['errors']:
                raise ValueError(f'Unexpected delivery: {key}')
            started = next(e for e in events if e['event'] == 'send_start')['ns']
            elapsed = (sent['ns'] - started) / 1e9
            if elapsed <= 0 or received['first_ns'] < started:
                raise ValueError(f'Invalid same-host timing: {key}')
            groups[mode, level, relay, 'publisher']['send_elapsed_s'].append(elapsed)
            groups[mode, level, relay, 'publisher']['payload_bytes_per_s'].append(sent['objects'] * 8192 / elapsed)
            groups[mode, level, relay, 'subscriber']['first_object_ms'].append((received['first_ns'] - started) / 1e6)
        for row in samples:
            metrics = {field: row[field] for field in (
                'pss_start_kib','pss_end_kib','pss_max_sampled_kib',
                'rss_start_kib','rss_end_kib','rss_max_sampled_kib')}
            if row['cpu_ns'] is None:
                output['invalid_cpu_rows'].append({'case': key, 'role': row['role']})
            if row['cpu_ns'] is not None:
                metrics['cpu_ms_per_s'] = row['cpu_ns'] / row['window_ns'] * 1000
            series = [s for s in row['series'] if s['elapsed_ns'] >= 5e9]
            if len(series) > 1 and all(s['cpu_valid'] for s in series):
                first, last = series[0], series[-1]
                metrics['post5_cpu_ms_per_s'] = (last['cpu_ns']-first['cpu_ns']) / (last['elapsed_ns']-first['elapsed_ns']) * 1000
                metrics['post5_pss_change_kib'] = last['pss_kib']-first['pss_kib']
            resources[*key, row['role']] = metrics
            for field, value in metrics.items():
                groups[mode, level, relay, row['role']][field].append(value)
        for row in wire:
            if mode == 'active':
                field = 'tx_udp_bytes' if row['role'] == 'publisher' else 'rx_udp_bytes'
                if row[field] < 1500 * level * 8192:
                    raise ValueError(f'Traffic capture below delivered payload: {key}')
            for field in ('tx_udp_bytes','rx_udp_bytes'):
                groups[mode, level, relay, row['role']][field].append(row[field])
        groups[mode, level, relay, 'relay']['tx_udp_bytes'].append(sum(e['rx_udp_bytes'] for e in wire))
        groups[mode, level, relay, 'relay']['rx_udp_bytes'].append(sum(e['tx_udp_bytes'] for e in wire))
    for (mode, level), sequence in itertools.groupby(sorted(orders), key=lambda k: k[:2]):
        observed = [tuple(orders[key][i] for i in (1, 2, 3)) for key in sequence]
        if set(observed) != set(itertools.permutations(('aiomoqt','imquic','moqtail'))) or len(observed) != 6:
            raise ValueError(f'Unbalanced orders: {mode} {level}')
        output['orders'][f'{mode}/{level}'] = observed
    for mode, level, relay, role in groups:
        key = '/'.join(map(str, (mode, level, relay, role)))
        details = {}
        for field in ('pss_end_kib', 'post5_cpu_ms_per_s', 'cpu_ms_per_s'):
            blocks = [(b, resources[(mode,level,b,relay,role)][field])
                      for b in range(1,7)
                      if (mode,level,b,relay,role) in resources
                      and field in resources[(mode,level,b,relay,role)]]
            if blocks:
                details[field] = {'by_block': blocks,
                    'first_half_median': statistics.median(v for b,v in blocks if b <= 3) if any(b <= 3 for b,v in blocks) else None,
                    'last_half_median': statistics.median(v for b,v in blocks if b > 3) if any(b > 3 for b,v in blocks) else None}
        for field, detail in details.items():
            by_position = collections.defaultdict(list)
            for block, value in detail['by_block']:
                position = next(e['position'] for e in cases[mode,level,block,relay])
                by_position[position].append(value)
            detail['position_medians'] = {str(pos): statistics.median(values)
                                          for pos, values in by_position.items()}
        output['diagnostics'][key] = details
    output['groups'] = {'/'.join(map(str, key)): {field: interval(values) for field, values in metrics.items()}
                        for key, metrics in groups.items()}
    for mode, baseline, levels in [('idle',0,[1,2,3]), ('active',1,[4])]:
        for level, relay, role in itertools.product(levels, ('aiomoqt','imquic','moqtail'), ('relay','publisher','subscriber')):
            pairs = [(resources.get((mode,level,b,relay,role)), resources.get((mode,baseline,b,relay,role))) for b in range(1,7)]
            deltas = collections.defaultdict(list)
            for current, base in pairs:
                if current and base:
                    for field in current.keys() & base.keys():
                        deltas[field].append(current[field]-base[field])
            output['increments'][f'{mode}/{level}-{baseline}/{relay}/{role}'] = {field: interval(values) for field,values in deltas.items()}
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    print(json.dumps(summarize(args.paths), indent=2))
