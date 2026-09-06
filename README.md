# DentDES: anonymous reproducibility package

This package accompanies **DentDES: A Factorial Discrete-Event Evaluation of Appointment Spacing and Readiness-Aware Dispatch in Dental Clinics**. It contains a synthetic, terminating discrete-event simulation and a matched factorial experiment. It does not contain real patient data, a trained AI model, an IoT deployment, or a live digital twin.

## What can be reproduced

The evaluation has 50 paired replication blocks, each averaging 30 independent days, for four policies, four demand settings and three instrument-kit capacities: 72,000 clinic-day runs. Patient inputs are identical across policies and kit capacities for a given demand/block/day. All attending patients and all reprocessing tasks finish; there is no closing-time truncation.

At the reference condition (28 requests and two kits per procedure class), dispatch alone changes mean waiting by -34.99 minutes (paired 95% CI [-35.90, -34.07]). Appointment spacing alone changes it by +0.40 minutes. These findings are conditional on the synthetic assumptions; substantial overtime remains.

## Install and verify

The evaluated environment used Python 3.14.6. Exact installed package versions, including transitive dependencies, are in `requirements.txt`. A TeX installation is only needed to build the manuscript; it is not needed to run or validate the experiment. Run commands from this package's root directory. Do not use Python's `-O` option because it disables invariant assertions.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v test_model.py
.venv/bin/python validate.py --replay-all --report replay_check.json
```

The replay command regenerates all 6,000 saved cohort-day inputs, verifies their hashes and pairing, re-runs every clinic day from its saved inputs, checks all output fields against the archived CSV, and verifies four detailed example traces. It also reconstructs replication means and checks every reported summary and factorial contrast. Expected comparisons allow an absolute tolerance of 1e-9 and a relative tolerance of 1e-11 for floating-point serialization. Runtime depends on the machine; progress is printed every 12,000 replays. Omitting `--replay-all` still checks all saved estimates and input sets but only replays the four detailed examples.

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. The provided shell examples were tested on macOS; Windows execution has not been tested.

## Generate a new complete copy of the experiment

```sh
.venv/bin/python model.py --out reproduced --replications 50 --days 30 --seed 2026090502
.venv/bin/python analyze.py --results reproduced
.venv/bin/python validate.py --results reproduced --replay-all
```

`analyze.py` intentionally requires the full 50-block design; it does not compute confidence intervals for a reduced pilot. It generates tables under `generated/` and figures under `figures/`, alongside the supplied results directory. Re-running it replaces generated figures and tables. Different PDF creation timestamps can change PDF bytes without changing the plotted data. Compare numerical outputs using `validate.py`; a regenerated gzip header can also differ while its decompressed patient records agree.

For a quick debugging run, use a separate destination and the independent pilot seed:

```sh
.venv/bin/python model.py --out debug --replications 2 --days 3 --seed 2026090501
```

This is not the evaluated experiment. Keep evaluation outputs separate from exploratory runs.

## Package contents

- `PROTOCOL.md`: frozen model assumptions, outcomes and analysis plan; its evaluated hash is in `results/manifest.json`.
- `METHOD_DETAILS.md`: mathematical definitions retained outside the applied main text; these do not change the frozen protocol or experiment.
- `model.py`: patient generation, scheduling, atomic dispatch, physical processing, conservation checks and experiment runner.
- `test_model.py`: 11 tests, including analytic timing, overtime drainage, input matching, abundant-kit negative control and bounded bypasses.
- `analyze.py`: replication summaries, paired effects, manuscript table and three figures.
- `validate.py`: independent reconstruction of stored summaries and numerical replay checks.
- `results/patient_inputs.jsonl.gz`: 6,000 synthetic cohort-day records, each with the complete pre-generated patient inputs.
- `results/daily_results.csv`: 72,000 clinic-day results; keys are replication, day, demand, kits and policy.
- `results/replication_results.csv`: 2,400 records, averaging daily outcomes within each 30-day block.
- `results/summary.csv`: means, SDs and marginal 95% confidence intervals by condition/policy/metric.
- `results/paired_effects.csv`: within-block policy differences, factorial main effects and interactions.
- `results/example_S*.json`: patient timelines and event traces for block 1, day 1, reference condition.
- `results/manifest.json` and `analysis_manifest.json`: evaluated inputs, versions and SHA-256 identifiers.
- `paper/`: anonymous IEEE-style manuscript and LaTeX source. The author-information file is deliberately excluded from the review archive.
- `figures/` and `generated/`: vector/raster figures and generated LaTeX table inputs.
- `verification/`: test and full-replay results for the packaged version.
- `SHA256SUMS.json`: checksums of all other distributed files.

## Outcome definitions

### Post-review supplementary diagnostics

The revised manuscript also reports exploratory capacity, queue-blocking and bypass-limit checks. These use the unchanged primary model and all 6,000 saved cohort inputs in 36,000 day-runs with uniform spacing. The original primary experiment remains distinct from this later analysis. Files in `feedback_assessment/` include the historical scope, runner, output tables and manifest. The scope's statement that the manuscript was unchanged describes the assessment stage; selected findings were incorporated on 6 September 2026.

To reproduce these diagnostics from this package's root, run `python feedback_assessment/review_checks.py`. This overwrites only the diagnostic outputs. The run verifies 12,000 repeated primary cases and identical patient outcomes in all 6,000 abundant-kit policy pairs. `python feedback_assessment/check_report.py` reconstructs diagnostic summaries and checks the new manuscript numbers without rerunning all clinic days. `fraction_patients_worse_than_fifo` compares each patient against two-kit strict FCFS under the same inputs; reported fractions average days equally. `maximum_wait` is the average daily maximum, not a pooled maximum. The unlimited case uses a bound of 10,000, larger than every cohort.

The timing/IoT exploration was omitted by author direction. No public RFID dataset, information-delay experiment or related results are part of this review package. `paired_effects.pdf` remains a supplementary figure; the main text uses the workflow and demand figures plus the compact bypass table.

### Primary outcome fields

`mean_wait` is arrival-to-treatment-start time, including registration; `post_registration_wait` starts after registration. `p90_wait` is the daily 90th percentile. Replication and grand means give equal weight to days, so the reported P90 is an average of daily percentiles. Procedure-specific wait means omit days without that class; missing patient means are never replaced with zero.

`completed_by_close` counts discharge by minute 480, while `completed` includes all eventual discharges. `overtime` is last patient discharge beyond closing. `reprocessing_overtime` uses the end of all events, including cleanup and kit return. It is not a continuously staffed calendar model.

`util_*` integrates actual occupied resource time during minutes 0-480 and divides by resource capacity times 480. `overtime_*_minutes` are occupied resource-minutes after closing, not percentages. Chair occupancy includes the time until cleaning releases that chair. Assistant occupancy includes treatment/documentation and turnover/kit preparation.

`kit_unavailable_wait` integrates the registered patient's waiting time during which no clean kit of that patient's class exists. It overlaps other resource waits and must not be summed with them as a causal decomposition. `max_bypasses` is the largest count for a patient; `bypass_events` counts all patient overtakes, which may exceed the number of dispatch decisions.

Demand multipliers are labels applied to 28 requests using rounding: 0.8, 1.0, 1.2 and 1.5 yield 22, 28, 34 and 42 requests. Kits are class-specific, with four procedure classes. Thus two kits per class means eight kits in total.

## Rebuild the anonymous manuscript

After running the analysis, execute from `paper/`:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=DentDES_ISMSIT_2026_anonymous manuscript.tex
```

The bundled `IEEEtran.cls` retains its original license and copyright notice. Other dependencies retain their upstream licenses. This review package does not grant a new redistribution license for the manuscript or study code; licensing can be decided by the authors separately.

Reproduction checks verify execution and internal consistency; they do not establish clinical validity or an independently replicated scientific study.
