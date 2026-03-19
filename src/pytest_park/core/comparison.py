from __future__ import annotations

from collections import defaultdict
from statistics import median

from pytest_park.core._grouping import IGNORED_COMPARISON_PARAMS, _implementation_role, build_group_label
from pytest_park.models import (
    BenchmarkCase,
    BenchmarkDelta,
    BenchmarkRun,
    GroupSummary,
    OverviewStatistics,
    SplitBarRow,
)


class RunComparator:
    """Compares two benchmark runs and produces deltas, group summaries, and statistics."""

    def __init__(self, reference_run: BenchmarkRun, candidate_run: BenchmarkRun) -> None:
        self.reference_run = reference_run
        self.candidate_run = candidate_run

    def compare(
        self,
        group_by: list[str] | None = None,
        distinct_params: list[str] | None = None,
    ) -> list[BenchmarkDelta]:
        """Calculate per-case deltas between reference and candidate runs."""
        reference_index = {_comparison_key(c, distinct_params): c for c in self.reference_run.cases}
        deltas: list[BenchmarkDelta] = []

        for candidate_case in self.candidate_run.cases:
            reference_case = reference_index.get(_comparison_key(candidate_case, distinct_params))
            if reference_case is None or reference_case.stats.mean <= 0:
                continue

            group_label = build_group_label(candidate_case, group_by)
            delta_pct = ((candidate_case.stats.mean - reference_case.stats.mean) / reference_case.stats.mean) * 100.0
            speedup = reference_case.stats.mean / candidate_case.stats.mean if candidate_case.stats.mean > 0 else 0.0
            deltas.append(
                BenchmarkDelta(
                    group_label=group_label,
                    case_key=candidate_case.case_key,
                    benchmark_name=candidate_case.normalized_name,
                    params=dict(candidate_case.params),
                    reference_run_id=self.reference_run.run_id,
                    candidate_run_id=self.candidate_run.run_id,
                    reference_mean=reference_case.stats.mean,
                    candidate_mean=candidate_case.stats.mean,
                    delta_pct=delta_pct,
                    speedup=speedup,
                )
            )

        deltas.sort(key=lambda item: (item.group_label, item.benchmark_name, tuple(sorted(item.params.items()))))
        return deltas

    @staticmethod
    def build_split_bars(run: BenchmarkRun) -> dict[str, list[SplitBarRow]]:
        """Build split-bar chart rows per method base name for original/new roles."""
        grouped: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )

        for case in run.cases:
            role = _implementation_role(case)
            if role not in {"original", "new"}:
                continue
            grouped[case.base_name][_argument_label(case)][role].append(case.stats.mean)

        output: dict[str, list[SplitBarRow]] = {}
        for method_name, by_argument in grouped.items():
            rows: list[SplitBarRow] = []
            for argument, values in sorted(by_argument.items()):
                original_values = values.get("original")
                new_values = values.get("new")
                if not original_values or not new_values:
                    continue
                original_mean = sum(original_values) / len(original_values)
                new_mean = sum(new_values) / len(new_values)
                rows.append(
                    SplitBarRow(
                        argument=argument,
                        original=original_mean,
                        new=new_mean,
                        delta_pct=((new_mean - original_mean) / original_mean) * 100.0 if original_mean > 0 else 0.0,
                        speedup=original_mean / new_mean if new_mean > 0 else 0.0,
                    )
                )
            if rows:
                output[method_name] = rows

        return output

    @staticmethod
    def summarize_groups(deltas: list[BenchmarkDelta]) -> list[GroupSummary]:
        """Build group-level summary from case-level deltas."""
        grouped: dict[str, list[BenchmarkDelta]] = defaultdict(list)
        for delta in deltas:
            grouped[delta.group_label].append(delta)

        summaries: list[GroupSummary] = []
        for label, items in grouped.items():
            delta_values = [item.delta_pct for item in items]
            improvements = sum(1 for v in delta_values if v < -1e-9)
            regressions = sum(1 for v in delta_values if v > 1e-9)
            summaries.append(
                GroupSummary(
                    label=label,
                    count=len(items),
                    average_delta_pct=sum(delta_values) / len(delta_values),
                    median_delta_pct=median(delta_values),
                    improvements=improvements,
                    regressions=regressions,
                    unchanged=len(items) - improvements - regressions,
                )
            )

        summaries.sort(key=lambda item: item.label)
        return summaries

    @staticmethod
    def build_overview_statistics(deltas: list[BenchmarkDelta]) -> OverviewStatistics:
        """Compute accumulated comparison statistics."""
        if not deltas:
            return OverviewStatistics(
                count=0,
                avg_delta_pct=0.0,
                median_delta_pct=0.0,
                avg_speedup=0.0,
                improved=0,
                regressed=0,
                unchanged=0,
            )
        delta_values = [item.delta_pct for item in deltas]
        speedups = [item.speedup for item in deltas]
        improved = sum(1 for v in delta_values if v < -1e-9)
        regressed = sum(1 for v in delta_values if v > 1e-9)
        return OverviewStatistics(
            count=len(deltas),
            avg_delta_pct=sum(delta_values) / len(delta_values),
            median_delta_pct=median(delta_values),
            avg_speedup=sum(speedups) / len(speedups),
            improved=improved,
            regressed=regressed,
            unchanged=len(deltas) - improved - regressed,
        )

    @staticmethod
    def build_method_statistics(deltas: list[BenchmarkDelta], method: str) -> OverviewStatistics | None:
        """Compute statistics for one benchmark method."""
        method_deltas = [item for item in deltas if item.benchmark_name == method]
        if not method_deltas:
            return None
        return RunComparator.build_overview_statistics(method_deltas)


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def compare_runs(
    reference_run: BenchmarkRun,
    candidate_run: BenchmarkRun,
    group_by: list[str] | None = None,
    distinct_params: list[str] | None = None,
) -> list[BenchmarkDelta]:
    """Compare two runs and calculate per-case deltas."""
    return RunComparator(reference_run, candidate_run).compare(group_by, distinct_params)


def summarize_groups(deltas: list[BenchmarkDelta]) -> list[GroupSummary]:
    """Build group-level summary from case-level deltas."""
    return RunComparator.summarize_groups(deltas)


def build_overview_statistics(deltas: list[BenchmarkDelta]) -> OverviewStatistics:
    """Compute accumulated comparison statistics."""
    return RunComparator.build_overview_statistics(deltas)


def build_method_statistics(deltas: list[BenchmarkDelta], method: str) -> OverviewStatistics | None:
    """Compute statistics for one benchmark method."""
    return RunComparator.build_method_statistics(deltas, method)


def build_method_group_split_bars(run: BenchmarkRun) -> dict[str, list[SplitBarRow]]:
    """Build split-bar chart rows per method base name for original/new roles."""
    return RunComparator.build_split_bars(run)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _comparison_key(case: BenchmarkCase, distinct_params: list[str] | None) -> str:
    if distinct_params:
        normalized = [token.strip() for token in distinct_params if token.strip()]
        comparable_params = {key: value for key, value in case.params.items() if key in normalized}
    else:
        comparable_params = {
            key: value for key, value in case.params.items() if key.lower() not in IGNORED_COMPARISON_PARAMS
        }
    param_bits = ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))
    return f"{case.normalized_fullname}|{param_bits}"


def _argument_label(case: BenchmarkCase) -> str:
    comparable_params = {
        key: value for key, value in case.params.items() if key.lower() not in IGNORED_COMPARISON_PARAMS
    }
    if not comparable_params:
        return "all"
    return ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))
