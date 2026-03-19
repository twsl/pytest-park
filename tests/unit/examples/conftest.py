from typing import Any

import pytest

from pytest_park.pytest_benchmark import default_pytest_benchmark_group_stats


@pytest.fixture(params=["cpu", "gpu"])
def device(request: pytest.FixtureRequest) -> str:
    """Device parameter for example benchmark tests."""
    return str(request.param)


def pytest_benchmark_group_stats(
    config: Any, benchmarks: list[Any], group_by: str
) -> list[tuple[str | None, list[Any]]]:
    """Group benchmark stats using pytest-park naming conventions.

    This hook lets pytest-benchmark group tests by *base method name* while
    still recognising every implementation postfix.

    ``original_postfix``
        A **list** of postfix strings that mark "old / baseline"
        implementations.  Both ``_numpy`` and ``_scipy`` (and the simpler
        ``_original`` used in test_func1/func2) are treated as the baseline
        for comparison purposes.  A plain string is also accepted when there
        is only one baseline postfix.

    ``reference_postfix``
        A **list** of postfix strings that mark the "new / optimised"
        implementations.  Here ``_torch`` and ``_jax`` join the simpler
        ``_new`` used by test_func1/func2.

    ``group_values_by_postfix``
        Maps each postfix (with or without the leading underscore) to a
        human-readable display label.  When ``group_by`` includes
        ``"postfix"``, the label appears in the benchmark group key so the
        report shows "numpy baseline" or "torch optimized" rather than the
        raw ``_numpy`` / ``_torch`` strings.

        Keys are matched case-insensitively and the leading underscore is
        ignored, so ``"_numpy"`` and ``"numpy"`` are equivalent keys.

    ``ignore_params``
        Param names excluded from the group key so that, for example,
        ``device=cpu`` and ``device=gpu`` variants of the same function
        collapse into one group row rather than appearing as separate rows.
    """
    return default_pytest_benchmark_group_stats(
        config,
        benchmarks,
        group_by,
        # Multiple baseline postfixes: plain "_original" for func1/func2 tests,
        # plus "_numpy" and "_scipy" for the multi-postfix encode tests.
        original_postfix=["_original", "_numpy", "_scipy"],
        # Multiple optimised postfixes: plain "_new" plus "_torch" and "_jax".
        reference_postfix=["_new", "_torch", "_jax"],
        # Human-readable labels shown in the pytest-benchmark table when
        # group_by contains "postfix".  The leading underscore is stripped
        # automatically before matching, so "_numpy" → key "numpy".
        group_values_by_postfix={
            "_original": "baseline",
            "_new": "optimized",
            "_numpy": "numpy baseline",
            "_scipy": "scipy baseline",
            "_torch": "torch optimized",
            "_jax": "jax optimized",
        },
        ignore_params=["device"],
    )
