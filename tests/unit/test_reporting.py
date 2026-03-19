from __future__ import annotations

from pytest_park.core.reporting import build_benchmark_header_label


def test_build_benchmark_header_label_uses_filename_when_available() -> None:
    assert build_benchmark_header_label("results/run_candidate_v2.json", "fallback") == "run_candidate_v2.json"
    assert build_benchmark_header_label("<live>", "current") == "current"
