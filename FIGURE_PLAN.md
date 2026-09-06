# Figure contracts

Delivery: standalone vector PDF plus PNG verification copies, embedded in an IEEE manuscript. No interactive/HTML surface or decorative branding.

- `demand_robustness`: ordered-parameter line/dot variant, 4 demand values × 3 kit capacities × 4 policies. Mean patient waiting in minutes with marginal 95% replication intervals. Demand is an experimental factor, not time; connectors are guides between evaluated values. Same zero-based y-axis across three panels. Two color roots (blue/orange) plus neutral; marker shape, fill and dash pattern distinguish policies in grayscale. Footprint 7.1 × approximately 2.6 inches.
- `paired_effects`: two-panel dot-and-interval comparison, 12 paired condition estimates per outcome. Combined-minus-baseline waiting and overtime differences in minutes. A visible zero line; signs show improvement or deterioration. Blue marks plus neutral, labels specify demand and kits. Footprint 7.1 × approximately 3.3 inches.
- `model_flow`: compact monochrome process/resource schematic matching the implemented model, emphasizing independent chair and kit return. Not a data chart. PDF inspection must check that arrows correctly join processes and labels remain readable.

Sources: replication_results.csv and derived summary.csv/paired_effects.csv, each retaining metrics, condition, policy/contrast, n, mean, SD and CI. Captions state the terminating synthetic setting and aggregation. Final QA is in the compiled manuscript at normal reading scale.
