"""Generate the endpoint pilot's English report from validated observations."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RECORDS=ROOT/'experiments/records'
data=json.loads((RECORDS/'2026-11-22-endpoint-summary.json').read_text())
lines=['# Small-payload Publisher/Subscriber implementation pilot\n\n',
'All 36 balanced trials completed with 50 correct Objects each. The measured role changes between imquic, MOQtail and aiomoqt; the external aiomoqt Relay and opposite aiomoqt endpoint remain fixed. This measures existing Linux implementations, not firmware or an intrinsic MoQT memory floor.\n\n',
'## Conditions\n\n',
'- IETF MoQT draft-22 over raw QUIC; one track; 50 Objects of 64 bytes at 100 ms intervals.\n',
'- Verified TLS with a dedicated CA and server leaf; no global trust-store changes. All three Publisher negative-trust checks rejected an unrelated CA.\n',
'- Six fresh-process trials per implementation/role, all six balanced orders; 2-second connected-idle and approximately 5-second transfer windows.\n',
'- Memory maxima are sampled every 100 ms. CPU is process CPU time per actual observed wall second, including exited threads. Startup peaks and transport-only endpoint controls are not measured.\n',
'- [Admission and failed attempts](2026-11-22-endpoint-admission.md), [conditions and procedure](../endpoints/README.md), [build commands](../endpoints/BUILD.md).\n\n']
for role in ('publisher','subscriber'):
    lines+=['## '+role.capitalize()+'\n\n',
    'PSS values are MiB. Transfer PSS is the median of each trial\'s sampled maximum; brackets show observed min–max across six independent trials, not a confidence interval. CPU is ms/s (10 ms/s is about 1% of one CPU core).\n\n',
    '| Implementation | Idle PSS | Transfer PSS [range] | Transfer CPU [range] | Threads |\n',
    '| --- | ---: | ---: | ---: | ---: |\n']
    for name in ('imquic','moqtail','aiomoqt'):
        idle=data['groups'][f'{role}/{name}/connected_idle']
        group=data['groups'][f'{role}/{name}/transfer'];m=group['pss_max_kib'];c=group['cpu_ms_per_s']
        lines.append(f"| {name} | {idle['pss_end_kib']['median']/1024:.2f} | {m['median']/1024:.2f} [{m['minimum']/1024:.2f}, {m['maximum']/1024:.2f}] | {c['median']:.2f} [{c['minimum']:.2f}, {c['maximum']:.2f}] | {group['thread_count']['median']:.0f} |\n")
    lines.append('\n')
categories=json.loads((RECORDS/'2026-11-22-endpoint-memory-categories-balanced-summary.json').read_text())
assert categories['trials']==36 and not categories['failed_cases']
lines+=['## Memory categories: six trials per implementation and role\n\n',
'An additional balanced series measured anonymous and file-backed PSS using Linux smaps_rollup. Values are medians of each trial\'s final transfer-window sample; brackets show the observed range across six independent trials. All 36 transfers verified 50 correct Objects.\n\n',
'| Role | Implementation | Anonymous PSS (MiB) | File-backed PSS (MiB) |\n',
'| --- | --- | ---: | ---: |\n']
for role in ('publisher','subscriber'):
    for name in ('imquic','moqtail','aiomoqt'):
        metrics=categories['groups'][f'{role}/{name}/transfer']
        values=[]
        for field in ('pss_anon_kib','pss_file_kib'):
            row=metrics[field]
            values.append(f"{row['median']/1024:.2f} [{row['minimum']/1024:.2f}, {row['maximum']/1024:.2f}]")
        lines.append(f"| {role} | {name} | {' | '.join(values)} |\n")
lines+=['\n## Interpretation\n\n',
'- Existing C/Rust endpoints do run with substantially smaller total PSS than the Python reference in this small workload: imquic is approximately one-seventh and MOQtail roughly one-quarter of the Python footprint. These are implementation/configuration differences, not isolated language effects.\n',
'- Total PSS and anonymous PSS answer different questions. The repeated category series has lower anonymous PSS for MOQtail than imquic despite the reverse total-PSS order. Anonymous PSS includes more than application heap, and file-backed code cannot simply be subtracted to derive MCU RAM requirements.\n',
'- CPU does not follow the memory ranking. imquic Subscriber uses more CPU during transfer than the Python reference in this pilot. The attribution is unresolved; source inspection found a 100 ms outer application sleep, which alone does not explain the difference. No pure protocol or MCU energy claim follows.\n',
'- Small payloads and short windows do not characterize media-rate buffers, handshake peaks, long-term retention or failure recovery. All role adapters use existing full libraries; this is not a minimal embedded port.\n',
'- No matched active QUIC-only endpoint control was measured, so these absolute values do not isolate MoQT overhead from QUIC/TLS, runtime and application logic.\n',
'- moxygen and libquicr were included in candidate inspection but do not have role-isolated draft-22 resource results in this pilot. Their absence is not a negative resource finding.\n\n',
'## Artifacts\n\n',
'- [Balanced events](2026-11-22-endpoint-resources.jsonl), [summary and paired differences](2026-11-22-endpoint-summary.json).\n',
'- [Balanced memory-category events](2026-11-22-endpoint-memory-categories-balanced.jsonl), [category summary](2026-11-22-endpoint-memory-categories-balanced-summary.json), [original one-run diagnostic](2026-11-22-endpoint-memory-categories.jsonl), [collector and binary hashes](2026-11-22-endpoint-provenance.json).\n',
'- [Figure](../../reports/blog/figures/endpoint-implementation-memory.png), [plot script](../endpoints/plot.py).\n']
target=RECORDS/'2026-11-22-endpoint-resources.md'
existing=target.read_text() if target.exists() else ''
validation='\n## Validation\n'+existing.split('\n## Validation\n',1)[1] if '\n## Validation\n' in existing else ''
target.write_text(''.join(lines)+validation)
