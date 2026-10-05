# Exploratory checks prompted by the external LLM review

These checks were specified after reading the review on 5 September 2026. They are post-review diagnostics, not part of the frozen primary experiment, not preregistered findings, and not replacements for the existing results. The primary model, protocol, manuscript and submission archive are unchanged during this assessment.

Reuse all 6,000 saved cohort-day inputs (four demand levels, 50 blocks, 30 days). Use uniform spacing throughout. Run six cases per cohort: two kits/class with bypass bounds 0, 1, 2 and effectively unlimited (10,000, greater than every cohort size); and 50 kits/class with FCFS and bound-2 readiness dispatch. This gives 36,000 diagnostic day-runs. Compare the original bound-0 and bound-2 cases with archived outputs, and verify identical patient outcomes in the two abundant-kit cases.

Report waiting, daily maximum waiting, discharge overtime, total resource workload, opening-hours and whole-run occupancy, sterilizer batch count/fill, and paired patient-level changes against FCFS. For the patients bypassed exactly twice under the original bound-2 policy, compare those same patients' waiting in FCFS. This is a descriptive outcome-selected subgroup, not a causal fairness estimate. No five-minute practical threshold is introduced retrospectively as a prespecified criterion.

For reference-demand, two-kit cases with bounds 0 and 2, reconstruct opening-hours intervals where the head patient lacks a kit while a dentist is idle; also count intervals with all other treatment resources available, and those with another kit-ready patient waiting. Preserve the first cohort's interval records for inspection. These are state reconstructions from complete patient/resource histories, not new logged clinical observations.

Aggregate daily measures into the same 50 blocks for summaries and paired marginal t intervals. Retain every specified case and demand; do not select a new reference or change the model to obtain a favorable result. Suggested scheduling redesigns and information-delay experiments are assessed as possible future work, not implemented in this diagnostic run.
