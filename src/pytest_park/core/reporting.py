from __future__ import annotations

from io import StringIO
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from pytest_park.core.improvements import build_overall_improvement_summary
from pytest_park.models import BenchmarkDelta, MethodImprovement


class ReportTableBuilder:
    """Builds individual Rich tables for benchmark analysis output."""

    @staticmethod
    def render(table: Table) -> str:
        """Render a Rich Table to a string, with ANSI colour codes only when output is a TTY."""
        sio = StringIO()
        force_terminal = bool(sys.__stdout__ and sys.__stdout__.isatty())
        console = Console(file=sio, highlight=False, force_terminal=force_terminal, width=220)
        console.print(table)
        return sio.getvalue().rstrip("\n")

    @staticmethod
    def improvement_cell(value: float | None, *, is_pct: bool = False) -> Text:
        """Return a right-justified Rich Text coloured green (improvement) or red (regression)."""
        if value is None:
            return Text("N/A", justify="right")
        suffix = "%" if is_pct else "s"
        formatted = f"{value:+.4f}{suffix}"
        if value < 0:
            return Text(formatted, style="green", justify="right")
        if value > 0:
            return Text(formatted, style="red", justify="right")
        return Text(formatted, justify="right")

    def regression_table(
        self,
        improvements: list[MethodImprovement],
        *,
        candidate_label: str,
        reference_label: str,
    ) -> str:
        """Build a flat regression table comparing each method to the previous run."""
        table = Table(
            title=escape(f"Regression: {candidate_label} vs {reference_label}"),
            show_header=True,
            header_style="bold",
        )
        table.add_column("Method")
        table.add_column("Avg Time", justify="right")
        table.add_column("Avg %", justify="right")
        table.add_column("Median Time", justify="right")
        table.add_column("Median %", justify="right")
        table.add_column("Min Time", justify="right")
        table.add_column("Min %", justify="right")
        table.add_column("Max Time", justify="right")
        table.add_column("Max %", justify="right")

        for imp in improvements:
            table.add_row(
                imp.method,
                self.improvement_cell(imp.avg_vs_prev_time),
                self.improvement_cell(imp.avg_vs_prev_pct, is_pct=True),
                self.improvement_cell(imp.med_vs_prev_time),
                self.improvement_cell(imp.med_vs_prev_pct, is_pct=True),
                self.improvement_cell(imp.min_vs_prev_time),
                self.improvement_cell(imp.min_vs_prev_pct, is_pct=True),
                self.improvement_cell(imp.max_vs_prev_time),
                self.improvement_cell(imp.max_vs_prev_pct, is_pct=True),
            )

        matched = [imp for imp in improvements if imp.avg_vs_prev_time is not None]
        if matched:
            summary = build_overall_improvement_summary(matched)
            table.add_section()
            table.add_row(
                "Overall",
                self.improvement_cell(summary.avg_vs_prev_time),
                self.improvement_cell(summary.avg_vs_prev_pct, is_pct=True),
                self.improvement_cell(summary.med_vs_prev_time),
                self.improvement_cell(summary.med_vs_prev_pct, is_pct=True),
                self.improvement_cell(summary.min_vs_prev_time),
                self.improvement_cell(summary.min_vs_prev_pct, is_pct=True),
                self.improvement_cell(summary.max_vs_prev_time),
                self.improvement_cell(summary.max_vs_prev_pct, is_pct=True),
            )

        return self.render(table)

    def postfix_comparison_tables(
        self,
        improvements: list[MethodImprovement],
        *,
        original_postfixes: list[str],
        reference_postfixes: list[str],
    ) -> list[str]:
        """Build one Rich table per method group comparing original-postfix vs reference-postfix methods."""
        orig_label = ",".join(original_postfixes)
        ref_label = ",".join(reference_postfixes)

        groups: dict[str, list[MethodImprovement]] = {}
        for imp in improvements:
            groups.setdefault(imp.group, []).append(imp)

        result: list[str] = []
        for group_name, group_improvements in groups.items():
            group_part = f" [{group_name}]" if group_name else ""
            table = Table(
                title=escape(f"Postfix Comparison{group_part}: {orig_label} vs {ref_label}"),
                show_header=True,
                header_style="bold",
            )
            table.add_column("Method")
            table.add_column(f"Original ({orig_label})")
            table.add_column(f"Reference ({ref_label})")
            table.add_column("Args", justify="center")
            table.add_column("Avg Time", justify="right")
            table.add_column("Avg %", justify="right")
            table.add_column("Median Time", justify="right")
            table.add_column("Median %", justify="right")
            table.add_column("Min Time", justify="right")
            table.add_column("Min %", justify="right")
            table.add_column("Max Time", justify="right")
            table.add_column("Max %", justify="right")

            for imp in group_improvements:
                args = f"{imp.orig_arg_count}/{imp.ref_arg_count}" if imp.orig_arg_count or imp.ref_arg_count else "-"
                table.add_row(
                    imp.method,
                    imp.original_benchmark_name or "N/A",
                    imp.current_benchmark_name or "N/A",
                    args,
                    self.improvement_cell(imp.avg_vs_orig_time),
                    self.improvement_cell(imp.avg_vs_orig_pct, is_pct=True),
                    self.improvement_cell(imp.med_vs_orig_time),
                    self.improvement_cell(imp.med_vs_orig_pct, is_pct=True),
                    self.improvement_cell(imp.min_vs_orig_time),
                    self.improvement_cell(imp.min_vs_orig_pct, is_pct=True),
                    self.improvement_cell(imp.max_vs_orig_time),
                    self.improvement_cell(imp.max_vs_orig_pct, is_pct=True),
                )

            matched = [imp for imp in group_improvements if imp.avg_vs_orig_time is not None]
            if matched:
                summary = build_overall_improvement_summary(matched)
                table.add_section()
                table.add_row(
                    "Overall",
                    "-",
                    "-",
                    "-",
                    self.improvement_cell(summary.avg_vs_orig_time),
                    self.improvement_cell(summary.avg_vs_orig_pct, is_pct=True),
                    self.improvement_cell(summary.med_vs_orig_time),
                    self.improvement_cell(summary.med_vs_orig_pct, is_pct=True),
                    self.improvement_cell(summary.min_vs_orig_time),
                    self.improvement_cell(summary.min_vs_orig_pct, is_pct=True),
                    self.improvement_cell(summary.max_vs_orig_time),
                    self.improvement_cell(summary.max_vs_orig_pct, is_pct=True),
                )

            result.append(self.render(table))

        return result


class BenchmarkReporter:
    """Orchestrates benchmark analysis output: assembles and renders all report sections."""

    def __init__(self, table_builder: ReportTableBuilder | None = None) -> None:
        self.tables = table_builder or ReportTableBuilder()

    @staticmethod
    def benchmark_header_label(source_file: str | None, fallback: str) -> str:
        """Return a compact table header label for a benchmark source file path."""
        if not source_file:
            return fallback
        if source_file.startswith("<") and source_file.endswith(">"):
            return fallback
        return source_file.replace("\\", "/").rsplit("/", maxsplit=1)[-1] or fallback

    @staticmethod
    def format_improvement_value(value: float | None, *, is_pct: bool = False) -> str:
        """Format one analysis value for terminal output."""
        if value is None:
            return "N/A"
        suffix = "%" if is_pct else "s"
        return f"{value:+.4f}{suffix}"

    @staticmethod
    def format_delta_line(delta: BenchmarkDelta, *, baseline_label: str | None = None) -> str:
        """Format a single benchmark delta as a concise summary line."""
        direction = "unchanged" if abs(delta.delta_pct) <= 1e-9 else "faster" if delta.delta_pct < 0 else "slower"
        baseline = baseline_label or delta.reference_run_id
        return (
            f"{delta.benchmark_name}: {abs(delta.delta_pct):.2f}% {direction} "
            f"({_format_duration(delta.candidate_mean)} vs {_format_duration(delta.reference_mean)}, {delta.speedup:.2f}x) "
            f"vs {baseline}"
        )


# ---------------------------------------------------------------------------
# Module-level private helpers
# ---------------------------------------------------------------------------


def _format_duration(value: float) -> str:
    if value >= 1:
        return f"{value:.3f}s"
    if value >= 1e-3:
        return f"{value * 1e3:.3f}ms"
    if value >= 1e-6:
        return f"{value * 1e6:.3f}μs"
    return f"{value * 1e9:.3f}ns"


# ---------------------------------------------------------------------------
# Module-level convenience functions (delegate to a default reporter instance)
# ---------------------------------------------------------------------------

_default_reporter = BenchmarkReporter()


def build_regression_table(
    improvements: list[MethodImprovement],
    *,
    candidate_label: str,
    reference_label: str,
) -> str:
    """Build a flat regression table comparing each method to the previous run."""
    return _default_reporter.tables.regression_table(
        improvements, candidate_label=candidate_label, reference_label=reference_label
    )


def build_postfix_comparison_table(
    improvements: list[MethodImprovement],
    *,
    original_postfixes: list[str],
    reference_postfixes: list[str],
) -> list[str]:
    """Build one Rich table per method group for postfix comparison."""
    return _default_reporter.tables.postfix_comparison_tables(
        improvements,
        original_postfixes=original_postfixes,
        reference_postfixes=reference_postfixes,
    )


def build_benchmark_header_label(source_file: str | None, fallback: str) -> str:
    """Return a compact table header label for a benchmark source."""
    return BenchmarkReporter.benchmark_header_label(source_file, fallback)


def format_improvement_value(value: float | None, *, is_pct: bool = False) -> str:
    """Format one analysis value for terminal table output."""
    return BenchmarkReporter.format_improvement_value(value, is_pct=is_pct)


def format_delta_line(delta: BenchmarkDelta, *, baseline_label: str | None = None) -> str:
    """Format a single benchmark delta as a concise summary line."""
    return BenchmarkReporter.format_delta_line(delta, baseline_label=baseline_label)
