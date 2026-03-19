from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_park.core import (
    build_method_history,
    build_method_statistics,
    build_overview_statistics,
    compare_method_history_to_reference,
)
from pytest_park.data import load_benchmark_folder
from pytest_park.utils import (
    compare_runs,
    list_methods,
    select_candidate_run,
    select_reference_run,
)


def _write_run_payload(path: Path, run_id: str, tag: str, dt: str, cases: list[dict]) -> None:
    payload = {
        "datetime": dt,
        "metadata": {"run_id": run_id, "tag": tag},
        "benchmarks": cases,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_compare_runs_reference_vs_candidate(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    reference = select_reference_run(runs, "reference")
    candidate = select_candidate_run(runs, "candidate-v2", reference)

    deltas = compare_runs(reference, candidate)
    assert len(deltas) == 3
    assert any(item.delta_pct < 0 for item in deltas)


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

    assert overview.count == len(deltas)
    assert method_stats is not None
    assert method_stats.count >= 1
    assert history
    assert compared_history


class TestCompareRunsIgnoredParams:
    """implementation / impl / variant params are excluded from the match key."""

    @pytest.fixture()
    def runs_with_implementation_param(self, tmp_path: Path) -> Path:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        ref_cases = [
            {
                "name": "sort_values",
                "fullname": "bench::sort_values",
                "group": "sorting",
                "params": {"device": "cpu", "implementation": "reference"},
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
        ]
        cand_cases = [
            {
                "name": "sort_values",
                "fullname": "bench::sort_values",
                "group": "sorting",
                "params": {"device": "cpu", "implementation": "new"},
                "stats": {
                    "mean": 1.5,
                    "median": 1.5,
                    "min": 1.4,
                    "max": 1.6,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.67,
                },
            }
        ]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", ref_cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cand_cases)
        return folder

    @pytest.fixture()
    def runs_with_impl_param(self, tmp_path: Path) -> Path:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        ref_cases = [
            {
                "name": "encode",
                "fullname": "bench::encode",
                "group": "codec",
                "params": {"impl": "v1"},
                "stats": {
                    "mean": 3.0,
                    "median": 3.0,
                    "min": 2.9,
                    "max": 3.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.33,
                },
            }
        ]
        cand_cases = [
            {
                "name": "encode",
                "fullname": "bench::encode",
                "group": "codec",
                "params": {"impl": "v2"},
                "stats": {
                    "mean": 2.5,
                    "median": 2.5,
                    "min": 2.4,
                    "max": 2.6,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.4,
                },
            }
        ]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", ref_cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cand_cases)
        return folder

    @pytest.fixture()
    def runs_with_variant_param(self, tmp_path: Path) -> Path:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        ref_cases = [
            {
                "name": "decode",
                "fullname": "bench::decode",
                "group": "codec",
                "params": {"variant": "alpha", "device": "cpu"},
                "stats": {
                    "mean": 4.0,
                    "median": 4.0,
                    "min": 3.9,
                    "max": 4.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.25,
                },
            }
        ]
        cand_cases = [
            {
                "name": "decode",
                "fullname": "bench::decode",
                "group": "codec",
                "params": {"variant": "beta", "device": "cpu"},
                "stats": {
                    "mean": 3.0,
                    "median": 3.0,
                    "min": 2.9,
                    "max": 3.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.33,
                },
            }
        ]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", ref_cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cand_cases)
        return folder

    def test_implementation_param_ignored_in_default_comparison(self, runs_with_implementation_param: Path) -> None:
        """Cases differing only by 'implementation' param should be matched."""
        runs = load_benchmark_folder(runs_with_implementation_param)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate)

        assert len(deltas) == 1
        assert deltas[0].benchmark_name == "sort_values"
        assert deltas[0].delta_pct == pytest.approx(-25.0)  # 1.5 vs 2.0

    def test_impl_param_ignored_in_default_comparison(self, runs_with_impl_param: Path) -> None:
        """Cases differing only by 'impl' param should be matched."""
        runs = load_benchmark_folder(runs_with_impl_param)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate)

        assert len(deltas) == 1
        assert deltas[0].benchmark_name == "encode"

    def test_variant_param_ignored_in_default_comparison(self, runs_with_variant_param: Path) -> None:
        """Cases differing only by 'variant' param should be matched."""
        runs = load_benchmark_folder(runs_with_variant_param)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate)

        # 'variant' is ignored; 'device' is kept → same key → matched
        assert len(deltas) == 1
        assert deltas[0].benchmark_name == "decode"


class TestCompareRunsDistinctParams:
    """distinct_params replaces the default ignored-params logic."""

    @pytest.fixture()
    def multi_param_folder(self, tmp_path: Path) -> Path:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        ref_cases = [
            {
                "name": "sort_values",
                "fullname": "bench::sort_values",
                "group": "sorting",
                "params": {"device": "cpu", "size": "small", "implementation": "v1"},
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
            {
                "name": "sort_values",
                "fullname": "bench::sort_values",
                "group": "sorting",
                "params": {"device": "gpu", "size": "small", "implementation": "v1"},
                "stats": {
                    "mean": 1.5,
                    "median": 1.5,
                    "min": 1.4,
                    "max": 1.6,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.67,
                },
            },
        ]
        cand_cases = [
            {
                "name": "sort_values",
                "fullname": "bench::sort_values",
                "group": "sorting",
                "params": {"device": "cpu", "size": "small", "implementation": "v2"},
                "stats": {
                    "mean": 1.8,
                    "median": 1.8,
                    "min": 1.7,
                    "max": 1.9,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.56,
                },
            },
            {
                "name": "sort_values",
                "fullname": "bench::sort_values",
                "group": "sorting",
                "params": {"device": "gpu", "size": "small", "implementation": "v2"},
                "stats": {
                    "mean": 1.2,
                    "median": 1.2,
                    "min": 1.1,
                    "max": 1.3,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.83,
                },
            },
        ]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", ref_cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cand_cases)
        return folder

    def test_distinct_params_matches_only_on_specified_keys(self, multi_param_folder: Path) -> None:
        """Only device is used as a match key; size and implementation are ignored."""
        runs = load_benchmark_folder(multi_param_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, distinct_params=["device"])

        assert len(deltas) == 2
        devices = {delta.params.get("device") for delta in deltas}
        assert devices == {"cpu", "gpu"}

    def test_distinct_params_no_match_when_key_differs(self, multi_param_folder: Path) -> None:
        """Using a param key that differs between runs yields no matches."""
        runs = load_benchmark_folder(multi_param_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        # implementation=v1 (ref) vs implementation=v2 (cand) → differ → no match
        deltas = compare_runs(reference, candidate, distinct_params=["implementation"])

        assert len(deltas) == 0

    def test_compare_runs_with_group_by_and_distinct_params(self, multi_param_folder: Path) -> None:
        """group_by and distinct_params can be combined independently."""
        runs = load_benchmark_folder(multi_param_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["param:device"], distinct_params=["device"])

        assert len(deltas) == 2
        assert all(delta.group_label.startswith("param:device=") for delta in deltas)
        cpu_delta = next(d for d in deltas if d.group_label == "param:device=cpu")
        assert cpu_delta.delta_pct == pytest.approx(-10.0)  # (1.8 - 2.0) / 2.0 * 100


class TestCompareRunsGroupBy:
    """Group labels in deltas reflect the chosen group_by strategy."""

    @pytest.fixture()
    def two_run_folder(self, tmp_path: Path) -> Path:
        folder = tmp_path / "benchmarks"
        folder.mkdir()

        def _case(name: str, group: str, mean: float, device: str, marks: list[str] | None = None) -> dict:
            return {
                "name": name,
                "fullname": f"bench::{name}",
                "group": group,
                "params": {"device": device},
                "marks": marks or [],
                "stats": {
                    "mean": mean,
                    "median": mean,
                    "min": mean * 0.95,
                    "max": mean * 1.05,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 1.0 / mean,
                },
            }

        ref_cases = [_case("func1", "io", 2.0, "cpu", ["fast"]), _case("func2", "compute", 4.0, "gpu")]
        cand_cases = [_case("func1", "io", 1.5, "cpu", ["fast"]), _case("func2", "compute", 3.0, "gpu")]
        _write_run_payload(folder / "ref.json", "run-ref", "ref", "2026-01-01T00:00:00Z", ref_cases)
        _write_run_payload(folder / "cand.json", "run-cand", "cand", "2026-01-02T00:00:00Z", cand_cases)
        return folder

    def test_group_by_benchmark_group(self, two_run_folder: Path) -> None:
        runs = load_benchmark_folder(two_run_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["benchmark_group"])

        labels = {d.group_label for d in deltas}
        assert "io" in labels
        assert "compute" in labels

    def test_group_by_name(self, two_run_folder: Path) -> None:
        runs = load_benchmark_folder(two_run_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["name"])

        assert {d.group_label for d in deltas} == {"func1", "func2"}

    def test_group_by_marks(self, two_run_folder: Path) -> None:
        runs = load_benchmark_folder(two_run_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["marks"])

        func1_delta = next(d for d in deltas if d.benchmark_name == "func1")
        func2_delta = next(d for d in deltas if d.benchmark_name == "func2")
        assert func1_delta.group_label == "marks:fast"
        assert func2_delta.group_label == "ungrouped"

    def test_group_by_specific_param(self, two_run_folder: Path) -> None:
        runs = load_benchmark_folder(two_run_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["param:device"])

        assert {d.group_label for d in deltas} == {"param:device=cpu", "param:device=gpu"}

    def test_group_by_unknown_token_produces_ungrouped(self, two_run_folder: Path) -> None:
        runs = load_benchmark_folder(two_run_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["totally_unknown"])

        assert all(d.group_label == "ungrouped" for d in deltas)

    def test_group_by_multiple_tokens(self, two_run_folder: Path) -> None:
        runs = load_benchmark_folder(two_run_folder)
        reference = select_reference_run(runs, "run-ref")
        candidate = select_reference_run(runs, "run-cand")

        deltas = compare_runs(reference, candidate, group_by=["benchmark_group", "param:device"])

        func1_delta = next(d for d in deltas if d.benchmark_name == "func1")
        assert func1_delta.group_label == "io | param:device=cpu"
