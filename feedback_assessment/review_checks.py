"""Post-review diagnostics; does not alter the frozen model or primary results."""
import bisect
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model import Clinic, Config, PatientInput, KINDS

OUT = Path(__file__).resolve().parent
CAP = dict(dentist=2, assistant=3, chair=4, frontdesk=1, sterilizer=1)
CASES = [('K2_B0', 2, 0, 0), ('K2_B1', 2, 1, 1),
         ('K2_B2', 2, 1, 2), ('K2_unlimited', 2, 1, 10000),
         ('K50_FCFS', 50, 0, 0), ('K50_B2', 50, 1, 2)]


def stats(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    assert len(v) == 50
    mean, sd = float(v.mean()), float(v.std(ddof=1))
    half = 2.009575 * sd / math.sqrt(50)
    return dict(mean=mean, sd=sd, ci_low=mean-half, ci_high=mean+half)


def mechanism(clinic):
    points = {0., 480.}
    for row in clinic.rows:
        points.update(row[k] for k in ('registered', 'start'))
    for _, a, b in clinic.occupancy:
        points.update((a, b))
    for history in clinic.kit_history.values():
        points.update(t for t, _ in history)
    points = sorted(t for t in points if 0 <= t <= 480)
    records = []
    for a, b in zip(points, points[1:]):
        waiting = sorted((row for row in clinic.rows if row['registered'] <= a < row['start']),
                         key=lambda row: (row['registered'], row['pid']))
        free = {k: c-sum(name == k and start <= a < end for name, start, end in clinic.occupancy)
                for k, c in CAP.items()}
        clean = {}
        for kind, h in clinic.kit_history.items():
            ix = bisect.bisect_right([t for t, _ in h], a)-1
            clean[kind] = h[ix][1]
        blocked = bool(waiting and clean[waiting[0]['kind']] == 0)
        ready_others = any(clean[row['kind']] > 0 for row in waiting[1:])
        all_other_resources = all(free[k] > 0 for k in ('dentist','assistant','chair'))
        records.append(dict(start=a, end=b, head_pid=waiting[0]['pid'] if waiting else -1,
                            head_kit_blocked=blocked, dentist_idle=free['dentist'] > 0,
                            other_resources_ready=all_other_resources,
                            later_patient_kit_ready=ready_others))
    return records


def run():
    archived = pd.read_csv(ROOT/'results/daily_results.csv').set_index(
        ['replication','day','demand','kits','policy'])
    rows, segments = [], []
    original_matches = abundant_matches = 0
    with gzip.open(ROOT/'results/patient_inputs.jsonl.gz', 'rt') as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            patients = [PatientInput(**p) for p in item['patients']]
            clinic_cases = {}
            for label, kits, r, bound in CASES:
                c = Clinic(patients, 0, r, Config(kits_per_kind=kits, max_bypasses=bound))
                result = c.run()
                rec = dict(result, case=label, replication=item['replication'],
                           day=item['day'], demand=item['demand'], kits=kits)
                clinic_cases[label] = c
                if label in ('K2_B0','K2_B2'):
                    expected = archived.loc[(item['replication'],item['day'],item['demand'],kits,f'S0R{r}')]
                    for key, val in result.items():
                        if key == 'policy':
                            continue
                        if isinstance(val, (int,float)):
                            assert (pd.isna(val) and pd.isna(expected[key])) or math.isclose(val, expected[key], rel_tol=1e-11, abs_tol=1e-9), key
                        else:
                            assert val == expected[key], key
                    original_matches += 1
                waits = {p['pid']: p['start']-p['arrival'] for p in c.rows}
                baseline = {p['pid']:p['start']-p['arrival'] for p in clinic_cases['K2_B0'].rows}
                rec['maximum_wait'] = max(waits.values(), default=0.)
                differences = [waits[pid]-baseline[pid] for pid in waits]
                rec['fraction_patients_worse_than_fifo'] = np.mean([d > 1e-9 for d in differences])
                rec['largest_patient_wait_increase'] = max(differences, default=0.)
                twice = [p['pid'] for p in c.rows if p['bypasses'] == 2] if label == 'K2_B2' else []
                rec['twice_count'] = len(twice)
                rec['twice_wait_sum'] = sum(waits[pid] for pid in twice)
                rec['twice_fifo_wait_sum'] = sum(baseline[pid] for pid in twice)
                rec['twice_worse_count'] = sum(waits[pid]-baseline[pid] > 1e-9 for pid in twice)
                batches = len(set(p['cycle_start'] for p in c.rows))
                rec['batch_count'] = batches
                rec['batch_fill_fraction'] = len(c.rows)/(4*batches) if batches else float('nan')
                rec['final_event_time'] = c.env.now
                for resource, capacity in CAP.items():
                    busy = sum(b-a for k,a,b in c.occupancy if k == resource)
                    rec[f'workload_{resource}_minutes'] = busy
                    rec[f'workload_{resource}_ratio'] = busy/(480*capacity)
                    rec[f'whole_run_util_{resource}'] = busy/(c.env.now*capacity)
                for kind in KINDS:
                    subset = [p for p in c.rows if p['kind'] == kind]
                    rec[f'kit_uses_per_stock_{kind}'] = len(subset)/kits
                    rec[f'kit_circulation_{kind}'] = np.mean([p['kit_released']-p['start'] for p in subset]) if subset else float('nan')
                if item['demand'] == 1 and label in ('K2_B0','K2_B2'):
                    history = mechanism(c)
                    rec['head_kit_blocked_dentist_idle'] = sum(h['end']-h['start'] for h in history if h['head_kit_blocked'] and h['dentist_idle'])
                    rec['head_kit_blocked_other_resources_ready'] = sum(h['end']-h['start'] for h in history if h['head_kit_blocked'] and h['other_resources_ready'])
                    rec['head_kit_blocked_ready_alternative'] = sum(h['end']-h['start'] for h in history if h['head_kit_blocked'] and h['other_resources_ready'] and h['later_patient_kit_ready'])
                    if item['replication'] == item['day'] == 1:
                        segments.extend(dict(h, case=label) for h in history)
                rows.append(rec)
            assert clinic_cases['K50_FCFS'].rows == clinic_cases['K50_B2'].rows
            abundant_matches += 1
            if number % 1000 == 0:
                print(f'Checked {number:,}/6,000 cohorts ({number*6:,} diagnostic days)',flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(OUT/'diagnostic_days.csv', index=False)
    pd.DataFrame(segments).to_csv(OUT/'example_mechanism_intervals.csv',index=False)
    keys=['demand','case','replication']
    metrics=[c for c in d.select_dtypes('number') if c not in keys+['day','kits','s','r']]
    rep=d.groupby(keys)[metrics].mean().reset_index()
    rep.to_csv(OUT/'diagnostic_replications.csv',index=False)
    sums=[]
    for (demand,label), g in rep.groupby(['demand','case']):
        for metric in metrics:
            if g[metric].notna().sum() == 50:
                sums.append(dict(demand=demand,case=label,metric=metric,**stats(g[metric])))
    pd.DataFrame(sums).to_csv(OUT/'diagnostic_summary.csv',index=False)
    effects=[]
    for demand,g in rep.groupby('demand'):
        for metric in ('mean_wait','maximum_wait','overtime'):
            p=g.pivot(index='replication',columns='case',values=metric)
            for label, *_ in CASES[1:]:
                effects.append(dict(demand=demand,case=label,metric=metric,**stats(p[label]-p.K2_B0)))
    pd.DataFrame(effects).to_csv(OUT/'paired_differences.csv',index=False)
    twice=[]
    for demand,g in d[d.case.eq('K2_B2')].groupby('demand'):
        p=g.groupby('replication')[['twice_count','twice_wait_sum','twice_fifo_wait_sum','twice_worse_count']].sum()
        for name,values in dict(mean_wait=p.twice_wait_sum/p.twice_count,
                                fifo_mean_wait=p.twice_fifo_wait_sum/p.twice_count,
                                paired_wait_change=(p.twice_wait_sum-p.twice_fifo_wait_sum)/p.twice_count,
                                fraction_worse=p.twice_worse_count/p.twice_count).items():
            twice.append(dict(demand=demand,metric=name,**stats(values)))
    pd.DataFrame(twice).to_csv(OUT/'twice_bypassed_subgroup.csv',index=False)
    manifest=dict(status='completed',design='post-review exploratory diagnostics; uniform spacing only',
                  clinic_day_runs=len(d),original_case_matches=original_matches,
                  abundant_kit_paired_patient_records_identical=abundant_matches,
                  model_sha256=hashlib.sha256((ROOT/'model.py').read_bytes()).hexdigest(),
                  primary_protocol_sha256=hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest(),
                  diagnostic_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  diagnostic_scope_sha256=hashlib.sha256((OUT/'SCOPE.md').read_bytes()).hexdigest())
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    run()
