from __future__ import annotations

from typing import Any

from pytest_park.core import (
    build_method_group_split_bars,
    build_method_statistics,
    build_overview_statistics,
    compare_method_history_to_reference,
    compare_method_to_all_prior_runs,
    compare_runs,
    list_methods,
    select_candidate_run,
    select_reference_run,
    summarize_groups,
)
from pytest_park.data import load_benchmark_folder


def serve_dashboard(
    benchmark_folder: str,
    reference: str | None,
    group_by: list[str] | None,
    distinct_params: list[str] | None,
    original_postfix: str | None,
    reference_postfix: str | None,
    host: str,
    port: int,
) -> None:
    """Serve a local NiceGUI dashboard for benchmark comparison."""
    try:
        from nicegui import app, ui
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NiceGUI is not installed. Install project dependencies with UI support.") from exc

    runs = load_benchmark_folder(
        benchmark_folder,
        original_postfix=original_postfix,
        reference_postfix=reference_postfix,
    )
    run_ids = [run.run_id for run in runs]
    default_reference = reference or (run_ids[-2] if len(run_ids) > 1 else run_ids[0])
    default_candidate = run_ids[-1]
    method_options = list_methods(runs)

    state: dict[str, Any] = {
        "reference": default_reference,
        "candidate": default_candidate,
        "group_by": ",".join(group_by or []),
        "distinct_params": ",".join(distinct_params or []),
        "method": method_options[0] if method_options else None,
        "original_postfix": original_postfix or "",
        "reference_postfix": reference_postfix or "",
    }

    @ui.page("/")
    def dashboard_page() -> None:
        ui.label("pytest-park benchmark dashboard").classes("text-h5")

        with ui.row():
            ui.select(
                run_ids,
                label="Reference run",
                value=default_reference,
                on_change=lambda event: _set(state, "reference", event.value),
            )
            ui.select(
                run_ids,
                label="Candidate run",
                value=default_candidate,
                on_change=lambda event: _set(state, "candidate", event.value),
            )
            ui.input(
                label="Group by (comma separated)",
                value=state["group_by"],
                on_change=lambda event: _set(state, "group_by", str(event.value)),
            )
            ui.input(
                label="Distinct params (comma separated)",
                value=state["distinct_params"],
                on_change=lambda event: _set(state, "distinct_params", str(event.value)),
            )
            ui.input(
                label="Original postfix",
                value=state["original_postfix"],
                on_change=lambda event: _set(state, "original_postfix", str(event.value)),
            )
            ui.input(
                label="Reference postfix",
                value=state["reference_postfix"],
                on_change=lambda event: _set(state, "reference_postfix", str(event.value)),
            )

        with ui.row():
            method_select = ui.select(
                method_options,
                label="Method",
                value=state["method"],
                on_change=lambda event: _set(state, "method", event.value),
            )

        with ui.row().classes("w-full"):
            compared_runs_label = ui.label("").classes("text-subtitle2")
            case_count_label = ui.label("").classes("text-subtitle2")
            improved_label = ui.label("").classes("text-subtitle2")
            regressed_label = ui.label("").classes("text-subtitle2")
            avg_delta_label = ui.label("").classes("text-subtitle2")
            avg_speedup_label = ui.label("").classes("text-subtitle2")

        with ui.row().classes("w-full"):
            best_case_label = ui.label("").classes("text-caption")
            worst_case_label = ui.label("").classes("text-caption")

        method_label = ui.label("")

        entry_history_table = ui.table(
            columns=[
                {"name": "method", "label": "Method", "field": "method"},
                {"name": "current_mean", "label": "Current mean", "field": "current_mean"},
                {"name": "reference_mean", "label": "Reference mean", "field": "reference_mean"},
                {"name": "delta", "label": "Delta %", "field": "delta"},
                {"name": "speedup", "label": "Speedup", "field": "speedup"},
                {"name": "history", "label": "Average history", "field": "history"},
            ],
            rows=[],
            row_key="method",
        )

        history_chart = ui.echart(
            {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["Mean", "Delta %", "Speedup"]},
                "xAxis": {"type": "category", "data": []},
                "yAxis": [
                    {"type": "value", "name": "Mean"},
                    {"type": "value", "name": "Delta %"},
                    {"type": "value", "name": "Speedup"},
                ],
                "series": [
                    {"name": "Mean", "type": "line", "data": []},
                    {"name": "Delta %", "type": "line", "yAxisIndex": 1, "data": []},
                    {"name": "Speedup", "type": "line", "yAxisIndex": 2, "data": []},
                ],
            }
        )

        with ui.row().classes("w-full"):
            delta_distribution_chart = ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "Cases"},
                    "series": [{"name": "Delta distribution", "type": "bar", "data": []}],
                }
            ).classes("col")
            group_performance_chart = ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["Avg delta %", "Cases"]},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": [
                        {"type": "value", "name": "Avg delta %"},
                        {"type": "value", "name": "Cases"},
                    ],
                    "series": [
                        {"name": "Avg delta %", "type": "bar", "data": []},
                        {"name": "Cases", "type": "line", "yAxisIndex": 1, "data": []},
                    ],
                }
            ).classes("col")

        top_movers_chart = ui.echart(
            {
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "value", "name": "Delta %"},
                "yAxis": {"type": "category", "data": []},
                "series": [{"name": "Top movers", "type": "bar", "data": []}],
            }
        )

        split_chart_container = ui.column()

        method_prior_table = ui.table(
            columns=[
                {"name": "reference_run", "label": "Reference run", "field": "reference_run"},
                {"name": "distinct", "label": "Distinct", "field": "distinct"},
                {"name": "candidate_mean", "label": "Candidate mean", "field": "candidate_mean"},
                {"name": "reference_mean", "label": "Reference mean", "field": "reference_mean"},
                {"name": "delta", "label": "Delta %", "field": "delta"},
                {"name": "speedup", "label": "Speedup", "field": "speedup"},
            ],
            rows=[],
            row_key="reference_run",
        )

        delta_table = ui.table(
            columns=[
                {"name": "group", "label": "Group", "field": "group"},
                {"name": "benchmark", "label": "Benchmark", "field": "benchmark"},
                {"name": "case_key", "label": "Case key", "field": "case_key"},
                {"name": "params", "label": "Params", "field": "params"},
                {"name": "delta", "label": "Delta %", "field": "delta"},
                {"name": "speedup", "label": "Speedup", "field": "speedup"},
            ],
            rows=[],
            row_key="benchmark",
        )
        group_table = ui.table(
            columns=[
                {"name": "label", "label": "Group", "field": "label"},
                {"name": "count", "label": "Cases", "field": "count"},
                {"name": "avg", "label": "Avg delta %", "field": "avg"},
                {"name": "median", "label": "Median delta %", "field": "median"},
                {"name": "improvements", "label": "Improved", "field": "improvements"},
                {"name": "regressions", "label": "Regressed", "field": "regressions"},
            ],
            rows=[],
            row_key="label",
        )

        def refresh() -> None:
            current_runs = load_benchmark_folder(
                benchmark_folder,
                original_postfix=str(state.get("original_postfix") or ""),
                reference_postfix=str(state.get("reference_postfix") or ""),
            )
            current_methods = list_methods(current_runs)
            method_select.options = current_methods
            method_select.update()

            selected_method = str(state.get("method") or "")
            if selected_method not in current_methods:
                selected_method = current_methods[0] if current_methods else ""
                state["method"] = selected_method

            reference_run = select_reference_run(current_runs, str(state["reference"]))
            candidate_run = select_candidate_run(current_runs, str(state["candidate"]), reference_run)
            group_tokens = [part.strip() for part in str(state["group_by"]).split(",") if part.strip()]
            distinct_tokens = [part.strip() for part in str(state["distinct_params"]).split(",") if part.strip()]
            deltas = compare_runs(reference_run, candidate_run, group_tokens or None, distinct_tokens or None)
            summaries = summarize_groups(deltas)
            overview = build_overview_statistics(deltas)

            compared_runs_label.text = f"Runs: {reference_run.run_id} -> {candidate_run.run_id}"
            case_count_label.text = f"Cases: {overview['count']}"
            improved_label.text = f"Improved: {overview['improved']}"
            regressed_label.text = f"Regressed: {overview['regressed']}"
            avg_delta_label.text = (
                f"Avg delta: {overview['avg_delta_pct']:.2f}% (median {overview['median_delta_pct']:.2f}%)"
            )
            avg_speedup_label.text = f"Avg speedup: {overview['avg_speedup']:.3f}x"

            best_case = min(deltas, key=lambda item: item.delta_pct, default=None)
            worst_case = max(deltas, key=lambda item: item.delta_pct, default=None)
            best_case_label.text = (
                f"Best: {_format_case(best_case)} ({best_case.delta_pct:.2f}%)" if best_case else "Best: n/a"
            )
            worst_case_label.text = (
                f"Worst: {_format_case(worst_case)} ({worst_case.delta_pct:.2f}%)" if worst_case else "Worst: n/a"
            )

            method_stats = build_method_statistics(deltas, selected_method) if selected_method else None
            if method_stats:
                method_label.text = (
                    f"Method {selected_method}: count={method_stats['count']} avg_delta={method_stats['avg_delta_pct']:.2f}% "
                    f"avg_speedup={method_stats['avg_speedup']:.3f}"
                )
            else:
                method_label.text = "Method statistics unavailable for selected method"

            history = (
                compare_method_history_to_reference(
                    current_runs, reference_run, selected_method, distinct_tokens or None
                )
                if selected_method
                else []
            )
            history_chart.options["xAxis"]["data"] = [f"{item['run_id']} ({item['distinct']})" for item in history]
            history_chart.options["series"][0]["data"] = [round(float(item["mean"]), 6) for item in history]
            history_chart.options["series"][1]["data"] = [round(float(item["delta_pct"]), 2) for item in history]
            history_chart.options["series"][2]["data"] = [round(float(item["speedup"]), 3) for item in history]
            history_chart.update()

            dist_labels, dist_counts = _build_delta_distribution(deltas)
            delta_distribution_chart.options["xAxis"]["data"] = dist_labels
            delta_distribution_chart.options["series"][0]["data"] = dist_counts
            delta_distribution_chart.update()

            group_labels = [item.label for item in summaries]
            group_avg = [round(item.average_delta_pct, 2) for item in summaries]
            group_counts = [item.count for item in summaries]
            group_performance_chart.options["xAxis"]["data"] = group_labels
            group_performance_chart.options["series"][0]["data"] = group_avg
            group_performance_chart.options["series"][1]["data"] = group_counts
            group_performance_chart.update()

            mover_labels, mover_values = _build_top_movers(deltas)
            top_movers_chart.options["yAxis"]["data"] = mover_labels
            top_movers_chart.options["series"][0]["data"] = mover_values
            top_movers_chart.update()

            split_rows_by_method = build_method_group_split_bars(candidate_run)
            split_chart_container.clear()
            with split_chart_container:
                ui.label(f"Original vs new (run {candidate_run.run_id})").classes("text-subtitle1")
                if not split_rows_by_method:
                    ui.label("No paired original/new benchmark data found in candidate run")
                for method_name, rows in sorted(split_rows_by_method.items()):
                    ui.label(method_name).classes("text-subtitle2")
                    ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["original", "new"]},
                            "xAxis": {"type": "category", "data": [str(item["argument"]) for item in rows]},
                            "yAxis": {"type": "value", "name": "Mean"},
                            "series": [
                                {
                                    "name": "original",
                                    "type": "bar",
                                    "data": [round(float(item["original"]), 6) for item in rows],
                                },
                                {
                                    "name": "new",
                                    "type": "bar",
                                    "data": [round(float(item["new"]), 6) for item in rows],
                                },
                            ],
                        }
                    )

            prior_rows = (
                compare_method_to_all_prior_runs(current_runs, candidate_run, selected_method, distinct_tokens or None)
                if selected_method
                else []
            )
            method_prior_table.rows = [
                {
                    "reference_run": str(item["reference_run_id"]),
                    "distinct": str(item["distinct"]),
                    "candidate_mean": round(float(item["mean"]), 6),
                    "reference_mean": round(float(item["reference_mean"]), 6),
                    "delta": round(float(item["delta_pct"]), 2),
                    "speedup": round(float(item["speedup"]), 3),
                }
                for item in prior_rows
            ]

            entry_rows: list[dict[str, Any]] = []
            for method_name in current_methods:
                method_history = compare_method_history_to_reference(
                    current_runs,
                    reference_run,
                    method_name,
                    distinct_tokens or None,
                )
                if not method_history:
                    continue

                history_by_run: dict[str, list[dict[str, float | str | None]]] = {}
                for point in method_history:
                    history_by_run.setdefault(str(point["run_id"]), []).append(point)

                ordered_runs = sorted(
                    history_by_run.keys(), key=lambda run_id: run_ids.index(run_id) if run_id in run_ids else -1
                )
                history_bits: list[str] = []
                for run_id in ordered_runs:
                    run_points = history_by_run[run_id]
                    avg_mean = sum(float(item["mean"]) for item in run_points) / len(run_points)
                    avg_delta = sum(float(item["delta_pct"]) for item in run_points) / len(run_points)
                    history_bits.append(f"{run_id}:{avg_mean:.6f} ({avg_delta:.2f}%)")

                candidate_points = history_by_run.get(candidate_run.run_id)
                if not candidate_points:
                    continue

                current_mean = sum(float(item["mean"]) for item in candidate_points) / len(candidate_points)
                reference_mean = sum(float(item["reference_mean"]) for item in candidate_points) / len(candidate_points)
                delta_pct = ((current_mean - reference_mean) / reference_mean) * 100.0 if reference_mean > 0 else 0.0
                speedup = reference_mean / current_mean if current_mean > 0 else 0.0

                entry_rows.append(
                    {
                        "method": method_name,
                        "current_mean": round(current_mean, 6),
                        "reference_mean": round(reference_mean, 6),
                        "delta": round(delta_pct, 2),
                        "speedup": round(speedup, 3),
                        "history": " -> ".join(history_bits),
                    }
                )

            entry_history_table.rows = entry_rows

            delta_table.rows = [
                {
                    "group": item.group_label,
                    "benchmark": item.benchmark_name,
                    "case_key": item.case_key,
                    "params": ", ".join(f"{k}={v}" for k, v in sorted(item.params.items())),
                    "delta": round(item.delta_pct, 2),
                    "speedup": round(item.speedup, 3),
                }
                for item in deltas
            ]
            group_table.rows = [
                {
                    "label": item.label,
                    "count": item.count,
                    "avg": round(item.average_delta_pct, 2),
                    "median": round(item.median_delta_pct, 2),
                    "improvements": item.improvements,
                    "regressions": item.regressions,
                }
                for item in summaries
            ]

        ui.button("Refresh", on_click=lambda: refresh())
        refresh()

    @app.get("/favicon.ico")
    async def favicon() -> dict[str, str]:
        return {"status": "ok"}

    ui.run(host=host, port=port, reload=False, show=False)


def _set(state: dict[str, Any], key: str, value: Any) -> None:
    state[key] = value


def _format_case(item) -> str:
    if item is None:
        return "n/a"
    params = ",".join(f"{key}={value}" for key, value in sorted(item.params.items()))
    if not params:
        return item.benchmark_name
    return f"{item.benchmark_name}[{params}]"


def _build_delta_distribution(deltas, bin_size: float = 5.0) -> tuple[list[str], list[int]]:
    if not deltas:
        return [], []

    buckets: dict[int, int] = {}
    for item in deltas:
        bucket = int(item.delta_pct // bin_size)
        buckets[bucket] = buckets.get(bucket, 0) + 1

    labels: list[str] = []
    counts: list[int] = []
    for bucket in sorted(buckets):
        lower = bucket * bin_size
        upper = lower + bin_size
        labels.append(f"{lower:.0f}%..{upper:.0f}%")
        counts.append(buckets[bucket])
    return labels, counts


def _build_top_movers(deltas, limit: int = 10) -> tuple[list[str], list[float]]:
    if not deltas:
        return [], []

    ordered = sorted(deltas, key=lambda item: abs(item.delta_pct), reverse=True)[:limit]
    labels = [_format_case(item) for item in ordered]
    values = [round(item.delta_pct, 2) for item in ordered]
    return labels, values
