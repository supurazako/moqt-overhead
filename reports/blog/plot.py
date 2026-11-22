"""Generate publication figures from the validated summaries (matplotlib 3.10.7)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'figures'
OUT.mkdir(exist_ok=True)
new = json.loads((ROOT/'experiments/records/2026-11-22-resource-summary.json').read_text())
old = json.loads((ROOT/'experiments/records/2026-11-20-idle-follow-up/summary.json').read_text())
relays = ['aiomoqt', 'imquic', 'moqtail']
colors = ['#2563eb', '#d97706', '#059669']
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none', 'savefig.dpi': 180})


def finish(fig, name):
    fig.tight_layout()
    fig.savefig(OUT/(name+'.svg'))
    fig.savefig(OUT/(name+'.png'))
    plt.close(fig)


fig, ax = plt.subplots(figsize=(7, 3.5))
for i, relay in enumerate(relays):
    row = old[relay]['cpu_pss_kib_delta']
    value = row['median']/1024
    ax.barh(i, value, color=colors[i])
    ax.errorbar(value, i, xerr=[[value-row['low']/1024], [row['high']/1024-value]],
                fmt='none', color='#111827', capsize=4)
    ax.text(value+.15, i, f'{value:.2f}', va='center')
ax.set_yticks(range(3), relays)
ax.invert_yaxis()
ax.set_xlim(0, 8.3)
ax.set_xlabel('Relay minus matched QUIC listener PSS (MiB)')
ax.set_title('No clients: implementation increment, not total memory')
fig.text(.02, .01, 'Six paired blocks; order-statistic intervals (nominal 96.9%).', fontsize=8)
fig.subplots_adjust(bottom=.25)
finish(fig, 'idle-increment')

for metric, label, filename in [
    ('pss_max_sampled_kib', 'Sampled maximum PSS (MiB)', 'active-role-memory'),
    ('post5_cpu_ms_per_s', 'Scheduled CPU after 5 s (ms/s)', 'active-role-cpu')]:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, tracks in zip(axes, [1, 4]):
        for i, relay in enumerate(relays):
            for j, role in enumerate(['publisher','relay','subscriber']):
                row = new['groups'][f'active/{tracks}/{relay}/{role}'][metric]
                divisor = 1024 if metric.startswith('pss') else 1
                median = row['median']/divisor
                low, high = [v/divisor for v in row['ci95']]
                x = j+(i-1)*.24
                ax.bar(x, median, width=.22, color=colors[i], label=relay if j==0 else None)
                ax.errorbar(x, median, yerr=[[median-low],[high-median]], color='#111827', fmt='none', capsize=2)
        ax.set_xticks(range(3), ['Publisher','Relay','Subscriber'])
        ax.set_title(f'{tracks} active track'+('s' if tracks>1 else ''))
    axes[0].set_ylabel(label)
    axes[1].legend(fontsize=8)
    fig.suptitle('Common aiomoqt endpoints; only Relay implementation varies')
    fig.text(.02, .01, 'Six blocks; exploratory 95% block-bootstrap intervals. 30 s synthetic transfer.', fontsize=8)
    fig.subplots_adjust(bottom=.20)
    finish(fig, filename)

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, metric, label in zip(axes, ['pss_end_kib','rss_end_kib'], ['PSS','RSS']):
    for i, relay in enumerate(relays):
        values=[]
        for extra in range(4):
            row = new['groups'][f'idle/{extra}/{relay}/relay'][metric]
            values.append(row['median']/1024)
        ax.plot(range(4), values, marker='o', color=colors[i], label=relay)
    ax.set_xticks(range(4))
    ax.set_xlabel('Additional SETUP-only connections')
    ax.set_ylabel(f'Relay {label} at idle-window end (MiB)')
axes[1].legend()
fig.suptitle('One subscribed track; two base connections')
fig.text(.02,.01,'PSS sharing changes when more endpoint processes are added. Medians of six blocks.',fontsize=8)
finish(fig, 'extra-connections')

raw = [json.loads(line) for line in (ROOT/'experiments/records/2026-11-22-active-resources.jsonl').read_text().splitlines()]
import statistics
fig, axes = plt.subplots(1, 3, figsize=(11, 3.7), sharex=True)
for ax, role in zip(axes, ['publisher','relay','subscriber']):
    for i, relay in enumerate(relays):
        trials = [r['series'] for r in raw if r['event']=='resource'
                  and r['level']==4 and r['relay']==relay and r['role']==role]
        times = list(range(30))
        medians = [statistics.median(min(series, key=lambda s:abs(s['elapsed_ns']/1e9-t))['pss_kib']/1024
                                    for series in trials) for t in times]
        ax.plot(times, medians, color=colors[i], label=relay)
    ax.set_title(role.capitalize())
    ax.set_xlabel('Seconds after transfer command')
    ax.set_ylabel('PSS (MiB)')
axes[-1].legend(fontsize=8)
fig.suptitle('Four tracks: memory did not reach a plateau in this window')
fig.text(.02,.01,'Median of six trials; nearest observed sample at each second. Common aiomoqt endpoints.',fontsize=8)
finish(fig, 'active-memory-over-time')
