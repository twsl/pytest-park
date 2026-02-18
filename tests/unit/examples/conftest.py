from typing import Any

import pytest

from pytest_park.pytest_benchmark import default_pytest_benchmark_group_stats


@pytest.fixture(params=["cpu", "gpu"])
def device(request: pytest.FixtureRequest) -> str:
    """Device parameter for example benchmark tests."""
    return str(request.param)


def pytest_benchmark_group_stats(config: Any, benchmarks: list[Any], group_by: str) -> dict[str, list[Any]]:
    """Group benchmark stats using pytest-park naming conventions.

    This hook allows pytest-benchmark to group tests by base method name,
    splitting out original and new postfixes for comparison.
    """
    return default_pytest_benchmark_group_stats(
        config,
        benchmarks,
        group_by,
        original_postfix="original",
        reference_postfix="new",
        group_values_by_postfix={
            "original": "baseline",
            "new": "optimized",
        },
    )
