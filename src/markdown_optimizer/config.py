"""Shared constants: the shape of the chain, the discount ladder and the clearance policy."""

from __future__ import annotations

from dataclasses import dataclass

HISTORY_WEEKS = 156
FIRST_WEEK = "2023-01-02"
N_SKUS = 400

CATEGORIES: dict[str, dict[str, float]] = {
    # name: mean elasticity, competitor cross-elasticity, regular price, holiday uplift (log)
    "dairy": {"beta": -1.4, "gamma": 0.35, "price": 3.2, "holiday": 0.10},
    "bakery": {"beta": -1.6, "gamma": 0.30, "price": 2.8, "holiday": 0.15},
    "snacks": {"beta": -2.6, "gamma": 0.70, "price": 3.9, "holiday": 0.30},
    "beverages": {"beta": -2.3, "gamma": 0.80, "price": 4.5, "holiday": 0.25},
    "frozen": {"beta": -2.0, "gamma": 0.55, "price": 5.8, "holiday": 0.12},
    "canned goods": {"beta": -1.5, "gamma": 0.40, "price": 2.1, "holiday": 0.08},
    "cereal": {"beta": -2.2, "gamma": 0.65, "price": 4.8, "holiday": 0.05},
    "household cleaning": {"beta": -1.8, "gamma": 0.60, "price": 6.5, "holiday": 0.04},
    "personal care": {"beta": -1.9, "gamma": 0.50, "price": 7.9, "holiday": 0.06},
    "pasta and rice": {"beta": -1.3, "gamma": 0.30, "price": 2.6, "holiday": 0.07},
    "condiments": {"beta": -1.2, "gamma": 0.25, "price": 3.4, "holiday": 0.12},
    "confectionery": {"beta": -2.9, "gamma": 0.75, "price": 3.6, "holiday": 0.45},
}

# Discount depths a store can actually print on a shelf label.
LADDER: tuple[float, ...] = (0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60)
FIXED_RULE_DEPTH = 0.30


@dataclass(frozen=True)
class ClearancePolicy:
    event_weeks: int = 4
    # Share of opening stock that has to be gone by the end of the event.
    sell_through_target: float = 0.75
    # Leftover units go to a liquidator at this share of unit cost.
    salvage_share_of_cost: float = 0.30
    n_events: int = 3
    skus_per_event: int = 100


POLICY = ClearancePolicy()
