"""Validate the archived experiment and optionally replay every saved clinic day."""
import argparse
import gzip
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from model import Clinic, Config, PatientInput, POLICIES, generate_inputs, inputs_hash


def close(actual, expected):
    if isinstance(actual, (int, float)):
        return ((math.isnan(actual) and math.isnan(expected)) or
                math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-9))
    return actual == expected


def validate(root, replay_all=False):
    started = time.perf_counter()
    source = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text())
    for name, key in (("model.py", "model_sha256"), ("PROTOCOL.md", "protocol_sha256")):
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == manifest[key], name
    analysis = json.loads((root / "analysis_manifest.json").read_text())
    assert hashlib.sha256((source / "analyze.py").read_bytes()).hexdigest() == analysis["script_sha256"]
    assert hashlib.sha256((root / "replication_results.csv").read_bytes()).hexdigest() == analysis["replication_csv_sha256"]
    d = pd.read_csv(root / "daily_results.csv")
    keys = ["demand", "kits", "policy", "s", "r", "replication"]
    assert len(d) == manifest["runs"] == 72000
    assert not d.duplicated(["replication", "day", "demand", "kits", "policy"]).any()
    assert d.groupby(["replication", "day", "demand"]).size().eq(12).all()
    for field in ("input_hash", "attended", "completed", "scheduled"):
        assert d.groupby(["replication", "day", "demand"])[field].nunique().eq(1).all(), field
    assert d.completed.eq(d.attended).all()
    assert d.completed_by_close.le(d.completed).all()
    assert d.max_bypasses.between(0, 2).all()
    assert d.filter(regex="^util_").ge(0).all().all()
    assert d.filter(regex="^util_").le(1 + 1e-12).all().all()
    np.testing.assert_allclose(d.mean_wait, d.registration_elapsed + d.post_registration_wait,
                               rtol=1e-11, atol=1e-9)
    metrics = [c for c in d.select_dtypes("number") if c not in keys + ["day"]]
    rebuilt = d.groupby(keys)[metrics].mean().sort_index()
    saved = pd.read_csv(root / "replication_results.csv").set_index(keys).sort_index()
    pd.testing.assert_frame_equal(rebuilt, saved, check_exact=False, rtol=1e-11, atol=1e-9)
    assert len(saved) == 2400
    summary = pd.read_csv(root / "summary.csv")
    effects = pd.read_csv(root / "paired_effects.csv")
    rep = saved.reset_index()
    estimate_checks = 0

    def check_estimate(values, row):
        nonlocal estimate_checks
        values = np.asarray(values, dtype=float)
        assert len(values) == 50 and np.isfinite(values).all()
        mean, sd = np.mean(values), np.std(values, ddof=1)
        half = 2.009575 * sd / math.sqrt(50)
        for field, value in dict(n=50, mean=mean, sd=sd, ci_low=mean-half, ci_high=mean+half).items():
            assert close(float(value), row[field]), (field, value, row[field])
        estimate_checks += 1

    for row in summary.to_dict("records"):
        mask = (rep.demand.eq(row["demand"]) & rep.kits.eq(row["kits"]) & rep.policy.eq(row["policy"]))
        check_estimate(rep.loc[mask, row["metric"]], row)
    for row in effects.to_dict("records"):
        subset = rep[rep.demand.eq(row["demand"]) & rep.kits.eq(row["kits"])]
        p = subset.pivot(index="replication", columns="policy", values=row["metric"])
        c = row["contrast"]
        if c == "S_main":
            values = (p.S1R0 + p.S1R1 - p.S0R0 - p.S0R1) / 2
        elif c == "R_main":
            values = (p.S0R1 + p.S1R1 - p.S0R0 - p.S1R0) / 2
        elif c == "SxR":
            values = p.S1R1 - p.S1R0 - p.S0R1 + p.S0R0
        else:
            left, right = c.split("-")
            values = p[left] - p[right]
        check_estimate(values, row)

    indexed = d.set_index(["replication", "day", "demand", "kits", "policy"])
    cohorts = replays = trace_checks = 0
    with gzip.open(root / "patient_inputs.jsonl.gz", "rt") as stream:
        for line in stream:
            item = json.loads(line)
            cohort = [PatientInput(**p) for p in item["patients"]]
            block, day, demand = item["replication"], item["day"], item["demand"]
            regenerated = generate_inputs(manifest["seed"], block, day, round(28*demand))
            assert cohort == regenerated
            digest = inputs_hash(cohort)
            for kits in (1, 2, 4):
                for s, r in POLICIES:
                    policy = f"S{s}R{r}"
                    archived = indexed.loc[(block, day, demand, kits, policy)]
                    assert archived.input_hash == digest
                    trace = block == 1 and day == 1 and demand == 1 and kits == 2
                    if replay_all or trace:
                        clinic = Clinic(cohort, s, r, Config(kits_per_kind=kits), trace=trace)
                        result = clinic.run()
                        for field, value in result.items():
                            expected = policy if field == "policy" else archived[field]
                            assert close(value, expected), (block, day, demand, kits, policy, field)
                        replays += 1
                        if trace:
                            example = json.loads((root / f"example_{policy}.json").read_text())
                            assert example == dict(patients=clinic.rows, events=clinic.events)
                            trace_checks += 1
            cohorts += 1
            if replay_all and cohorts % 1000 == 0:
                print(f"Replayed {replays:,}/72,000 clinic days", flush=True)
    assert cohorts == 6000
    assert trace_checks == 4
    report = dict(status="passed", python=platform.python_version(),
                  input_cohorts_regenerated=cohorts, archived_day_runs=len(d),
                  replication_rows=len(saved), statistical_estimates_checked=estimate_checks,
                  full_clinic_day_replays=replays, example_traces_reproduced=trace_checks,
                  numeric_absolute_tolerance=1e-9, numeric_relative_tolerance=1e-11,
                  elapsed_seconds=round(time.perf_counter()-started, 2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--replay-all", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(args.results, args.replay_all)
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload)
