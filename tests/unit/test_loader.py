from __future__ import annotations

import json

from pytest_park.data import load_benchmark_folder


def test_load_benchmark_folder_parses_runs_and_cases(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)

    assert len(runs) == 3
    assert runs[0].run_id == "run-reference"
    assert runs[-1].run_id == "run-candidate-v2"

    first_case = runs[0].cases[0]
    assert first_case.benchmark_group == "sorting"
    assert "algo" in first_case.marks
    assert first_case.params["device"] == "cpu"
    assert first_case.custom_groups["scenario"] == "cpu-baseline"
    assert first_case.normalized_name == first_case.name
    assert first_case.normalized_fullname == first_case.fullname
    assert first_case.base_name == first_case.name
    assert first_case.method_parameters is None
    assert first_case.method_postfix is None


def test_load_benchmark_folder_splits_postfix_and_params(tmp_path) -> None:
    folder = tmp_path / "benchmarks"
    folder.mkdir()
    payload = {
        "datetime": "2026-02-10T10:00:00Z",
        "metadata": {"run_id": "run-reference", "tag": "reference"},
        "benchmarks": [
            {
                "name": "sort_values_ref[cpu-fast]",
                "fullname": "bench::sort_values_ref[cpu-fast]",
                "group": "sorting",
                "params": {"device": "cpu"},
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
        ],
    }
    (folder / "run_reference.json").write_text(json.dumps(payload), encoding="utf-8")

    runs = load_benchmark_folder(folder, reference_postfix="_ref")
    case = runs[0].cases[0]

    assert case.name == "sort_values_ref[cpu-fast]"
    assert case.base_name == "sort_values"
    assert case.method_parameters == "cpu-fast"
    assert case.method_postfix == "_ref"
    assert case.normalized_name == "sort_values[cpu-fast]"
    assert case.normalized_fullname == "bench::sort_values[cpu-fast]"


def test_load_benchmark_folder_auto_detects_original_new_postfixes(tmp_path) -> None:
    folder = tmp_path / "benchmarks"
    folder.mkdir()
    payload = {
        "datetime": "2026-02-10T10:00:00Z",
        "metadata": {"run_id": "run-1", "tag": "candidate"},
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
        ],
    }
    (folder / "run.json").write_text(json.dumps(payload), encoding="utf-8")

    runs = load_benchmark_folder(folder)
    original_case, new_case = runs[0].cases

    assert original_case.base_name == "func1"
    assert original_case.method_postfix == "_original"
    assert original_case.normalized_name == "func1"

    assert new_case.base_name == "func1"
    assert new_case.method_postfix == "_new"
    assert new_case.normalized_name == "func1"
