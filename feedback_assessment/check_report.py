"""Reconstruct supplementary block summaries and check manuscript numbers."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
daily = pd.read_csv(HERE/'diagnostic_days.csv')
rep = pd.read_csv(HERE/'diagnostic_replications.csv')
summary = pd.read_csv(HERE/'diagnostic_summary.csv')
keys = ['demand','case','replication']
metrics = [c for c in rep.columns if c not in keys]
rebuilt = daily.groupby(keys)[metrics].mean().sort_index()
np.testing.assert_allclose(rebuilt.values, rep.set_index(keys).sort_index()[metrics].values,
                           rtol=1e-10, atol=1e-9, equal_nan=True)
for r in summary.itertuples():
    v = rep[(rep.demand==r.demand)&(rep.case==r.case)][r.metric]
    assert v.notna().sum()==50
    m, sd = v.mean(), v.std()
    np.testing.assert_allclose([m,sd,m-2.009575*sd/50**.5,m+2.009575*sd/50**.5],
                               [r.mean,r.sd,r.ci_low,r.ci_high], rtol=1e-10, atol=1e-9)
checks = [('K2_B0','workload_dentist_minutes',974.65),('K2_B0','workload_sterilizer_minutes',615.50),
          ('K50_FCFS','mean_wait',50.36),('K50_FCFS','overtime',93.55),
          ('K2_B0','head_kit_blocked_ready_alternative',137.86),('K2_B2','head_kit_blocked_ready_alternative',37.59),
          ('K2_B1','mean_wait',103.70),('K2_unlimited','mean_wait',85.28),
          ('K2_B0','maximum_wait',266.77),('K2_B1','maximum_wait',239.54),
          ('K2_B2','maximum_wait',232.24),('K2_unlimited','maximum_wait',235.44)]
for case,metric,expected in checks:
    value = summary[(summary.demand==1)&(summary.case==case)&(summary.metric==metric)]['mean'].item()
    assert round(value,2)==expected, (case,metric,value)
manifest=json.loads((HERE/'manifest.json').read_text())
assert hashlib.sha256((HERE.parent/'model.py').read_bytes()).hexdigest()==manifest['model_sha256']
assert hashlib.sha256((HERE.parent/'PROTOCOL.md').read_bytes()).hexdigest()==manifest['primary_protocol_sha256']
out=dict(status='passed', diagnostic_runs=len(daily), summary_rows_checked=len(summary),
         rounded_manuscript_values_checked=len(checks), primary_model_and_protocol_unchanged=True)
(HERE.parent/'verification/supplementary_checks.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
