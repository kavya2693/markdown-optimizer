import numpy as np

from markdown_optimizer.features import prepare
from markdown_optimizer.lift import naive_baseline


def test_pooling_beats_no_pooling_on_elasticity_error(results) -> None:
    e = results.elasticity_error.set_index("estimator")
    assert e.at["partial_pooling", "beta_mae"] < e.at["no_pooling", "beta_mae"]
    # The gain should come from SKUs with little price variation.
    gain_few = e.at["no_pooling", "beta_mae_few_promos"] - e.at["partial_pooling", "beta_mae_few_promos"]
    gain_many = e.at["no_pooling", "beta_mae_many_promos"] - e.at["partial_pooling", "beta_mae_many_promos"]
    assert gain_few > gain_many


def test_model_baseline_is_closer_to_the_counterfactual_than_the_pre_period(results) -> None:
    lift = results.lift_summary.set_index("baseline")
    assert lift.at["model", "baseline_wape"] < lift.at["naive", "baseline_wape"]


def test_scorer_ranks_the_oracle_above_the_estimated_plans_and_the_fixed_rule(results) -> None:
    s = results.markdown_summary.set_index("policy")
    assert s.at["oracle", "promotional_margin"] >= s.at["partial_pooling", "promotional_margin"]
    assert s.at["partial_pooling", "promotional_margin"] > s.at["fixed_30", "promotional_margin"]
    assert s.at["no_markdown", "sell_through"] < s.at["fixed_30", "sell_through"]


def test_naive_baseline_ignores_promotion_weeks(small) -> None:
    p = prepare(small.sales[small.sales["sku_id"] == small.sales["sku_id"].iat[0]].copy())
    p = p.reset_index(drop=True)
    promo_rows = np.flatnonzero(p["promo"].to_numpy() == 1)
    i = int(promo_rows[promo_rows > 10][0])
    before = naive_baseline(p).iat[i + 2]
    p.loc[i, "units"] = 10**7  # a promotion week spike must not leak into later baselines
    assert naive_baseline(p).iat[i + 2] == before
