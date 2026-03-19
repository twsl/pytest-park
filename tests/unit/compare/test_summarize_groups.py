from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_park.data import load_benchmark_folder
from pytest_park.utils import (
    build_trends,
    compare_runs,
    select_candidate_run,
    select_reference_run,
    summarize_groups,
)


def _write_run_payload(path: Path, run_id: str, tag: str, dt: str, cases: list[dict]) -> None:
    payload = {
        "datetime": dt,
        "metadata": {"run_id": run_id, "tag": tag},
        "benchmarks": cases,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_group_summary_and_trends(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    reference = select_reference_run(runs, "run-reference")
    candidate = select_candidate_run(runs, "run-candidate-v2", reference)

    deltas = compare_runs(reference, candidate, ["group", "param:device"])
    summaries = summarize_groups(deltas)
    trends = build_trends(runs)

    assert summaries
    assert all(item.count >= 1 for item in summaries)
    assert any(point.run_id == "run-candidate-v2" for points in trends.values() for point in points)


class TestSummarizeGroups:
    def test_group_summary_counts_improvements_regressions_unchanged(self, benchmark_folder: Path) -> None:
        runs = load_benchmark_folder(benchmark_folder)
        reference = select_reference_run(runs, "run-reference")
        candidate = select_reference_run(runs, "run-candidate-v2")

        deltas = compare_runs(reference, candidate)
        summaries = summarize_groups(deltas)

        total_cases = sum(s.count for s in summaries)
        assert total_cases == len(deltas)
        for s in summaries:
            assert s.improvements + s.regressions + s.unchanged == s.count

    def test_all_improved_group_has_zero_regressions(self, tmp_path: Path) -> None:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        ref_cases = [
            {
                "name": f"func{i}",
                "fullname": f"bench::func{i}",
                "group": "perf",
                "params": {},
                "stats": {
                    "mean": 2.0,
                    "median": 2.0,
                    "min": 1.9,
                    "max": 2.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.5,
                },
            }
            for i in range(3)
        ]
        cand_cases = [
            {
                "name": f"func{i}",
                "fullname": f"bench::func{i}",
                "group": "perf",
                "params": {},
                "stats": {
                    "mean": 1.0,
                    "median": 1.0,
                    "min": 0.9,
                    "max": 1.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 1.0,
                },
            }
            for i in range(3)
        ]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", ref_cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cand_cases)

        runs = load_benchmark_folder(folder)
        deltas = compare_runs(select_reference_run(runs, "run-ref"), select_reference_run(runs, "run-cand"))
        summaries = summarize_groups(deltas)

        assert len(summaries) == 1
        s = summaries[0]
        assert s.improvements == 3
        assert s.regressions == 0
        assert s.unchanged == 0
        assert s.average_delta_pct == pytest.approx(-50.0)
        assert s.median_delta_pct == pytest.approx(-50.0)

    def test_unchanged_benchmark_counted_correctly(self, tmp_path: Path) -> None:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        cases = [
            {
                "name": "func1",
                "fullname": "bench::func1",
                "group": "base",
                "params": {},
                "stats": {
                    "mean": 1.0,
                    "median": 1.0,
                    "min": 0.95,
                    "max": 1.05,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 1.0,
                },
            },
        ]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cases)

        runs = load_benchmark_folder(folder)
        deltas = compare_runs(select_reference_run(runs, "run-ref"), select_reference_run(runs, "run-cand"))
        summaries = summarize_groups(deltas)

        s = summaries[0]
        assert s.unchanged == 1
        assert s.improvements == 0
        assert s.regressions == 0
