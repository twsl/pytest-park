from __future__ import annotations

from pytest_park.models import MethodImprovement
from pytest_park.reporting import build_analysis_tables, build_benchmark_header_label


def _render_table(improvements: list[MethodImprovement]) -> str:
    return "\n\n".join(
        build_analysis_tables(
            improvements,
            "candidate-run",
            current_benchmark_header="candidate.json",
            comparison_benchmark_header="reference.json",
        )
    )


def test_build_analysis_tables_only_include_comparison_table_without_original_data() -> None:
    tables = build_analysis_tables(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_current",
                comparison_benchmark_name="func1_previous",
                avg_vs_orig_time=None,
                avg_vs_orig_pct=None,
                med_vs_orig_time=None,
                med_vs_orig_pct=None,
                avg_vs_prev_time=1.0,
                avg_vs_prev_pct=20.0,
                med_vs_prev_time=0.5,
                med_vs_prev_pct=10.0,
                min_vs_prev_time=0.25,
                min_vs_prev_pct=5.0,
                max_vs_prev_time=1.25,
                max_vs_prev_pct=25.0,
            )
        ],
        "candidate-run",
        current_benchmark_header="candidate.json",
        comparison_benchmark_header="reference.json",
    )
    assert len(tables) == 1
    assert "Current Run vs Comparison Run (Candidate: candidate-run)" in tables[0]
    assert "candidate.json" in tables[0]
    assert "reference.json" in tables[0]
    assert "Avg Time" in tables[0]
    assert "Median Time" in tables[0]
    assert "Min Time" in tables[0]
    assert "Max Time" in tables[0]


def test_build_analysis_tables_include_original_table_when_available() -> None:
    tables = build_analysis_tables(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_new",
                comparison_benchmark_name="func1_ref",
                original_benchmark_name="func1_original",
                avg_vs_orig_time=1.0,
                avg_vs_orig_pct=20.0,
                med_vs_orig_time=0.5,
                med_vs_orig_pct=10.0,
                min_vs_orig_time=0.25,
                min_vs_orig_pct=5.0,
                max_vs_orig_time=1.25,
                max_vs_orig_pct=25.0,
                avg_vs_prev_time=0.25,
                avg_vs_prev_pct=5.0,
                med_vs_prev_time=0.125,
                med_vs_prev_pct=2.5,
                min_vs_prev_time=0.100,
                min_vs_prev_pct=2.0,
                max_vs_prev_time=0.500,
                max_vs_prev_pct=10.0,
            )
        ],
        "candidate-run",
        current_benchmark_header="candidate.json",
        comparison_benchmark_header="reference.json",
    )

    assert len(tables) == 2
    assert "Current Run vs Comparison Run (Candidate: candidate-run)" in tables[0]
    assert "Reference vs Original Implementation (Candidate: candidate-run)" in tables[1]
    assert "candidate.json" in tables[0]
    assert "reference.json" in tables[0]
    assert "Reference Benchmark" in tables[1]
    assert "Original Benchmark" in tables[1]
    assert "Min %" in tables[0]
    assert "Max %" in tables[1]


def test_build_analysis_tables_hide_methods_without_original_benchmarks_in_second_table() -> None:
    tables = build_analysis_tables(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_new",
                comparison_benchmark_name="func1_ref",
                original_benchmark_name="func1_original",
                avg_vs_orig_time=1.0,
                avg_vs_orig_pct=20.0,
                med_vs_orig_time=0.5,
                med_vs_orig_pct=10.0,
                min_vs_orig_time=0.25,
                min_vs_orig_pct=5.0,
                max_vs_orig_time=1.25,
                max_vs_orig_pct=25.0,
                avg_vs_prev_time=0.25,
                avg_vs_prev_pct=5.0,
                med_vs_prev_time=0.125,
                med_vs_prev_pct=2.5,
                min_vs_prev_time=0.100,
                min_vs_prev_pct=2.0,
                max_vs_prev_time=0.500,
                max_vs_prev_pct=10.0,
            ),
            MethodImprovement(
                group="ungrouped",
                method="func2",
                current_benchmark_name="func2_new",
                comparison_benchmark_name="func2_ref",
                original_benchmark_name=None,
                avg_vs_orig_time=None,
                avg_vs_orig_pct=None,
                med_vs_orig_time=None,
                med_vs_orig_pct=None,
                min_vs_orig_time=None,
                min_vs_orig_pct=None,
                max_vs_orig_time=None,
                max_vs_orig_pct=None,
                avg_vs_prev_time=0.25,
                avg_vs_prev_pct=5.0,
                med_vs_prev_time=0.125,
                med_vs_prev_pct=2.5,
                min_vs_prev_time=0.100,
                min_vs_prev_pct=2.0,
                max_vs_prev_time=0.500,
                max_vs_prev_pct=10.0,
            ),
        ],
        "candidate-run",
        current_benchmark_header="candidate.json",
        comparison_benchmark_header="reference.json",
    )

    assert len(tables) == 2
    assert "func1" in tables[1]
    assert "func1_original" in tables[1]
    assert "func2" not in tables[1]
    assert "func2_ref" not in tables[1]


def test_build_analysis_tables_show_message_when_comparison_is_missing() -> None:
    tables = build_analysis_tables(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_current",
                comparison_benchmark_name=None,
                avg_vs_prev_time=None,
                avg_vs_prev_pct=None,
                med_vs_prev_time=None,
                med_vs_prev_pct=None,
                min_vs_prev_time=None,
                min_vs_prev_pct=None,
                max_vs_prev_time=None,
                max_vs_prev_pct=None,
            )
        ],
        "candidate-run",
        current_benchmark_header="candidate.json",
        comparison_benchmark_header=None,
    )

    assert tables == ["No comparison benchmark found. Run with --benchmark-save first to create a benchmark file."]


def test_build_benchmark_header_label_uses_filename_when_available() -> None:
    assert build_benchmark_header_label("results/run_candidate_v2.json", "fallback") == "run_candidate_v2.json"
    assert build_benchmark_header_label("<live>", "current") == "current"


def test_rendered_analysis_tables_include_both_titles() -> None:
    output = _render_table(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_new",
                comparison_benchmark_name="func1_ref",
                original_benchmark_name="func1_original",
                avg_vs_orig_time=1.0,
                avg_vs_orig_pct=20.0,
                med_vs_orig_time=0.5,
                med_vs_orig_pct=10.0,
                min_vs_orig_time=0.25,
                min_vs_orig_pct=5.0,
                max_vs_orig_time=1.25,
                max_vs_orig_pct=25.0,
                avg_vs_prev_time=0.25,
                avg_vs_prev_pct=5.0,
                med_vs_prev_time=0.125,
                med_vs_prev_pct=2.5,
                min_vs_prev_time=0.100,
                min_vs_prev_pct=2.0,
                max_vs_prev_time=0.500,
                max_vs_prev_pct=10.0,
            )
        ]
    )

    assert "Current Run vs Comparison Run (Candidate: candidate-run)" in output
    assert "Reference vs Original Implementation (Candidate: candidate-run)" in output
    assert "func1_new" in output
    assert "func1_ref" in output
    assert "func1_original" in output


def test_rendered_analysis_tables_use_benchmark_style_dividers() -> None:
    output = _render_table(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_new",
                comparison_benchmark_name="func1_ref",
                original_benchmark_name="func1_original",
                avg_vs_orig_time=1.0,
                avg_vs_orig_pct=20.0,
                med_vs_orig_time=0.5,
                med_vs_orig_pct=10.0,
                min_vs_orig_time=0.25,
                min_vs_orig_pct=5.0,
                max_vs_orig_time=1.25,
                max_vs_orig_pct=25.0,
                avg_vs_prev_time=0.25,
                avg_vs_prev_pct=5.0,
                med_vs_prev_time=0.125,
                med_vs_prev_pct=2.5,
                min_vs_prev_time=0.100,
                min_vs_prev_pct=2.0,
                max_vs_prev_time=0.500,
                max_vs_prev_pct=10.0,
            )
        ]
    )

    assert "---" in output
    assert "+0.2500s" in output
    assert "+0.1000s" in output
    assert "+0.5000s" in output


def test_rendered_analysis_tables_show_each_benchmark_name_on_its_own_line() -> None:
    output = _render_table(
        [
            MethodImprovement(
                group="ungrouped",
                method="func1",
                current_benchmark_name="func1_cpu\nfunc1_gpu",
                comparison_benchmark_name="func1_prev_cpu\nfunc1_prev_gpu",
                original_benchmark_name="func1_orig_cpu\nfunc1_orig_gpu",
                avg_vs_orig_time=1.0,
                avg_vs_orig_pct=20.0,
                med_vs_orig_time=0.5,
                med_vs_orig_pct=10.0,
                min_vs_orig_time=0.25,
                min_vs_orig_pct=5.0,
                max_vs_orig_time=1.25,
                max_vs_orig_pct=25.0,
                avg_vs_prev_time=0.25,
                avg_vs_prev_pct=5.0,
                med_vs_prev_time=0.125,
                med_vs_prev_pct=2.5,
                min_vs_prev_time=0.100,
                min_vs_prev_pct=2.0,
                max_vs_prev_time=0.500,
                max_vs_prev_pct=10.0,
            )
        ]
    )

    assert "func1_cpu       func1_prev_cpu" in output
    assert "func1_gpu       func1_prev_gpu" in output
    assert "func1_cpu            func1_orig_cpu" in output
    assert "func1_gpu            func1_orig_gpu" in output
    assert "func1_cpu, func1_gpu" not in output
    assert "func1_prev_cpu, func1_prev_gpu" not in output
    assert "func1_orig_cpu, func1_orig_gpu" not in output
