"""Plot independently measured Pub/Sub implementation footprints."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
data=json.loads((ROOT/'experiments/records/2026-11-22-endpoint-summary.json').read_text())
out=ROOT/'reports/blog/figures';out.mkdir(exist_ok=True)
names=['imquic','moqtail','aiomoqt'];colors=['#d97706','#059669','#2563eb']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(9,3.7),sharey=True)
for ax,role in zip(axes,['publisher','subscriber']):
    for i,name in enumerate(names):
        row=data['groups'][f'{role}/{name}/transfer']['pss_max_kib']
        value=row['median']/1024
        ax.bar(i,value,color=colors[i])
        ax.errorbar(i,value,yerr=[[value-row['minimum']/1024],[row['maximum']/1024-value]],fmt='none',color='#111827',capsize=4)
        ax.text(i,value+.5,f'{value:.2f}',ha='center')
    ax.set_xticks(range(3),names)
    ax.set_title(role.capitalize())
axes[0].set_ylabel('Sampled maximum process PSS (MiB)')
fig.suptitle('Small-payload endpoints; common external relay and Python counterpart')
fig.text(.02,.01,'Six independent trials per cell; bars: median, whiskers: observed range. 64 B, 10 Objects/s, verified TLS.',fontsize=8)
fig.tight_layout(rect=(0,.05,1,1))
for suffix in ('png','svg'): fig.savefig(out/f'endpoint-implementation-memory.{suffix}',dpi=180)
plt.close(fig)
