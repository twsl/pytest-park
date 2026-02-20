"""Demo benchmark with custom metadata for testing pytest-park features."""

import time

from pytest_benchmark.fixture import BenchmarkFixture


def demo_func_v1() -> int:
    """Version 1 - baseline."""
    time.sleep(0.01)
    return 42


def demo_func_v2() -> int:
    """Version 2 - optimized with caching."""
    time.sleep(0.005)
    return 42


def test_demo_v1(benchmark: BenchmarkFixture) -> None:
    """Benchmark baseline implementation with custom metadata."""
    benchmark.extra_info["custom_groups"] = {
        "technique": "baseline",
        "complexity": "O(n)",
    }
    result = benchmark.pedantic(demo_func_v1, rounds=1, iterations=1)
    assert result == 42


def test_demo_v2(benchmark: BenchmarkFixture) -> None:
    """Benchmark optimized implementation with custom metadata."""
    benchmark.extra_info["custom_groups"] = {
        "technique": "caching",
        "complexity": "O(1)",
    }
    result = benchmark.pedantic(demo_func_v2, rounds=1, iterations=1)
    assert result == 42
