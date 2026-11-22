"""Measure file-backed and anonymous PSS with optional balanced repetitions."""
import argparse
import asyncio
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('endpoint_measurement',Path(__file__).with_name('measure.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
original=m.snapshot


def snapshot(pid):
    memory,cpu,state=original(pid)
    for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
        if line.startswith(('Pss:', 'Rss:', 'Pss_Anon:','Pss_File:','Private_Clean:','Private_Dirty:')):
            key,value,_=line.split()
            memory[key[:-1].lower()+'_kib']=int(value)
    return memory,cpu,state


if __name__=='__main__':
    m.snapshot=snapshot
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--balanced',action='store_true')
    options=parser.parse_args()
    args=argparse.Namespace(balanced=options.balanced,roles=['publisher','subscriber'],port=45458,negative_trust=False)
    asyncio.run(m.run(args))
