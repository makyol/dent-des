# DentDES V5 experimental protocol

Frozen before evaluation runs on 5 September 2026. This protocol implements the approved ISMSIT revision scope. All numbers below are synthetic design assumptions, not measured clinic parameters or device instructions. V4 outputs are not used as evidence for V5.

## Question and estimand

How do proportional duration-aware appointment spacing (S) and readiness-aware dispatch (R) affect arrival-to-treatment-start waiting, and what waiting/overtime tradeoffs occur under demand and reusable-instrument constraints? The method is a transparent heuristic comparison, not a claim of a new optimization algorithm, trained AI, live IoT, or deployed digital twin.

Four policies are S0R0, S1R0, S0R1, S1R1. The same patient input record is replayed under every policy and kit configuration. S changes appointments, so arrival deviations, rather than absolute arrival times, are matched. No future realized service times or no-show outcomes enter the scheduler.

## Inputs and physical model

Each independent day has 28 requested appointments at normal demand; multipliers 0.8, 1.0, 1.2, 1.5 produce 22, 28, 34, 42 appointments. A day starts empty with all kits clean; all patients and reprocessing finish before the next independent day. No inventory state is carried between days. A replication averages 30 days; 50 independent replications are used for inference. This deliberate change from V4 removes consumable replenishment from the evaluated scope.

- Four chairs, two interchangeable dentists, three interchangeable assistants, one front-desk worker, one sterilizer with capacity four kits per batch.
- Four operational procedure categories: routine/restorative/impression/complex, probabilities 0.52/0.28/0.13/0.07. Each category requires one dedicated kit class; kits are interchangeable within, not between classes. This is an abstraction for stress-testing heterogeneity, not a validated instrument bill of materials.
- Kits per class: 1, 2, 4, for 4/8/16 total kits. Two per class is the reference configuration; four is the abundant-kit comparison.
- No-show probability 0.13 for all policies. Arrival deviation is normal (SD 6 min) clipped at +/-12 min. Booking endpoints are minutes 15 and 435, so no arrivals are clipped or rejected.
- Treatment is a clipped normal with mean 30 times category multiplier (0.82/1.10/1.00/1.45), SD 8, bounds 12–65 minutes. An independent exponential overrun of mean 13 minutes occurs with probability 0.22. Both are drawn once per patient and held identical across policies.
- Registration/checkout use clipped normals with means 3/3, SD 0.8, minimum 1. Documentation uses mean 8, SD 1.8, minimum 3; chair cleaning mean 9, SD 1.5, minimum 4. Values are drawn per patient in advance.
- Patient treatment and documentation reserve one chair, dentist, assistant and kit. After documentation the dentist and assistant are released, and checkout proceeds at the front desk independently of chair turnover. A turnover task obtains an assistant, cleans the chair, releases the chair, then performs eight minutes of instrument preparation before releasing the assistant and putting the kit in the dirty queue.
- The sterilizer greedily takes up to four waiting kits whenever free, with a fixed 29-minute synthetic cycle (24 processing + 5 release/drying proxy). No policy shortens physical service. Instrument preparation and cycles are assumptions to vary in future calibration, not recommended sterilization settings.
- Turnover tasks take assistant priority over new treatments. This fixed rule is identical for every policy. Staff time is measured as actual resource occupancy, including turnover and documentation.
- Consumables are assumed available; there are no stockout or inventory-improvement claims. Breaks, emergencies, provider specialties, clinical outcomes and real-time data capture are outside scope.

## Algorithms

S0 spaces all n requests uniformly from minute 15 to 435 in their request order. S1 preserves the same request order and endpoints, but assigns each inter-appointment gap proportional to the preceding category's expected treatment + expected overrun + documentation (30*m + 0.22*13 + 8). It is a pooled-workload spacing heuristic, not individual dentist slot assignment. It does not drop appointments, add opening hours, see no-shows, or use realized durations. Compressed schedules under high demand remain in the experiment and their overtime is reported.

R0 dispatches only the oldest registered patient when that patient's kit and all staff/chair resources are available. R1 chooses the oldest feasible registered patient; a patient may be bypassed at most twice. Once the head patient has been bypassed twice, dispatch waits for that patient. Bypass counts increase only for earlier waiting patients passed over by an actual dispatch. This is a count bound, not a guaranteed maximum waiting time. Both policies acquire resources atomically and obey identical feasibility conditions. Cleaning priority, kit return, and patient readiness events all trigger reevaluation without polling delay.

## Outcomes and inference

Primary: day-level mean arrival-to-treatment-start wait over all attending patients, averaged over 30 days per replication. Also report daily P90 wait (then averaged, not a pooled P90), post-registration wait, registration wait, length of stay, opening-hours completions (by minute 480), final completions, patient-discharge overtime, cleanup/reprocessing overtime, staff/chair/sterilizer occupancy within 0–480, and procedure-specific wait. Days without attendees have missing patient means, not artificial zero waits; completion and overtime outcomes remain defined.

Use two-sided t intervals over 50 independent replication summaries (df=49; critical value 2.009575). Policy differences are paired by replication and condition. S and R effects average the corresponding contrasts across the other factor; interaction is Y11-Y10-Y01+Y00. Relative reductions are descriptive; absolute paired differences with intervals are primary. No significance-based selection or guaranteed direction of effects. All 12 demand/kit conditions and all four policies are reported. Cross-condition inference is exploratory; intervals are marginal, without multiplicity adjustment.

## Verification and freeze rules

Separate pilot seed 2026090501 from evaluation seed 2026090502. Pilot runs debug code; results are not pooled into evaluation. Evaluation seeds, model, and protocol hashes accompany outputs. Changes after evaluation require a documented reason and a full rerun; no favorable parameter tuning. Tests cover analytic one-patient timing, resource integrals, conservation of patients/kits, non-clairvoyant scheduling, common inputs, exact deterministic reruns, drain past 720 minutes, absence of readiness effects with abundant resources, actual readiness activation, and the bypass bound.

Day inputs are saved as compressed JSON lines; daily and replication outputs as CSV; patient-level traces are retained for a deterministic example and can be regenerated for any input. Fifty 30-day blocks across 12 conditions and four policies produce 72,000 clinic-day runs. The anonymous artifact must include model, tests, protocol, inputs, outputs, figure/table generation, dependency versions and reproduction instructions.

## Manuscript outline

1. Introduction: operational question and conditional simulation contribution.
2. Related work: dental DES, scheduling, inventory/coordination and healthcare twins; precise distinctions.
3. Model and policies: physical state, observability, algorithms and assumptions.
4. Experiment: paired inputs, terminating-day metrics, factors and uncertainty.
5. Results: all policy effects, interaction and resource/demand robustness; procedure-level tradeoffs.
6. Discussion/conclusion: explain findings without clinical-effectiveness claims, disclose synthetic assumptions and baseline dependence.

This follows the structure approved in the preceding assessment. Portal page limit, supplementary support, original reviews, clinical face validation and author confirmation remain external checks; they do not change the numerical protocol.
