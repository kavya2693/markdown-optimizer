"""Own-price and competitor-price elasticity per SKU, with three pooling choices.

The demand model is log-log: log E[units] is linear in log own price and log competitor price
index, plus promotion, post-promotion dip, seasonality, holiday and trend. It is fitted as a
Poisson GLM with log link (quasi-Poisson standard errors) instead of OLS on log(units), because
OLS needs log(units + c) on thin SKUs and the constant biases the elasticity towards zero.

- no pooling: each SKU on its own history
- complete pooling: every SKU in a category gets the category's precision-weighted mean
- partial pooling: empirical-Bayes shrinkage of each SKU towards its category mean, with the
  between-SKU variance estimated by DerSimonian-Laird. Noisy SKUs move a lot, well-measured
  SKUs barely move.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from markdown_optimizer.features import ALL_COLS, CONTROL_COLS, PRICE_COLS

OUTLIER_PEARSON = 5.0


@dataclass
class GlmFit:
    coef: np.ndarray
    cov: np.ndarray
    mu: np.ndarray
    dispersion: float


def poisson_irls(
    X: np.ndarray, y: np.ndarray, offset: np.ndarray | None = None, max_iter: int = 100, tol: float = 1e-9
) -> GlmFit:
    off = np.zeros(len(y)) if offset is None else offset
    b = np.linalg.lstsq(X, np.log(y + 0.5) - off, rcond=None)[0]
    for _ in range(max_iter):
        eta = np.clip(X @ b + off, -30, 30)
        mu = np.exp(eta)
        z = eta - off + (y - mu) / mu
        XtW = X.T * mu
        b_new = np.linalg.solve(XtW @ X + 1e-9 * np.eye(X.shape[1]), XtW @ z)
        done = np.max(np.abs(b_new - b)) < tol
        b = b_new
        if done:
            break
    mu = np.exp(np.clip(X @ b + off, -30, 30))
    dof = max(len(y) - X.shape[1], 1)
    dispersion = float(np.sum((y - mu) ** 2 / mu) / dof)
    cov = dispersion * np.linalg.inv((X.T * mu) @ X + 1e-9 * np.eye(X.shape[1]))
    return GlmFit(b, cov, mu, dispersion)


def fit_robust(X: np.ndarray, y: np.ndarray, offset: np.ndarray | None = None) -> GlmFit:
    """Fit, drop rows whose Pearson residual says bulk order, refit once."""
    first = poisson_irls(X, y, offset)
    resid = (y - first.mu) / np.sqrt(first.dispersion * first.mu)
    keep = np.abs(resid) < OUTLIER_PEARSON
    if keep.all() or keep.sum() < X.shape[1] + 5:
        return first
    return poisson_irls(X[keep], y[keep], None if offset is None else offset[keep])


def _usable(prepared: pd.DataFrame) -> pd.DataFrame:
    # Stockout weeks record what was on the shelf, not what was wanted.
    return prepared.loc[prepared["stockout"] == 0]


def fit_unpooled(prepared: pd.DataFrame, with_competitor: bool = True) -> pd.DataFrame:
    cols = ALL_COLS if with_competitor else [c for c in ALL_COLS if c != "log_cpi"]
    rows = []
    for sku, g in _usable(prepared).groupby("sku_id", sort=True):
        fit = fit_robust(g[cols].to_numpy(), g["units"].to_numpy(dtype=float))
        se = np.sqrt(np.diag(fit.cov))
        row = {
            "sku_id": sku,
            "category": g["category"].iat[0],
            "n_weeks": len(g),
            "n_promo_weeks": int(g["promo"].sum()),
            "mean_units": float(g["units"].mean()),
            "beta": fit.coef[0],
            "beta_se": se[0],
            "gamma": fit.coef[1] if with_competitor else 0.0,
            "gamma_se": se[1] if with_competitor else np.nan,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def dersimonian_laird(est: np.ndarray, se: np.ndarray) -> tuple[float, float]:
    """Random-effects mean and between-unit variance tau^2 for one group."""
    w = 1 / se**2
    fixed = np.sum(w * est) / np.sum(w)
    q = np.sum(w * (est - fixed) ** 2)
    denom = np.sum(w) - np.sum(w**2) / np.sum(w)
    tau2 = max(0.0, (q - (len(est) - 1)) / denom) if denom > 0 else 0.0
    w_re = 1 / (se**2 + tau2)
    return float(np.sum(w_re * est) / np.sum(w_re)), tau2


def shrink(est: pd.Series, se: pd.Series, groups: pd.Series, complete: bool = False) -> pd.Series:
    out = pd.Series(index=est.index, dtype=float)
    for _, idx in groups.groupby(groups).groups.items():
        e, s = est.loc[idx].to_numpy(), se.loc[idx].to_numpy()
        mean, tau2 = dersimonian_laird(e, s)
        if complete:
            w = 1 / s**2
            out.loc[idx] = np.sum(w * e) / np.sum(w)
        elif tau2 == 0.0:
            out.loc[idx] = mean
        else:
            weight = tau2 / (tau2 + s**2)
            out.loc[idx] = mean + weight * (e - mean)
    return out


def estimate(prepared: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Elasticity tables for every estimator compared in the report."""
    unpooled = fit_unpooled(prepared)
    no_cpi = fit_unpooled(prepared, with_competitor=False)
    out: dict[str, pd.DataFrame] = {}
    for name, base, complete, pooled in [
        ("no_pooling", unpooled, False, False),
        ("complete_pooling", unpooled, True, True),
        ("partial_pooling", unpooled, False, True),
        ("partial_pooling_no_competitor", no_cpi, False, True),
    ]:
        t = base[["sku_id", "category", "n_weeks", "n_promo_weeks", "mean_units"]].copy()
        if pooled:
            t["beta"] = shrink(base["beta"], base["beta_se"], base["category"], complete)
            t["gamma"] = (
                shrink(base["gamma"], base["gamma_se"], base["category"], complete)
                if base["gamma_se"].notna().all()
                else 0.0
            )
        else:
            t["beta"], t["gamma"] = base["beta"], base["gamma"]
        out[name] = t
    return out


def fit_controls(prepared: pd.DataFrame, elasticities: pd.DataFrame) -> pd.DataFrame:
    """Refit intercept, promotion, seasonality and trend with the chosen elasticities held fixed,
    so the demand curve used for planning is consistent with the shrunk slope."""
    el = elasticities.set_index("sku_id")
    rows = []
    for sku, g in _usable(prepared).groupby("sku_id", sort=True):
        b, c = float(el.at[sku, "beta"]), float(el.at[sku, "gamma"])
        offset = b * g["log_price"].to_numpy() + c * g["log_cpi"].to_numpy()
        fit = fit_robust(g[CONTROL_COLS].to_numpy(), g["units"].to_numpy(dtype=float), offset)
        rows.append({"sku_id": sku, "log_price": b, "log_cpi": c, **dict(zip(CONTROL_COLS, fit.coef, strict=True))})
    return pd.DataFrame(rows).set_index("sku_id")[PRICE_COLS + CONTROL_COLS]


def predict(coef: pd.Series, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(np.exp(np.clip(X[ALL_COLS].to_numpy() @ coef[ALL_COLS].to_numpy(), -30, 30)))
