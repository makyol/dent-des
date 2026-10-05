"""DentDES: matched-input terminating dental-clinic simulation.

All operating distributions are synthetic assumptions. See PROTOCOL.md.
No policy changes physical durations or attendance. No clinical advice.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import platform
import random
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import simpy

KINDS = ("routine", "restorative", "impression", "complex")
MULTIPLIERS = (0.82, 1.10, 1.00, 1.45)
POLICIES = ((0, 0), (1, 0), (0, 1), (1, 1))
EVALUATION_SEED = 2026090502
PILOT_SEED = 2026090501


@dataclass(frozen=True)
class Config:
    chairs: int = 4
    dentists: int = 2
    assistants: int = 3
    kits_per_kind: int = 2
    batch_capacity: int = 4
    cycle_minutes: float = 29.0
    kit_preparation: float = 8.0
    closing: float = 480.0
    max_bypasses: int = 2

    def __post_init__(self):
        if min(self.chairs, self.dentists, self.assistants,
               self.kits_per_kind, self.batch_capacity) < 1:
            raise ValueError("Resource capacities must be positive")
        if min(self.cycle_minutes, self.closing) <= 0 or self.kit_preparation < 0:
            raise ValueError("Invalid durations")
        if self.max_bypasses < 0:
            raise ValueError("Bypass bound must be nonnegative")


@dataclass(frozen=True)
class PatientInput:
    pid: int
    kind: str
    attends: bool
    arrival_offset: float
    treatment: float
    registration: float
    documentation: float
    checkout: float
    cleaning: float


@dataclass(frozen=True)
class BookingRequest:
    """The scheduler's entire view: no outcome, attendance or future timestamps."""
    pid: int
    kind: str


def input_seed(base: int, rep: int, day: int, n: int) -> int:
    payload = f"{base}:{rep}:{day}:{n}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def generate_inputs(base: int, rep: int, day: int, n: int) -> list[PatientInput]:
    rng = random.Random(input_seed(base, rep, day, n))
    patients = []
    for pid in range(n):
        kind = rng.choices(KINDS, (0.52, 0.28, 0.13, 0.07))[0]
        attends = rng.random() >= 0.13
        offset = max(-12., min(12., rng.gauss(0., 6.)))
        treatment = max(12., min(65., rng.gauss(30 * MULTIPLIERS[KINDS.index(kind)], 8.)))
        if rng.random() < 0.22:
            treatment += rng.expovariate(1 / 13.)
        patients.append(PatientInput(pid, kind, attends, offset, treatment,
                                     max(1., rng.gauss(3., .8)),
                                     max(3., rng.gauss(8., 1.8)),
                                     max(1., rng.gauss(3., .8)),
                                     max(4., rng.gauss(9., 1.5))))
    return patients


def make_schedule(requests: list[BookingRequest], duration_aware: bool) -> dict[int, float]:
    if not requests:
        return {}
    if len(requests) == 1:
        return {requests[0].pid: 15.}
    gaps = [30 * MULTIPLIERS[KINDS.index(p.kind)] + .22 * 13 + 8
            if duration_aware else 1. for p in requests[:-1]]
    total, cumulative = sum(gaps), 0.
    schedule = {}
    for i, p in enumerate(requests):
        schedule[p.pid] = 15 + 420 * cumulative / total
        if i < len(gaps):
            cumulative += gaps[i]
    schedule[requests[-1].pid] = 435.
    return schedule


def inputs_hash(inputs: list[PatientInput]) -> str:
    return hashlib.sha256(json.dumps([asdict(p) for p in inputs],
                                     sort_keys=True).encode()).hexdigest()


class Clinic:
    def __init__(self, inputs: list[PatientInput], s: int, r: int,
                 config: Config | None = None, trace: bool = False):
        self.inputs = inputs
        self.s, self.r = s, r
        self.cfg = config or Config()
        self.env = simpy.Environment()
        self.schedule = make_schedule([BookingRequest(p.pid, p.kind) for p in inputs], bool(s))
        self.frontdesk = simpy.Resource(self.env, 1)
        self.free = dict(chair=self.cfg.chairs, dentist=self.cfg.dentists,
                         assistant=self.cfg.assistants)
        self.clean = {k: self.cfg.kits_per_kind for k in KINDS}
        self.kit_history = {k: [(0., self.cfg.kits_per_kind)] for k in KINDS}
        self.waiting: list[dict] = []
        self.turnovers: list[dict] = []
        self.dirty: list[dict] = []
        self.sterilizing = False
        self.occupancy: list[tuple[str, float, float]] = []
        self.rows: list[dict[str, Any]] = []
        self.events: list[dict] = []
        self.trace = trace
        self.dispatches = 0
        self.bypass_events = 0

    def log(self, event: str, row: dict | None = None, **extra):
        if self.trace:
            self.events.append(dict(time=self.env.now, event=event,
                                    pid=row["pid"] if row else None, **extra))

    def register(self, p: PatientInput):
        arrival = self.schedule[p.pid] + p.arrival_offset
        yield self.env.timeout(arrival)
        row = dict(asdict(p), appointment=self.schedule[p.pid], arrival=self.env.now,
                   bypasses=0, instrument_unavailable_at_registration=self.clean[p.kind] == 0)
        self.rows.append(row)
        self.log("arrival", row)
        with self.frontdesk.request() as req:
            yield req
            start = self.env.now
            yield self.env.timeout(p.registration)
            self.occupancy.append(("frontdesk", start, self.env.now))
        row["registered"] = self.env.now
        self.waiting.append(row)
        self.waiting.sort(key=lambda x: (x["registered"], x["pid"]))
        self.log("registered", row)
        self.dispatch()

    def dispatch(self):
        # Resource mutations occur before scheduling processes: acquisition is atomic.
        while self.turnovers and self.free["assistant"]:
            row = self.turnovers.pop(0)
            self.free["assistant"] -= 1
            self.env.process(self.turnover(row))
        while self.waiting and all(self.free[k] > 0 for k in self.free):
            selected = 0
            if self.clean[self.waiting[0]["kind"]] == 0:
                if not self.r or self.waiting[0]["bypasses"] >= self.cfg.max_bypasses:
                    return
                selected = next((i for i, row in enumerate(self.waiting)
                                 if self.clean[row["kind"]] > 0), -1)
                if selected < 0:
                    return
                # Do not pass any earlier patient already at the bypass bound.
                if any(row["bypasses"] >= self.cfg.max_bypasses
                       for row in self.waiting[:selected]):
                    return
            for row in self.waiting[:selected]:
                row["bypasses"] += 1
                self.bypass_events += 1
            row = self.waiting.pop(selected)
            for resource in self.free:
                self.free[resource] -= 1
            self.clean[row["kind"]] -= 1
            self.kit_history[row["kind"]].append((self.env.now, self.clean[row["kind"]]))
            row["start"] = self.env.now
            self.dispatches += 1
            self.log("treatment_start", row, bypasses=row["bypasses"])
            self.env.process(self.treat(row))

    def treat(self, row: dict):
        yield self.env.timeout(row["treatment"] + row["documentation"])
        row["clinical_end"] = self.env.now
        for resource in ("dentist", "assistant"):
            self.occupancy.append((resource, row["start"], self.env.now))
            self.free[resource] += 1
        self.turnovers.append(row)
        self.env.process(self.checkout(row))
        self.dispatch()

    def checkout(self, row: dict):
        with self.frontdesk.request() as req:
            yield req
            start = self.env.now
            yield self.env.timeout(row["checkout"])
            self.occupancy.append(("frontdesk", start, self.env.now))
        row["discharge"] = self.env.now
        self.log("discharge", row)

    def turnover(self, row: dict):
        start = self.env.now
        row["cleaning_start"] = start
        yield self.env.timeout(row["cleaning"])
        self.free["chair"] += 1
        row["chair_released"] = self.env.now
        self.occupancy.append(("chair", row["start"], self.env.now))
        self.dispatch()
        yield self.env.timeout(self.cfg.kit_preparation)
        self.occupancy.append(("assistant", start, self.env.now))
        self.free["assistant"] += 1
        row["kit_ready_for_cycle"] = self.env.now
        self.dirty.append(row)
        if not self.sterilizing:
            self.sterilizing = True
            self.env.process(self.reprocess())
        self.dispatch()

    def reprocess(self):
        while self.dirty:
            batch = self.dirty[:self.cfg.batch_capacity]
            del self.dirty[:len(batch)]
            start = self.env.now
            for row in batch:
                row["cycle_start"] = start
            self.log("cycle_start", size=len(batch))
            yield self.env.timeout(self.cfg.cycle_minutes)
            self.occupancy.append(("sterilizer", start, self.env.now))
            for row in batch:
                self.clean[row["kind"]] += 1
                self.kit_history[row["kind"]].append((self.env.now, self.clean[row["kind"]]))
                row["kit_released"] = self.env.now
            self.dispatch()
        self.sterilizing = False

    def run(self) -> dict[str, Any]:
        for patient in self.inputs:
            if patient.attends:
                self.env.process(self.register(patient))
        self.env.run()  # Finite event set, including all checkout and reprocessing.
        self.verify_conservation()
        for row in self.rows:
            history = self.kit_history[row["kind"]] + [(self.env.now, 0)]
            row["kit_unavailable_wait"] = sum(
                max(0., min(right[0], row["start"])-max(left[0], row["registered"]))
                for left, right in zip(history, history[1:]) if left[1] == 0)
        return self.summary()

    def verify_conservation(self):
        attended = sum(p.attends for p in self.inputs)
        assert len(self.rows) == self.dispatches == attended
        assert all("discharge" in row and "kit_released" in row for row in self.rows)
        assert not self.waiting and not self.turnovers and not self.dirty and not self.sterilizing
        assert self.free == dict(chair=self.cfg.chairs, dentist=self.cfg.dentists,
                                 assistant=self.cfg.assistants)
        assert all(v == self.cfg.kits_per_kind for v in self.clean.values())
        assert all(row["bypasses"] <= self.cfg.max_bypasses for row in self.rows)
        for row in self.rows:
            assert row["arrival"] <= row["registered"] <= row["start"] <= row["clinical_end"]
            assert row["clinical_end"] <= row["chair_released"] <= row["kit_released"]
            assert row["clinical_end"] <= row["discharge"]
        capacities = dict(chair=self.cfg.chairs, dentist=self.cfg.dentists,
                          assistant=self.cfg.assistants, frontdesk=1, sterilizer=1)
        for resource, capacity in capacities.items():
            edges = []
            for key, start, end in self.occupancy:
                if key == resource and end > start:
                    edges.extend(((start, 1), (end, -1)))
            current = 0
            for _, delta in sorted(edges):
                current += delta
                assert 0 <= current <= capacity, (resource, current)
            assert current == 0

    def summary(self):
        def mean(values):
            return statistics.fmean(values) if values else float("nan")
        waits = [r["start"] - r["arrival"] for r in self.rows]
        out = dict(s=self.s, r=self.r, policy=f"S{self.s}R{self.r}",
                   scheduled=len(self.inputs), attended=len(self.rows),
                   completed=len(self.rows), input_hash=inputs_hash(self.inputs),
                   mean_wait=mean(waits), p90_wait=float(np.quantile(waits, .9)) if waits else float("nan"),
                   post_registration_wait=mean([r["start"]-r["registered"] for r in self.rows]),
                   registration_elapsed=mean([r["registered"]-r["arrival"] for r in self.rows]),
                   mean_los=mean([r["discharge"]-r["arrival"] for r in self.rows]),
                   completed_by_close=sum(r["discharge"] <= self.cfg.closing for r in self.rows),
                   overtime=max(0., max([r["discharge"] for r in self.rows], default=0.)-self.cfg.closing),
                   reprocessing_overtime=max(0., self.env.now-self.cfg.closing),
                   bypass_events=self.bypass_events,
                   max_bypasses=max([r["bypasses"] for r in self.rows], default=0),
                   kit_unavailable_wait=mean([r["kit_unavailable_wait"] for r in self.rows]),
                   mean_cycle_queue=mean([r["cycle_start"]-r["kit_ready_for_cycle"] for r in self.rows]))
        for kind in KINDS:
            subset = [r for r in self.rows if r["kind"] == kind]
            out[f"wait_{kind}"] = mean([r["start"]-r["arrival"] for r in subset])
            out[f"count_{kind}"] = len(subset)
        capacities = dict(chair=self.cfg.chairs, dentist=self.cfg.dentists,
                          assistant=self.cfg.assistants, frontdesk=1, sterilizer=1)
        for resource, capacity in capacities.items():
            intervals = [(a,b) for k,a,b in self.occupancy if k == resource]
            out[f"util_{resource}"] = sum(max(0., min(b,self.cfg.closing)-a)
                                          for a,b in intervals if a < self.cfg.closing) / (capacity*self.cfg.closing)
            out[f"overtime_{resource}_minutes"] = sum(max(0., b-max(a,self.cfg.closing)) for a,b in intervals)
        return out


def run_experiment(out_dir: Path, replications: int, days: int, seed: int):
    import pandas as pd
    out_dir.mkdir(parents=True, exist_ok=True)
    demands = (0.8, 1., 1.2, 1.5)
    rows = []
    with gzip.open(out_dir / "patient_inputs.jsonl.gz", "wt") as input_file:
        for rep in range(1, replications + 1):
            for day in range(1, days + 1):
                for demand in demands:
                    n = round(28 * demand)
                    inputs = generate_inputs(seed, rep, day, n)
                    input_file.write(json.dumps(dict(replication=rep, day=day, demand=demand,
                                                    patients=[asdict(p) for p in inputs])) + "\n")
                    for kits in (1, 2, 4):
                        for s, r in POLICIES:
                            clinic = Clinic(inputs, s, r, Config(kits_per_kind=kits),
                                            trace=(rep==1 and day==1 and demand==1 and kits==2))
                            rec = clinic.run()
                            rec.update(replication=rep, day=day, demand=demand, kits=kits)
                            rows.append(rec)
                            if clinic.trace:
                                (out_dir / f"example_{rec['policy']}.json").write_text(json.dumps(
                                    dict(patients=clinic.rows, events=clinic.events), indent=2))
            print(f"Completed replication {rep}/{replications}", flush=True)
    daily = pd.DataFrame(rows)
    daily.to_csv(out_dir / "daily_results.csv", index=False)
    group = ["demand", "kits", "policy", "s", "r", "replication"]
    metrics = [c for c in daily.select_dtypes(include="number").columns if c not in group + ["day"]]
    daily.groupby(group)[metrics].mean().reset_index().to_csv(out_dir / "replication_results.csv", index=False)
    manifest = dict(seed=seed, replications=replications, days=days,
                    conditions=len(demands)*3, runs=len(rows),
                    python=platform.python_version(), simpy=simpy.__version__, numpy=np.__version__,
                    model_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    protocol_sha256=hashlib.sha256(Path(__file__).with_name("PROTOCOL.md").read_bytes()).hexdigest(),
                    config=asdict(Config()), case="synthetic terminating clinic days")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--replications", type=int, default=50)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=EVALUATION_SEED)
    args = parser.parse_args()
    run_experiment(args.out, args.replications, args.days, args.seed)
