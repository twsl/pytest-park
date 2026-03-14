from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class BenchmarkStats:
    """Core benchmark statistics from pytest-benchmark."""

    mean: float
    median: float
    min: float
    max: float
    stddev: float
    rounds: int
    iterations: int
    ops: float


@dataclass(slots=True)
class BenchmarkCase:
    """A single benchmark case in a run."""

    name: str
    fullname: str
    normalized_name: str
    normalized_fullname: str
    base_name: str
    method_parameters: str | None
    method_postfix: str | None
    benchmark_group: str | None
    marks: tuple[str, ...]
    params: dict[str, str]
    custom_groups: dict[str, str]
    stats: BenchmarkStats

    @property
    def case_key(self) -> str:
        """Build a deterministic key for cross-run comparisons."""
        param_bits = ",".join(f"{key}={value}" for key, value in sorted(self.params.items()))
        return f"{self.fullname}|{param_bits}"


@dataclass(slots=True)
class BenchmarkRun:
    """A full benchmark run loaded from one JSON artifact."""

    run_id: str
    source_file: str
    created_at: datetime | None
    tag: str | None
    commit_id: str | None
    machine: str | None
    python_version: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    cases: list[BenchmarkCase] = field(default_factory=list)
    profiler: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkDelta:
    """A comparison result for one benchmark case."""

    group_label: str
    case_key: str
    benchmark_name: str
    params: dict[str, str]
    reference_run_id: str
    candidate_run_id: str
    reference_mean: float
    candidate_mean: float
    delta_pct: float
    speedup: float


@dataclass(slots=True)
class GroupSummary:
    """Aggregated comparison metrics for a logical group."""

    label: str
    count: int
    average_delta_pct: float
    median_delta_pct: float
    improvements: int
    regressions: int
    unchanged: int


@dataclass(slots=True)
class TrendPoint:
    """Time-series data for one case and run."""

    run_id: str
    timestamp: datetime | None
    mean: float


@dataclass(slots=True)
class MethodImprovement:
    """Aggregated improvement metrics for a method within a group."""

    group: str
    method: str
    current_benchmark_name: str | None = None
    comparison_benchmark_name: str | None = None
    original_benchmark_name: str | None = None
    avg_vs_orig_time: float | None = None
    avg_vs_orig_pct: float | None = None
    med_vs_orig_time: float | None = None
    med_vs_orig_pct: float | None = None
    min_vs_orig_time: float | None = None
    min_vs_orig_pct: float | None = None
    max_vs_orig_time: float | None = None
    max_vs_orig_pct: float | None = None
    avg_vs_prev_time: float | None = None
    avg_vs_prev_pct: float | None = None
    med_vs_prev_time: float | None = None
    med_vs_prev_pct: float | None = None
    min_vs_prev_time: float | None = None
    min_vs_prev_pct: float | None = None
    max_vs_prev_time: float | None = None
    max_vs_prev_pct: float | None = None
