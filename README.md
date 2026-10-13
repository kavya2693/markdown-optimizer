# markdown-optimizer

[![ci](https://github.com/kavya2693/markdown-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/kavya2693/markdown-optimizer/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11-blue)
![license](https://img.shields.io/badge/license-MIT-green)

How deep to mark down each slow-moving grocery SKU in a clearance event, worked out from its
own price elasticity instead of a blanket 30% off, and checked against demand where the right
answer is known.

## The problem

A grocery chain ends every season with SKUs it overbought: holiday confectionery, a snack
flavour that did not take, a cleaning product the supplier is replacing. Each one has a few
weeks of shelf space left before the leftovers go to a liquidator for a fraction of cost. A
pricing analyst has to choose a markdown for a hundred or more of these per event, and in
practice the answer is a rule: 30% off everything, deepen it if it is still there in two weeks.

The rule is easy to run and easy to defend, and it is wrong in both directions at once. On a
price-sensitive SKU, 30% off clears the shelf in a week and gives away margin that 10% would
have kept. On an insensitive one, 30% is not enough, the stock is still there at the end, and
the write-down eats what the markdown earned. Nobody sees this, because the only number anyone
looks at afterwards is whether the shelf emptied.

## Why it is hard

The decision needs one number per SKU that is never observed directly: how much demand moves
when the price moves. A typical SKU is promoted a handful of times a year, usually in peak
season (so the promotion and the season are tangled together), sometimes in a week when a
competitor is also on deal (so part of the lift is theirs), and the data has stockouts, missing
store-week files and caterers buying in bulk. Fitted SKU by SKU, a quarter of the estimates are
off by half a unit of elasticity or more.

The other half of the problem is that nobody can check a markdown recommendation on real data,
because the counterfactual price was never charged. A tool that says "this plan made more
money" is only as good as the demand model it was scored on, which is usually the same model
that made the plan.

## The approach

Elasticity is estimated per SKU with a log-log demand model (own price, competitor price index,
promotion, post-promotion dip, seasonality, holiday, trend), fitted as a Poisson GLM, and then
shrunk towards its category mean by empirical Bayes so that SKUs with little price history
borrow from their neighbours while well-measured SKUs keep their own estimate. For each
clearance event, every non-decreasing markdown path on a 0-60% ladder over four weeks is scored
and the one with the best margin that still clears 75% of the stock is chosen.

The key decision is how the plans are judged. The dataset is generated from known true
elasticities, and every plan is scored on that true demand curve, with the competitor prices
that actually happened during the event, which the planner never sees. Nothing is scored on
the model that produced it. See [ADR-0001](docs/adr/0001-glm-with-empirical-bayes-and-exhaustive-ladder-search.md).

## The result

300 SKU-events across three clearance events, 400 demand draws each, seed 7. Promotional margin
is gross margin over the event including the write-down on leftovers, in currency units. The
95% interval is paired over SKU-events against the 30% rule.

| Policy | Promotional margin | vs 30% rule | Sell-through | Events hitting 75% target |
|---|---:|---:|---:|---:|
| No markdown | -39,393 | -58,270 | 49.5% | 7.4% |
| Fixed 30% off | 18,877 | — | 93.0% | 92.1% |
| Best single depth for all SKUs, chosen in hindsight (20%) | 42,761 | +23,884 ± 6,475 | 82.6% | 71.1% |
| Per-SKU plan, no pooling | 55,582 | +36,705 ± 8,347 | 91.0% | 89.1% |
| Per-SKU plan, complete pooling | 53,458 | +34,581 ± 8,048 | 92.4% | 92.0% |
| **Per-SKU plan, partial pooling** | **56,628** | **+37,750 ± 8,252** | 92.0% | 90.6% |
| Per-SKU plan, partial pooling without competitor index | 55,096 | +36,219 ± 8,173 | 92.4% | 91.2% |
| Planner that knows the true curve (upper bound) | 62,373 | +43,496 | 92.3% | 92.1% |

The two metrics disagree. The optimised plan triples the margin of the 30% rule and captures
87% of the gap to a planner that knows the true curve, but it sells through less (92.0% against
93.0%) and misses the clearance target slightly more often (90.6% of events against 92.1%),
because it plans right up to the 75% line on expected demand and noise pushes some events under
it. The 30% rule sells more because it gives more away.

The finding I did not want: **better elasticities barely move the money.** Partial pooling cuts
elasticity error by 28% against fitting each SKU alone, and the margin gain from that is 1,046
± 1,042, under 2% of the total. Across five data seeds partial pooling beat no pooling every
time, but only by 900 to 1,854. Most of the gain comes from making the decision per SKU with a
clearance constraint at all. The hindsight blanket depth, the arm most likely to embarrass the
optimiser, gets 63% of the gain over the 30% rule with no model, but it misses the clearance
target on almost a third of events.

Elasticity error against the true value (mean absolute error, own-price elasticity):

| Estimator | All SKUs | Fewest promotions (bottom third) | Rest | Bias | Competitor elasticity MAE |
|---|---:|---:|---:|---:|---:|
| No pooling | 0.385 | 0.497 | 0.330 | +0.017 | 0.166 |
| Complete pooling (category mean) | 0.334 | 0.347 | 0.328 | -0.056 | 0.154 |
| **Partial pooling** | **0.279** | **0.321** | **0.258** | +0.000 | 0.113 |
| Partial pooling, competitor index left out | 0.299 | 0.336 | 0.280 | +0.077 | — |

Pooling helps most where price history is thinnest, as it should. Leaving the competitor index
out biases own-price elasticity by +0.08, because competitors sometimes match a promotion in the
same week and their price cut gets credited to ours.

Promotional lift against the true counterfactual (6,531 historical promotion weeks):

| Baseline | Baseline WAPE | Lift bias | Correctly calls whether a promotion lost margin |
|---|---:|---:|---:|
| Demand model, regular price and no promotion in the same week | 3.7% | +0.6% | 86.8% |
| Mean of the last four clean weeks | 13.0% | -0.7% | 84.0% |

82% of historical promotions lost margin against their true counterfactual. The model baseline
is far closer week by week, but both baselines are nearly unbiased in total, and the
pre-period average still classifies most promotions correctly, because most promotions lose
money by a wide margin.

Across seeds 7 to 11 ([outputs/seed_sweep.csv](outputs/seed_sweep.csv)): elasticity MAE 0.405
± 0.038 unpooled and 0.265 ± 0.015 pooled, share of oracle headroom captured 0.869 ± 0.008,
sell-through 92.9% ± 1.2 for the 30% rule against 91.0% ± 1.3 for the plan. The 30% rule's
margin swings from 1,599 to 19,942 by seed; the plan's gain over it does not depend on that.

## How it works

```
sales history ──► prepare ──► per-SKU Poisson GLM ──► empirical-Bayes shrink ──► refit controls
(stockouts dropped,          (own price, competitor   (per category,             with pooled
 gaps filled,                 index, promo, dip,       DerSimonian-Laird)         elasticities fixed)
 dip flagged)                 season, holiday, trend)                                    │
                                                                                         ▼
clearance events ──────────────────────────────► 210 ladder paths per SKU-event ──► best margin
(opening stock, cost, salvage)                    scored on expected demand          with ≥75% expected
                                                                                     sell-through
                                                                                         │
true demand curve + realised competitor prices ──► 400 paired draws per SKU-event ◄──────┘
```

A path never raises the price mid-event. If no path reaches 75% expected sell-through, the plan
takes the one that sells the most, since the stock has to go regardless, and the shortfall
shows up in the hit rate. Leftovers are sold to a liquidator at 30% of unit cost.

## Running it

```bash
uv sync
make data            # writes data/ from seed 7
make run             # full study, writes outputs/
make sweep           # same, plus seeds 8-11 into outputs/seed_sweep.csv
make check           # ruff, format, mypy, pytest
docker build -t markdown-optimizer . && docker run --rm markdown-optimizer
```

Every number above comes from [outputs/report.md](outputs/report.md),
[outputs/results.json](outputs/results.json) and the CSVs next to them; the console output of
the run is in [outputs/run_log.txt](outputs/run_log.txt). The chosen markdown path for every
SKU-event, with its realised margin next to the 30% rule's, is in
[outputs/markdown_plan.csv](outputs/markdown_plan.csv). Policy (target, salvage share, ladder)
is in `src/markdown_optimizer/config.py`.

```
src/markdown_optimizer/
  data.py         seeded generator and the true demand function
  features.py     design matrix: Fourier seasonality, holiday, post-promotion flag
  elasticity.py   Poisson GLM by IRLS, outlier refit, empirical-Bayes pooling
  lift.py         counterfactual baselines and incremental margin of past promotions
  optimize.py     ladder paths, margin and sell-through scoring, constrained choice
  simulate.py     scores plans on the true curve with paired demand draws
  pipeline.py     runs every estimator and policy; cli.py writes outputs/
```

## The data

The dataset is generated by the seeded script `scripts/generate_data.py` (`make data`) and
sized to the production problem; the production data is proprietary. It covers a 60-store
grocery chain at chain level: 400 SKUs in 12 categories, 156 weeks of history (about 61,800
SKU-weeks), and three four-week clearance events of 100 slow-moving SKUs each.

Each SKU draws its true own-price elasticity from its category mean (-1.2 to -2.9) with
between-SKU spread 0.4, plus a competitor cross-elasticity, promotion display lift, a
post-promotion dip, seasonality, holiday uplift and trend. Promotions are more likely in peak
season and holiday weeks. Competitors run their own deals and match ours 35% of the time.
Sales are negative binomial (about 16% noise on a high-volume SKU), with 0.5% bulk-order spikes,
stockouts that cap sales (6% of promotion weeks, 2% otherwise), 1% of SKU-weeks missing and 2%
of competitor prices missing. Opening stock for a clearance SKU is 5 to 11 weeks of
regular-price demand. The true parameters are written to `data/truth/` and are read only by the
evaluation code.

The limit that matters: the generator uses the same constant-elasticity form the estimator
assumes, so model misspecification costs nothing here and would cost something on real data.

## Tests

`tests/test_optimize.py::test_a_wrong_sign_curve_never_marks_down` feeds the optimiser a
deliberately broken demand curve in which discounts reduce demand. It must not mark down, and
the clearance shortfall must be visible rather than hidden. Together with the hand-computed
margin check in `test_score_caps_sales_at_remaining_stock`, this is what makes the margin
numbers above trustworthy.

`tests/test_pipeline.py::test_pooling_beats_no_pooling_on_elasticity_error` runs the whole
pipeline on a fresh 150-SKU dataset with a different seed and checks that pooling lowers
elasticity error and that the gain is larger for SKUs with few promotions. If shrinkage were
pulling well-measured SKUs as hard as noisy ones, the second assertion would fail. The GLM
itself is checked for recovering known coefficients to within 0.05.

18 tests, about 25 seconds, no network and no model server.

## Known limitations

- **Biggest gap: the evaluation cannot catch a wrong functional form.** Data and estimator share
  the constant-elasticity log-log form. On real data, elasticity usually rises with discount
  depth, and the optimiser would then be extrapolating to 50-60% off from promotions that
  rarely went past 30%.
- The planner optimises expected demand. A version that plans against demand quantiles would
  trade some margin for hitting the clearance target more often; it is not built.
- No cannibalisation or halo between SKUs: marking down one snack does not take sales from
  another.
- Competitor prices during an event are held at their last observed value when planning, and
  competitors do not react to our markdowns. The scorer uses the prices that actually happened.
- The incremental margin of past promotions ignores the post-promotion dip, so it flatters
  promotions slightly.
- The resume line this backs also mentions a promotion calendar. This repository measures lift
  and margin of past promotions but does not optimise a calendar.
- One price zone at chain level. Store-level elasticity and stock positions are not modelled.

## Insights and learning

I picked markdowns because it is the pricing decision where a wrong answer is most visible
after the fact and least understood before it. Everyone sees the leftover stock; nobody sees
the margin a too-deep markdown gave away on the SKUs that cleared. Building the scorer first,
on a curve where the true elasticity is known, was the only way to see both sides.

What surprised me was how little the elasticity accuracy mattered once the decision was
framed properly. I expected pooling to be the headline, and on estimation error it is. But a
discrete ladder with a sell-through floor is forgiving: an elasticity off by 0.3 usually lands
on the same rung or the next one, and the clearance constraint stops the worst mistakes. The
structure of the decision carried more value than the precision of the estimate.

What I got wrong at first was the noise level. With the first setting, single-SKU estimates
were so noisy that pooling looked almost like replacing every SKU with its category mean. Chain
level weekly sales sum dozens of stores and are much smoother than that, and once the noise
matched that, partial pooling separated cleanly from both extremes.

Next I would let elasticity vary with depth (a piecewise or spline price term) and break the
shared functional form between generator and estimator, which is the test this project cannot
yet pass. After that, planning against the 25th percentile of demand instead of the mean, to
see what it costs in margin to match the 30% rule's clearance rate.

## License

MIT
