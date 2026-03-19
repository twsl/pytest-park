from pytest_park.core._grouping import DEFAULT_GROUPING_PRECEDENCE, build_group_label
from pytest_park.core.comparison import (
    build_method_group_split_bars,
    build_method_statistics,
    build_overview_statistics,
    compare_runs,
    summarize_groups,
)
from pytest_park.core.history import (
    build_method_history,
    build_trends,
    compare_method_history_to_reference,
    compare_method_to_all_prior_runs,
)
from pytest_park.core.runs import (
    attach_profiler_data,
    list_methods,
    select_candidate_run,
    select_latest_and_previous_runs,
    select_reference_run,
)

__all__ = [
    "DEFAULT_GROUPING_PRECEDENCE",
    "attach_profiler_data",
    "build_method_group_split_bars",
    "build_group_label",
    "build_method_history",
    "build_method_statistics",
    "build_overview_statistics",
    "build_trends",
    "compare_method_history_to_reference",
    "compare_method_to_all_prior_runs",
    "compare_runs",
    "list_methods",
    "select_candidate_run",
    "select_latest_and_previous_runs",
    "select_reference_run",
    "summarize_groups",
]
