from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MethodImprovement:
    """Aggregated improvement metrics for a method within a group."""

    group: str
    method: str
    current_benchmark_name: str | None = None
    comparison_benchmark_name: str | None = None
    original_benchmark_name: str | None = None
    orig_arg_count: int = 0
    ref_arg_count: int = 0
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


@dataclass(slots=True)
class OverviewStatistics:
    """Accumulated comparison statistics across all benchmark deltas."""

    count: int
    avg_delta_pct: float
    median_delta_pct: float
    avg_speedup: float
    improved: int
    regressed: int
    unchanged: int


@dataclass(slots=True)
class MethodHistoryPoint:
    """A single mean observation for a method in one run."""

    run_id: str
    timestamp: str | None
    method: str
    distinct: str
    mean: float


@dataclass(slots=True)
class MethodHistoryComparison:
    """A method mean observation compared against a reference run baseline."""

    run_id: str
    timestamp: str | None
    method: str
    distinct: str
    mean: float
    reference_mean: float
    delta_pct: float
    speedup: float


@dataclass(slots=True)
class PriorRunComparison:
    """Comparison of a candidate method mean against one prior reference run."""

    method: str
    candidate_run_id: str
    reference_run_id: str
    distinct: str
    mean: float
    reference_mean: float
    delta_pct: float
    speedup: float
    reference_timestamp: str | None


@dataclass(slots=True)
class ImprovementSummary:
    """Aggregated improvement metrics across all methods."""

    count: int
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


@dataclass(slots=True)
class SplitBarRow:
    """Original vs new mean pair for one argument combination."""

    argument: str
    original: float
    new: float
    delta_pct: float
    speedup: float
