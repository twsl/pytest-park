from __future__ import annotations

import json
from pathlib import Path

from pytest_park.core import (
    build_method_group_split_bars,
    compare_method_to_all_prior_runs,
)
from pytest_park.data import load_benchmark_folder
from pytest_park.utils import select_reference_run


def test_compare_method_to_all_prior_runs(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    candidate = select_reference_run(runs, "candidate-v2")

    compared = compare_method_to_all_prior_runs(runs, candidate, "sort_values", ["device"])

    assert len(compared) == 4
    assert {item.reference_run_id for item in compared} == {"run-reference", "run-candidate-v1"}
    assert all(item.candidate_run_id == "run-candidate-v2" for item in compared)


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
    arguments = [item.argument for item in split_rows["func1"]]
    assert arguments == ["device=cpu", "device=gpu"]
    assert [round(item.original, 2) for item in split_rows["func1"]] == [3.0, 3.5]
    assert [round(item.new, 2) for item in split_rows["func1"]] == [2.0, 2.5]
