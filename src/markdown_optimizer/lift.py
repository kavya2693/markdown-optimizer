"""Promotional lift against a counterfactual baseline: what the week would have sold at the
regular price with no promotion.

Two baselines are scored against the true counterfactual known from the generator:
the demand model (same week, same season, same competitor price, regular price, no promotion)
and the pre-period average most promotion reviews use (mean of the last four clean weeks).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from markdown_optimizer.data import true_log_mu
from markdown_optimizer.elasticity import predict


def naive_baseline(prepared: pd.DataFrame, window: int = 4) -> pd.Series:
    """Mean units over the last ``window`` non-promotion, non-dip, non-stockout weeks before each row."""
    clean = (prepared["promo"] == 0) & (prepared["post_promo"] == 0) & (prepared["stockout"] == 0)
    units = prepared["units"].where(clean)
    return units.groupby(prepared["sku_id"]).transform(
        lambda s: s.shift(1).rolling(52, min_periods=1).apply(_last_n_mean(window), raw=True)
    )


def _last_n_mean(n: int):  # type: ignore[no-untyped-def]
    def f(x: np.ndarray) -> float:
        vals = x[~np.isnan(x)][-n:]
        return float(vals.mean()) if len(vals) else np.nan

    return f


def evaluate_lift(prepared: pd.DataFrame, coefs: pd.DataFrame, truth: pd.DataFrame, skus: pd.DataFrame) -> pd.DataFrame:
    """One row per historical promotion week, with estimated and true baselines and margins."""
    df = prepared.copy()
    df["naive_baseline"] = naive_baseline(df)
    promo = df.loc[(df["promo"] == 1) & (df["stockout"] == 0)].copy()

    cf = promo.copy()
    cf["log_price"] = np.log(cf["regular_price"])
    cf["promo"] = 0.0
    cf["post_promo"] = 0.0
    model_base = np.empty(len(cf))
    for sku, idx in cf.groupby("sku_id").indices.items():
        model_base[idx] = predict(coefs.loc[sku], cf.iloc[idx])
    promo["model_baseline"] = model_base

    params = truth.set_index("sku_id").loc[promo["sku_id"]].reset_index()
    t = promo["t"].to_numpy()
    cpi = promo["competitor_index"].to_numpy()
    hol = promo["holiday"].to_numpy()
    zeros = np.zeros(len(promo))
    promo["true_baseline"] = np.exp(true_log_mu(params, t, promo["regular_price"].to_numpy(), cpi, zeros, zeros, hol))
    promo["true_promo_mean"] = np.exp(
        true_log_mu(params, t, promo["price"].to_numpy(), cpi, np.ones(len(promo)), zeros, hol)
    )

    cost = skus.set_index("sku_id").loc[promo["sku_id"], "unit_cost"].to_numpy()
    reg_margin = promo["regular_price"].to_numpy() - cost
    promo_margin = promo["price"].to_numpy() - cost
    promo["true_incremental_margin"] = promo_margin * promo["true_promo_mean"] - reg_margin * promo["true_baseline"]
    for name in ("model", "naive"):
        promo[f"{name}_incremental_margin"] = (
            promo_margin * promo["units"].to_numpy() - reg_margin * promo[f"{name}_baseline"].to_numpy()
        )
    keep = [
        "sku_id", "category", "t", "discount", "units", "regular_price", "price",
        "true_baseline", "model_baseline", "naive_baseline", "true_promo_mean",
        "true_incremental_margin", "model_incremental_margin", "naive_incremental_margin",
    ]  # fmt: skip
    return promo[keep].reset_index(drop=True)


def summarise_lift(lift: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ok = lift.dropna(subset=["naive_baseline"])
    truth_lift = ok["true_promo_mean"] - ok["true_baseline"]
    true_loses = ok["true_incremental_margin"] < 0
    for name in ("model", "naive"):
        base = ok[f"{name}_baseline"]
        err = base - ok["true_baseline"]
        est_lift = ok["units"] - base
        said_loses = ok[f"{name}_incremental_margin"] < 0
        rows.append(
            {
                "baseline": name,
                "promotions": len(ok),
                "baseline_wape": float(err.abs().sum() / ok["true_baseline"].sum()),
                "baseline_bias": float(err.sum() / ok["true_baseline"].sum()),
                "lift_bias": float((est_lift.sum() - truth_lift.sum()) / truth_lift.sum()),
                "true_share_margin_negative": float(true_loses.mean()),
                "estimated_share_margin_negative": float(said_loses.mean()),
                "margin_sign_accuracy": float((said_loses == true_loses).mean()),
            }
        )
    return pd.DataFrame(rows)
