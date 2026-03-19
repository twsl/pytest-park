"""Parameterised benchmarks verifying multi-value parameter grouping.

Two implementations (numpy baseline, torch optimised) are run across every
combination of ``device`` (cpu/gpu, from conftest.py) and ``batch_size``
(10/100/1000), producing 6 benchmark entries each.

With ``ignore_params=["device"]`` set in conftest.py, all device variants of
the same base name collapse into the same group row.  Combined with multiple
``batch_size`` values this exercises the multi-value parameter grouping path:

  Expected grouping (group_by="name postfix"):
    encode_numpy  →  "numpy baseline"   – 6 entries (2 devices × 3 batch sizes)
    encode_torch  →  "torch optimized"  – 6 entries (2 devices × 3 batch sizes)

All 12 parameterised entries must collapse into exactly 2 rows in the
pytest-benchmark comparison table.
"""

from __future__ import annotations

import time

import pytest
from pytest_benchmark.fixture import BenchmarkFixture


def encode_numpy(data: list[int]) -> list[int]:
    """Simulate a numpy-based encoding baseline."""
    time.sleep(0.002)
    return [x * 2 for x in data]


def encode_torch(data: list[int]) -> list[int]:
    """Simulate a torch-based optimised encoding."""
    time.sleep(0.001)
    return [x * 2 for x in data]


BATCH_SIZES = [10, 100, 1000]


@pytest.mark.parametrize("batch_size", BATCH_SIZES)
def test_encode_numpy(
    benchmark: BenchmarkFixture,
    device: str,
    batch_size: int,
) -> None:
    """Baseline numpy across devices and batch sizes.

    With ignore_params=["device"] in conftest.py, all device variants of
    the same batch_size collapse into a single group row. Combined with
    multiple batch_size values this exercises the multi-value parameter
    grouping path.
    """
    data = list(range(batch_size))
    result = benchmark.pedantic(encode_numpy, args=(data,), rounds=1, iterations=1)
    assert len(result) == batch_size


@pytest.mark.parametrize("batch_size", BATCH_SIZES)
def test_encode_torch(
    benchmark: BenchmarkFixture,
    device: str,
    batch_size: int,
) -> None:
    """Optimised torch across devices and batch sizes.

    The postfix ``_torch`` maps to "torch optimized" via group_values_by_postfix
    so both postfix groups appear side-by-side in the benchmark table regardless
    of device or batch size.
    """
    data = list(range(batch_size))
    result = benchmark.pedantic(encode_torch, args=(data,), rounds=1, iterations=1)
    assert len(result) == batch_size
