from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_park.core import (
    analyze_method_improvements,
    build_overall_improvement_summary,
)
from pytest_park.core.analysis import _format_benchmark_names
from pytest_park.data import load_benchmark_folder
from pytest_park.utils import select_reference_run


def _make_case_payload(
    name: str,
    fullname: str,
    group: str,
    mean: float,
    params: dict[str, str],
    *,
    median: float | None = None,
) -> dict:
    median_value = mean if median is None else median
    return {
        "name": name,
        "fullname": fullname,
        "group": group,
        "params": params,
        "stats": {
            "mean": mean,
            "median": median_value,
            "min": mean * 0.95,
            "max": mean * 1.05,
            "stddev": mean * 0.01,
            "rounds": 5,
            "iterations": 1,
            "ops": 1.0 / mean if mean else 0.0,
        },
    }


def _write_run_file(path: Path, run_id: str, tag: str, dt: str, cases: list[dict]) -> None:
    payload = {
        "datetime": dt,
        "metadata": {"run_id": run_id, "tag": tag},
        "benchmarks": cases,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def postfix_role_folder(tmp_path: Path) -> Path:
    """Run where implementation role is encoded in the method name postfix.

    func1_original / func1_new  ×  device=cpu / device=gpu.
    A second (reference) run holds the previous func1_new results.
    """
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    candidate_cases = [
        _make_case_payload("func1_original", "bench::func1_original", "examples", 3.0, {"device": "cpu"}),
        _make_case_payload("func1_new", "bench::func1_new", "examples", 2.0, {"device": "cpu"}),
        _make_case_payload("func1_original", "bench::func1_original", "examples", 6.0, {"device": "gpu"}),
        _make_case_payload("func1_new", "bench::func1_new", "examples", 4.0, {"device": "gpu"}),
    ]
    reference_cases = [
        _make_case_payload("func1_new", "bench::func1_new", "examples", 2.5, {"device": "cpu"}),
        _make_case_payload("func1_new", "bench::func1_new", "examples", 5.0, {"device": "gpu"}),
    ]

    _write_run_file(folder / "run_reference.json", "run-ref", "ref", "2026-02-10T10:00:00Z", reference_cases)
    _write_run_file(folder / "run_candidate.json", "run-cand", "cand", "2026-02-12T10:00:00Z", candidate_cases)
    return folder


@pytest.fixture()
def param_role_folder(tmp_path: Path) -> Path:
    """Run where implementation role comes from an ``implementation`` param.

    func1  ×  device=cpu/gpu  ×  implementation=original/new.
    A reference run holds the previous *new* results.
    """
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    candidate_cases = [
        _make_case_payload("func1", "bench::func1", "examples", 3.0, {"device": "cpu", "implementation": "original"}),
        _make_case_payload("func1", "bench::func1", "examples", 2.0, {"device": "cpu", "implementation": "new"}),
        _make_case_payload("func1", "bench::func1", "examples", 6.0, {"device": "gpu", "implementation": "original"}),
        _make_case_payload("func1", "bench::func1", "examples", 4.0, {"device": "gpu", "implementation": "new"}),
        _make_case_payload("func2", "bench::func2", "examples", 5.0, {"device": "cpu", "implementation": "original"}),
        _make_case_payload("func2", "bench::func2", "examples", 3.0, {"device": "cpu", "implementation": "new"}),
    ]
    reference_cases = [
        _make_case_payload("func1", "bench::func1", "examples", 2.5, {"device": "cpu", "implementation": "new"}),
        _make_case_payload("func1", "bench::func1", "examples", 5.0, {"device": "gpu", "implementation": "new"}),
        _make_case_payload("func2", "bench::func2", "examples", 3.5, {"device": "cpu", "implementation": "new"}),
    ]

    _write_run_file(folder / "run_reference.json", "run-ref", "ref", "2026-02-10T10:00:00Z", reference_cases)
    _write_run_file(folder / "run_candidate.json", "run-cand", "cand", "2026-02-12T10:00:00Z", candidate_cases)
    return folder


@pytest.fixture()
def postfix_role_unparameterized_original_folder(tmp_path: Path) -> Path:
    """Run where the original implementation has no params but new variants do."""
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    candidate_cases = [
        _make_case_payload("func1_original", "bench::func1_original", "", 3.0, {}),
        _make_case_payload("func1_new", "bench::func1_new", "", 2.0, {"device": "cpu"}),
        _make_case_payload("func1_new", "bench::func1_new", "", 4.0, {"device": "gpu"}),
    ]
    reference_cases = [
        _make_case_payload("func1_new", "bench::func1_new", "", 2.5, {"device": "cpu"}),
        _make_case_payload("func1_new", "bench::func1_new", "", 5.0, {"device": "gpu"}),
    ]

    _write_run_file(folder / "run_reference.json", "run-ref", "ref", "2026-02-10T10:00:00Z", reference_cases)
    _write_run_file(folder / "run_candidate.json", "run-cand", "cand", "2026-02-12T10:00:00Z", candidate_cases)
    return folder


@pytest.fixture()
def postfix_role_distinct_medians_folder(tmp_path: Path) -> Path:
    """Run where mean- and median-based improvements differ."""
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    candidate_cases = [
        _make_case_payload("func1_original", "bench::func1_original", "", 10.0, {}, median=6.0),
        _make_case_payload("func1_new", "bench::func1_new", "", 8.0, {"device": "cpu"}, median=5.0),
    ]
    reference_cases = [
        _make_case_payload("func1_new", "bench::func1_new", "", 9.0, {"device": "cpu"}, median=7.0),
    ]

    _write_run_file(folder / "run_reference.json", "run-ref", "ref", "2026-02-10T10:00:00Z", reference_cases)
    _write_run_file(folder / "run_candidate.json", "run-cand", "cand", "2026-02-12T10:00:00Z", candidate_cases)
    return folder


def test_postfix_roles_per_device_vs_orig(postfix_role_folder) -> None:
    """func1_new and func1_original in same run should each compare per device."""
    runs = load_benchmark_folder(postfix_role_folder)
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=None,
        exclude_params=["device"],
    )

    assert len(improvements) == 2
    methods = {imp.method for imp in improvements}
    assert methods == {"func1[device=cpu]", "func1[device=gpu]"}

    cpu_imp = next(imp for imp in improvements if imp.method == "func1[device=cpu]")
    gpu_imp = next(imp for imp in improvements if imp.method == "func1[device=gpu]")

    assert cpu_imp.avg_vs_orig_time == pytest.approx(1.0)  # 3.0 - 2.0
    assert cpu_imp.avg_vs_orig_pct == pytest.approx(100.0 / 3.0)  # 33.33 %
    assert gpu_imp.avg_vs_orig_time == pytest.approx(2.0)  # 6.0 - 4.0
    assert gpu_imp.avg_vs_orig_pct == pytest.approx(100.0 / 3.0)  # 33.33 %

    assert cpu_imp.avg_vs_prev_time is None
    assert gpu_imp.avg_vs_prev_time is None


def test_postfix_roles_vs_reference_run(postfix_role_folder) -> None:
    """vs_prev columns are populated when a reference run is provided."""
    runs = load_benchmark_folder(postfix_role_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=reference_run,
        exclude_params=["device"],
    )

    assert len(improvements) == 2

    cpu_imp = next(imp for imp in improvements if imp.method == "func1[device=cpu]")
    gpu_imp = next(imp for imp in improvements if imp.method == "func1[device=gpu]")

    # candidate new: 2.0 vs reference new: 2.5 → improved by 0.5 s / 20 %
    assert cpu_imp.avg_vs_prev_time == pytest.approx(0.5)
    assert cpu_imp.avg_vs_prev_pct == pytest.approx(20.0)
    # candidate new: 4.0 vs reference new: 5.0 → improved by 1.0 s / 20 %
    assert gpu_imp.avg_vs_prev_time == pytest.approx(1.0)
    assert gpu_imp.avg_vs_prev_pct == pytest.approx(20.0)
    assert cpu_imp.current_benchmark_name == "func1_new"
    assert cpu_imp.comparison_benchmark_name == "func1_new"


def test_param_roles_per_device_vs_orig(param_role_folder) -> None:
    """implementation=new/original param is auto-detected as role."""
    runs = load_benchmark_folder(param_role_folder)
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=None,
        exclude_params=["device"],
    )

    assert len(improvements) == 3
    methods = {imp.method for imp in improvements}
    assert methods == {"func1[device=cpu]", "func1[device=gpu]", "func2[device=cpu]"}

    imp_f1_cpu = next(imp for imp in improvements if imp.method == "func1[device=cpu]")
    imp_f1_gpu = next(imp for imp in improvements if imp.method == "func1[device=gpu]")
    imp_f2_cpu = next(imp for imp in improvements if imp.method == "func2[device=cpu]")

    assert imp_f1_cpu.avg_vs_orig_time == pytest.approx(1.0)  # 3.0 - 2.0
    assert imp_f1_gpu.avg_vs_orig_time == pytest.approx(2.0)  # 6.0 - 4.0
    assert imp_f2_cpu.avg_vs_orig_time == pytest.approx(2.0)  # 5.0 - 3.0
    assert imp_f2_cpu.avg_vs_orig_pct == pytest.approx(40.0)  # 2/5 * 100


def test_format_benchmark_names_uses_new_lines_when_multiple_names_exist() -> None:
    assert _format_benchmark_names({"func1_gpu", "func1_cpu"}) == "func1_cpu\nfunc1_gpu"


def test_param_roles_vs_reference_run(param_role_folder) -> None:
    """Temporal comparison (vs reference run) works with param-based roles."""
    runs = load_benchmark_folder(param_role_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=reference_run,
        exclude_params=["device"],
    )

    assert len(improvements) == 3

    imp_f1_cpu = next(imp for imp in improvements if imp.method == "func1[device=cpu]")
    imp_f1_gpu = next(imp for imp in improvements if imp.method == "func1[device=gpu]")
    imp_f2_cpu = next(imp for imp in improvements if imp.method == "func2[device=cpu]")

    # func1 cpu: cand new=2.0, ref new=2.5 → +0.5 s / +20 %
    assert imp_f1_cpu.avg_vs_prev_time == pytest.approx(0.5)
    assert imp_f1_cpu.avg_vs_prev_pct == pytest.approx(20.0)
    # func1 gpu: cand new=4.0, ref new=5.0 → +1.0 s / +20 %
    assert imp_f1_gpu.avg_vs_prev_time == pytest.approx(1.0)
    assert imp_f1_gpu.avg_vs_prev_pct == pytest.approx(20.0)
    # func2 cpu: cand new=3.0, ref new=3.5 → +0.5 s / ≈14.3 %
    assert imp_f2_cpu.avg_vs_prev_time == pytest.approx(0.5)
    assert imp_f2_cpu.avg_vs_prev_pct == pytest.approx(100.0 / 7.0, rel=1e-3)


def test_postfix_roles_fall_back_to_unparameterized_original(postfix_role_unparameterized_original_folder) -> None:
    """A generic original baseline should compare against each parameterized new variant."""
    runs = load_benchmark_folder(postfix_role_unparameterized_original_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(candidate_run=candidate_run, reference_run=reference_run)

    cpu_imp = next(imp for imp in improvements if imp.group == "params:device=cpu" and imp.method == "func1")
    gpu_imp = next(imp for imp in improvements if imp.group == "params:device=gpu" and imp.method == "func1")

    assert cpu_imp.avg_vs_orig_time == pytest.approx(1.0)  # 3.0 - 2.0
    assert cpu_imp.avg_vs_orig_pct == pytest.approx(100.0 / 3.0, rel=1e-3)
    assert gpu_imp.avg_vs_orig_time == pytest.approx(-1.0)  # 3.0 - 4.0
    assert gpu_imp.avg_vs_orig_pct == pytest.approx(-100.0 / 3.0, rel=1e-3)

    assert cpu_imp.avg_vs_prev_time == pytest.approx(0.5)  # 2.5 - 2.0
    assert gpu_imp.avg_vs_prev_time == pytest.approx(1.0)  # 5.0 - 4.0


def test_postfix_roles_use_median_stats_for_med_columns(postfix_role_distinct_medians_folder) -> None:
    """Median columns should compare benchmark median values, not mean values."""
    runs = load_benchmark_folder(postfix_role_distinct_medians_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(candidate_run=candidate_run, reference_run=reference_run)

    imp = next(imp for imp in improvements if imp.method == "func1" and imp.group == "params:device=cpu")

    assert imp.avg_vs_orig_time == pytest.approx(2.0)  # 10.0 - 8.0
    assert imp.med_vs_orig_time == pytest.approx(1.0)  # 6.0 - 5.0
    assert imp.avg_vs_prev_time == pytest.approx(1.0)  # 9.0 - 8.0
    assert imp.med_vs_prev_time == pytest.approx(2.0)  # 7.0 - 5.0


def test_overall_summary_aggregates_correctly(param_role_folder) -> None:
    """Overall summary aggregates all per-method/device entries correctly."""
    runs = load_benchmark_folder(param_role_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=reference_run,
        exclude_params=["device"],
    )

    summary = build_overall_improvement_summary(improvements)

    assert summary["count"] == 3
    assert summary["avg_vs_orig_time"] is not None
    assert summary["avg_vs_orig_pct"] is not None
    assert summary["avg_vs_prev_time"] is not None
    assert summary["avg_vs_prev_pct"] is not None

    # avg of time savings (1.0, 2.0, 2.0) = 5/3 ≈ 1.667
    assert summary["avg_vs_orig_time"] == pytest.approx(5.0 / 3.0, rel=1e-3)


def test_overall_summary_empty() -> None:
    summary = build_overall_improvement_summary([])
    assert summary["count"] == 0
    assert all(v is None for k, v in summary.items() if k != "count")
