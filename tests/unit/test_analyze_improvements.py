from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_park.core import (
    analyze_method_improvements,
    build_overall_improvement_summary,
    build_postfix_comparison,
    build_regression_improvements,
)
from pytest_park.core.improvements import _format_benchmark_names
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

    assert cpu_imp.avg_vs_orig_time == pytest.approx(-1.0)  # 2.0 - 3.0
    assert cpu_imp.avg_vs_orig_pct == pytest.approx(-100.0 / 3.0)  # -33.33 %
    assert gpu_imp.avg_vs_orig_time == pytest.approx(-2.0)  # 4.0 - 6.0
    assert gpu_imp.avg_vs_orig_pct == pytest.approx(-100.0 / 3.0)  # -33.33 %

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

    # candidate new: 2.0 vs reference new: 2.5 → improved by -0.5 s / -20 %
    assert cpu_imp.avg_vs_prev_time == pytest.approx(-0.5)
    assert cpu_imp.avg_vs_prev_pct == pytest.approx(-20.0)
    # candidate new: 4.0 vs reference new: 5.0 → improved by -1.0 s / -20 %
    assert gpu_imp.avg_vs_prev_time == pytest.approx(-1.0)
    assert gpu_imp.avg_vs_prev_pct == pytest.approx(-20.0)
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

    assert imp_f1_cpu.avg_vs_orig_time == pytest.approx(-1.0)  # 2.0 - 3.0
    assert imp_f1_gpu.avg_vs_orig_time == pytest.approx(-2.0)  # 4.0 - 6.0
    assert imp_f2_cpu.avg_vs_orig_time == pytest.approx(-2.0)  # 3.0 - 5.0
    assert imp_f2_cpu.avg_vs_orig_pct == pytest.approx(-40.0)  # -2/5 * 100


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

    # func1 cpu: cand new=2.0, ref new=2.5 → -0.5 s / -20 %
    assert imp_f1_cpu.avg_vs_prev_time == pytest.approx(-0.5)
    assert imp_f1_cpu.avg_vs_prev_pct == pytest.approx(-20.0)
    # func1 gpu: cand new=4.0, ref new=5.0 → -1.0 s / -20 %
    assert imp_f1_gpu.avg_vs_prev_time == pytest.approx(-1.0)
    assert imp_f1_gpu.avg_vs_prev_pct == pytest.approx(-20.0)
    # func2 cpu: cand new=3.0, ref new=3.5 → -0.5 s / ≈-14.3 %
    assert imp_f2_cpu.avg_vs_prev_time == pytest.approx(-0.5)
    assert imp_f2_cpu.avg_vs_prev_pct == pytest.approx(-100.0 / 7.0, rel=1e-3)


def test_postfix_roles_fall_back_to_unparameterized_original(postfix_role_unparameterized_original_folder) -> None:
    """A generic original baseline should compare against each parameterized new variant."""
    runs = load_benchmark_folder(postfix_role_unparameterized_original_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(candidate_run=candidate_run, reference_run=reference_run)

    cpu_imp = next(imp for imp in improvements if imp.group == "params:device=cpu" and imp.method == "func1")
    gpu_imp = next(imp for imp in improvements if imp.group == "params:device=gpu" and imp.method == "func1")

    assert cpu_imp.avg_vs_orig_time == pytest.approx(-1.0)  # 2.0 - 3.0
    assert cpu_imp.avg_vs_orig_pct == pytest.approx(-100.0 / 3.0, rel=1e-3)
    assert gpu_imp.avg_vs_orig_time == pytest.approx(1.0)  # 4.0 - 3.0
    assert gpu_imp.avg_vs_orig_pct == pytest.approx(100.0 / 3.0, rel=1e-3)

    assert cpu_imp.avg_vs_prev_time == pytest.approx(-0.5)  # 2.0 - 2.5
    assert gpu_imp.avg_vs_prev_time == pytest.approx(-1.0)  # 4.0 - 5.0


def test_postfix_roles_use_median_stats_for_med_columns(postfix_role_distinct_medians_folder) -> None:
    """Median columns should compare benchmark median values, not mean values."""
    runs = load_benchmark_folder(postfix_role_distinct_medians_folder)
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = analyze_method_improvements(candidate_run=candidate_run, reference_run=reference_run)

    imp = next(imp for imp in improvements if imp.method == "func1" and imp.group == "params:device=cpu")

    assert imp.avg_vs_orig_time == pytest.approx(-2.0)  # 8.0 - 10.0
    assert imp.med_vs_orig_time == pytest.approx(-1.0)  # 5.0 - 6.0
    assert imp.avg_vs_prev_time == pytest.approx(-1.0)  # 8.0 - 9.0
    assert imp.med_vs_prev_time == pytest.approx(-2.0)  # 5.0 - 7.0


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

    assert summary.count == 3
    assert summary.avg_vs_orig_time is not None
    assert summary.avg_vs_orig_pct is not None
    assert summary.avg_vs_prev_time is not None
    assert summary.avg_vs_prev_pct is not None

    # avg of time savings (-1.0, -2.0, -2.0) = -5/3 ≈ -1.667
    assert summary.avg_vs_orig_time == pytest.approx(-5.0 / 3.0, rel=1e-3)


def test_overall_summary_empty() -> None:
    summary = build_overall_improvement_summary([])
    assert summary.count == 0
    assert all(
        v is None
        for k, v in [
            ("avg_vs_orig_time", summary.avg_vs_orig_time),
            ("avg_vs_orig_pct", summary.avg_vs_orig_pct),
            ("med_vs_orig_time", summary.med_vs_orig_time),
            ("med_vs_orig_pct", summary.med_vs_orig_pct),
            ("min_vs_orig_time", summary.min_vs_orig_time),
            ("min_vs_orig_pct", summary.min_vs_orig_pct),
            ("max_vs_orig_time", summary.max_vs_orig_time),
            ("max_vs_orig_pct", summary.max_vs_orig_pct),
            ("avg_vs_prev_time", summary.avg_vs_prev_time),
            ("avg_vs_prev_pct", summary.avg_vs_prev_pct),
            ("med_vs_prev_time", summary.med_vs_prev_time),
            ("med_vs_prev_pct", summary.med_vs_prev_pct),
            ("min_vs_prev_time", summary.min_vs_prev_time),
            ("min_vs_prev_pct", summary.min_vs_prev_pct),
            ("max_vs_prev_time", summary.max_vs_prev_time),
            ("max_vs_prev_pct", summary.max_vs_prev_pct),
        ]
    )


# ---------------------------------------------------------------------------
# Fixtures for multi-postfix tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def multi_postfix_folder(tmp_path: Path) -> Path:
    """Run with multiple original postfixes (_np, _numpy) and reference postfixes (_pt, _torch).

    func1_np, func1_numpy  (two original variants)
    func1_pt, func1_torch  (two reference variants)
    All parameterized by device=cpu.
    """
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    cases = [
        _make_case_payload("func1_np", "bench::func1_np", "compute", 3.0, {"device": "cpu"}),
        _make_case_payload("func1_numpy", "bench::func1_numpy", "compute", 3.2, {"device": "cpu"}),
        _make_case_payload("func1_pt", "bench::func1_pt", "compute", 2.0, {"device": "cpu"}),
        _make_case_payload("func1_torch", "bench::func1_torch", "compute", 1.8, {"device": "cpu"}),
    ]

    _write_run_file(folder / "run_candidate.json", "run-cand", "cand", "2026-03-01T10:00:00Z", cases)
    return folder


@pytest.fixture()
def multi_postfix_multi_method_folder(tmp_path: Path) -> Path:
    """Multiple methods each having both original (_np) and reference (_pt) postfixes."""
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    cases = [
        _make_case_payload("encode_np", "bench::encode_np", "codec", 5.0, {"device": "cpu"}),
        _make_case_payload("encode_np", "bench::encode_np", "codec", 5.5, {"device": "gpu"}),
        _make_case_payload("encode_pt", "bench::encode_pt", "codec", 3.0, {"device": "cpu"}),
        _make_case_payload("encode_pt", "bench::encode_pt", "codec", 3.5, {"device": "gpu"}),
        _make_case_payload("decode_np", "bench::decode_np", "codec", 4.0, {"device": "cpu"}),
        _make_case_payload("decode_pt", "bench::decode_pt", "codec", 4.5, {"device": "cpu"}),
    ]

    _write_run_file(folder / "run_candidate.json", "run-cand", "cand", "2026-03-01T10:00:00Z", cases)
    return folder


@pytest.fixture()
def multi_postfix_no_reference_run_folder(tmp_path: Path) -> Path:
    """Only a candidate run with _np/_pt methods; no reference run at all."""
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    cases = [
        _make_case_payload("func1_np", "bench::func1_np", "", 3.0, {"device": "cpu"}),
        _make_case_payload("func1_np", "bench::func1_np", "", 6.0, {"device": "gpu"}),
        _make_case_payload("func1_pt", "bench::func1_pt", "", 2.0, {"device": "cpu"}),
        _make_case_payload("func1_pt", "bench::func1_pt", "", 4.0, {"device": "gpu"}),
        _make_case_payload("func2_np", "bench::func2_np", "", 10.0, {}),
        _make_case_payload("func2_pt", "bench::func2_pt", "", 8.0, {}),
    ]

    _write_run_file(folder / "run_only.json", "run-only", "only", "2026-03-01T10:00:00Z", cases)
    return folder


@pytest.fixture()
def regression_folder(tmp_path: Path) -> Path:
    """Two runs for regression comparison, methods have postfixes and params."""
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    ref_cases = [
        _make_case_payload("func1_np", "bench::func1_np", "", 3.0, {"device": "cpu"}),
        _make_case_payload("func1_np", "bench::func1_np", "", 6.0, {"device": "gpu"}),
        _make_case_payload("func1_pt", "bench::func1_pt", "", 2.5, {"device": "cpu"}),
        _make_case_payload("func2_np", "bench::func2_np", "", 10.0, {}),
    ]
    cand_cases = [
        _make_case_payload("func1_np", "bench::func1_np", "", 2.8, {"device": "cpu"}),
        _make_case_payload("func1_np", "bench::func1_np", "", 5.5, {"device": "gpu"}),
        _make_case_payload("func1_pt", "bench::func1_pt", "", 2.2, {"device": "cpu"}),
        _make_case_payload("func2_np", "bench::func2_np", "", 9.0, {}),
        _make_case_payload("func3_pt", "bench::func3_pt", "", 1.0, {}),
    ]

    _write_run_file(folder / "run_ref.json", "run-ref", "ref", "2026-03-01T10:00:00Z", ref_cases)
    _write_run_file(folder / "run_cand.json", "run-cand", "cand", "2026-03-02T10:00:00Z", cand_cases)
    return folder


# ---------------------------------------------------------------------------
# build_postfix_comparison tests
# ---------------------------------------------------------------------------


def test_postfix_comparison_multiple_original_postfixes(multi_postfix_folder) -> None:
    """Both _np and _numpy are recognized as original; _pt and _torch as reference."""
    runs = load_benchmark_folder(
        multi_postfix_folder,
        original_postfix=["_np", "_numpy"],
        reference_postfix=["_pt", "_torch"],
    )
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = build_postfix_comparison(
        candidate_run,
        original_postfixes=["_np", "_numpy"],
        reference_postfixes=["_pt", "_torch"],
    )

    assert len(improvements) == 1
    imp = improvements[0]
    assert imp.method == "func1"
    # original avg = (3.0 + 3.2) / 2 = 3.1
    # reference avg = (2.0 + 1.8) / 2 = 1.9
    assert imp.avg_vs_orig_time == pytest.approx(1.9 - 3.1)
    assert imp.avg_vs_orig_pct == pytest.approx((1.9 - 3.1) / 3.1 * 100)


def test_postfix_comparison_multi_method(multi_postfix_multi_method_folder) -> None:
    """Postfix comparison groups by base name, averages across params."""
    runs = load_benchmark_folder(
        multi_postfix_multi_method_folder,
        original_postfix="_np",
        reference_postfix="_pt",
    )
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = build_postfix_comparison(
        candidate_run,
        original_postfixes=["_np"],
        reference_postfixes=["_pt"],
    )

    assert len(improvements) == 2
    methods = {imp.method for imp in improvements}
    assert methods == {"encode", "decode"}

    enc = next(imp for imp in improvements if imp.method == "encode")
    # original: (5.0 + 5.5) / 2 = 5.25;  reference: (3.0 + 3.5) / 2 = 3.25
    assert enc.avg_vs_orig_time == pytest.approx(3.25 - 5.25)

    dec = next(imp for imp in improvements if imp.method == "decode")
    # original: 4.0;  reference: 4.5 → original is faster
    assert dec.avg_vs_orig_time == pytest.approx(4.5 - 4.0)
    assert dec.avg_vs_orig_pct == pytest.approx((4.5 - 4.0) / 4.0 * 100)


def test_postfix_comparison_no_reference_run_needed(multi_postfix_no_reference_run_folder) -> None:
    """Postfix comparison works with only a candidate run (no saved reference)."""
    runs = load_benchmark_folder(
        multi_postfix_no_reference_run_folder,
        original_postfix="_np",
        reference_postfix="_pt",
    )
    candidate_run = runs[0]

    improvements = build_postfix_comparison(
        candidate_run,
        original_postfixes=["_np"],
        reference_postfixes=["_pt"],
    )

    assert len(improvements) == 2
    methods = {imp.method for imp in improvements}
    assert methods == {"func1", "func2"}

    f1 = next(imp for imp in improvements if imp.method == "func1")
    # original _np: (3.0 + 6.0) / 2 = 4.5;  reference _pt: (2.0 + 4.0) / 2 = 3.0
    assert f1.avg_vs_orig_time == pytest.approx(3.0 - 4.5)

    f2 = next(imp for imp in improvements if imp.method == "func2")
    # original _np: 10.0;  reference _pt: 8.0
    assert f2.avg_vs_orig_time == pytest.approx(8.0 - 10.0)


def test_postfix_comparison_partial_match() -> None:
    """When only one side has a postfix match, no delta is computed."""
    from datetime import UTC, datetime

    from pytest_park.data import build_benchmark_run

    cases = [
        _make_case_payload("func1_np", "bench::func1_np", "", 3.0, {}),
        _make_case_payload("func2_pt", "bench::func2_pt", "", 2.0, {}),
    ]
    run = build_benchmark_run(
        cases,
        run_id="test",
        original_postfix=["_np"],
        reference_postfix=["_pt"],
        created_at=datetime.now(tz=UTC),
    )

    improvements = build_postfix_comparison(run, original_postfixes=["_np"], reference_postfixes=["_pt"])

    assert len(improvements) == 2
    f1 = next(imp for imp in improvements if imp.method == "func1")
    f2 = next(imp for imp in improvements if imp.method == "func2")
    assert f1.avg_vs_orig_time is None  # no _pt counterpart
    assert f2.avg_vs_orig_time is None  # no _np counterpart


# ---------------------------------------------------------------------------
# build_regression_improvements tests
# ---------------------------------------------------------------------------


def test_regression_improvements_per_method(regression_folder) -> None:
    """Regression table compares each method+postfix to its previous value."""
    runs = load_benchmark_folder(regression_folder, original_postfix="_np", reference_postfix="_pt")
    reference_run = select_reference_run(runs, "run-ref")
    candidate_run = select_reference_run(runs, "run-cand")

    improvements = build_regression_improvements(candidate_run, reference_run)

    methods = {imp.method for imp in improvements}
    assert "func1_np" in methods
    assert "func1_pt" in methods
    assert "func2_np" in methods
    assert "func3_pt" in methods  # only in candidate

    f1_np = next(imp for imp in improvements if imp.method == "func1_np")
    # ref avg: (3.0 + 6.0) / 2 = 4.5;  cand avg: (2.8 + 5.5) / 2 = 4.15
    assert f1_np.avg_vs_prev_time == pytest.approx(4.15 - 4.5)

    f1_pt = next(imp for imp in improvements if imp.method == "func1_pt")
    # ref: 2.5;  cand: 2.2
    assert f1_pt.avg_vs_prev_time == pytest.approx(2.2 - 2.5)

    f3_pt = next(imp for imp in improvements if imp.method == "func3_pt")
    # No reference counterpart → N/A
    assert f3_pt.avg_vs_prev_time is None


def test_regression_improvements_empty_reference() -> None:
    """When reference has no matching methods, all entries are N/A."""
    from datetime import UTC, datetime

    from pytest_park.data import build_benchmark_run

    cand_cases = [_make_case_payload("func1_np", "bench::func1_np", "", 2.0, {})]
    ref_cases = [_make_case_payload("func2_pt", "bench::func2_pt", "", 3.0, {})]

    cand = build_benchmark_run(cand_cases, run_id="cand", created_at=datetime.now(tz=UTC))
    ref = build_benchmark_run(ref_cases, run_id="ref", created_at=datetime.now(tz=UTC))

    improvements = build_regression_improvements(cand, ref)
    assert len(improvements) == 1
    assert improvements[0].method == "func1_np"
    assert improvements[0].avg_vs_prev_time is None


# ---------------------------------------------------------------------------
# analyze_method_improvements with configured postfixes
# ---------------------------------------------------------------------------


def test_configured_postfixes_used_for_role_detection(multi_postfix_no_reference_run_folder) -> None:
    """Custom postfixes (_np/_pt) are used for role detection in analyze_method_improvements."""
    runs = load_benchmark_folder(
        multi_postfix_no_reference_run_folder,
        original_postfix="_np",
        reference_postfix="_pt",
    )
    candidate_run = runs[0]

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=None,
        original_postfixes=["_np"],
        reference_postfixes=["_pt"],
    )

    # _np → original, _pt → new (reference=new)
    # Should detect vs_orig comparisons
    has_orig = any(imp.avg_vs_orig_time is not None for imp in improvements)
    assert has_orig
