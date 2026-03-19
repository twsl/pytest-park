from pytest_park.core._grouping import DEFAULT_GROUPING_PRECEDENCE, BenchmarkGrouper, build_group_label
from pytest_park.core.comparison import (
    RunComparator,
    build_method_group_split_bars,
    build_method_statistics,
    build_overview_statistics,
    compare_runs,
    summarize_groups,
)
from pytest_park.core.history import (
    HistoryAnalyzer,
    build_method_history,
    build_trends,
    compare_method_history_to_reference,
    compare_method_to_all_prior_runs,
)
from pytest_park.core.improvements import (
    ImprovementAnalyzer,
    analyze_method_improvements,
    build_overall_improvement_summary,
    build_postfix_comparison,
    build_regression_improvements,
)
from pytest_park.core.reporting import (
    BenchmarkReporter,
    ReportTableBuilder,
    build_benchmark_header_label,
    build_postfix_comparison_table,
    build_regression_table,
    format_delta_line,
    format_improvement_value,
)
from pytest_park.core.runs import (
    RunSelector,
    attach_profiler_data,
    list_methods,
    select_candidate_run,
    select_latest_and_previous_runs,
    select_reference_run,
)

__all__ = [
    "BenchmarkGrouper",
    "BenchmarkReporter",
    "DEFAULT_GROUPING_PRECEDENCE",
    "ReportTableBuilder",
    "analyze_method_improvements",
    "attach_profiler_data",
    "build_benchmark_header_label",
    "build_group_label",
    "build_method_group_split_bars",
    "build_method_history",
    "build_method_statistics",
    "build_overall_improvement_summary",
    "build_overview_statistics",
    "build_postfix_comparison",
    "build_postfix_comparison_table",
    "build_regression_improvements",
    "build_regression_table",
    "build_trends",
    "compare_method_history_to_reference",
    "compare_method_to_all_prior_runs",
    "compare_runs",
    "format_delta_line",
    "format_improvement_value",
    "list_methods",
    "select_candidate_run",
    "select_latest_and_previous_runs",
    "select_reference_run",
    "summarize_groups",
]
