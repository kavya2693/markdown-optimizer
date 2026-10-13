import numpy as np
import pandas as pd

from markdown_optimizer.elasticity import dersimonian_laird, poisson_irls, shrink


def test_poisson_glm_recovers_known_coefficients() -> None:
    rng = np.random.default_rng(0)
    n = 4000
    log_p = rng.uniform(-0.5, 0.0, n)
    x = np.column_stack([log_p, np.ones(n), rng.normal(size=n)])
    true = np.array([-2.0, 4.0, 0.3])
    y = rng.poisson(np.exp(x @ true)).astype(float)
    fit = poisson_irls(x, y)
    assert np.allclose(fit.coef, true, atol=0.05)
    assert 0.8 < fit.dispersion < 1.2


def test_offset_is_held_fixed() -> None:
    rng = np.random.default_rng(1)
    n = 3000
    log_p = rng.uniform(-0.5, 0.0, n)
    y = rng.poisson(np.exp(3.0 - 1.5 * log_p)).astype(float)
    fit = poisson_irls(np.ones((n, 1)), y, offset=-1.5 * log_p)
    assert abs(fit.coef[0] - 3.0) < 0.05


def test_noisy_estimates_shrink_more_than_precise_ones() -> None:
    est = pd.Series([-1.0, -3.0, -2.0, -2.2, -1.8])
    se = pd.Series([0.05, 2.0, 0.1, 0.1, 0.1])
    groups = pd.Series(["a"] * 5)
    pooled = shrink(est, se, groups)
    mean, _ = dersimonian_laird(est.to_numpy(), se.to_numpy())
    assert abs(pooled[0] - est[0]) < 0.05  # precise, stays
    assert abs(pooled[1] - mean) < abs(est[1] - mean) / 4  # noisy, pulled in


def test_identical_estimates_give_zero_between_sku_variance() -> None:
    _, tau2 = dersimonian_laird(np.full(6, -2.0), np.full(6, 0.3))
    assert tau2 == 0.0


def test_complete_pooling_gives_one_value_per_category() -> None:
    est = pd.Series([-1.0, -2.0, -3.0, -0.5])
    se = pd.Series([0.2, 0.2, 0.2, 0.2])
    groups = pd.Series(["a", "a", "b", "b"])
    pooled = shrink(est, se, groups, complete=True)
    assert pooled[0] == pooled[1] == -1.5
    assert pooled[2] == pooled[3] == -1.75
