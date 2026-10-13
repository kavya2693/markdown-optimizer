"""Design matrix for the per-SKU demand model.

Seasonality is two Fourier harmonics on the week index rather than week-of-year dummies: with
three years of history, 52 dummies per SKU would eat a third of the degrees of freedom.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from markdown_optimizer.data import YEAR_WEEKS, holiday_flag

PRICE_COLS = ["log_price", "log_cpi"]
CONTROL_COLS = ["const", "promo", "post_promo", "sin1", "cos1", "sin2", "cos2", "holiday", "trend"]
ALL_COLS = PRICE_COLS + CONTROL_COLS


def calendar(t: np.ndarray) -> dict[str, np.ndarray]:
    angle = 2 * np.pi * np.asarray(t, dtype=float) / YEAR_WEEKS
    return {
        "sin1": np.sin(angle),
        "cos1": np.cos(angle),
        "sin2": np.sin(2 * angle),
        "cos2": np.cos(2 * angle),
        "holiday": holiday_flag(np.asarray(t)).astype(float),
        "trend": np.asarray(t, dtype=float) / YEAR_WEEKS,
    }


def prepare(sales: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw history into model-ready rows.

    Competitor index gaps are carried forward within a SKU (the shelf price was most likely
    unchanged). The post-promotion flag is computed on the full week grid so a missing row
    does not hide the week that followed a promotion.
    """
    df = sales.sort_values(["sku_id", "t"]).reset_index(drop=True).copy()
    df["competitor_index"] = df.groupby("sku_id")["competitor_index"].transform(lambda s: s.ffill().bfill())
    promo_weeks = set(zip(df.loc[df["promo"] == 1, "sku_id"], df.loc[df["promo"] == 1, "t"], strict=True))
    prev_promo = [(s, t - 1) in promo_weeks for s, t in zip(df["sku_id"], df["t"], strict=True)]
    df["post_promo"] = ((df["promo"] == 0) & np.array(prev_promo)).astype(float)
    df["log_price"] = np.log(df["price"])
    df["log_cpi"] = np.log(df["competitor_index"])
    df["const"] = 1.0
    df["promo"] = df["promo"].astype(float)
    for k, v in calendar(df["t"].to_numpy()).items():
        df[k] = v
    return df


def design(
    t: np.ndarray, price: np.ndarray, cpi: np.ndarray, promo: np.ndarray, post_promo: np.ndarray
) -> pd.DataFrame:
    """Rows for a hypothetical price plan, in the same column order as the fitted model."""
    out = pd.DataFrame(
        {
            "log_price": np.log(price),
            "log_cpi": np.log(cpi),
            "const": 1.0,
            "promo": promo.astype(float),
            "post_promo": post_promo.astype(float),
        }
    )
    for k, v in calendar(t).items():
        out[k] = v
    return out[ALL_COLS]
