"""Audit final observations and publication artifacts against declared scope."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT/'experiments/records'
summary = json.loads((RECORDS/'2026-11-22-resource-summary.json').read_text())
assert summary['trials'] == 108 and not summary['failures']
assert len(summary['invalid_cpu_rows']) == 2
assert all(row['case'][0] == 'idle' and row['role'].startswith('idle-')
           for row in summary['invalid_cpu_rows'])
for mode, expected in [('idle',72),('active',36)]:
    rows = [json.loads(line) for line in (RECORDS/f'2026-11-22-{mode}-resources.jsonl').read_text().splitlines()]
    assert sum(r['event'] == 'trial_completed' and r['passed'] for r in rows) == expected
    assert not any(r['event'] == 'trial_failed' for r in rows)
    assert rows[0]['event_timestamps'] == 'nanoseconds since first event in each trial'
    for row in rows:
        if 'ns' in row:
            assert row['ns'] >= 0
        if row['event'] != 'resource':
            continue
        minimum = 29e9 if mode == 'active' else 4.5e9
        assert row['window_ns'] >= minimum
        assert row['samples'] == len(row['series']) >= (100 if mode == 'active' else 18)
        assert row['pss_max_sampled_kib'] >= row['pss_end_kib'] > 0
        elapsed = [s['elapsed_ns'] for s in row['series']]
        assert elapsed == sorted(elapsed) and len(elapsed) == len(set(elapsed))
        assert elapsed[-1] == row['window_ns']
        if mode == 'active':
            assert row['cpu_ns'] is not None and row['cpu_ns'] >= 0
            assert all(s['cpu_valid'] for s in row['series'])
            cpu = [s['cpu_ns'] for s in row['series']]
            assert cpu == sorted(cpu)
for relay in ('aiomoqt','imquic','moqtail'):
    for tracks in (1,4):
        for role in ('publisher','relay','subscriber'):
            group = summary['groups'][f'active/{tracks}/{relay}/{role}']
            assert group['post5_cpu_ms_per_s']['n'] == 6
            assert group['pss_max_sampled_kib']['n'] == 6
            assert group['tx_udp_bytes']['n'] == 6

blog = ROOT/'reports/blog/moqt-fixed-costs.md'
text = blog.read_text()
assert not re.search(r'Results pending|still being collected', text, re.I)
for relative in ('experiment-plan.md','experiments/resources/README.md',
                 'experiments/records/2026-11-22-resource-series.md',
                 'reports/blog/moqt-fixed-costs.md'):
    path = ROOT/relative
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if '://' not in target and not target.startswith('#'):
            assert (path.parent/target.split('#')[0]).exists(), (relative,target)
for name in ('idle-increment','extra-connections','active-role-memory','active-role-cpu','active-memory-over-time'):
    for extension in ('png','svg'):
        assert (blog.parent/'figures'/f'{name}.{extension}').stat().st_size > 1000
for path in [blog, RECORDS/'2026-11-22-resource-series.md',
             *RECORDS.glob('2026-11-22-*-resources*.jsonl')]:
    content = path.read_text()
    assert not re.search(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}',content)
    assert '/home/sprzk/' not in content
print('PASS: 108 cases, role/window/timing invariants, CPU validity, links, figures and targeted secret scan')
