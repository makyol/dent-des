# DentDES

**DentDES** is a discrete-event simulation study of patient flow and reusable instrument-kit availability in dental clinics. The project evaluates whether appointment spacing and readiness-aware patient dispatch can reduce waiting when a patient is ready but the required kit is still being reprocessed.

The associated manuscript is:

> **DentDES: A Factorial Discrete-Event Evaluation of Appointment Spacing and Readiness-Aware Dispatch in Dental Clinics**

## Research question

The study compares two operational policies:

- **Appointment spacing:** whether changing the time between bookings reduces queueing and overtime.
- **Readiness-aware dispatch:** whether serving another registered patient whose required kit is ready reduces blocking.

The policies are evaluated in a synthetic clinic model with four chairs, two dentists, three assistants, a front-desk worker, a batch sterilizer and class-specific reusable instrument kits. The experiment uses synthetic clinic inputs and evaluates offline policy behavior.

## Study design

The experiment uses four policy combinations, four demand levels and three kit-capacity settings. Each condition has 50 paired replication blocks of 30 independent clinic days. The same attendance, treatment and service inputs are supplied to the compared policies, allowing within-block policy differences to be estimated directly.

The reference condition uses 28 requests per day and two kits per procedure class. At this condition, readiness-aware dispatch reduces mean arrival-to-treatment-start waiting from 127.94 to 92.96 minutes, a paired difference of −34.99 minutes (95% CI [−35.90, −34.07]). Appointment spacing alone changes waiting by +0.40 minutes. The dispatch effect becomes small when kit capacity is abundant, while overtime remains substantial in high-demand settings.

The findings identify operating conditions in which instrument availability may constrain patient flow and support future calibration work.

## Reproduce the experiment

The evaluated environment uses Python 3.14.6. Create an isolated environment and install the pinned dependencies:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v test_model.py
```

Validate the packaged results and replay the complete experiment:

```sh
.venv/bin/python validate.py --replay-all --report replay_check.json
```

The replay regenerates the saved patient-input cohorts, reruns the clinic days, checks pairing and conservation rules, reconstructs the replication summaries and verifies the reported contrasts. Omitting `--replay-all` performs the stored-summary checks and replays the detailed example traces.

To generate a separate copy of the experiment:

```sh
.venv/bin/python model.py --out reproduced --replications 50 --days 30 --seed 2026090502
.venv/bin/python analyze.py --results reproduced
.venv/bin/python validate.py --results reproduced --replay-all
```

The exploratory diagnostics reported in the paper (bypass bounds and 50-kit controls, 36,000 additional clinic-day runs) are in `feedback_assessment/`. Check them against the saved inputs and primary results with:

```sh
.venv/bin/python feedback_assessment/check_report.py
```

`feedback_assessment/review_checks.py` regenerates the diagnostic files from the saved cohort inputs, and `feedback_assessment/SCOPE.md` states their design.

Use a separate output directory for exploratory runs. For a quick debugging run:

```sh
.venv/bin/python model.py --out debug --replications 2 --days 3 --seed 2026090501
```

## Repository contents

- `model.py` — patient generation, scheduling, dispatch, resource processing and experiment execution.
- `test_model.py` — unit tests for timing, input matching, overtime drainage, kit-capacity controls and bounded bypass.
- `analyze.py` — replication summaries, paired effects, tables and figures.
- `validate.py` — independent reconstruction and replay checks.
- `PROTOCOL.md` — model assumptions, outcomes and the analysis plan.
- `METHOD_DETAILS.md` — supporting mathematical definitions.
- `results/` — synthetic patient inputs, daily results, replication summaries, paired effects and example traces.
- `figures/` — workflow and results figures in PDF and PNG formats.
- `generated/` — generated LaTeX table fragments.
- `feedback_assessment/` — exploratory bypass-bound and abundant-kit diagnostics reported in the paper, with their check script.
- `paper/` — manuscript source and the IEEEtran class file.
- `verification/` — recorded test, replay and manuscript checks.
- `LICENSE`, `LICENSE-DATA.md`, `CITATION.cff` — licenses and citation metadata.
- `web/` — a static browser-based results explorer for GitHub Pages.

## Interpreting the results

`mean_wait` measures arrival-to-treatment-start time, including registration. `post_registration_wait` starts after registration. `p90_wait` is calculated per day and then averaged across replication blocks. `overtime` is the final discharge time beyond the 480-minute opening period.

`kit_unavailable_wait` measures time spent waiting while no clean kit of the patient’s class is available. It can overlap other resource waits and should not be added to them as a causal decomposition. Kit capacities are class-specific: two kits per class means eight kits across the four procedure classes.

## Scope and limitations

The inputs, service distributions, kit classes and staffing assumptions are synthetic. Future calibration will use observed clinic and instrument-circulation data.

The browser explorer presents the packaged results alongside the simulation outputs. Reproduction checks establish execution and internal consistency.

## Manuscript build

From `paper/`, build the manuscript with:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=DentDES_ISMSIT_2026_camera_ready manuscript.tex
```

The manuscript is formatted for the IEEE conference template. The compiled PDF is not distributed in this repository. The repository can be archived with a release tag so that the code, synthetic inputs and reported results remain associated with a specific version of the study.

## Recorded hashes

`results/manifest.json`, `results/analysis_manifest.json` and `feedback_assessment/manifest.json` record SHA-256 hashes of `model.py`, `PROTOCOL.md` and `analyze.py`. The hashes taken when the experiment was evaluated (5 September 2026) are kept in the `evaluation_*` fields. The three files were edited afterwards (docstring and wording changes) and the original bytes are not retained, so the main fields hold the hashes of the files in this repository. `verification/shipped_code_replay.json` records that these files reproduce all 72,000 archived clinic days. In `verification/supplementary_checks.json`, `primary_model_and_protocol_unchanged` refers to these shipped files.

## Authors and citation

Fatemeh Astaraki and Mehmet Ali Akyol, Ankara Medipol University. Release v1.0.0 is archived on Figshare at <https://doi.org/10.6084/m9.figshare.33442582.v1>; the base DOI 10.6084/m9.figshare.33442582 always resolves to the latest version. Cite this repository with the metadata in `CITATION.cff`.

## License

Code is released under the MIT License (`LICENSE`). Data, results, figures and documentation are released under CC BY 4.0 (`LICENSE-DATA.md`). The manuscript in `paper/` is not covered by either license.
