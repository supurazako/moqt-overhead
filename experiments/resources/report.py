"""Write the English measurement record from the validated resource summary."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
summary = json.loads((ROOT/'experiments/records/2026-11-22-resource-summary.json').read_text())
record = ROOT/'experiments/records/2026-11-22-resource-series.md'
lines = ['\n## Results\n\n',
 f"Validated {summary['trials']} scheduled cases. Cases with failure events: {len(summary['failures'])}.\n\n",
 '### Active transfer by role\n\n',
 'PSS values are medians of sampled maxima (MiB). CPU values are medians of scheduled runtime after 5 seconds (ms/s). These are total process resources, not matched-control increments.\n\n']
for tracks in (1,4):
    lines.append(f'- {tracks} track(s):\n')
    for relay in ('aiomoqt','imquic','moqtail'):
        values=[]
        for role in ('publisher','relay','subscriber'):
            group=summary['groups'][f'active/{tracks}/{relay}/{role}']
            pss=group['pss_max_sampled_kib']['median']/1024
            cpu=group.get('post5_cpu_ms_per_s',{}).get('median')
            values.append(f'{role}: {pss:.2f} MiB / {cpu:.2f} ms/s' if cpu is not None else f'{role}: {pss:.2f} MiB / CPU unresolved')
        lines.append(f"  - {relay}: {'; '.join(values)}.\n")
lines += ['\n### Incremental relay resources\n\n',
 'Each value is a median within-block difference; brackets show exploratory 95% block-bootstrap intervals. Six blocks are a small sample.\n\n']
for mode, baseline, levels in [('idle',0,(1,2,3)),('active',1,(4,))]:
    for level in levels:
        lines.append(f'- {mode}, level {level} minus {baseline}:\n')
        for relay in ('aiomoqt','imquic','moqtail'):
            group=summary['increments'][f'{mode}/{level}-{baseline}/{relay}/relay']
            field='pss_end_kib' if mode=='idle' else 'pss_max_sampled_kib'
            row=group[field]
            low,high=row['ci95']
            lines.append(f"  - {relay}: {row['median']:.1f} [{low:.1f}, {high:.1f}] KiB.\n")
lines += ['\n### Data and limitations\n\n',
 '- [Idle observations](2026-11-22-idle-resources.jsonl), [active observations](2026-11-22-active-resources.jsonl), [validated summary](2026-11-22-resource-summary.json).\n',
 '- The active stream lifecycle differs from the finite-transfer pilot: all data are verified before FIN/PUBLISH_DONE. This does not demonstrate correct handling of the earlier terminal-message race.\n',
 '- Traffic covers setup and teardown as well as the resource window. Relay transmit/receive bytes sum link counters in the reversed endpoint direction.\n',
 '- [Memory growth investigation](2026-11-22-memory-growth.md): the Relay and Subscriber did not establish a memory plateau. Post-five-second averages do not assert equilibrium.\n',
 '- More active tracks also mean more aggregate traffic. Extra idle processes alter PSS sharing. No MCU feasibility, intrinsic protocol minimum, or constant per-client slope is inferred.\n',
 '- The six-block intervals do not guarantee the prespecified resolution targets. Inspect widths; small differences and long-term stability can remain unresolved.\n',
 '- PSS maxima are sampled every 250 ms and can miss shorter peaks. No allocation-level peak, application startup peak, kernel socket memory, or energy measurement is claimed.\n']
text=record.read_text().split('\n## Results\n')[0]+''.join(lines)
record.write_text(text)
print(record)
