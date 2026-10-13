"""Markdown depth per SKU per week of a clearance event.

Each SKU-event picks a path on the discount ladder that never goes back up during the event
(a price that rises mid-clearance trains shoppers to wait and is not allowed by most store
policies). With seven rungs and four weeks there are 210 such paths, so every one is scored
exactly instead of handing the problem to a solver.

Objective: event margin = sum over weeks of (price - unit cost) x units sold, plus leftover
units x (salvage value - unit cost). Constraint: expected sell-through must reach the target.
When no path reaches it, the path with the highest sell-through is chosen, because the stock
has to go regardless and the shortfall is reported.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations_with_replacement

import numpy as np
import pandas as pd

from markdown_optimizer.config import FIXED_RULE_DEPTH, LADDER, POLICY, ClearancePolicy


def ladder_paths(n_weeks: int, n_rungs: int = len(LADDER)) -> np.ndarray:
    """All non-decreasing rung sequences, shape (n_paths, n_weeks)."""
    return np.array(list(combinations_with_replacement(range(n_rungs), n_weeks)), dtype=int)


def score_paths(
    paths: np.ndarray, demand: np.ndarray, stock: float, price: np.ndarray, cost: float, salvage: float
) -> tuple[np.ndarray, np.ndarray]:
    """Expected margin and sell-through of each path.

    ``demand`` and ``price`` are (n_rungs, n_weeks): expected units and shelf price at each rung.
    """
    weeks = np.arange(paths.shape[1])
    mu = demand[paths, weeks]
    p = price[paths, weeks]
    left = np.full(len(paths), float(stock))
    margin = np.zeros(len(paths))
    for w in weeks:
        sold = np.minimum(left, mu[:, w])
        margin += (p[:, w] - cost) * sold
        left -= sold
    margin += left * (salvage - cost)
    return margin, 1 - left / stock


def choose(margin: np.ndarray, sell_through: np.ndarray, target: float) -> int:
    feasible = sell_through >= target - 1e-9
    if feasible.any():
        return int(np.flatnonzero(feasible)[np.argmax(margin[feasible])])
    best = sell_through.max()
    near = np.flatnonzero(sell_through >= best - 1e-9)
    return int(near[np.argmax(margin[near])])


DemandFn = Callable[[pd.Series, np.ndarray], np.ndarray]
"""Maps an event row and a depth vector to expected units, shape (n_rungs, n_weeks)."""


def plan_events(events: pd.DataFrame, demand_fn: DemandFn, policy: ClearancePolicy = POLICY) -> pd.DataFrame:
    paths = ladder_paths(policy.event_weeks)
    depths = np.array(LADDER)
    rows = []
    for ev in events.itertuples(index=False):
        row = pd.Series(ev._asdict())
        demand = demand_fn(row, depths)
        price = np.round(row["regular_price"] * (1 - depths), 2)[:, None] * np.ones((1, policy.event_weeks))
        margin, st = score_paths(
            paths, demand, row["opening_stock"], price, row["unit_cost"], row["salvage_value"]
        )
        k = choose(margin, st, policy.sell_through_target)
        rows.append(_plan_row(row, depths[paths[k]], margin[k], st[k]))
    return pd.DataFrame(rows)


def fixed_plan(events: pd.DataFrame, depth: float = FIXED_RULE_DEPTH, policy: ClearancePolicy = POLICY) -> pd.DataFrame:
    return pd.DataFrame(
        [
            _plan_row(pd.Series(ev._asdict()), np.full(policy.event_weeks, depth), np.nan, np.nan)
            for ev in events.itertuples(index=False)
        ]
    )


def _plan_row(row: pd.Series, depth_path: np.ndarray, margin: float, st: float) -> dict[str, object]:
    return {
        "event_id": row["event_id"],
        "sku_id": row["sku_id"],
        **{f"depth_w{w + 1}": float(d) for w, d in enumerate(depth_path)},
        "planned_margin": float(margin),
        "planned_sell_through": float(st),
    }


def depth_matrix(plan: pd.DataFrame) -> np.ndarray:
    cols = sorted(c for c in plan.columns if c.startswith("depth_w"))
    return plan[cols].to_numpy(dtype=float)
