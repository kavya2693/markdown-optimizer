"""Seeded generator for a grocery chain's weekly SKU history, competitor prices and clearance events.

The generator is the inverse of the estimation pipeline: it draws the true elasticity of every
SKU first and then produces sales from it, so estimation error can be measured exactly. The
true parameters are written to ``data/truth/`` and nothing under ``src`` reads them except the
evaluation code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from markdown_optimizer.config import CATEGORIES, FIRST_WEEK, HISTORY_WEEKS, N_SKUS, POLICY, ClearancePolicy

YEAR_WEEKS = 52.1775
NB_SIZE = 15.0  # negative binomial size; variance = mu + mu^2 / size

HOLIDAYS = [
    "2023-01-01", "2023-04-09", "2023-11-23", "2023-12-25", "2023-12-31",
    "2024-03-31", "2024-11-28", "2024-12-25", "2024-12-31",
    "2025-04-20", "2025-11-27", "2025-12-25", "2025-12-31",
    "2026-04-05", "2026-11-26", "2026-12-25", "2026-12-31",
]  # fmt: skip


def week_start(t: np.ndarray | int) -> pd.DatetimeIndex:
    return pd.to_datetime(FIRST_WEEK) + pd.to_timedelta(np.asarray(t) * 7, unit="D")


def holiday_flag(t: np.ndarray) -> np.ndarray:
    starts = week_start(t)
    flags = np.zeros(len(starts), dtype=int)
    for day in pd.to_datetime(HOLIDAYS):
        flags |= (starts <= day) & (day < starts + pd.Timedelta(days=7))
    return flags


def season_index(t: np.ndarray, phase: np.ndarray | float) -> np.ndarray:
    angle = 2 * np.pi * np.asarray(t) / YEAR_WEEKS
    return np.sin(angle + phase) + 0.4 * np.sin(2 * angle + 2 * phase)


def true_log_mu(
    params: pd.DataFrame,
    t: np.ndarray,
    price: np.ndarray,
    cpi: np.ndarray,
    promo: np.ndarray,
    post_promo: np.ndarray,
    holiday: np.ndarray,
) -> np.ndarray:
    """Expected log units for rows aligned with ``params`` (one params row per demand row)."""
    p = params
    return np.asarray(
        p["log_base"].to_numpy()
        + p["season_amp"].to_numpy() * season_index(t, p["phase"].to_numpy())
        + p["trend"].to_numpy() * t / YEAR_WEEKS
        + p["holiday"].to_numpy() * holiday
        + p["beta"].to_numpy() * np.log(price / p["price_ref"].to_numpy())
        + p["gamma"].to_numpy() * np.log(cpi)
        + p["delta"].to_numpy() * promo
        - p["dip"].to_numpy() * post_promo
    )


def draw_units(rng: np.random.Generator, mu: np.ndarray) -> np.ndarray:
    lam = rng.gamma(NB_SIZE, mu / NB_SIZE)
    return rng.poisson(lam)


@dataclass
class Dataset:
    skus: pd.DataFrame
    sales: pd.DataFrame
    events: pd.DataFrame
    truth: pd.DataFrame
    future_cpi: pd.DataFrame


def _sku_params(rng: np.random.Generator, n_skus: int) -> pd.DataFrame:
    names = list(CATEGORIES)
    weights = rng.dirichlet(np.full(len(names), 8.0))
    category = rng.choice(names, size=n_skus, p=weights)
    rows = []
    phase_by_cat = {c: rng.uniform(0, 2 * np.pi) for c in names}
    delta_by_cat = {c: rng.uniform(0.05, 0.25) for c in names}
    dip_by_cat = {c: rng.uniform(0.0, 0.15) for c in names}
    for i, cat in enumerate(category):
        spec = CATEGORIES[cat]
        price_ref = round(spec["price"] * float(np.exp(rng.normal(0, 0.35))), 2)
        margin = rng.uniform(0.25, 0.45)
        rows.append(
            {
                "sku_id": f"SKU{i:04d}",
                "category": cat,
                "price_ref": price_ref,
                "unit_cost": round(price_ref * (1 - margin), 2),
                # Chain-level weekly units; the long left tail is where single-SKU fits break down.
                "log_base": rng.normal(np.log(110), 1.0),
                "season_amp": rng.uniform(0.05, 0.35),
                "phase": phase_by_cat[cat] + rng.normal(0, 0.3),
                "trend": rng.normal(0.0, 0.06),
                "holiday": spec["holiday"] * rng.uniform(0.5, 1.5),
                "beta": min(spec["beta"] + rng.normal(0, 0.4), -0.4),
                "gamma": max(spec["gamma"] + rng.normal(0, 0.2), 0.0),
                "delta": delta_by_cat[cat] + rng.normal(0, 0.03),
                "dip": dip_by_cat[cat],
            }
        )
    return pd.DataFrame(rows)


def _competitor_paths(rng: np.random.Generator, params: pd.DataFrame, n_weeks: int) -> np.ndarray:
    """Competitor price index (competitor shelf price / our reference price), per SKU per week."""
    cats = params["category"].to_numpy()
    cat_path: dict[str, np.ndarray] = {}
    for cat in np.unique(cats):
        x = np.zeros(n_weeks)
        for w in range(1, n_weeks):
            x[w] = 0.92 * x[w - 1] + rng.normal(0, 0.025)
        cat_path[cat] = x
    log_cpi = np.vstack([cat_path[c] for c in cats]) + rng.normal(0, 0.02, (len(cats), n_weeks))
    competitor_promo = rng.random((len(cats), n_weeks)) < 0.07
    log_cpi += np.where(competitor_promo, np.log(1 - rng.uniform(0.10, 0.30, log_cpi.shape)), 0.0)
    return np.asarray(np.exp(log_cpi))


def _promo_calendar(rng: np.random.Generator, params: pd.DataFrame, n_weeks: int) -> np.ndarray:
    """Discount depth per SKU per week. Buyers promote into peak season, which confounds price and
    seasonality unless the model controls for both."""
    t = np.arange(n_weeks)
    hol = holiday_flag(t)
    depth = np.zeros((len(params), n_weeks))
    depths = np.array([0.10, 0.15, 0.20, 0.25, 0.30, 0.40])
    depth_p = np.array([0.18, 0.20, 0.22, 0.18, 0.14, 0.08])
    for i, row in enumerate(params.itertuples()):
        base_rate = rng.uniform(0.03, 0.20)
        season = season_index(t, row.phase)
        prob = base_rate * (1 + 0.6 * season) * (1 + 0.8 * hol)
        run = 0
        for w in range(n_weeks):
            if run >= 2:
                run = 0
                continue
            if rng.random() < prob[w]:
                depth[i, w] = depth[i, w - 1] if run and w > 0 else rng.choice(depths, p=depth_p)
                run += 1
            else:
                run = 0
    return depth


def _regular_prices(rng: np.random.Generator, params: pd.DataFrame, n_weeks: int) -> np.ndarray:
    reg = np.tile(params["price_ref"].to_numpy()[:, None], (1, n_weeks))
    for i in range(len(params)):
        for _ in range(rng.integers(0, 3)):
            w = rng.integers(10, n_weeks - 10)
            reg[i, w:] *= 1 + rng.choice([-1, 1]) * rng.uniform(0.03, 0.09)
    return np.round(reg, 2)


def generate(seed: int = 7, n_skus: int = N_SKUS, policy: ClearancePolicy = POLICY) -> Dataset:
    rng = np.random.default_rng(seed)
    params = _sku_params(rng, n_skus)
    event_starts = [HISTORY_WEEKS + 4 + 12 * k for k in range(policy.n_events)]
    horizon = event_starts[-1] + policy.event_weeks
    cpi = _competitor_paths(rng, params, horizon)
    depth = _promo_calendar(rng, params, HISTORY_WEEKS)
    regular = _regular_prices(rng, params, HISTORY_WEEKS)

    # A competitor sometimes matches our promotion in the same week, so leaving the competitor
    # index out of the model pushes part of its effect into our own price coefficient.
    match = (depth > 0) & (rng.random(depth.shape) < 0.35)
    cpi[:, :HISTORY_WEEKS] *= np.where(match, 1 - 0.6 * depth, 1.0)

    n, w = depth.shape
    t = np.tile(np.arange(w), n)
    sku_idx = np.repeat(np.arange(n), w)
    long = params.iloc[sku_idx].reset_index(drop=True)
    price = (regular * (1 - depth)).ravel()
    promo = (depth > 0).astype(int)
    post = np.zeros_like(promo)
    post[:, 1:] = (promo[:, :-1] == 1) & (promo[:, 1:] == 0)
    hol = holiday_flag(t)
    mu = np.exp(true_log_mu(long, t, price, cpi[:, :w].ravel(), promo.ravel(), post.ravel(), hol))
    units = draw_units(rng, mu)

    # Bulk buys by caterers and small shops: unexplained spikes the model has to survive.
    spike = rng.random(units.shape) < 0.005
    units = np.where(spike, (units * rng.uniform(2.5, 4.0, units.shape)).astype(int), units)
    # Stockouts cap sales; more likely on promotion because promotions are under-forecast.
    p_out = np.where(promo.ravel() == 1, 0.06, 0.02)
    stockout = rng.random(units.shape) < p_out
    units = np.where(stockout, (units * rng.uniform(0.3, 0.8, units.shape)).astype(int), units)

    sales = pd.DataFrame(
        {
            "week": week_start(t).strftime("%Y-%m-%d"),
            "t": t,
            "sku_id": long["sku_id"],
            "category": long["category"],
            "regular_price": regular.ravel(),
            "discount": depth.ravel(),
            "price": np.round(price, 2),
            "promo": promo.ravel(),
            "competitor_index": np.round(cpi[:, :w].ravel(), 4),
            "units": units,
            "stockout": stockout.astype(int),
        }
    )
    # Feed gaps: some store-week files never arrive, and the competitor scrape misses weeks.
    sales = sales.loc[rng.random(len(sales)) >= 0.01].reset_index(drop=True)
    cpi_gap = rng.random(len(sales)) < 0.02
    sales.loc[cpi_gap, "competitor_index"] = np.nan

    events = _events(rng, params, regular[:, -1], cpi, event_starts, policy)
    future = [
        {"sku_id": params["sku_id"].iat[i], "t": int(tt), "competitor_index": round(float(cpi[i, tt]), 4)}
        for i in range(n)
        for tt in range(HISTORY_WEEKS, horizon)
    ]
    skus = params[["sku_id", "category", "price_ref", "unit_cost"]].copy()
    skus["regular_price"] = regular[:, -1]
    return Dataset(skus, sales, events, params, pd.DataFrame(future))


def _events(
    rng: np.random.Generator,
    params: pd.DataFrame,
    last_regular: np.ndarray,
    cpi: np.ndarray,
    starts: list[int],
    policy: ClearancePolicy,
) -> pd.DataFrame:
    """Clearance events on slow movers: opening stock is several weeks of regular-price demand,
    more than the event window will sell without a markdown."""
    slow = np.flatnonzero(params["log_base"].to_numpy() < np.quantile(params["log_base"], 0.6))
    rows = []
    for k, start in enumerate(starts):
        chosen = rng.choice(slow, size=min(policy.skus_per_event, len(slow)), replace=False)
        tt = np.arange(start, start + policy.event_weeks)
        hol = holiday_flag(tt)
        for i in chosen:
            p = params.iloc[[i] * len(tt)].reset_index(drop=True)
            price = np.full(len(tt), last_regular[i])
            mu = np.exp(true_log_mu(p, tt, price, cpi[i, tt], np.zeros(len(tt)), np.zeros(len(tt)), hol))
            cover = rng.uniform(5.0, 11.0)
            unit_cost = float(params["unit_cost"].iat[i])
            rows.append(
                {
                    "event_id": f"E{k + 1}",
                    "sku_id": params["sku_id"].iat[i],
                    "category": params["category"].iat[i],
                    "start_t": start,
                    "start_week": week_start(np.array([start])).strftime("%Y-%m-%d")[0],
                    "weeks": policy.event_weeks,
                    "opening_stock": int(round(cover * mu.mean())),
                    "regular_price": float(last_regular[i]),
                    "unit_cost": unit_cost,
                    "salvage_value": round(unit_cost * policy.salvage_share_of_cost, 2),
                }
            )
    return pd.DataFrame(rows)


def write(ds: Dataset, out: Path) -> None:
    (out / "truth").mkdir(parents=True, exist_ok=True)
    ds.skus.to_csv(out / "skus.csv", index=False)
    ds.sales.to_csv(out / "sales.csv", index=False)
    ds.events.to_csv(out / "events.csv", index=False)
    ds.truth.to_csv(out / "truth" / "sku_params.csv", index=False)
    ds.future_cpi.to_csv(out / "truth" / "future_competitor_index.csv", index=False)


def load(out: Path) -> Dataset:
    return Dataset(
        skus=pd.read_csv(out / "skus.csv"),
        sales=pd.read_csv(out / "sales.csv"),
        events=pd.read_csv(out / "events.csv"),
        truth=pd.read_csv(out / "truth" / "sku_params.csv"),
        future_cpi=pd.read_csv(out / "truth" / "future_competitor_index.csv"),
    )
