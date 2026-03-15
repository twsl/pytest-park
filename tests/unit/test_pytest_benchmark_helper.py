from __future__ import annotations

from typing import Any, cast

from pytest_park.core import analyze_method_improvements
from pytest_park.data import build_benchmark_run
from pytest_park.pytest_benchmark import default_pytest_benchmark_group_stats


class _Config:
    def __init__(self, original_postfix: str = "", reference_postfix: str = "") -> None:
        self.option = type(
            "Opt",
            (),
            {
                "benchmark_original_postfix": original_postfix,
                "benchmark_reference_postfix": reference_postfix,
            },
        )()


def test_default_group_stats_splits_name_parts() -> None:
    config = _Config(reference_postfix="_ref")
    benchmarks: list[dict[str, Any]] = [
        {
            "name": "sort_values_ref[cpu]",
            "extra_info": {},
        },
        {
            "name": "reduce_sum_ref[gpu]",
            "extra_info": {},
        },
    ]

    grouped = dict(default_pytest_benchmark_group_stats(config, benchmarks, "group"))
    extra_info = cast(dict[str, object], benchmarks[0]["extra_info"])

    assert set(grouped.keys()) == {"sort_values", "reduce_sum"}
    assert extra_info["pytest_park_name_parts"] == {
        "base_name": "sort_values",
        "parameters": "cpu",
        "postfix": "_ref",
    }


def test_default_group_stats_keeps_original_grouping_for_custom_group_by() -> None:
    config = _Config(reference_postfix="_ref")
    benchmarks = [{"name": "sort_values_ref[cpu]", "extra_info": {}}]

    grouped = dict(default_pytest_benchmark_group_stats(config, benchmarks, "custom:scenario"))

    assert list(grouped.keys()) == ["sort_values_ref[cpu]"]


def test_default_group_stats_accepts_postfix_arguments() -> None:
    config = _Config()
    benchmarks = [{"name": "sort_values_ref[cpu]", "extra_info": {}}]

    grouped = dict(
        default_pytest_benchmark_group_stats(
            config,
            benchmarks,
            "group",
            reference_postfix="_ref",
        )
    )

    assert list(grouped.keys()) == ["sort_values"]
    assert benchmarks[0]["group"] == "sort_values"


def test_default_group_stats_groups_by_postfix_with_custom_values() -> None:
    config = _Config(original_postfix="_orig", reference_postfix="_ref")
    benchmarks = [
        {"name": "sort_values_orig[cpu]", "extra_info": {}},
        {"name": "sort_values_ref[cpu]", "extra_info": {}},
        {"name": "sort_values[cpu]", "extra_info": {}},
    ]

    grouped = dict(
        default_pytest_benchmark_group_stats(
            config,
            benchmarks,
            "postfix",
            group_values_by_postfix={
                "_orig": "original",
                "_ref": "reference",
                "none": "unlabeled",
            },
        )
    )

    assert set(grouped.keys()) == {"original", "reference", "unlabeled"}


def test_default_group_stats_drops_fully_ignored_param_grouping() -> None:
    config = _Config()
    benchmarks = [
        {
            "name": "sort_values_ref[cpu]",
            "param": "cpu",
            "params": {"device": "cpu"},
            "extra_info": {},
        }
    ]

    grouped = dict(
        default_pytest_benchmark_group_stats(
            config,
            benchmarks,
            "param",
            ignore_params=["device"],
        )
    )

    assert list(grouped.keys()) == [None]
    assert benchmarks[0]["group"] is None


def test_live_grouped_benchmarks_prefer_persisted_group_over_raw_params() -> None:
    config = _Config(original_postfix="original", reference_postfix="new")
    benchmarks: list[dict[str, Any]] = [
        {
            "name": "test_func1_original",
            "fullname": "tests/unit/examples/test_func1.py::test_func1_original",
            "param": "",
            "params": {},
            "extra_info": {},
            "stats": {
                "mean": 3.0,
                "median": 3.0,
                "min": 2.9,
                "max": 3.1,
                "stddev": 0.01,
                "rounds": 5,
                "iterations": 1,
                "ops": 1.0 / 3.0,
            },
        },
        {
            "name": "test_func1_new[cpu]",
            "fullname": "tests/unit/examples/test_func1.py::test_func1_new[cpu]",
            "param": "cpu",
            "params": {"device": "cpu"},
            "extra_info": {},
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
        },
    ]

    default_pytest_benchmark_group_stats(
        config,
        benchmarks,
        "group",
        original_postfix="original",
        reference_postfix="new",
        ignore_params=["device"],
    )

    candidate_run = build_benchmark_run(
        benchmarks,
        run_id="run-live",
        source_file="<live>",
        original_postfix="original",
        reference_postfix="new",
    )

    improvements = analyze_method_improvements(candidate_run=candidate_run, reference_run=None)

    assert len(improvements) == 1
    assert improvements[0].group == "test_func1"
    assert improvements[0].method == "test_func1"


def test_build_benchmark_run_normalizes_live_benchmark_entries() -> None:
    run = build_benchmark_run(
        [
            {
                "name": "sort_values_ref[cpu]",
                "fullname": "tests/test_demo.py::test_sort_values_ref[cpu]",
                "group": "sorting",
                "params": {"device": "cpu"},
                "param": "cpu",
                "extra_info": {},
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
        run_id="run-live",
        source_file="<live>",
        reference_postfix="_ref",
    )

    assert run.run_id == "run-live"
    assert len(run.cases) == 1
    assert run.cases[0].base_name == "sort_values"
    assert run.cases[0].method_postfix == "_ref"
