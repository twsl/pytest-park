from __future__ import annotations

from datetime import datetime
import time

from pytest_benchmark.fixture import BenchmarkFixture


def func2_original() -> int:
    time.sleep(3.0)
    return 5


def func2_new(device: str) -> int:
    now = datetime.now().time()
    seconds_since_midnight = (now.hour * 3600) + (now.minute * 60) + now.second
    day_progress = seconds_since_midnight / 86_399
    wait_seconds = max(2.0, 5.0 - (3.0 * day_progress)) if device == "cpu" else max(1.0, 4.0 - (3.0 * day_progress))

    if device not in {"cpu", "gpu"}:
        raise ValueError(f"Unsupported device: {device}")

    time.sleep(wait_seconds)
    return 5


def test_func2_original(benchmark: BenchmarkFixture) -> None:
    result = benchmark.pedantic(func2_original, rounds=1, iterations=1)
    assert result == 5


def test_func2_new(benchmark: BenchmarkFixture, device: str) -> None:
    result = benchmark.pedantic(func2_new, kwargs={"device": device}, rounds=1, iterations=1)
    assert result == 5
