import numpy as np
import pandas as pd

from markdown_optimizer.config import LADDER
from markdown_optimizer.optimize import choose, ladder_paths, plan_events, score_paths


def test_paths_never_raise_price_mid_event() -> None:
    paths = ladder_paths(4)
    assert paths.shape == (210, 4)
    assert (np.diff(paths, axis=1) >= 0).all()


def test_score_caps_sales_at_remaining_stock() -> None:
    paths = np.array([[0, 0], [1, 1]])
    demand = np.array([[30.0, 30.0], [80.0, 80.0]])
    price = np.array([[10.0, 10.0], [5.0, 5.0]])
    margin, st = score_paths(paths, demand, stock=100, price=price, cost=4.0, salvage=1.0)
    # path 0: sells 60 at margin 6, 40 left written down by 3 each
    assert margin[0] == 60 * 6 - 40 * 3
    # path 1: sells 80 then the last 20, all at margin 1
    assert margin[1] == 100 * 1
    assert st.tolist() == [0.6, 1.0]


def test_choose_respects_target_then_falls_back_to_clearing() -> None:
    margin = np.array([100.0, 80.0, 50.0])
    st = np.array([0.5, 0.8, 0.9])
    assert choose(margin, st, target=0.75) == 1
    assert choose(margin, st, target=0.95) == 2


def _event() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "E1", "sku_id": "S", "category": "c", "start_t": 0, "start_week": "x",
                "weeks": 4, "opening_stock": 400, "regular_price": 10.0, "unit_cost": 6.0,
                "salvage_value": 1.8,
            }
        ]
    )  # fmt: skip


def test_more_elastic_demand_gets_a_shallower_markdown_for_the_same_clearance() -> None:
    def curve(elasticity: float):
        def fn(ev: pd.Series, depths: np.ndarray) -> np.ndarray:
            return np.tile((60 * (1 - depths) ** elasticity)[:, None], (1, 4))

        return fn

    flat = plan_events(_event(), curve(-1.2)).iloc[0]
    steep = plan_events(_event(), curve(-3.5)).iloc[0]
    cols = [f"depth_w{w}" for w in range(1, 5)]
    assert steep[cols].mean() < flat[cols].mean()
    assert steep["planned_sell_through"] >= 0.75


def test_a_wrong_sign_curve_never_marks_down() -> None:
    # Deliberately broken input: if the model says discounts reduce demand, the
    # optimiser must not discount, and the clearance shortfall must show up.
    def fn(ev: pd.Series, depths: np.ndarray) -> np.ndarray:
        return np.tile((60 * (1 - depths) ** 1.0)[:, None], (1, 4))

    plan = plan_events(_event(), fn).iloc[0]
    assert plan[[f"depth_w{w}" for w in range(1, 5)]].max() == LADDER[0]
    assert plan["planned_sell_through"] < 0.75
