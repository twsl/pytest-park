from __future__ import annotations

from pytest_park.core import build_overall_improvement_summary
from pytest_park.models import BenchmarkDelta, MethodImprovement

_MISSING_COMPARISON_MESSAGE = (
    "No comparison benchmark found. Run with --benchmark-save first to create a benchmark file."
)


def build_analysis_tables(
    improvements: list[MethodImprovement],
    candidate_run_id: str,
    *,
    current_benchmark_header: str | None = None,
    comparison_benchmark_header: str | None = None,
) -> list[str]:
    """Build the text tables used for benchmark analysis output.

    The layout intentionally mirrors the plain terminal style used by
    `pytest-benchmark`: title centered in dashes, header row, divider, rows,
    summary divider, summary row, closing divider. Column widths are derived
    from content and are not artificially capped.
    """
    tables: list[str] = []

    if comparison_benchmark_header is not None:
        tables.append(
            _build_improvement_table(
                improvements,
                title=f"Current Run vs Comparison Run (Candidate: {candidate_run_id})",
                left_benchmark_header=current_benchmark_header or "Current Benchmark",
                right_benchmark_header=comparison_benchmark_header,
                left_benchmark_attr="current_benchmark_name",
                right_benchmark_attr="comparison_benchmark_name",
                avg_time_attr="avg_vs_prev_time",
                avg_pct_attr="avg_vs_prev_pct",
                median_time_attr="med_vs_prev_time",
                median_pct_attr="med_vs_prev_pct",
                min_time_attr="min_vs_prev_time",
                min_pct_attr="min_vs_prev_pct",
                max_time_attr="max_vs_prev_time",
                max_pct_attr="max_vs_prev_pct",
            )
        )
    else:
        tables.append(_MISSING_COMPARISON_MESSAGE)

    original_improvements = [improvement for improvement in improvements if _has_original_benchmark(improvement)]
    if original_improvements:
        tables.append(
            _build_improvement_table(
                original_improvements,
                title=f"Reference vs Original Implementation (Candidate: {candidate_run_id})",
                left_benchmark_header="Reference Benchmark",
                right_benchmark_header="Original Benchmark",
                left_benchmark_attr="current_benchmark_name",
                right_benchmark_attr="original_benchmark_name",
                avg_time_attr="avg_vs_orig_time",
                avg_pct_attr="avg_vs_orig_pct",
                median_time_attr="med_vs_orig_time",
                median_pct_attr="med_vs_orig_pct",
                min_time_attr="min_vs_orig_time",
                min_pct_attr="min_vs_orig_pct",
                max_time_attr="max_vs_orig_time",
                max_pct_attr="max_vs_orig_pct",
            )
        )

    return tables


def build_analysis_table(improvements: list[MethodImprovement], candidate_run_id: str) -> str:
    """Build the primary text table used for benchmark analysis output."""
    return build_analysis_tables(improvements, candidate_run_id)[0]


def build_benchmark_header_label(source_file: str | None, fallback: str) -> str:
    """Return a compact table header label for a benchmark source."""
    if not source_file:
        return fallback

    if source_file.startswith("<") and source_file.endswith(">"):
        return fallback

    return source_file.replace("\\", "/").rsplit("/", maxsplit=1)[-1] or fallback


def _has_original_benchmark(improvement: MethodImprovement) -> bool:
    return improvement.original_benchmark_name is not None or any(
        value is not None
        for value in (
            improvement.avg_vs_orig_time,
            improvement.avg_vs_orig_pct,
            improvement.med_vs_orig_time,
            improvement.med_vs_orig_pct,
            improvement.min_vs_orig_time,
            improvement.min_vs_orig_pct,
            improvement.max_vs_orig_time,
            improvement.max_vs_orig_pct,
        )
    )


def _build_improvement_table(
    improvements: list[MethodImprovement],
    *,
    title: str,
    left_benchmark_header: str,
    right_benchmark_header: str,
    left_benchmark_attr: str,
    right_benchmark_attr: str,
    avg_time_attr: str,
    avg_pct_attr: str,
    median_time_attr: str,
    median_pct_attr: str,
    min_time_attr: str,
    min_pct_attr: str,
    max_time_attr: str,
    max_pct_attr: str,
) -> str:
    headers = [
        "Group",
        "Method",
        left_benchmark_header,
        right_benchmark_header,
        "Avg Time",
        "Avg %",
        "Median Time",
        "Median %",
        "Min Time",
        "Min %",
        "Max Time",
        "Max %",
    ]
    rows = [
        [
            improvement.group,
            improvement.method,
            getattr(improvement, left_benchmark_attr) or "N/A",
            getattr(improvement, right_benchmark_attr) or "N/A",
            format_improvement_value(getattr(improvement, avg_time_attr)),
            format_improvement_value(getattr(improvement, avg_pct_attr), is_pct=True),
            format_improvement_value(getattr(improvement, median_time_attr)),
            format_improvement_value(getattr(improvement, median_pct_attr), is_pct=True),
            format_improvement_value(getattr(improvement, min_time_attr)),
            format_improvement_value(getattr(improvement, min_pct_attr), is_pct=True),
            format_improvement_value(getattr(improvement, max_time_attr)),
            format_improvement_value(getattr(improvement, max_pct_attr), is_pct=True),
        ]
        for improvement in improvements
    ]

    summary_row: list[str] | None = None
    if improvements:
        summary = build_overall_improvement_summary(improvements)
        summary_row = [
            "Overall",
            "All Methods",
            "-",
            "-",
            format_improvement_value(summary.get(avg_time_attr)),
            format_improvement_value(summary.get(avg_pct_attr), is_pct=True),
            format_improvement_value(summary.get(median_time_attr)),
            format_improvement_value(summary.get(median_pct_attr), is_pct=True),
            format_improvement_value(summary.get(min_time_attr)),
            format_improvement_value(summary.get(min_pct_attr), is_pct=True),
            format_improvement_value(summary.get(max_time_attr)),
            format_improvement_value(summary.get(max_pct_attr), is_pct=True),
        ]

    widths = [
        max(
            len(headers[index]),
            max((len(row[index]) for row in rows), default=0),
            len(summary_row[index]) if summary_row is not None else 0,
        )
        for index in range(len(headers))
    ]
    alignments = [
        "left",
        "left",
        "left",
        "left",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
    ]

    header_line = _format_row(headers, widths, alignments)
    divider = "-" * len(header_line)
    lines = [f" {title} ".center(len(header_line), "-"), header_line, divider]
    lines.extend(_format_row(row, widths, alignments) for row in rows)
    if summary_row is not None:
        lines.append(divider)
        lines.append(_format_row(summary_row, widths, alignments))
    lines.append(divider)
    return "\n".join(lines)


def _format_row(values: list[str], widths: list[int], alignments: list[str]) -> str:
    cells = []
    for value, width, alignment in zip(values, widths, alignments, strict=True):
        if alignment == "right":
            cells.append(value.rjust(width))
        else:
            cells.append(value.ljust(width))
    return "  ".join(cells)


def format_improvement_value(value: float | None, *, is_pct: bool = False) -> str:
    """Format one analysis value for terminal table output."""
    if value is None:
        return "N/A"
    suffix = "%" if is_pct else "s"
    return f"{value:+.4f}{suffix}"


def format_delta_line(delta: BenchmarkDelta, *, baseline_label: str | None = None) -> str:
    """Format a single benchmark delta as a concise summary line."""
    direction = "unchanged" if abs(delta.delta_pct) <= 1e-9 else "faster" if delta.delta_pct < 0 else "slower"

    baseline = baseline_label or delta.reference_run_id
    return (
        f"{delta.benchmark_name}: {abs(delta.delta_pct):.2f}% {direction} "
        f"({_format_duration(delta.candidate_mean)} vs {_format_duration(delta.reference_mean)}, {delta.speedup:.2f}x) "
        f"vs {baseline}"
    )


def _format_duration(value: float) -> str:
    if value >= 1:
        return f"{value:.3f}s"
    if value >= 1e-3:
        return f"{value * 1e3:.3f}ms"
    if value >= 1e-6:
        return f"{value * 1e6:.3f}μs"
    return f"{value * 1e9:.3f}ns"
