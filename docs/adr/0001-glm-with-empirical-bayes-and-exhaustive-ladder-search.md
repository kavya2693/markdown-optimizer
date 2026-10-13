# ADR-0001: Poisson GLM with empirical-Bayes pooling for elasticity; exhaustive search over the discount ladder

## Status
Accepted

## Context
A clearance plan needs one number per SKU that it cannot observe directly: how much demand
moves when the shelf price moves. Most grocery SKUs are promoted a handful of times a year,
often in peak season and sometimes while a competitor is also on deal, so a single SKU's
history is short, confounded and noisy. The markdown decision itself is small: a price label
can only show a few depths, an event lasts a few weeks, and stores do not raise a clearance
price mid-event.

## Decision
- Demand is log-log: log E[units] = own-price elasticity x log price + competitor elasticity x
  log competitor price index + promotion flag + post-promotion dip + two Fourier harmonics +
  holiday + trend. It is fitted per SKU as a Poisson GLM with log link by IRLS, with
  quasi-Poisson standard errors, dropping stockout weeks and refitting once without rows whose
  Pearson residual is above 5 (bulk orders).
- Elasticities are pooled by empirical Bayes within category: DerSimonian-Laird estimates the
  between-SKU variance, and each SKU is shrunk towards the category mean by its own standard
  error. The remaining coefficients are then refitted with the pooled elasticities held as an
  offset, so the curve used for planning matches the slope that was chosen.
- The markdown plan for each SKU-event is the best of all 210 non-decreasing paths over a
  seven-rung ladder (0-60%) and four weeks, maximising margin including the leftover write-down,
  subject to expected sell-through of at least 75%.
- Plans are scored on the generator's true demand curve, never on the model that made them.

## Alternatives rejected
- **Full hierarchical Bayes (PyMC / Stan).** Gives the same shrinkage behaviour with proper
  uncertainty, but adds a compiler toolchain and minutes of sampling to every CI run. Worth it
  when the posterior is used downstream; here only the point estimate is.
- **OLS on log(units + 1).** The constant biases elasticity towards zero on thin SKUs, which
  are exactly the SKUs that end up in clearance.
- **MILP solver for the markdown.** The feasible set is 210 paths per SKU-event. Enumerating
  them is exact, has no dependency and is easier to explain to a merchant.
- **Reinforcement-learning dynamic pricing.** Needs an environment that is trusted more than the
  demand model it would be trained on.

## Consequences
- The whole study runs in well under a minute on a laptop and in CI, with numpy and pandas only.
- The planner uses expected demand, so it plans right up to the sell-through target and misses
  it under noise more often than a deeper blanket markdown would. That shortfall is reported.
