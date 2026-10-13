import numpy as np
import pandas as pd

from markdown_optimizer.data import generate


def test_same_seed_same_data() -> None:
    a, b = generate(seed=5, n_skus=20), generate(seed=5, n_skus=20)
    pd.testing.assert_frame_equal(a.sales, b.sales)
    pd.testing.assert_frame_equal(a.events, b.events)


def test_history_carries_the_mess_the_estimator_must_handle(small) -> None:
    s = small.sales
    assert s["stockout"].sum() > 0
    assert s["competitor_index"].isna().sum() > 0
    weeks_per_sku = s.groupby("sku_id")["t"].nunique()
    assert (weeks_per_sku < 156).any()  # dropped feed weeks
    assert 0.05 < s["promo"].mean() < 0.25


def test_true_elasticities_are_negative_and_vary_within_category(small) -> None:
    tr = small.truth
    assert (tr["beta"] < 0).all()
    assert (tr.groupby("category")["beta"].std().dropna() > 0.1).all()


def test_events_need_a_markdown_to_clear(small) -> None:
    # Opening stock is 5-11 weeks of regular-price demand for a 4-week event.
    ev = small.events
    assert len(ev) > 0
    assert (ev["opening_stock"] > 0).all()
    assert np.all(ev["salvage_value"] < ev["unit_cost"])
