from __future__ import annotations

import json

from pytest_park.core import (
    build_method_group_split_bars,
    build_method_history,
    build_method_statistics,
    build_overview_statistics,
    compare_method_history_to_reference,
    compare_method_to_all_prior_runs,
)
from pytest_park.data import load_benchmark_folder
from pytest_park.utils import (
    build_group_label,
    build_trends,
    compare_runs,
    list_methods,
    select_candidate_run,
    select_reference_run,
    summarize_groups,
)


def test_compare_runs_reference_vs_candidate(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    reference = select_reference_run(runs, "reference")
    candidate = select_candidate_run(runs, "candidate-v2", reference)

    deltas = compare_runs(reference, candidate)
    assert len(deltas) == 3
    assert any(item.delta_pct < 0 for item in deltas)


def test_grouping_priority_uses_custom_then_group(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    case = runs[0].cases[0]

    default_label = build_group_label(case)
    custom_label = build_group_label(case, ["custom:scenario", "param:device"])

    assert default_label.startswith("custom:")
    assert custom_label == "custom:scenario=cpu-baseline | param:device=cpu"


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


def test_distinct_params_and_method_history(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    reference = select_reference_run(runs, "reference")
    candidate = select_candidate_run(runs, "candidate-v2", reference)

    methods = list_methods(runs)
    assert "sort_values" in methods

    deltas = compare_runs(reference, candidate, ["group"], ["device"])
    overview = build_overview_statistics(deltas)
    method_stats = build_method_statistics(deltas, "sort_values")
    history = build_method_history(runs, "sort_values", ["device"])
    compared_history = compare_method_history_to_reference(runs, reference, "sort_values", ["device"])

    assert overview["count"] == len(deltas)
    assert method_stats is not None
    assert method_stats["count"] >= 1
    assert history
    assert compared_history


def test_compare_method_to_all_prior_runs(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    candidate = select_reference_run(runs, "candidate-v2")

    compared = compare_method_to_all_prior_runs(runs, candidate, "sort_values", ["device"])

    assert len(compared) == 4
    assert {str(item["reference_run_id"]) for item in compared} == {"run-reference", "run-candidate-v1"}
    assert all(str(item["candidate_run_id"]) == "run-candidate-v2" for item in compared)


def test_build_method_group_split_bars_by_shared_argument(tmp_path) -> None:
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    payload = {
        "datetime": "2026-02-12T10:00:00Z",
        "metadata": {"run_id": "run-current", "tag": "current"},
        "benchmarks": [
            {
                "name": "func1_original",
                "fullname": "bench::func1_original",
                "group": "examples",
                "params": {"device": "cpu"},
                "stats": {
                    "mean": 3.0,
                    "median": 3.0,
                    "min": 2.9,
                    "max": 3.1,
                    "stddev": 0.01,
                    "rounds": 1,
                    "iterations": 1,
                    "ops": 0.33,
                },
            },
            {
                "name": "func1_new",
                "fullname": "bench::func1_new",
                "group": "examples",
                "params": {"device": "cpu"},
                "stats": {
                    "mean": 2.0,
                    "median": 2.0,
                    "min": 1.9,
                    "max": 2.1,
                    "stddev": 0.01,
                    "rounds": 1,
                    "iterations": 1,
                    "ops": 0.5,
                },
            },
            {
                "name": "func1_original",
                "fullname": "bench::func1_original",
                "group": "examples",
                "params": {"device": "gpu"},
                "stats": {
                    "mean": 3.5,
                    "median": 3.5,
                    "min": 3.4,
                    "max": 3.6,
                    "stddev": 0.01,
                    "rounds": 1,
                    "iterations": 1,
                    "ops": 0.28,
                },
            },
            {
                "name": "func1_new",
                "fullname": "bench::func1_new",
                "group": "examples",
                "params": {"device": "gpu"},
                "stats": {
                    "mean": 2.5,
                    "median": 2.5,
                    "min": 2.4,
                    "max": 2.6,
                    "stddev": 0.01,
                    "rounds": 1,
                    "iterations": 1,
                    "ops": 0.4,
                },
            },
        ],
    }
    (folder / "run_current.json").write_text(json.dumps(payload), encoding="utf-8")

    runs = load_benchmark_folder(folder)
    split_rows = build_method_group_split_bars(runs[0])

    assert "func1" in split_rows
    arguments = [str(item["argument"]) for item in split_rows["func1"]]
    assert arguments == ["device=cpu", "device=gpu"]
    assert [round(float(item["original"]), 2) for item in split_rows["func1"]] == [3.0, 3.5]
    assert [round(float(item["new"]), 2) for item in split_rows["func1"]] == [2.0, 2.5]
