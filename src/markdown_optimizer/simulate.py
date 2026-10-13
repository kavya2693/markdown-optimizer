"""Score markdown plans against the true demand curve.

Plans are made from estimated elasticities; outcomes are drawn from the generator's true
parameters and the competitor prices that actually happened during the event, which the
planner never sees. Every policy sees the same random draws for a SKU-event, so differences
between policies are paired rather than noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from markdown_optimizer.config import POLICY, ClearancePolicy
from markdown_optimizer.data import draw_units, holiday_flag, true_log_mu
from markdown_optimizer.elasticity import predict
from markdown_optimizer.features import design
from markdown_optimizer.optimize import DemandFn, depth_matrix


def model_demand(coefs: pd.DataFrame, last_cpi: pd.Series) -> DemandFn:
    """Planner's view: fitted curve, competitor index held at its last observed value."""

    def fn(ev: pd.Series, depths: np.ndarray) -> np.ndarray:
        weeks = int(ev["weeks"])
        t = np.tile(np.arange(ev["start_t"], ev["start_t"] + weeks), len(depths))
        d = np.repeat(depths, weeks)
        x = design(
            t,
            ev["regular_price"] * (1 - d),
            np.full(len(t), last_cpi[ev["sku_id"]]),
            (d > 0).astype(float),
            np.zeros(len(t)),
        )
        return predict(coefs.loc[ev["sku_id"]], x).reshape(len(depths), weeks)

    return fn


def true_mean(ev: pd.Series, depths: np.ndarray, truth: pd.DataFrame, future_cpi: pd.Series) -> np.ndarray:
    """True expected units, shape (len(depths), weeks)."""
    weeks = int(ev["weeks"])
    t = np.tile(np.arange(ev["start_t"], ev["start_t"] + weeks), len(depths))
    d = np.repeat(depths, weeks)
    params = truth.loc[[ev["sku_id"]] * len(t)].reset_index()
    cpi = np.array([future_cpi[(ev["sku_id"], int(x))] for x in t])
    log_mu = true_log_mu(
        params,
        t,
        ev["regular_price"] * (1 - d),
        cpi,
        (d > 0).astype(float),
        np.zeros(len(t)),
        holiday_flag(t),
    )
    return np.exp(log_mu).reshape(len(depths), weeks)


def oracle_demand(truth: pd.DataFrame, future_cpi: pd.Series) -> DemandFn:
    """Upper bound: plans with the true curve and the competitor prices that actually happened."""

    def fn(ev: pd.Series, depths: np.ndarray) -> np.ndarray:
        return true_mean(ev, depths, truth, future_cpi)

    return fn


def simulate(
    events: pd.DataFrame,
    plan: pd.DataFrame,
    truth: pd.DataFrame,
    future_cpi: pd.Series,
    draws: int = 400,
    seed: int = 11,
    policy: ClearancePolicy = POLICY,
) -> pd.DataFrame:
    """Mean realised margin and sell-through per SKU-event over ``draws`` demand draws."""
    depth = depth_matrix(plan)
    rows = []
    for i, ev in enumerate(events.itertuples(index=False)):
        e = pd.Series(ev._asdict())
        path = depth[i]
        mu = np.diag(true_mean(e, path, truth, future_cpi))
        rng = np.random.default_rng([seed, i])
        units = draw_units(rng, np.tile(mu, (draws, 1)))
        price = np.round(e["regular_price"] * (1 - path), 2)
        left = np.full(draws, float(e["opening_stock"]))
        margin = np.zeros(draws)
        for w in range(len(path)):
            sold = np.minimum(left, units[:, w])
            margin += (price[w] - e["unit_cost"]) * sold
            left -= sold
        margin += left * (e["salvage_value"] - e["unit_cost"])
        st = 1 - left / e["opening_stock"]
        rows.append(
            {
                "event_id": e["event_id"],
                "sku_id": e["sku_id"],
                "opening_stock": e["opening_stock"],
                "margin": float(margin.mean()),
                "units_sold": float((e["opening_stock"] - left).mean()),
                "sell_through": float(st.mean()),
                "hit_target": float((st >= policy.sell_through_target).mean()),
                "mean_depth": float(path.mean()),
            }
        )
    return pd.DataFrame(rows)


def paired_difference(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, float]:
    """Total margin of ``a`` minus ``b`` and the 95% half-width over SKU-events."""
    diff = a["margin"].to_numpy() - b["margin"].to_numpy()
    se = diff.std(ddof=1) * np.sqrt(len(diff)) if len(diff) > 1 else 0.0
    return float(diff.sum()), float(1.96 * se)


def summarise(outcomes: dict[str, pd.DataFrame], reference: str = "fixed_30") -> pd.DataFrame:
    ref = outcomes[reference]
    oracle_gain = outcomes["oracle"]["margin"].sum() - ref["margin"].sum() if "oracle" in outcomes else np.nan
    rows = []
    for name, o in outcomes.items():
        diff = o["margin"].to_numpy() - ref["margin"].to_numpy()
        _, ci = paired_difference(o, ref)
        rows.append(
            {
                "policy": name,
                "promotional_margin": o["margin"].sum(),
                "margin_vs_fixed_30": o["margin"].sum() - ref["margin"].sum(),
                "margin_diff_95ci_halfwidth": ci,
                # Share of the gap between the fixed rule and a planner who knew the true curve.
                "oracle_headroom_captured": diff.sum() / oracle_gain,
                "sell_through": o["units_sold"].sum() / o["opening_stock"].sum(),
                "share_events_hitting_target": o["hit_target"].mean(),
                "mean_depth": o["mean_depth"].mean(),
                "skus_better_than_fixed": float((diff > 0).mean()),
            }
        )
    return pd.DataFrame(rows)
