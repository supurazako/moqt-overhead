"""Validate all role-isolated endpoint trials and report descriptive statistics."""
import argparse
import collections
import itertools
import json
import statistics
from pathlib import Path

NAMES=('imquic','moqtail','aiomoqt')
ROLES=('publisher','subscriber')


def describe(values):
    return dict(n=len(values),median=statistics.median(values),minimum=min(values),maximum=max(values))


def summarize(path):
    rows=[json.loads(line) for line in Path(path).read_text().splitlines()]
    trials=collections.defaultdict(list)
    for row in rows:
        trials[row['role'],row['block'],row['implementation']].append(row)
    expected=set(itertools.product(ROLES,range(1,7),NAMES))
    if trials.keys()!=expected: raise ValueError('Expected all 36 endpoint trials')
    groups=collections.defaultdict(lambda:collections.defaultdict(list))
    blocks={}; failures=[]; orders=collections.defaultdict(dict)
    for key,events in trials.items():
        role,block,name=key
        orders[role,block][events[0]['position']]=name
        completed=[e for e in events if e['event']=='completed' and e['passed']]
        if any(e['event']=='failed' for e in events) or len(completed)!=1:
            failures.append(key);continue
        assert completed[0]['objects']==50 and completed[0]['payload_bytes']==3200
        resources=[e for e in events if e['event']=='resource']
        assert {r['phase'] for r in resources}=={'connected_idle','transfer'} and len(resources)==2
        for row in resources:
            samples=row['samples'];phase=row['phase']
            assert len(samples)>=18 if phase=='connected_idle' else len(samples)>=45
            assert row['window_ns'] >= (1.8e9 if phase=='connected_idle' else 4.5e9)
            assert row['cpu_ns']>=0 and row['pss_end_kib']>0
            cpu=[s['cpu_ns'] for s in samples]
            assert cpu==sorted(cpu)
            metrics={f:row[f] for f in ('pss_start_kib','pss_end_kib','pss_max_kib','rss_max_kib','thread_count')}
            metrics['cpu_ms_per_s']=row['cpu_ns']/row['window_ns']*1000
            blocks[role,block,name,phase]=metrics
            for field,value in metrics.items(): groups[role,name,phase][field].append(value)
    for role in ROLES:
        observed=[tuple(orders[role,block][i] for i in (1,2,3)) for block in range(1,7)]
        assert set(observed)==set(itertools.permutations(NAMES))
    differences={}
    for role,phase,name in itertools.product(ROLES,('connected_idle','transfer'),('imquic','moqtail')):
        paired=collections.defaultdict(list)
        for block in range(1,7):
            current=blocks.get((role,block,name,phase)); base=blocks.get((role,block,'aiomoqt',phase))
            if current and base:
                for field in current: paired[field].append(current[field]-base[field])
        differences[f'{role}/{name}-aiomoqt/{phase}']={f:describe(v) for f,v in paired.items()}
    return {'trials':len(trials),'failed_cases':failures,
        'groups':{'/'.join(key):{f:describe(v) for f,v in metrics.items()} for key,metrics in groups.items()},
        'paired_differences':differences}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('events')
    print(json.dumps(summarize(parser.parse_args().events),indent=2))
