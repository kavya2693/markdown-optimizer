from __future__ import annotations

import pytest

from markdown_optimizer.data import Dataset, generate
from markdown_optimizer.pipeline import Results, run


@pytest.fixture(scope="session")
def small() -> Dataset:
    return generate(seed=3, n_skus=150)


@pytest.fixture(scope="session")
def results(small: Dataset) -> Results:
    return run(small, draws=60)
