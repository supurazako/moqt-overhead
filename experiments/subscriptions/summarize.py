"""Validate fixed-connection subscription trials and summarize per-role increments."""

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

RELAYS = ('aiomoqt','imquic','moqtail')
ROLES = ('relay','publisher','subscriber')


def describe(values):
    return {'n':len(values),'median':median(values),'min':min(values),'max':max(values)} if values else None


def summarize(path):
    trials=defaultdict(list)
    for line in path.read_text().splitlines():
        row=json.loads(line)
        trials[row['subscriptions'],row['block'],row['relay']].append(row)
    if trials.keys() != set(itertools.product(range(5),range(1,7),RELAYS)):
        raise ValueError('Expected 90 distinct scheduled trials')
    for count in range(5):
        orders=set()
        for block in range(1,7):
            positions={trials[count,block,name][0]['position']:name for name in RELAYS}
            orders.add(tuple(positions.get(p) for p in (1,2,3)))
        if orders != set(itertools.permutations(RELAYS)):
            raise ValueError('Unbalanced execution order')
    result=[]
    for count in range(5):
        for name in RELAYS:
            values=defaultdict(list)
            passed=0
            for block in range(1,7):
                rows=trials[count,block,name]
                completed=[r for r in rows if r['event']=='trial_completed']
                if len(completed)!=1 or not completed[0]['passed']:
                    continue
                established=[r for r in rows if r['event']=='established']
                if len(established)!=2 or any(r['count']!=count for r in established):
                    raise ValueError('Incorrect subscription acknowledgment count')
                passed+=1
                for role in ROLES:
                    samples={r['phase']:r for r in rows
                             if r['event']=='sample' and r['role']==role}
                    if samples.keys() != {'setup','subscribed'}:
                        raise ValueError('Missing phase samples')
                    before,after=(samples[p] for p in ('setup','subscribed'))
                    for metric in ('pss_kib','rss_kib'):
                        values[f'{role}.{metric}_delta'].append(after[metric]-before[metric])
                        values[f'{role}.{metric}'].append(after[metric])
                    if before['cpu_ns'] is not None and after['cpu_ns'] is not None:
                        prior_cpu = 1000 * before['cpu_ns'] / before['window_ns']
                        final_cpu = 1000 * after['cpu_ns'] / after['window_ns']
                        values[f'{role}.cpu_ms_per_s_delta'].append(final_cpu - prior_cpu)
            result.append({'relay':name,'subscriptions':count,'passed':passed,'trials':6,
                           'metrics':{key:describe(v) for key,v in values.items()}})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    args=parser.parse_args()
    print(json.dumps(summarize(args.input),indent=2))
