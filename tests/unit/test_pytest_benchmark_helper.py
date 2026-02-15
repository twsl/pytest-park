from __future__ import annotations

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
    benchmarks = [
        {
            "name": "sort_values_ref[cpu]",
            "extra_info": {},
        },
        {
            "name": "reduce_sum_ref[gpu]",
            "extra_info": {},
        },
    ]

    grouped = default_pytest_benchmark_group_stats(config, benchmarks, "group")

    assert set(grouped.keys()) == {"sort_values", "reduce_sum"}
    assert benchmarks[0]["extra_info"]["pytest_park_name_parts"] == {
        "base_name": "sort_values",
        "parameters": "cpu",
        "postfix": "_ref",
    }


def test_default_group_stats_keeps_original_grouping_for_custom_group_by() -> None:
    config = _Config(reference_postfix="_ref")
    benchmarks = [{"name": "sort_values_ref[cpu]", "extra_info": {}}]

    grouped = default_pytest_benchmark_group_stats(config, benchmarks, "custom:scenario")

    assert list(grouped.keys()) == ["sort_values_ref[cpu]"]


def test_default_group_stats_accepts_postfix_arguments() -> None:
    config = _Config()
    benchmarks = [{"name": "sort_values_ref[cpu]", "extra_info": {}}]

    grouped = default_pytest_benchmark_group_stats(
        config,
        benchmarks,
        "group",
        reference_postfix="_ref",
    )

    assert list(grouped.keys()) == ["sort_values"]


def test_default_group_stats_groups_by_postfix_with_custom_values() -> None:
    config = _Config(original_postfix="_orig", reference_postfix="_ref")
    benchmarks = [
        {"name": "sort_values_orig[cpu]", "extra_info": {}},
        {"name": "sort_values_ref[cpu]", "extra_info": {}},
        {"name": "sort_values[cpu]", "extra_info": {}},
    ]

    grouped = default_pytest_benchmark_group_stats(
        config,
        benchmarks,
        "postfix",
        group_values_by_postfix={
            "_orig": "original",
            "_ref": "reference",
            "none": "unlabeled",
        },
    )

    assert set(grouped.keys()) == {"original", "reference", "unlabeled"}
