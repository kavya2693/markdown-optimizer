"""End to end: history -> elasticities -> lift -> markdown plans -> outcomes on the true curve."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from markdown_optimizer.config import POLICY
from markdown_optimizer.data import Dataset
from markdown_optimizer.elasticity import estimate, fit_controls
from markdown_optimizer.features import prepare
from markdown_optimizer.lift import evaluate_lift, summarise_lift
from markdown_optimizer.optimize import fixed_plan, plan_events
from markdown_optimizer.simulate import model_demand, oracle_demand, paired_difference, simulate, summarise

ESTIMATORS = ["no_pooling", "complete_pooling", "partial_pooling", "partial_pooling_no_competitor"]


@dataclass
class Results:
    elasticity_error: pd.DataFrame
    elasticity_by_sku: pd.DataFrame
    lift_summary: pd.DataFrame
    lift_rows: pd.DataFrame
    markdown_summary: pd.DataFrame
    markdown_by_event: pd.DataFrame
    pooling_comparison: pd.DataFrame
    plan: pd.DataFrame


def elasticity_error(est: dict[str, pd.DataFrame], truth: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Absolute error against the true elasticity, split by how much price variation a SKU saw.

    The split is on promotion weeks rather than volume: with multiplicative noise, a big SKU that
    never changes price tells the model as little as a small one.
    """
    tr = truth.set_index("sku_id")
    rows, per_sku = [], []
    for name, t in est.items():
        t = t.set_index("sku_id")
        err = t["beta"] - tr.loc[t.index, "beta"]
        gerr = t["gamma"] - tr.loc[t.index, "gamma"]
        few = t["n_promo_weeks"] < t["n_promo_weeks"].quantile(1 / 3)
        rows.append(
            {
                "estimator": name,
                "beta_mae": err.abs().mean(),
                "beta_mae_few_promos": err[few].abs().mean(),
                "beta_mae_many_promos": err[~few].abs().mean(),
                "beta_bias": err.mean(),
                "beta_wrong_sign": float((t["beta"] >= 0).mean()),
                "gamma_mae": gerr.abs().mean(),
            }
        )
        per_sku.append(pd.DataFrame({"estimator": name, "beta_hat": t["beta"], "beta_true": tr.loc[t.index, "beta"]}))
    return pd.DataFrame(rows), pd.concat(per_sku).reset_index()


def run(ds: Dataset, draws: int = 400) -> Results:
    prepared = prepare(ds.sales)
    est = estimate(prepared)
    err, err_sku = elasticity_error(est, ds.truth)

    coefs = {name: fit_controls(prepared, est[name]) for name in ESTIMATORS}
    lift_rows = evaluate_lift(prepared, coefs["partial_pooling"], ds.truth, ds.skus)
    lift_summary = summarise_lift(lift_rows)

    truth = ds.truth.set_index("sku_id")
    future = ds.future_cpi.set_index(["sku_id", "t"])["competitor_index"]
    last_cpi = prepared.sort_values("t").groupby("sku_id")["competitor_index"].last()
    events = ds.events

    plans = {
        "no_markdown": fixed_plan(events, 0.0),
        "fixed_30": fixed_plan(events),
        **{name: plan_events(events, model_demand(coefs[name], last_cpi)) for name in ESTIMATORS},
        "oracle": plan_events(events, oracle_demand(truth, future)),
    }
    outcomes = {name: simulate(events, plan, truth, future, draws=draws) for name, plan in plans.items()}
    summary = summarise(outcomes)
    pooling = pd.DataFrame(
        [
            {"comparison": f"partial_pooling - {name}", "margin_difference": d, "ci95_halfwidth": ci}
            for name in ESTIMATORS
            if name != "partial_pooling"
            for d, ci in [paired_difference(outcomes["partial_pooling"], outcomes[name])]
        ]
    )

    by_event = pd.concat(
        [
            o.groupby("event_id")
            .agg(margin=("margin", "sum"), sold=("units_sold", "sum"), stock=("opening_stock", "sum"))
            .assign(sell_through=lambda d: d["sold"] / d["stock"], policy=name)
            .reset_index()
            for name, o in outcomes.items()
        ]
    )[["policy", "event_id", "margin", "sell_through"]]

    plan = plans["partial_pooling"].merge(
        outcomes["partial_pooling"][["event_id", "sku_id", "margin", "sell_through"]], on=["event_id", "sku_id"]
    )
    plan = plan.merge(
        outcomes["fixed_30"][["event_id", "sku_id", "margin", "sell_through"]].rename(
            columns={"margin": "fixed_30_margin", "sell_through": "fixed_30_sell_through"}
        ),
        on=["event_id", "sku_id"],
    )
    return Results(err, err_sku, lift_summary, lift_rows, summary, by_event, pooling, plan)


def headline(res: Results) -> dict[str, float]:
    s = res.markdown_summary.set_index("policy")
    e = res.elasticity_error.set_index("estimator")
    lift = res.lift_summary.set_index("baseline")
    return {
        "beta_mae_no_pooling": float(e.at["no_pooling", "beta_mae"]),
        "beta_mae_partial_pooling": float(e.at["partial_pooling", "beta_mae"]),
        "baseline_wape_model": float(lift.at["model", "baseline_wape"]),
        "baseline_wape_naive": float(lift.at["naive", "baseline_wape"]),
        "margin_fixed_30": float(s.at["fixed_30", "promotional_margin"]),
        "margin_partial_pooling": float(s.at["partial_pooling", "promotional_margin"]),
        "margin_oracle": float(s.at["oracle", "promotional_margin"]),
        "oracle_headroom_captured": float(s.at["partial_pooling", "oracle_headroom_captured"]),
        "sell_through_fixed_30": float(s.at["fixed_30", "sell_through"]),
        "sell_through_partial_pooling": float(s.at["partial_pooling", "sell_through"]),
        "hit_target_fixed_30": float(s.at["fixed_30", "share_events_hitting_target"]),
        "hit_target_partial_pooling": float(s.at["partial_pooling", "share_events_hitting_target"]),
        "sell_through_target": POLICY.sell_through_target,
    }
