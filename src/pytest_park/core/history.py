from __future__ import annotations

from collections import defaultdict

from pytest_park.models import (
    BenchmarkCase,
    BenchmarkRun,
    MethodHistoryComparison,
    MethodHistoryPoint,
    PriorRunComparison,
    TrendPoint,
)


class HistoryAnalyzer:
    """Analyzes benchmark performance history and trends across multiple runs."""

    def __init__(self, runs: list[BenchmarkRun]) -> None:
        self.runs = runs

    def build_trends(self) -> dict[str, list[TrendPoint]]:
        """Build time-series means per case across run history."""
        series: dict[str, list[TrendPoint]] = defaultdict(list)
        for run in self.runs:
            for case in run.cases:
                series[case.case_key].append(
                    TrendPoint(run_id=run.run_id, timestamp=run.created_at, mean=case.stats.mean)
                )
        for points in series.values():
            points.sort(key=lambda item: (item.timestamp is None, item.timestamp, item.run_id))
        return dict(series)

    def build_method_history(
        self,
        method: str,
        distinct_params: list[str] | None = None,
    ) -> list[MethodHistoryPoint]:
        """Build method mean history across runs."""
        history: list[MethodHistoryPoint] = []
        for run in self.runs:
            method_cases = [case for case in run.cases if case.normalized_name == method]
            if not method_cases:
                continue

            groups: dict[str, list[BenchmarkCase]] = defaultdict(list)
            for case in method_cases:
                groups[_distinct_label(case, distinct_params)].append(case)

            for distinct_label_val, cases in groups.items():
                means = [case.stats.mean for case in cases]
                history.append(
                    MethodHistoryPoint(
                        run_id=run.run_id,
                        timestamp=run.created_at.isoformat() if run.created_at else None,
                        method=method,
                        distinct=distinct_label_val,
                        mean=sum(means) / len(means),
                    )
                )

        history.sort(key=lambda item: (item.timestamp is None, item.timestamp, item.run_id, item.distinct))
        return history

    def compare_to_reference(
        self,
        reference_run: BenchmarkRun,
        method: str,
        distinct_params: list[str] | None = None,
    ) -> list[MethodHistoryComparison]:
        """Compare method mean over runs against a fixed reference run mean."""
        reference_history = HistoryAnalyzer([reference_run]).build_method_history(method, distinct_params)
        reference_by_distinct = {point.distinct: point.mean for point in reference_history}

        compared: list[MethodHistoryComparison] = []
        for point in self.build_method_history(method, distinct_params):
            baseline = reference_by_distinct.get(point.distinct)
            if baseline is None or baseline <= 0:
                continue
            current = point.mean
            delta_pct = ((current - baseline) / baseline) * 100.0
            compared.append(
                MethodHistoryComparison(
                    run_id=point.run_id,
                    timestamp=point.timestamp,
                    method=point.method,
                    distinct=point.distinct,
                    mean=current,
                    reference_mean=baseline,
                    delta_pct=delta_pct,
                    speedup=baseline / current if current > 0 else 0.0,
                )
            )

        return compared

    def compare_to_all_prior(
        self,
        candidate_run: BenchmarkRun,
        method: str,
        distinct_params: list[str] | None = None,
    ) -> list[PriorRunComparison]:
        """Compare candidate method means against every prior run in history."""
        candidate_index = _method_mean_index(candidate_run, method, distinct_params)
        if not candidate_index:
            return []

        candidate_position = _run_index(self.runs, candidate_run)
        compared: list[PriorRunComparison] = []

        for reference_run in self.runs[:candidate_position]:
            reference_index = _method_mean_index(reference_run, method, distinct_params)
            if not reference_index:
                continue

            for distinct, candidate_mean in candidate_index.items():
                reference_mean = reference_index.get(distinct)
                if reference_mean is None or reference_mean <= 0:
                    continue
                delta_pct = ((candidate_mean - reference_mean) / reference_mean) * 100.0
                compared.append(
                    PriorRunComparison(
                        method=method,
                        candidate_run_id=candidate_run.run_id,
                        reference_run_id=reference_run.run_id,
                        distinct=distinct,
                        mean=candidate_mean,
                        reference_mean=reference_mean,
                        delta_pct=delta_pct,
                        speedup=reference_mean / candidate_mean if candidate_mean > 0 else 0.0,
                        reference_timestamp=(
                            reference_run.created_at.isoformat() if reference_run.created_at else None
                        ),
                    )
                )

        compared.sort(
            key=lambda item: (
                item.reference_timestamp is None,
                item.reference_timestamp,
                item.reference_run_id,
                item.distinct,
            )
        )
        return compared


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def build_trends(runs: list[BenchmarkRun]) -> dict[str, list[TrendPoint]]:
    """Build time-series means per case across run history."""
    return HistoryAnalyzer(runs).build_trends()


def build_method_history(
    runs: list[BenchmarkRun],
    method: str,
    distinct_params: list[str] | None = None,
) -> list[MethodHistoryPoint]:
    """Build method mean history across runs."""
    return HistoryAnalyzer(runs).build_method_history(method, distinct_params)


def compare_method_history_to_reference(
    runs: list[BenchmarkRun],
    reference_run: BenchmarkRun,
    method: str,
    distinct_params: list[str] | None = None,
) -> list[MethodHistoryComparison]:
    """Compare method mean over runs against reference run mean."""
    return HistoryAnalyzer(runs).compare_to_reference(reference_run, method, distinct_params)


def compare_method_to_all_prior_runs(
    runs: list[BenchmarkRun],
    candidate_run: BenchmarkRun,
    method: str,
    distinct_params: list[str] | None = None,
) -> list[PriorRunComparison]:
    """Compare candidate method means against all prior runs."""
    return HistoryAnalyzer(runs).compare_to_all_prior(candidate_run, method, distinct_params)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _distinct_label(case: BenchmarkCase, distinct_params: list[str] | None) -> str:
    if not distinct_params:
        return "all"
    bits = [f"{key}={case.params.get(key, 'n/a')}" for key in distinct_params]
    return ",".join(bits)


def _run_index(runs: list[BenchmarkRun], selected_run: BenchmarkRun) -> int:
    for index, run in enumerate(runs):
        if run.run_id == selected_run.run_id:
            return index
    raise ValueError(f"Run not found in run history: {selected_run.run_id}")


def _method_mean_index(
    run: BenchmarkRun,
    method: str,
    distinct_params: list[str] | None,
) -> dict[str, float]:
    groups: dict[str, list[float]] = defaultdict(list)
    for case in run.cases:
        if case.normalized_name != method:
            continue
        groups[_distinct_label(case, distinct_params)].append(case.stats.mean)
    return {label: sum(values) / len(values) for label, values in groups.items() if values}
