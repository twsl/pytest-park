"""Basic (non-parameterised) benchmarks for each encode implementation.

Each test targets a single implementation with a fixed 100-element dataset.
These four tests together cover all four postfixes recognised by conftest.py:
  _numpy  → "numpy baseline"
  _scipy  → "scipy baseline"
  _torch  → "torch optimized"
  _jax    → "jax optimized"
"""

from __future__ import annotations

import time

import pytest
from pytest_benchmark.fixture import BenchmarkFixture


def encode_numpy(data: list[int]) -> list[int]:
    """Simulate a numpy-based encoding baseline."""
    time.sleep(0.002)
    return [x * 2 for x in data]


def encode_scipy(data: list[int]) -> list[int]:
    """Simulate a scipy-based encoding baseline (slightly slower)."""
    time.sleep(0.003)
    return [x * 2 for x in data]


def encode_torch(data: list[int]) -> list[int]:
    """Simulate a torch-based optimised encoding."""
    time.sleep(0.001)
    return [x * 2 for x in data]


def encode_jax(data: list[int]) -> list[int]:
    """Simulate a JAX-based optimised encoding (fastest)."""
    time.sleep(0.0005)
    return [x * 2 for x in data]


@pytest.fixture()
def sample_data() -> list[int]:
    return list(range(100))


def test_encode_numpy(benchmark: BenchmarkFixture, sample_data: list[int]) -> None:
    """Baseline: numpy implementation, no device variation."""
    result = benchmark.pedantic(encode_numpy, args=(sample_data,), rounds=1, iterations=1)
    assert result == [x * 2 for x in sample_data]


def test_encode2_scipy(benchmark: BenchmarkFixture, sample_data: list[int]) -> None:
    """Baseline: scipy implementation, no device variation."""
    result = benchmark.pedantic(encode_scipy, args=(sample_data,), rounds=1, iterations=1)
    assert result == [x * 2 for x in sample_data]


def test_encode_torch(benchmark: BenchmarkFixture, sample_data: list[int]) -> None:
    """Optimised: torch implementation."""
    result = benchmark.pedantic(encode_torch, args=(sample_data,), rounds=1, iterations=1)
    assert result == [x * 2 for x in sample_data]


def test_encode2_jax(benchmark: BenchmarkFixture, sample_data: list[int]) -> None:
    """Optimised: JAX implementation."""
    result = benchmark.pedantic(encode_jax, args=(sample_data,), rounds=1, iterations=1)
    assert result == [x * 2 for x in sample_data]
