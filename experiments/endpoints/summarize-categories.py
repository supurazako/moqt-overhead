"""Validate balanced category runs and summarize final per-trial samples."""
import argparse
import collections
import json
import statistics
from pathlib import Path
from summarize import summarize


def category_summary(path):
    validation=summarize(path)
    if validation['failed_cases']:
        raise ValueError('Category trials failed; retain and inspect the events')
    groups=collections.defaultdict(lambda:collections.defaultdict(list))
    fields=('pss_kib','pss_anon_kib','pss_file_kib','private_clean_kib','private_dirty_kib','other_pss_residual_kib')
    for line in Path(path).read_text().splitlines():
        row=json.loads(line)
        if row['event']!='resource': continue
        sample=row['samples'][-1]
        if any(sample[f]<0 for f in fields if f!='other_pss_residual_kib'): raise ValueError('Negative memory category')
        residual=sample['pss_kib']-sample['pss_anon_kib']-sample['pss_file_kib']
        if residual < -4:
            raise ValueError('Category sum exceeds total beyond rounding')
        sample['other_pss_residual_kib']=residual
        key='/'.join((row['role'],row['implementation'],row['phase']))
        for field in fields: groups[key][field].append(sample[field])
    output={}
    for key,metrics in groups.items():
        output[key]={}
        for field,values in metrics.items():
            if len(values)!=6: raise ValueError('Expected six independent samples per category')
            output[key][field]=dict(n=6,median=statistics.median(values),minimum=min(values),maximum=max(values))
    return dict(trials=validation['trials'],failed_cases=[],statistic='final window sample per trial',groups=output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('events')
    print(json.dumps(category_summary(parser.parse_args().events),indent=2))
