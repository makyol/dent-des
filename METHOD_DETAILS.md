# Mathematical details accompanying the applied manuscript

These equations describe the evaluated model without changing its frozen protocol or results. The main manuscript presents the same methods in operational language.

## Treatment duration and appointment spacing

For patient i in procedure class c, let m_c be 0.82, 1.10, 1.00 or 1.45 for routine, restorative, impression or complex procedures. The generated treatment time is

`T_i = clip(N(30*m_c, 8^2), 12, 65) + B_i*E_i`,

where `B_i ~ Bernoulli(0.22)` and `E_i ~ Exponential(mean=13 minutes)`. Each patient's values are sampled once and reused across all policies and kit capacities.

For n > 1 requests in fixed order, S0 uses equal gaps between minutes 15 and 435. S1 uses the weight

`w_i = 30*m_c + 0.22*13 + 8`,

and appointment time

`a_i = 15 + 420 * sum(w_j for j < i) / sum(w_j for j = 1,...,n-1)`.

There are n-1 gaps; the final request's weight does not define a following gap. The first and last appointments are 15 and 435. For one request the appointment is 15. Actual arrival is `a_i + epsilon_i`, with the same pre-generated deviation under every policy. Expected workload is approximate because the weights do not correct for clipping of the treatment distribution.

## Outcomes

`W_i = treatment_start_i - arrival_i`.

Day-level mean waiting averages W_i over attending patients. A replication averages 30 day means. A daily P90 uses the default NumPy linear quantile interpolation, then is averaged over days. Days without attendees yield missing patient means. Procedure-specific averages omit days without the corresponding class.

`Discharge overtime = max(0, latest patient discharge - 480)`.

Opening-hours utilization for resource k is the sum of occupied interval lengths intersected with [0,480], divided by `480*capacity_k`. Overtime resource-minutes count interval lengths after 480. Cleanup/reprocessing overtime ends when the final event completes. See the code for the resource-release events and the distinction between chair return and kit return.

## Paired uncertainty and factorial effects

Let Y_sr be a replication outcome under spacing s and dispatch r. Every contrast pairs the same replication and condition. For the 50 resulting values D_r:

`95% CI = mean(D) +/- 2.009575 * sample_SD(D) / sqrt(50)`.

The critical value is for a two-sided Student's t interval with 49 degrees of freedom; SD uses denominator 49. The same interval construction describes policy means using their 50 replication outcomes.

- Spacing main effect: `((Y10 - Y00) + (Y11 - Y01)) / 2`.
- Dispatch main effect: `((Y01 - Y00) + (Y11 - Y10)) / 2`.
- Interaction: `Y11 - Y10 - Y01 + Y00`.
- Combined-policy difference: `Y11 - Y00`.

Negative differences indicate lower waiting or overtime. Intervals are marginal and not adjusted for multiple comparisons. They quantify Monte Carlo variability under fixed synthetic assumptions. They do not establish real-clinic effectiveness.

`analyze.py` generates the estimates; `validate.py` independently reconstructs them from the archived replication outcomes. No new analysis or parameter tuning was introduced by moving these equations out of the main paper.
