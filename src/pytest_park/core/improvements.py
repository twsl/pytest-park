from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median

from pytest_park.core._grouping import (
    IGNORED_COMPARISON_PARAMS,
    _implementation_role,
    _normalize_postfix_key,
    build_group_label,
)
from pytest_park.models import BenchmarkCase, BenchmarkRun, ImprovementSummary, MethodImprovement


@dataclass
class _RoleStats:
    mean: list[float] = field(default_factory=list)
    median: list[float] = field(default_factory=list)
    min: list[float] = field(default_factory=list)
    max: list[float] = field(default_factory=list)
    names: set[str] = field(default_factory=set)


class ImprovementAnalyzer:
    """Computes per-method improvement metrics relative to originals and/or a reference run."""

    def __init__(
        self,
        candidate_run: BenchmarkRun,
        reference_run: BenchmarkRun | None = None,
    ) -> None:
        self.candidate_run = candidate_run
        self.reference_run = reference_run

    def analyze(
        self,
        group_by: list[str] | None = None,
        exclude_params: list[str] | None = None,
        original_postfixes: list[str] | None = None,
        reference_postfixes: list[str] | None = None,
    ) -> list[MethodImprovement]:
        """Calculate mean/median improvements per method vs original and comparison run."""
        grouped_cand: dict[str, dict[str, dict[str, dict[str, _RoleStats]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(_RoleStats)))
        )
        for case in self.candidate_run.cases:
            _accumulate(grouped_cand, case, group_by, exclude_params, original_postfixes, reference_postfixes)

        grouped_ref: dict[str, dict[str, dict[str, dict[str, _RoleStats]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(_RoleStats)))
        )
        if self.reference_run:
            for case in self.reference_run.cases:
                _accumulate(grouped_ref, case, group_by, exclude_params, original_postfixes, reference_postfixes)

        return _build_improvements(grouped_cand, grouped_ref, self.reference_run)

    def regression(self) -> list[MethodImprovement]:
        """Build flat per-method comparison between candidate and reference runs."""
        if self.reference_run is None:
            raise ValueError("A reference run is required for regression analysis")

        cand_by_method: dict[str, list[BenchmarkCase]] = defaultdict(list)
        for case in self.candidate_run.cases:
            cand_by_method[_method_function_name(case)].append(case)

        ref_by_method: dict[str, list[BenchmarkCase]] = defaultdict(list)
        for case in self.reference_run.cases:
            ref_by_method[_method_function_name(case)].append(case)

        improvements: list[MethodImprovement] = []
        for method, cand_cases in cand_by_method.items():
            ref_cases = ref_by_method.get(method, [])
            if ref_cases:
                improvements.append(_compare_case_lists(method, cand_cases, ref_cases))
            else:
                improvements.append(MethodImprovement(group="", method=method))

        improvements.sort(key=lambda item: item.method)
        return improvements

    @staticmethod
    def postfix_comparison(
        run: BenchmarkRun,
        original_postfixes: list[str],
        reference_postfixes: list[str],
    ) -> list[MethodImprovement]:
        """Compare methods matched by base name after stripping their postfix.

        Average stats of original-postfix implementations are compared against
        reference-postfix implementations. Parameters are ignored — all variants
        are averaged together.
        """
        norm_orig = {_normalize_postfix_key(p) for p in original_postfixes if p}
        norm_ref = {_normalize_postfix_key(p) for p in reference_postfixes if p}

        orig_by_base: dict[str, list[BenchmarkCase]] = defaultdict(list)
        ref_by_base: dict[str, list[BenchmarkCase]] = defaultdict(list)
        for case in run.cases:
            if not case.method_postfix:
                continue
            key = _normalize_postfix_key(case.method_postfix)
            if key in norm_orig:
                orig_by_base[case.base_name].append(case)
            elif key in norm_ref:
                ref_by_base[case.base_name].append(case)

        improvements: list[MethodImprovement] = []
        for base_name in sorted(set(orig_by_base) | set(ref_by_base)):
            orig_cases = orig_by_base.get(base_name, [])
            ref_cases = ref_by_base.get(base_name, [])
            orig_label = ",".join(sorted({_method_function_name(c) for c in orig_cases})) if orig_cases else None
            ref_label = ",".join(sorted({_method_function_name(c) for c in ref_cases})) if ref_cases else None

            if orig_cases and ref_cases:
                imp = _compare_case_lists_as_orig(base_name, ref_cases, orig_cases)
                imp.current_benchmark_name = ref_label
                imp.original_benchmark_name = orig_label
                imp.orig_arg_count = len(orig_cases)
                imp.ref_arg_count = len(ref_cases)
                improvements.append(imp)
            else:
                improvements.append(
                    MethodImprovement(
                        group="",
                        method=base_name,
                        current_benchmark_name=ref_label,
                        original_benchmark_name=orig_label,
                        orig_arg_count=len(orig_cases),
                        ref_arg_count=len(ref_cases),
                    )
                )

        improvements.sort(key=lambda item: item.method)
        return improvements

    @staticmethod
    def summarize(improvements: list[MethodImprovement]) -> ImprovementSummary:
        """Compute overall aggregated improvement metrics across all methods."""
        if not improvements:
            return ImprovementSummary(count=0)

        def _avg(values: list[float]) -> float | None:
            return sum(values) / len(values) if values else None

        def _med(values: list[float]) -> float | None:
            return median(values) if values else None

        def _collect(attr: str) -> list[float]:
            return [v for imp in improvements if (v := getattr(imp, attr)) is not None]

        return ImprovementSummary(
            count=len(improvements),
            avg_vs_orig_time=_avg(_collect("avg_vs_orig_time")),
            avg_vs_orig_pct=_avg(_collect("avg_vs_orig_pct")),
            med_vs_orig_time=_med(_collect("med_vs_orig_time")),
            med_vs_orig_pct=_med(_collect("med_vs_orig_pct")),
            min_vs_orig_time=_avg(_collect("min_vs_orig_time")),
            min_vs_orig_pct=_avg(_collect("min_vs_orig_pct")),
            max_vs_orig_time=_avg(_collect("max_vs_orig_time")),
            max_vs_orig_pct=_avg(_collect("max_vs_orig_pct")),
            avg_vs_prev_time=_avg(_collect("avg_vs_prev_time")),
            avg_vs_prev_pct=_avg(_collect("avg_vs_prev_pct")),
            med_vs_prev_time=_med(_collect("med_vs_prev_time")),
            med_vs_prev_pct=_med(_collect("med_vs_prev_pct")),
            min_vs_prev_time=_avg(_collect("min_vs_prev_time")),
            min_vs_prev_pct=_avg(_collect("min_vs_prev_pct")),
            max_vs_prev_time=_avg(_collect("max_vs_prev_time")),
            max_vs_prev_pct=_avg(_collect("max_vs_prev_pct")),
        )


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def analyze_method_improvements(
    candidate_run: BenchmarkRun,
    reference_run: BenchmarkRun | None = None,
    group_by: list[str] | None = None,
    exclude_params: list[str] | None = None,
    original_postfixes: list[str] | None = None,
    reference_postfixes: list[str] | None = None,
) -> list[MethodImprovement]:
    """Calculate mean and median improvements per method vs original and comparison run."""
    return ImprovementAnalyzer(candidate_run, reference_run).analyze(
        group_by=group_by,
        exclude_params=exclude_params,
        original_postfixes=original_postfixes,
        reference_postfixes=reference_postfixes,
    )


def build_overall_improvement_summary(improvements: list[MethodImprovement]) -> ImprovementSummary:
    """Compute overall aggregated improvement metrics across all methods and devices."""
    return ImprovementAnalyzer.summarize(improvements)


def build_regression_improvements(
    candidate_run: BenchmarkRun,
    reference_run: BenchmarkRun,
) -> list[MethodImprovement]:
    """Build flat per-method comparison between candidate and reference runs."""
    return ImprovementAnalyzer(candidate_run, reference_run).regression()


def build_postfix_comparison(
    run: BenchmarkRun,
    original_postfixes: list[str],
    reference_postfixes: list[str],
) -> list[MethodImprovement]:
    """Compare methods matched by base name after stripping postfixes."""
    return ImprovementAnalyzer.postfix_comparison(run, original_postfixes, reference_postfixes)


def _format_benchmark_names(names: set[str]) -> str | None:
    if not names:
        return None
    return "\n".join(sorted(names))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _accumulate(
    grouped: dict[str, dict[str, dict[str, dict[str, _RoleStats]]]],
    case: BenchmarkCase,
    group_by: list[str] | None,
    exclude_params: list[str] | None,
    original_postfixes: list[str] | None,
    reference_postfixes: list[str] | None,
) -> None:
    group_label = build_group_label(case, group_by)
    match_label = _match_label(case, exclude_params)
    role = _implementation_role(case, original_postfixes=original_postfixes, reference_postfixes=reference_postfixes)

    excluded_param_values = {k: v for k, v in case.params.items() if k in (exclude_params or [])}
    if excluded_param_values:
        suffix = ",".join(f"{k}={v}" for k, v in sorted(excluded_param_values.items()))
        method_name = f"{case.base_name}[{suffix}]"
    else:
        method_name = case.base_name

    role_stats = grouped[group_label][method_name][match_label][role]
    role_stats.mean.append(case.stats.mean)
    role_stats.median.append(case.stats.median)
    role_stats.min.append(case.stats.min)
    role_stats.max.append(case.stats.max)
    role_stats.names.add(case.name)


def _build_improvements(
    grouped_cand: dict[str, dict[str, dict[str, dict[str, _RoleStats]]]],
    grouped_ref: dict[str, dict[str, dict[str, dict[str, _RoleStats]]]],
    reference_run: BenchmarkRun | None,
) -> list[MethodImprovement]:
    improvements: list[MethodImprovement] = []

    for group_label, methods in grouped_cand.items():
        for base_name, matches in methods.items():
            all_roles: set[str] = set()
            for roles in matches.values():
                all_roles.update(roles.keys())

            if "new" in all_roles:
                primary_role = "new"
            elif "unknown" in all_roles:
                primary_role = "unknown"
            elif "original" in all_roles:
                primary_role = "original"
            else:
                continue

            vs_orig_time_diffs: list[float] = []
            vs_orig_pct_diffs: list[float] = []
            vs_orig_median_time_diffs: list[float] = []
            vs_orig_median_pct_diffs: list[float] = []
            vs_orig_min_time_diffs: list[float] = []
            vs_orig_min_pct_diffs: list[float] = []
            vs_orig_max_time_diffs: list[float] = []
            vs_orig_max_pct_diffs: list[float] = []
            vs_prev_time_diffs: list[float] = []
            vs_prev_pct_diffs: list[float] = []
            vs_prev_median_time_diffs: list[float] = []
            vs_prev_median_pct_diffs: list[float] = []
            vs_prev_min_time_diffs: list[float] = []
            vs_prev_min_pct_diffs: list[float] = []
            vs_prev_max_time_diffs: list[float] = []
            vs_prev_max_pct_diffs: list[float] = []
            current_names: set[str] = set()
            comparison_names: set[str] = set()
            original_names: set[str] = set()

            for match_label, roles in matches.items():
                cand_stats = roles.get(primary_role)
                if not cand_stats:
                    continue
                if not cand_stats.mean or not cand_stats.median or not cand_stats.min or not cand_stats.max:
                    continue

                cand_mean = sum(cand_stats.mean) / len(cand_stats.mean)
                cand_median = median(cand_stats.median)
                cand_min = sum(cand_stats.min) / len(cand_stats.min)
                cand_max = sum(cand_stats.max) / len(cand_stats.max)
                current_names.update(cand_stats.names)

                orig_stats = _resolve_role_stats(grouped_cand, group_label, base_name, match_label, "original")
                if (
                    orig_stats
                    and primary_role != "original"
                    and (not orig_stats.mean or not orig_stats.median or not orig_stats.min or not orig_stats.max)
                ):
                    orig_stats = None

                if orig_stats and primary_role != "original":
                    orig_mean = sum(orig_stats.mean) / len(orig_stats.mean)
                    orig_median = median(orig_stats.median)
                    orig_min = sum(orig_stats.min) / len(orig_stats.min)
                    orig_max = sum(orig_stats.max) / len(orig_stats.max)
                    original_names.update(orig_stats.names)

                    vs_orig_time_diffs.append(cand_mean - orig_mean)
                    vs_orig_pct_diffs.append(((cand_mean - orig_mean) / orig_mean) * 100.0 if orig_mean > 0 else 0.0)
                    vs_orig_median_time_diffs.append(cand_median - orig_median)
                    vs_orig_median_pct_diffs.append(
                        ((cand_median - orig_median) / orig_median) * 100.0 if orig_median > 0 else 0.0
                    )
                    vs_orig_min_time_diffs.append(cand_min - orig_min)
                    vs_orig_min_pct_diffs.append(((cand_min - orig_min) / orig_min) * 100.0 if orig_min > 0 else 0.0)
                    vs_orig_max_time_diffs.append(cand_max - orig_max)
                    vs_orig_max_pct_diffs.append(((cand_max - orig_max) / orig_max) * 100.0 if orig_max > 0 else 0.0)

                if reference_run:
                    ref_stats = _resolve_role_stats(
                        grouped_ref,
                        group_label,
                        base_name,
                        match_label,
                        primary_role,
                        cand_names=cand_stats.names,
                    )
                    if ref_stats and ref_stats.mean and ref_stats.median and ref_stats.min and ref_stats.max:
                        ref_mean = sum(ref_stats.mean) / len(ref_stats.mean)
                        ref_median = median(ref_stats.median)
                        ref_min = sum(ref_stats.min) / len(ref_stats.min)
                        ref_max = sum(ref_stats.max) / len(ref_stats.max)
                        comparison_names.update(ref_stats.names)

                        vs_prev_time_diffs.append(cand_mean - ref_mean)
                        vs_prev_pct_diffs.append(((cand_mean - ref_mean) / ref_mean) * 100.0 if ref_mean > 0 else 0.0)
                        vs_prev_median_time_diffs.append(cand_median - ref_median)
                        vs_prev_median_pct_diffs.append(
                            ((cand_median - ref_median) / ref_median) * 100.0 if ref_median > 0 else 0.0
                        )
                        vs_prev_min_time_diffs.append(cand_min - ref_min)
                        vs_prev_min_pct_diffs.append(((cand_min - ref_min) / ref_min) * 100.0 if ref_min > 0 else 0.0)
                        vs_prev_max_time_diffs.append(cand_max - ref_max)
                        vs_prev_max_pct_diffs.append(((cand_max - ref_max) / ref_max) * 100.0 if ref_max > 0 else 0.0)

            def _avg(lst: list[float]) -> float | None:
                return sum(lst) / len(lst) if lst else None

            def _med(lst: list[float]) -> float | None:
                return median(lst) if lst else None

            improvements.append(
                MethodImprovement(
                    group=group_label,
                    method=base_name,
                    current_benchmark_name=_format_benchmark_names(current_names),
                    comparison_benchmark_name=_format_benchmark_names(comparison_names),
                    original_benchmark_name=_format_benchmark_names(original_names),
                    orig_arg_count=len(original_names),
                    ref_arg_count=len(current_names),
                    avg_vs_orig_time=_avg(vs_orig_time_diffs),
                    avg_vs_orig_pct=_avg(vs_orig_pct_diffs),
                    med_vs_orig_time=_med(vs_orig_median_time_diffs),
                    med_vs_orig_pct=_med(vs_orig_median_pct_diffs),
                    min_vs_orig_time=_avg(vs_orig_min_time_diffs),
                    min_vs_orig_pct=_avg(vs_orig_min_pct_diffs),
                    max_vs_orig_time=_avg(vs_orig_max_time_diffs),
                    max_vs_orig_pct=_avg(vs_orig_max_pct_diffs),
                    avg_vs_prev_time=_avg(vs_prev_time_diffs),
                    avg_vs_prev_pct=_avg(vs_prev_pct_diffs),
                    med_vs_prev_time=_med(vs_prev_median_time_diffs),
                    med_vs_prev_pct=_med(vs_prev_median_pct_diffs),
                    min_vs_prev_time=_avg(vs_prev_min_time_diffs),
                    min_vs_prev_pct=_avg(vs_prev_min_pct_diffs),
                    max_vs_prev_time=_avg(vs_prev_max_time_diffs),
                    max_vs_prev_pct=_avg(vs_prev_max_pct_diffs),
                )
            )

    improvements.sort(key=lambda item: (item.group, item.method))
    return improvements


def _resolve_role_stats(
    grouped_runs: dict[str, dict[str, dict[str, dict[str, _RoleStats]]]],
    group_label: str,
    method_name: str,
    match_label: str,
    role: str,
    cand_names: set[str] | None = None,
) -> _RoleStats | None:
    role_matches = grouped_runs.get(group_label, {}).get(method_name, {})

    exact = role_matches.get(match_label, {}).get(role)
    if exact and _has_role_values(exact):
        return exact

    generic = role_matches.get("all", {}).get(role)
    if generic and _has_role_values(generic):
        return generic

    for methods in grouped_runs.values():
        fallback_exact = methods.get(method_name, {}).get(match_label, {}).get(role)
        if fallback_exact and _has_role_values(fallback_exact):
            return fallback_exact

    for methods in grouped_runs.values():
        fallback_generic = methods.get(method_name, {}).get("all", {}).get(role)
        if fallback_generic and _has_role_values(fallback_generic):
            return fallback_generic

    # Final fallback: match by benchmark name when params-based matching fails
    if cand_names:
        for methods in grouped_runs.values():
            for roles in methods.get(method_name, {}).values():
                stats = roles.get(role)
                if stats and _has_role_values(stats) and stats.names & cand_names:
                    return stats

    return None


def _has_role_values(stats: _RoleStats) -> bool:
    return bool(stats.mean or stats.median)


def _match_label(case: BenchmarkCase, exclude_params: list[str] | None) -> str:
    exclude = set(exclude_params or []) | IGNORED_COMPARISON_PARAMS
    comparable_params = {key: value for key, value in case.params.items() if key.lower() not in exclude}
    if not comparable_params:
        return "all"
    return ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))


def _method_function_name(case: BenchmarkCase) -> str:
    """Reconstruct the raw test function name (base_name + postfix, without parameters)."""
    return case.base_name + (case.method_postfix or "")


def _compare_case_lists(
    method: str, cand_cases: list[BenchmarkCase], ref_cases: list[BenchmarkCase]
) -> MethodImprovement:
    """Build a MethodImprovement comparing candidate vs reference case lists (prev-run columns)."""
    cand_avg = sum(c.stats.mean for c in cand_cases) / len(cand_cases)
    cand_med = median([c.stats.median for c in cand_cases])
    cand_min = sum(c.stats.min for c in cand_cases) / len(cand_cases)
    cand_max = sum(c.stats.max for c in cand_cases) / len(cand_cases)

    ref_avg = sum(c.stats.mean for c in ref_cases) / len(ref_cases)
    ref_med = median([c.stats.median for c in ref_cases])
    ref_min = sum(c.stats.min for c in ref_cases) / len(ref_cases)
    ref_max = sum(c.stats.max for c in ref_cases) / len(ref_cases)

    avg_dt = cand_avg - ref_avg
    med_dt = cand_med - ref_med
    min_dt = cand_min - ref_min
    max_dt = cand_max - ref_max

    return MethodImprovement(
        group="",
        method=method,
        avg_vs_prev_time=avg_dt,
        avg_vs_prev_pct=(avg_dt / ref_avg * 100) if ref_avg > 0 else 0.0,
        med_vs_prev_time=med_dt,
        med_vs_prev_pct=(med_dt / ref_med * 100) if ref_med > 0 else 0.0,
        min_vs_prev_time=min_dt,
        min_vs_prev_pct=(min_dt / ref_min * 100) if ref_min > 0 else 0.0,
        max_vs_prev_time=max_dt,
        max_vs_prev_pct=(max_dt / ref_max * 100) if ref_max > 0 else 0.0,
    )


def _compare_case_lists_as_orig(
    method: str, new_cases: list[BenchmarkCase], orig_cases: list[BenchmarkCase]
) -> MethodImprovement:
    """Build a MethodImprovement comparing new vs original case lists (orig columns)."""
    new_avg = sum(c.stats.mean for c in new_cases) / len(new_cases)
    new_med = median([c.stats.median for c in new_cases])
    new_min = sum(c.stats.min for c in new_cases) / len(new_cases)
    new_max = sum(c.stats.max for c in new_cases) / len(new_cases)

    orig_avg = sum(c.stats.mean for c in orig_cases) / len(orig_cases)
    orig_med = median([c.stats.median for c in orig_cases])
    orig_min = sum(c.stats.min for c in orig_cases) / len(orig_cases)
    orig_max = sum(c.stats.max for c in orig_cases) / len(orig_cases)

    avg_dt = new_avg - orig_avg
    med_dt = new_med - orig_med
    min_dt = new_min - orig_min
    max_dt = new_max - orig_max

    return MethodImprovement(
        group="",
        method=method,
        avg_vs_orig_time=avg_dt,
        avg_vs_orig_pct=(avg_dt / orig_avg * 100) if orig_avg > 0 else 0.0,
        med_vs_orig_time=med_dt,
        med_vs_orig_pct=(med_dt / orig_med * 100) if orig_med > 0 else 0.0,
        min_vs_orig_time=min_dt,
        min_vs_orig_pct=(min_dt / orig_min * 100) if orig_min > 0 else 0.0,
        max_vs_orig_time=max_dt,
        max_vs_orig_pct=(max_dt / orig_max * 100) if orig_max > 0 else 0.0,
    )
