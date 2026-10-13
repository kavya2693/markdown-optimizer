# Run report (seed 7)

## Elasticity error against the true value
| estimator | beta_mae | beta_mae_few_promos | beta_mae_many_promos | beta_bias | beta_wrong_sign | gamma_mae |
|---|---|---|---|---|---|---|
| no_pooling | 0.385 | 0.497 | 0.330 | 0.017 | 0.013 | 0.166 |
| complete_pooling | 0.334 | 0.347 | 0.328 | -0.056 | 0.000 | 0.154 |
| partial_pooling | 0.279 | 0.321 | 0.258 | 0.000 | 0.000 | 0.113 |
| partial_pooling_no_competitor | 0.299 | 0.336 | 0.280 | 0.077 | 0.000 | 0.505 |

## Promotion baseline against the true counterfactual
| baseline | promotions | baseline_wape | baseline_bias | lift_bias | true_share_margin_negative | estimated_share_margin_negative | margin_sign_accuracy |
|---|---|---|---|---|---|---|---|
| model | 6531 | 0.037 | 0.002 | 0.006 | 0.823 | 0.804 | 0.868 |
| naive | 6531 | 0.130 | 0.014 | -0.007 | 0.823 | 0.797 | 0.840 |

## Clearance events scored on the true demand curve
| policy | promotional_margin | margin_vs_fixed_30 | margin_diff_95ci_halfwidth | oracle_headroom_captured | sell_through | share_events_hitting_target | mean_depth | skus_better_than_fixed |
|---|---|---|---|---|---|---|---|---|
| no_markdown | -39,392.67 | -58,269.82 | 11,948.28 | -1.34 | 0.49 | 0.07 | 0.00 | 0.26 |
| fixed_30 | 18,877.15 | 0.00 | 0.00 | 0.00 | 0.93 | 0.92 | 0.30 | 0.00 |
| no_pooling | 55,581.67 | 36,704.52 | 8,346.91 | 0.84 | 0.91 | 0.89 | 0.21 | 0.70 |
| complete_pooling | 53,458.25 | 34,581.10 | 8,047.91 | 0.80 | 0.92 | 0.92 | 0.23 | 0.64 |
| partial_pooling | 56,627.60 | 37,750.45 | 8,251.67 | 0.87 | 0.92 | 0.91 | 0.22 | 0.71 |
| partial_pooling_no_competitor | 55,096.10 | 36,218.95 | 8,172.92 | 0.83 | 0.92 | 0.91 | 0.22 | 0.68 |
| oracle | 62,373.27 | 43,496.12 | 8,401.06 | 1.00 | 0.92 | 0.92 | 0.21 | 0.80 |
| best_blanket_depth_hindsight | 42,760.78 | 23,883.63 | 6,475.36 | 0.55 | 0.83 | 0.71 | 0.20 | 0.72 |

## Partial pooling against the other estimators (paired over SKU-events)
| comparison | margin_difference | ci95_halfwidth |
|---|---|---|
| partial_pooling - no_pooling | 1,046 | 1,042 |
| partial_pooling - complete_pooling | 3,169 | 1,893 |
| partial_pooling - partial_pooling_no_competitor | 1,531 | 1,362 |

## By event
| policy | event_id | margin | sell_through |
|---|---|---|---|
| no_markdown | E1 | -9,829.21 | 0.50 |
| no_markdown | E2 | -13,938.95 | 0.49 |
| no_markdown | E3 | -15,624.52 | 0.49 |
| fixed_30 | E1 | 8,674.76 | 0.94 |
| fixed_30 | E2 | 8,080.47 | 0.94 |
| fixed_30 | E3 | 2,121.93 | 0.91 |
| no_pooling | E1 | 20,487.53 | 0.90 |
| no_pooling | E2 | 20,516.70 | 0.91 |
| no_pooling | E3 | 14,577.43 | 0.91 |
| complete_pooling | E1 | 19,719.02 | 0.92 |
| complete_pooling | E2 | 19,082.25 | 0.93 |
| complete_pooling | E3 | 14,656.97 | 0.92 |
| partial_pooling | E1 | 20,673.46 | 0.91 |
| partial_pooling | E2 | 20,517.51 | 0.92 |
| partial_pooling | E3 | 15,436.62 | 0.93 |
| partial_pooling_no_competitor | E1 | 20,186.51 | 0.91 |
| partial_pooling_no_competitor | E2 | 20,131.59 | 0.93 |
| partial_pooling_no_competitor | E3 | 14,778.00 | 0.93 |
| oracle | E1 | 22,190.36 | 0.92 |
| oracle | E2 | 22,502.04 | 0.93 |
| oracle | E3 | 17,680.87 | 0.92 |
| best_blanket_depth_hindsight | E1 | 16,523.87 | 0.84 |
| best_blanket_depth_hindsight | E2 | 15,499.46 | 0.83 |
| best_blanket_depth_hindsight | E3 | 10,737.45 | 0.81 |
