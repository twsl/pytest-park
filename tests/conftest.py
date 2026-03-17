from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_benchmark_case(
    name: str,
    group: str,
    mean: float,
    *,
    device: str,
    implementation: str,
    marks: list[str],
    scenario: str,
) -> dict[str, object]:
    return {
        "name": name,
        "fullname": f"bench::{name}",
        "group": group,
        "params": {
            "device": device,
            "implementation": implementation,
        },
        "marks": marks,
        "extra_info": {
            "custom_groups": {
                "scenario": scenario,
                "implementation": implementation,
            }
        },
        "stats": {
            "mean": mean,
            "median": mean,
            "min": mean * 0.95,
            "max": mean * 1.05,
            "stddev": mean * 0.01,
            "rounds": 5,
            "iterations": 1,
            "ops": (1.0 / mean) if mean else 0.0,
        },
    }


def _write_run(path: Path, run_id: str, tag: str, dt: str, cases: list[dict[str, object]]) -> None:
    payload = {
        "datetime": dt,
        "metadata": {"run_id": run_id, "tag": tag},
        "machine_info": {"node": "test-node", "python_version": "3.12.2"},
        "commit_info": {"id": f"{run_id}-commit"},
        "benchmarks": cases,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def benchmark_folder(tmp_path: Path) -> Path:
    """Create a realistic benchmark folder with reference and candidate runs."""
    folder = tmp_path / "benchmarks"
    folder.mkdir()

    reference_cases = [
        _make_benchmark_case(
            "sort_values",
            "sorting",
            1.0,
            device="cpu",
            implementation="reference",
            marks=["algo", "baseline"],
            scenario="cpu-baseline",
        ),
        _make_benchmark_case(
            "sort_values",
            "sorting",
            2.0,
            device="gpu",
            implementation="reference",
            marks=["algo", "baseline"],
            scenario="gpu-baseline",
        ),
        _make_benchmark_case(
            "reduce_sum",
            "reduction",
            0.7,
            device="cpu",
            implementation="reference",
            marks=["algo"],
            scenario="cpu-baseline",
        ),
    ]
    candidate_v1_cases = [
        _make_benchmark_case(
            "sort_values",
            "sorting",
            0.8,
            device="cpu",
            implementation="candidate",
            marks=["algo", "candidate"],
            scenario="cpu-candidate",
        ),
        _make_benchmark_case(
            "sort_values",
            "sorting",
            2.4,
            device="gpu",
            implementation="candidate",
            marks=["algo", "candidate"],
            scenario="gpu-candidate",
        ),
        _make_benchmark_case(
            "reduce_sum",
            "reduction",
            0.65,
            device="cpu",
            implementation="candidate",
            marks=["algo"],
            scenario="cpu-candidate",
        ),
    ]
    candidate_v2_cases = [
        _make_benchmark_case(
            "sort_values",
            "sorting",
            0.6,
            device="cpu",
            implementation="candidate",
            marks=["algo", "candidate"],
            scenario="cpu-candidate",
        ),
        _make_benchmark_case(
            "sort_values",
            "sorting",
            1.9,
            device="gpu",
            implementation="candidate",
            marks=["algo", "candidate"],
            scenario="gpu-candidate",
        ),
        _make_benchmark_case(
            "reduce_sum",
            "reduction",
            0.58,
            device="cpu",
            implementation="candidate",
            marks=["algo"],
            scenario="cpu-candidate",
        ),
    ]

    _write_run(folder / "run_reference.json", "run-reference", "reference", "2026-02-10T10:00:00Z", reference_cases)
    _write_run(
        folder / "run_candidate_v1.json", "run-candidate-v1", "candidate-v1", "2026-02-11T10:00:00Z", candidate_v1_cases
    )
    _write_run(
        folder / "run_candidate_v2.json", "run-candidate-v2", "candidate-v2", "2026-02-12T10:00:00Z", candidate_v2_cases
    )

    return folder


@pytest.fixture()
def profiler_folder(tmp_path: Path) -> Path:
    """Create profiler artifacts keyed by run and case."""
    folder = tmp_path / "profilers"
    folder.mkdir()

    profiler_payload = {
        "run_id": "run-candidate-v2",
        "cases": [
            {
                "fullname": "bench::sort_values",
                "function": "sort_values",
                "file": "algo.py",
                "line": 42,
                "total_time": 0.11,
            },
            {
                "fullname": "bench::reduce_sum",
                "function": "reduce_sum",
                "file": "algo.py",
                "line": 88,
                "total_time": 0.08,
            },
        ],
    }
    (folder / "profile_candidate_v2.json").write_text(json.dumps(profiler_payload), encoding="utf-8")
    return folder
