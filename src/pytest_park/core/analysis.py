from __future__ import annotations

from collections import defaultdict
from statistics import median

from pytest_park.models import BenchmarkCase, BenchmarkDelta, BenchmarkRun, GroupSummary, TrendPoint

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
    implementation_role = _implementation_role(case)
    return f"{case.normalized_fullname}|{param_bits}|role={implementation_role}"


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
    if not case.method_postfix:
        return "unknown"

    normalized = case.method_postfix.strip().lower().replace("-", "_")
    normalized = normalized.lstrip("_")

    if any(token in normalized for token in ("orig", "old", "baseline", "reference", "ref")):
        return "original"
    if any(token in normalized for token in ("new", "candidate", "cand")):
        return "new"
    return "unknown"


def _argument_label(case: BenchmarkCase) -> str:
    comparable_params = {
        key: value for key, value in case.params.items() if key.lower() not in _IGNORED_COMPARISON_PARAMS
    }
    if not comparable_params:
        return "all"
    return ",".join(f"{key}={value}" for key, value in sorted(comparable_params.items()))
