from __future__ import annotations

from collections import defaultdict
from statistics import median

from pytest_park.models import BenchmarkCase, BenchmarkDelta, BenchmarkRun, GroupSummary, MethodImprovement, TrendPoint

DEFAULT_GROUPING_PRECEDENCE = ("custom", "benchmark_group", "marks", "params")
_IGNORED_COMPARISON_PARAMS = {"implementation", "impl", "variant"}


def attach_profiler_data(
    runs: list[BenchmarkRun],
    profiler_by_run: dict[str, dict[str, dict[str, object]]],
) -> list[BenchmarkRun]:
    """Attach profiler records to matching benchmark runs."""
    for run in runs:
        run.profiler = profiler_by_run.get(run.run_id, {})
    return runs


def select_reference_run(runs: list[BenchmarkRun], reference_id_or_tag: str) -> BenchmarkRun:
    """Select a run by explicit run_id or tag."""
    for run in runs:
        if run.run_id == reference_id_or_tag or run.tag == reference_id_or_tag:
            return run
    raise ValueError(f"No run found for reference identifier: {reference_id_or_tag}")


def select_latest_and_previous_runs(runs: list[BenchmarkRun]) -> tuple[BenchmarkRun, BenchmarkRun]:
    """Select previous and latest run as reference/candidate pair."""
    if len(runs) < 2:
        raise ValueError("At least two runs are required for comparison")
    return runs[-2], runs[-1]


def select_candidate_run(
    runs: list[BenchmarkRun],
    candidate_id_or_tag: str | None,
    reference_run: BenchmarkRun,
) -> BenchmarkRun:
    """Select candidate run or default to latest non-reference run."""
    if candidate_id_or_tag:
        for run in runs:
            if run.run_id == candidate_id_or_tag or run.tag == candidate_id_or_tag:
                return run
        raise ValueError(f"No run found for candidate identifier: {candidate_id_or_tag}")

    non_reference = [run for run in runs if run.run_id != reference_run.run_id]
    if not non_reference:
        raise ValueError("No candidate run available besides the selected reference run")
    return non_reference[-1]


def list_methods(runs: list[BenchmarkRun]) -> list[str]:
    """List unique benchmark methods seen across runs."""
    methods = {case.normalized_name for run in runs for case in run.cases}
    return sorted(methods)


def compare_runs(
    reference_run: BenchmarkRun,
    candidate_run: BenchmarkRun,
    group_by: list[str] | None = None,
    distinct_params: list[str] | None = None,
) -> list[BenchmarkDelta]:
    """Compare two runs and calculate per-case deltas."""
    reference_index = {_comparison_key(case, distinct_params): case for case in reference_run.cases}
    deltas: list[BenchmarkDelta] = []

    for candidate_case in candidate_run.cases:
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
                reference_run_id=reference_run.run_id,
                candidate_run_id=candidate_run.run_id,
                reference_mean=reference_case.stats.mean,
                candidate_mean=candidate_case.stats.mean,
                delta_pct=delta_pct,
                speedup=speedup,
            )
        )

    deltas.sort(key=lambda item: (item.group_label, item.benchmark_name, tuple(sorted(item.params.items()))))
    return deltas


def summarize_groups(deltas: list[BenchmarkDelta]) -> list[GroupSummary]:
    """Build group-level summary from case-level deltas."""
    grouped: dict[str, list[BenchmarkDelta]] = defaultdict(list)
    for delta in deltas:
        grouped[delta.group_label].append(delta)

    summaries: list[GroupSummary] = []
    for label, items in grouped.items():
        delta_values = [item.delta_pct for item in items]
        improvements = sum(1 for value in delta_values if value < -1e-9)
        regressions = sum(1 for value in delta_values if value > 1e-9)
        unchanged = len(items) - improvements - regressions
        summaries.append(
            GroupSummary(
                label=label,
                count=len(items),
                average_delta_pct=sum(delta_values) / len(delta_values),
                median_delta_pct=median(delta_values),
                improvements=improvements,
                regressions=regressions,
                unchanged=unchanged,
            )
        )

    summaries.sort(key=lambda item: item.label)
    return summaries


def build_overview_statistics(deltas: list[BenchmarkDelta]) -> dict[str, float | int]:
    """Compute accumulated comparison statistics."""
    if not deltas:
        return {
            "count": 0,
            "avg_delta_pct": 0.0,
            "median_delta_pct": 0.0,
            "avg_speedup": 0.0,
            "improved": 0,
            "regressed": 0,
            "unchanged": 0,
        }

    delta_values = [item.delta_pct for item in deltas]
    speedups = [item.speedup for item in deltas]
    improved = sum(1 for value in delta_values if value < -1e-9)
    regressed = sum(1 for value in delta_values if value > 1e-9)
    unchanged = len(deltas) - improved - regressed
    return {
        "count": len(deltas),
        "avg_delta_pct": sum(delta_values) / len(delta_values),
        "median_delta_pct": median(delta_values),
        "avg_speedup": sum(speedups) / len(speedups),
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
    }


def build_method_statistics(deltas: list[BenchmarkDelta], method: str) -> dict[str, float | int] | None:
    """Compute statistics for one benchmark method."""
    method_deltas = [item for item in deltas if item.benchmark_name == method]
    if not method_deltas:
        return None
    return build_overview_statistics(method_deltas)


def build_trends(runs: list[BenchmarkRun]) -> dict[str, list[TrendPoint]]:
    """Build time-series means per case across run history."""
    series: dict[str, list[TrendPoint]] = defaultdict(list)
    for run in runs:
        for case in run.cases:
            series[case.case_key].append(
                TrendPoint(
                    run_id=run.run_id,
                    timestamp=run.created_at,
                    mean=case.stats.mean,
                )
            )

    for points in series.values():
        points.sort(key=lambda item: (item.timestamp is None, item.timestamp, item.run_id))

    return dict(series)


def build_method_history(
    runs: list[BenchmarkRun],
    method: str,
    distinct_params: list[str] | None = None,
) -> list[dict[str, float | str | None]]:
    """Build method mean history across runs."""
    history: list[dict[str, float | str | None]] = []
    for run in runs:
        method_cases = [case for case in run.cases if case.normalized_name == method]
        if not method_cases:
            continue

        groups: dict[str, list[BenchmarkCase]] = defaultdict(list)
        for case in method_cases:
            groups[_distinct_label(case, distinct_params)].append(case)

        for distinct_label, cases in groups.items():
            means = [case.stats.mean for case in cases]
            history.append(
                {
                    "run_id": run.run_id,
                    "timestamp": run.created_at.isoformat() if run.created_at else None,
                    "method": method,
                    "distinct": distinct_label,
                    "mean": sum(means) / len(means),
                }
            )

    history.sort(
        key=lambda item: (item["timestamp"] is None, item["timestamp"], str(item["run_id"]), str(item["distinct"]))
    )
    return history


def compare_method_history_to_reference(
    runs: list[BenchmarkRun],
    reference_run: BenchmarkRun,
    method: str,
    distinct_params: list[str] | None = None,
) -> list[dict[str, float | str | None]]:
    """Compare method mean over runs against reference run mean."""
    reference_history = build_method_history([reference_run], method, distinct_params)
    reference_by_distinct = {str(item["distinct"]): float(item["mean"]) for item in reference_history}

    compared: list[dict[str, float | str | None]] = []
    for point in build_method_history(runs, method, distinct_params):
        distinct = str(point["distinct"])
        baseline = reference_by_distinct.get(distinct)
        if baseline is None or baseline <= 0:
            continue

        current = float(point["mean"])
        delta_pct = ((current - baseline) / baseline) * 100.0
        compared.append(
            {
                **point,
                "reference_mean": baseline,
                "delta_pct": delta_pct,
                "speedup": baseline / current if current > 0 else 0.0,
            }
        )

    return compared


def compare_method_to_all_prior_runs(
    runs: list[BenchmarkRun],
    candidate_run: BenchmarkRun,
    method: str,
    distinct_params: list[str] | None = None,
) -> list[dict[str, float | str | None]]:
    """Compare candidate method means against all prior runs."""
    candidate_index = _method_mean_index(candidate_run, method, distinct_params)
    if not candidate_index:
        return []

    candidate_position = _run_index(runs, candidate_run)
    prior_runs = runs[:candidate_position]
    compared: list[dict[str, float | str | None]] = []

    for reference_run in prior_runs:
        reference_index = _method_mean_index(reference_run, method, distinct_params)
        if not reference_index:
            continue

        for distinct, candidate_mean in candidate_index.items():
            reference_mean = reference_index.get(distinct)
            if reference_mean is None or reference_mean <= 0:
                continue

            delta_pct = ((candidate_mean - reference_mean) / reference_mean) * 100.0
            compared.append(
                {
                    "method": method,
                    "candidate_run_id": candidate_run.run_id,
                    "reference_run_id": reference_run.run_id,
                    "distinct": distinct,
                    "mean": candidate_mean,
                    "reference_mean": reference_mean,
                    "delta_pct": delta_pct,
                    "speedup": reference_mean / candidate_mean if candidate_mean > 0 else 0.0,
                    "reference_timestamp": reference_run.created_at.isoformat() if reference_run.created_at else None,
                }
            )

    compared.sort(
        key=lambda item: (
            item["reference_timestamp"] is None,
            item["reference_timestamp"],
            str(item["reference_run_id"]),
            str(item["distinct"]),
        )
    )
    return compared


def analyze_method_improvements(
    candidate_run: BenchmarkRun,
    reference_run: BenchmarkRun | None = None,
    group_by: list[str] | None = None,
    exclude_params: list[str] | None = None,
) -> list[MethodImprovement]:
    """Calculate mean and median improvements per method vs original and comparison run."""
    improvements: list[MethodImprovement] = []

    grouped_cand: dict[str, dict[str, dict[str, dict[str, dict[str, list[float] | set[str]]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(_empty_role_stats)))
    )

    for case in candidate_run.cases:
        group_label = build_group_label(case, group_by)
        match_label = _match_label(case, exclude_params)
        role = _implementation_role(case)

        excluded_param_values = {k: v for k, v in case.params.items() if k in (exclude_params or [])}
        if excluded_param_values:
            suffix = ",".join(f"{k}={v}" for k, v in sorted(excluded_param_values.items()))
            method_name = f"{case.base_name}[{suffix}]"
        else:
            method_name = case.base_name

        role_stats = grouped_cand[group_label][method_name][match_label][role]
        role_stats["mean"].append(case.stats.mean)
        role_stats["median"].append(case.stats.median)
        role_stats["min"].append(case.stats.min)
        role_stats["max"].append(case.stats.max)
        role_stats["names"].add(case.name)

    grouped_ref: dict[str, dict[str, dict[str, dict[str, dict[str, list[float] | set[str]]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(_empty_role_stats)))
    )
    if reference_run:
        for case in reference_run.cases:
            group_label = build_group_label(case, group_by)
            match_label = _match_label(case, exclude_params)
            role = _implementation_role(case)

            excluded_param_values = {k: v for k, v in case.params.items() if k in (exclude_params or [])}
            if excluded_param_values:
                suffix = ",".join(f"{k}={v}" for k, v in sorted(excluded_param_values.items()))
                method_name = f"{case.base_name}[{suffix}]"
            else:
                method_name = case.base_name

            role_stats = grouped_ref[group_label][method_name][match_label][role]
            role_stats["mean"].append(case.stats.mean)
            role_stats["median"].append(case.stats.median)
            role_stats["min"].append(case.stats.min)
            role_stats["max"].append(case.stats.max)
            role_stats["names"].add(case.name)

    for group_label, methods in grouped_cand.items():
        for base_name, matches in methods.items():
            all_roles = set()
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

            vs_orig_time_diffs = []
            vs_orig_pct_diffs = []
            vs_orig_median_time_diffs = []
            vs_orig_median_pct_diffs = []
            vs_orig_min_time_diffs = []
            vs_orig_min_pct_diffs = []
            vs_orig_max_time_diffs = []
            vs_orig_max_pct_diffs = []
            vs_prev_time_diffs = []
            vs_prev_pct_diffs = []
            vs_prev_median_time_diffs = []
            vs_prev_median_pct_diffs = []
            vs_prev_min_time_diffs = []
            vs_prev_min_pct_diffs = []
            vs_prev_max_time_diffs = []
            vs_prev_max_pct_diffs = []
            current_names: set[str] = set()
            comparison_names: set[str] = set()
            original_names: set[str] = set()

            for match_label, roles in matches.items():
                cand_role_stats = roles.get(primary_role)
                if not cand_role_stats:
                    continue
                cand_means = _float_list(cand_role_stats.get("mean"))
                cand_medians = _float_list(cand_role_stats.get("median"))
                cand_mins = _float_list(cand_role_stats.get("min"))
                cand_maxes = _float_list(cand_role_stats.get("max"))
                current_names.update(_name_set(cand_role_stats.get("names")))
                if not cand_means or not cand_medians or not cand_mins or not cand_maxes:
                    continue
                cand_mean = sum(cand_means) / len(cand_means)
                cand_median = median(cand_medians)
                cand_min = sum(cand_mins) / len(cand_mins)
                cand_max = sum(cand_maxes) / len(cand_maxes)

                orig_stats = _resolve_role_stats(grouped_cand, group_label, base_name, match_label, "original")
                if orig_stats and primary_role != "original":
                    orig_means = _float_list(orig_stats.get("mean"))
                    orig_medians = _float_list(orig_stats.get("median"))
                    orig_mins = _float_list(orig_stats.get("min"))
                    orig_maxes = _float_list(orig_stats.get("max"))
                    if not orig_means or not orig_medians or not orig_mins or not orig_maxes:
                        orig_stats = None

                if orig_stats and primary_role != "original":
                    orig_mean = sum(orig_means) / len(orig_means)
                    orig_median = median(orig_medians)
                    orig_min = sum(orig_mins) / len(orig_mins)
                    orig_max = sum(orig_maxes) / len(orig_maxes)
                    original_names.update(_name_set(orig_stats.get("names")))

                    mean_time_diff = orig_mean - cand_mean
                    mean_pct_diff = (mean_time_diff / orig_mean) * 100.0 if orig_mean > 0 else 0.0
                    vs_orig_time_diffs.append(mean_time_diff)
                    vs_orig_pct_diffs.append(mean_pct_diff)

                    median_time_diff = orig_median - cand_median
                    median_pct_diff = (median_time_diff / orig_median) * 100.0 if orig_median > 0 else 0.0
                    vs_orig_median_time_diffs.append(median_time_diff)
                    vs_orig_median_pct_diffs.append(median_pct_diff)

                    min_time_diff = orig_min - cand_min
                    min_pct_diff = (min_time_diff / orig_min) * 100.0 if orig_min > 0 else 0.0
                    vs_orig_min_time_diffs.append(min_time_diff)
                    vs_orig_min_pct_diffs.append(min_pct_diff)

                    max_time_diff = orig_max - cand_max
                    max_pct_diff = (max_time_diff / orig_max) * 100.0 if orig_max > 0 else 0.0
                    vs_orig_max_time_diffs.append(max_time_diff)
                    vs_orig_max_pct_diffs.append(max_pct_diff)

                if reference_run:
                    cand_names_for_match = _name_set(cand_role_stats.get("names"))
                    ref_stats = _resolve_role_stats(
                        grouped_ref,
                        group_label,
                        base_name,
                        match_label,
                        primary_role,
                        cand_names=cand_names_for_match,
                    )
                    if ref_stats:
                        ref_means = _float_list(ref_stats.get("mean"))
                        ref_medians = _float_list(ref_stats.get("median"))
                        ref_mins = _float_list(ref_stats.get("min"))
                        ref_maxes = _float_list(ref_stats.get("max"))
                    else:
                        ref_means = []
                        ref_medians = []
                        ref_mins = []
                        ref_maxes = []

                    if ref_means and ref_medians and ref_mins and ref_maxes:
                        ref_mean = sum(ref_means) / len(ref_means)
                        ref_median = median(ref_medians)
                        ref_min = sum(ref_mins) / len(ref_mins)
                        ref_max = sum(ref_maxes) / len(ref_maxes)
                        comparison_names.update(_name_set(ref_stats.get("names")) if ref_stats else set())

                        mean_time_diff = ref_mean - cand_mean
                        mean_pct_diff = (mean_time_diff / ref_mean) * 100.0 if ref_mean > 0 else 0.0
                        vs_prev_time_diffs.append(mean_time_diff)
                        vs_prev_pct_diffs.append(mean_pct_diff)

                        median_time_diff = ref_median - cand_median
                        median_pct_diff = (median_time_diff / ref_median) * 100.0 if ref_median > 0 else 0.0
                        vs_prev_median_time_diffs.append(median_time_diff)
                        vs_prev_median_pct_diffs.append(median_pct_diff)

                        min_time_diff = ref_min - cand_min
                        min_pct_diff = (min_time_diff / ref_min) * 100.0 if ref_min > 0 else 0.0
                        vs_prev_min_time_diffs.append(min_time_diff)
                        vs_prev_min_pct_diffs.append(min_pct_diff)

                        max_time_diff = ref_max - cand_max
                        max_pct_diff = (max_time_diff / ref_max) * 100.0 if ref_max > 0 else 0.0
                        vs_prev_max_time_diffs.append(max_time_diff)
                        vs_prev_max_pct_diffs.append(max_pct_diff)

            improvements.append(
                MethodImprovement(
                    group=group_label,
                    method=base_name,
                    current_benchmark_name=_format_benchmark_names(current_names),
                    comparison_benchmark_name=_format_benchmark_names(comparison_names),
                    original_benchmark_name=_format_benchmark_names(original_names),
                    avg_vs_orig_time=sum(vs_orig_time_diffs) / len(vs_orig_time_diffs) if vs_orig_time_diffs else None,
                    avg_vs_orig_pct=sum(vs_orig_pct_diffs) / len(vs_orig_pct_diffs) if vs_orig_pct_diffs else None,
                    med_vs_orig_time=median(vs_orig_median_time_diffs) if vs_orig_median_time_diffs else None,
                    med_vs_orig_pct=median(vs_orig_median_pct_diffs) if vs_orig_median_pct_diffs else None,
                    min_vs_orig_time=sum(vs_orig_min_time_diffs) / len(vs_orig_min_time_diffs)
                    if vs_orig_min_time_diffs
                    else None,
                    min_vs_orig_pct=sum(vs_orig_min_pct_diffs) / len(vs_orig_min_pct_diffs)
                    if vs_orig_min_pct_diffs
                    else None,
                    max_vs_orig_time=sum(vs_orig_max_time_diffs) / len(vs_orig_max_time_diffs)
                    if vs_orig_max_time_diffs
                    else None,
                    max_vs_orig_pct=sum(vs_orig_max_pct_diffs) / len(vs_orig_max_pct_diffs)
                    if vs_orig_max_pct_diffs
                    else None,
                    avg_vs_prev_time=sum(vs_prev_time_diffs) / len(vs_prev_time_diffs) if vs_prev_time_diffs else None,
                    avg_vs_prev_pct=sum(vs_prev_pct_diffs) / len(vs_prev_pct_diffs) if vs_prev_pct_diffs else None,
                    med_vs_prev_time=median(vs_prev_median_time_diffs) if vs_prev_median_time_diffs else None,
                    med_vs_prev_pct=median(vs_prev_median_pct_diffs) if vs_prev_median_pct_diffs else None,
                    min_vs_prev_time=sum(vs_prev_min_time_diffs) / len(vs_prev_min_time_diffs)
                    if vs_prev_min_time_diffs
                    else None,
                    min_vs_prev_pct=sum(vs_prev_min_pct_diffs) / len(vs_prev_min_pct_diffs)
                    if vs_prev_min_pct_diffs
                    else None,
                    max_vs_prev_time=sum(vs_prev_max_time_diffs) / len(vs_prev_max_time_diffs)
                    if vs_prev_max_time_diffs
                    else None,
                    max_vs_prev_pct=sum(vs_prev_max_pct_diffs) / len(vs_prev_max_pct_diffs)
                    if vs_prev_max_pct_diffs
                    else None,
                )
            )

    improvements.sort(key=lambda item: (item.group, item.method))
    return improvements


def _empty_role_stats() -> dict[str, list[float] | set[str]]:
    return {"mean": [], "median": [], "min": [], "max": [], "names": set()}


def _resolve_role_stats(
    grouped_runs: dict[str, dict[str, dict[str, dict[str, dict[str, list[float] | set[str]]]]]],
    group_label: str,
    method_name: str,
    match_label: str,
    role: str,
    cand_names: set[str] | None = None,
) -> dict[str, list[float] | set[str]] | None:
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
    # (e.g. when callspec.params contains non-serializable objects whose str()
    # representations differ between the live run and the saved JSON).
    if cand_names:
        for methods in grouped_runs.values():
            for roles in methods.get(method_name, {}).values():
                stats = roles.get(role)
                if stats and _has_role_values(stats):
                    if _name_set(stats.get("names")) & cand_names:
                        return stats

    return None


def _has_role_values(stats: dict[str, list[float] | set[str]]) -> bool:
    return bool(_float_list(stats.get("mean")) or _float_list(stats.get("median")))


def _float_list(values: object) -> list[float]:
    return list(values) if isinstance(values, list) else []


def _name_set(values: object) -> set[str]:
    return {str(value) for value in values} if isinstance(values, set) else set()


def _format_benchmark_names(names: set[str]) -> str | None:
    if not names:
        return None
    return "\n".join(sorted(names))


def build_overall_improvement_summary(improvements: list[MethodImprovement]) -> dict[str, float | int | None]:
    """Compute overall aggregated improvement metrics across all methods and devices.

    Aggregates the per-method/per-device entries returned by :func:`analyze_method_improvements`
    into a single summary covering:

    * ``vs_orig`` columns – new implementation vs original within the same run.
    * ``vs_prev`` columns – new implementation in the candidate run vs the reference run.
    """
    if not improvements:
        return {
            "count": 0,
            "avg_vs_orig_time": None,
            "avg_vs_orig_pct": None,
            "med_vs_orig_time": None,
            "med_vs_orig_pct": None,
            "min_vs_orig_time": None,
            "min_vs_orig_pct": None,
            "max_vs_orig_time": None,
            "max_vs_orig_pct": None,
            "avg_vs_prev_time": None,
            "avg_vs_prev_pct": None,
            "med_vs_prev_time": None,
            "med_vs_prev_pct": None,
            "min_vs_prev_time": None,
            "min_vs_prev_pct": None,
            "max_vs_prev_time": None,
            "max_vs_prev_pct": None,
        }

    avg_orig_times = [imp.avg_vs_orig_time for imp in improvements if imp.avg_vs_orig_time is not None]
    avg_orig_pcts = [imp.avg_vs_orig_pct for imp in improvements if imp.avg_vs_orig_pct is not None]
    med_orig_times = [imp.med_vs_orig_time for imp in improvements if imp.med_vs_orig_time is not None]
    med_orig_pcts = [imp.med_vs_orig_pct for imp in improvements if imp.med_vs_orig_pct is not None]
    min_orig_times = [imp.min_vs_orig_time for imp in improvements if imp.min_vs_orig_time is not None]
    min_orig_pcts = [imp.min_vs_orig_pct for imp in improvements if imp.min_vs_orig_pct is not None]
    max_orig_times = [imp.max_vs_orig_time for imp in improvements if imp.max_vs_orig_time is not None]
    max_orig_pcts = [imp.max_vs_orig_pct for imp in improvements if imp.max_vs_orig_pct is not None]
    avg_prev_times = [imp.avg_vs_prev_time for imp in improvements if imp.avg_vs_prev_time is not None]
    avg_prev_pcts = [imp.avg_vs_prev_pct for imp in improvements if imp.avg_vs_prev_pct is not None]
    med_prev_times = [imp.med_vs_prev_time for imp in improvements if imp.med_vs_prev_time is not None]
    med_prev_pcts = [imp.med_vs_prev_pct for imp in improvements if imp.med_vs_prev_pct is not None]
    min_prev_times = [imp.min_vs_prev_time for imp in improvements if imp.min_vs_prev_time is not None]
    min_prev_pcts = [imp.min_vs_prev_pct for imp in improvements if imp.min_vs_prev_pct is not None]
    max_prev_times = [imp.max_vs_prev_time for imp in improvements if imp.max_vs_prev_time is not None]
    max_prev_pcts = [imp.max_vs_prev_pct for imp in improvements if imp.max_vs_prev_pct is not None]

    return {
        "count": len(improvements),
        "avg_vs_orig_time": sum(avg_orig_times) / len(avg_orig_times) if avg_orig_times else None,
        "avg_vs_orig_pct": sum(avg_orig_pcts) / len(avg_orig_pcts) if avg_orig_pcts else None,
        "med_vs_orig_time": median(med_orig_times) if med_orig_times else None,
        "med_vs_orig_pct": median(med_orig_pcts) if med_orig_pcts else None,
        "min_vs_orig_time": sum(min_orig_times) / len(min_orig_times) if min_orig_times else None,
        "min_vs_orig_pct": sum(min_orig_pcts) / len(min_orig_pcts) if min_orig_pcts else None,
        "max_vs_orig_time": sum(max_orig_times) / len(max_orig_times) if max_orig_times else None,
        "max_vs_orig_pct": sum(max_orig_pcts) / len(max_orig_pcts) if max_orig_pcts else None,
        "avg_vs_prev_time": sum(avg_prev_times) / len(avg_prev_times) if avg_prev_times else None,
        "avg_vs_prev_pct": sum(avg_prev_pcts) / len(avg_prev_pcts) if avg_prev_pcts else None,
        "med_vs_prev_time": median(med_prev_times) if med_prev_times else None,
        "med_vs_prev_pct": median(med_prev_pcts) if med_prev_pcts else None,
        "min_vs_prev_time": sum(min_prev_times) / len(min_prev_times) if min_prev_times else None,
        "min_vs_prev_pct": sum(min_prev_pcts) / len(min_prev_pcts) if min_prev_pcts else None,
        "max_vs_prev_time": sum(max_prev_times) / len(max_prev_times) if max_prev_times else None,
        "max_vs_prev_pct": sum(max_prev_pcts) / len(max_prev_pcts) if max_prev_pcts else None,
    }


def build_method_group_split_bars(run: BenchmarkRun) -> dict[str, list[dict[str, float | str]]]:
    """Build split-bar chart rows per method base name for original/new roles."""
    grouped: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for case in run.cases:
        implementation_role = _implementation_role(case)
        if implementation_role not in {"original", "new"}:
            continue

        argument_label = _argument_label(case)
        grouped[case.base_name][argument_label][implementation_role].append(case.stats.mean)

    output: dict[str, list[dict[str, float | str]]] = {}
    for method_name, by_argument in grouped.items():
        rows: list[dict[str, float | str]] = []
        for argument, values in sorted(by_argument.items()):
            original_values = values.get("original")
            new_values = values.get("new")
            if not original_values or not new_values:
                continue

            original_mean = sum(original_values) / len(original_values)
            new_mean = sum(new_values) / len(new_values)
            rows.append(
                {
                    "argument": argument,
                    "original": original_mean,
                    "new": new_mean,
                    "delta_pct": ((new_mean - original_mean) / original_mean) * 100.0 if original_mean > 0 else 0.0,
                    "speedup": original_mean / new_mean if new_mean > 0 else 0.0,
                }
            )

        if rows:
            output[method_name] = rows

    return output


def build_group_label(case: BenchmarkCase, group_by: list[str] | None = None) -> str:
    """Create a logical group label for a benchmark case."""
    if group_by:
        custom_parts: list[str] = []
        for token in group_by:
            maybe_part = _resolve_group_token(case, token)
            if maybe_part:
                custom_parts.append(maybe_part)
        if custom_parts:
            return " | ".join(custom_parts)
        return "ungrouped"

    for token in DEFAULT_GROUPING_PRECEDENCE:
        maybe_part = _resolve_group_token(case, token)
        if maybe_part:
            return maybe_part

    return "ungrouped"


def _resolve_group_token(case: BenchmarkCase, token: str) -> str | None:
    normalized = token.strip().lower()

    if normalized in {"custom", "custom_group"}:
        if not case.custom_groups:
            return None
        bits = [f"{key}={value}" for key, value in sorted(case.custom_groups.items())]
        return "custom:" + ",".join(bits)

    if normalized.startswith("custom:"):
        key = token.split(":", 1)[1].strip()
        value = case.custom_groups.get(key)
        return f"custom:{key}={value}" if value else None

    if normalized in {"group", "benchmark_group"}:
        return case.benchmark_group

    if normalized in {"mark", "marks"}:
        return f"marks:{','.join(case.marks)}" if case.marks else None

    if normalized == "params":
        if not case.params:
            return None
        bits = [f"{key}={value}" for key, value in sorted(case.params.items())]
        return "params:" + ",".join(bits)

    if normalized.startswith("param:"):
        key = token.split(":", 1)[1].strip()
        value = case.params.get(key)
        return f"param:{key}={value}" if value else None

    if normalized in {"name", "benchmark_name", "method"}:
        return case.normalized_name

    if normalized in {"fullname", "nodeid"}:
        return case.normalized_fullname

    return None


def _comparison_key(case: BenchmarkCase, distinct_params: list[str] | None) -> str:
    if distinct_params:
        normalized = [token.strip() for token in distinct_params if token.strip()]
        comparable_params = {key: value for key, value in case.params.items() if key in normalized}
    else:
        comparable_params = {
            key: value for key, value in case.params.items() if key.lower() not in _IGNORED_COMPARISON_PARAMS
        }
    param_bits = ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))
    return f"{case.normalized_fullname}|{param_bits}"


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


def _implementation_role(case: BenchmarkCase) -> str:
    # First try the method postfix (e.g., method_new, method_original)
    if case.method_postfix:
        normalized = case.method_postfix.strip().lower().replace("-", "_").lstrip("_")
        if any(token in normalized for token in ("orig", "old", "baseline", "reference", "ref")):
            return "original"
        if any(token in normalized for token in ("new", "candidate", "cand")):
            return "new"

    # Fall back to implementation-related params (e.g., implementation=new, impl=original)
    for param_key in _IGNORED_COMPARISON_PARAMS:
        value = case.params.get(param_key)
        if value is not None:
            norm_val = value.strip().lower().replace("-", "_")
            if any(token in norm_val for token in ("orig", "old", "baseline", "reference", "ref")):
                return "original"
            if any(token in norm_val for token in ("new", "candidate", "cand")):
                return "new"
    return "unknown"


def _argument_label(case: BenchmarkCase) -> str:
    comparable_params = {
        key: value for key, value in case.params.items() if key.lower() not in _IGNORED_COMPARISON_PARAMS
    }
    if not comparable_params:
        return "all"
    return ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))


def _match_label(case: BenchmarkCase, exclude_params: list[str] | None) -> str:
    exclude = set(exclude_params or []) | _IGNORED_COMPARISON_PARAMS
    comparable_params = {key: value for key, value in case.params.items() if key.lower() not in exclude}
    if not comparable_params:
        return "all"
    return ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))
