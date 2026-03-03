from __future__ import annotations

import argparse
from pathlib import Path
import sys

from rich.console import Console
from rich.table import Table

from pytest_park.__about__ import __version__
from pytest_park.core import (
    analyze_method_improvements,
    attach_profiler_data,
    build_overall_improvement_summary,
    select_candidate_run,
    select_latest_and_previous_runs,
    select_reference_run,
)
from pytest_park.data import BenchmarkLoadError, ProfilerLoadError, load_benchmark_folder, load_profiler_folder
from pytest_park.ui import serve_dashboard


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        return _run_interactive(parser)

    if args.command == "version":
        print(f"pytest-park v{__version__}")
        return 0

    try:
        runs = load_benchmark_folder(
            Path(args.benchmark_folder),
            original_postfix=args.original_postfix,
            reference_postfix=args.reference_postfix,
        )
    except BenchmarkLoadError as exc:
        parser.error(str(exc))

    if args.profiler_folder:
        try:
            profiler_by_run = load_profiler_folder(Path(args.profiler_folder))
        except ProfilerLoadError as exc:
            parser.error(str(exc))
        attach_profiler_data(runs, profiler_by_run)

    if args.command == "analyze":
        _cmd_analyze(
            runs,
            args.reference,
            args.candidate,
            args.grouping,
            args.distinct_param,
            args.exclude_param,
        )
        return 0

    if args.command == "serve":
        serve_dashboard(
            benchmark_folder=args.benchmark_folder,
            reference=args.reference,
            group_by=args.grouping,
            distinct_params=args.distinct_param,
            original_postfix=args.original_postfix,
            reference_postfix=args.reference_postfix,
            host=args.host,
            port=args.port,
        )
        return 0

    parser.error("Unknown command")
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pytest-park")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("version")

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("benchmark_folder", help="Folder containing pytest-benchmark JSON artifacts")
    shared.add_argument("--profiler-folder", default=None, help="Optional folder containing profiler JSON artifacts")
    shared.add_argument(
        "--original-postfix",
        default="",
        help="Optional postfix used in original/candidate method names (for name normalization)",
    )
    shared.add_argument(
        "--reference-postfix",
        default="",
        help="Optional postfix used in reference method names (for name normalization)",
    )

    analyze_parser = subparsers.add_parser("analyze", parents=[shared])
    analyze_parser.add_argument("--reference", default=None, help="Reference run_id or tag (defaults to oldest run)")
    analyze_parser.add_argument("--candidate", default=None, help="Candidate run_id or tag")
    analyze_parser.add_argument("--grouping", action="append", default=[], help="Grouping token, repeatable")
    analyze_parser.add_argument("--group-by", dest="grouping", action="append", help=argparse.SUPPRESS)
    analyze_parser.add_argument(
        "--distinct-param", action="append", default=[], help="Distinct parameter key, repeatable"
    )
    analyze_parser.add_argument(
        "--exclude-param", action="append", default=[], help="Parameter key to exclude from comparison, repeatable"
    )
    analyze_parser.set_defaults(command="analyze")

    serve_parser = subparsers.add_parser("serve", parents=[shared])
    serve_parser.add_argument("--reference", default=None, help="Default reference run_id or tag")
    serve_parser.add_argument("--grouping", action="append", default=[], help="Grouping token, repeatable")
    serve_parser.add_argument("--group-by", dest="grouping", action="append", help=argparse.SUPPRESS)
    serve_parser.add_argument(
        "--distinct-param", action="append", default=[], help="Distinct parameter key, repeatable"
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    serve_parser.set_defaults(command="serve")

    parser.set_defaults(command=None)
    return parser


def _cmd_analyze(
    runs,
    reference: str | None,
    candidate: str | None,
    grouping: list[str],
    distinct_params: list[str],
    exclude_params: list[str],
) -> None:
    if reference is None and candidate is None:
        reference_run, candidate_run = select_latest_and_previous_runs(runs)
    elif candidate and reference is None:
        candidate_run = select_reference_run(runs, candidate)
        try:
            reference_run = _select_previous_run(runs, candidate_run)
        except ValueError:
            reference_run = None
    else:
        reference_run = select_reference_run(runs, reference) if reference else select_latest_and_previous_runs(runs)[0]
        candidate_run = select_candidate_run(runs, candidate, reference_run)

    improvements = analyze_method_improvements(
        candidate_run=candidate_run,
        reference_run=reference_run,
        group_by=grouping or None,
        exclude_params=exclude_params or None,
    )

    console = Console(width=200 if not sys.stdout.isatty() else None)
    table = Table(title=f"Benchmark Analysis (Candidate: {candidate_run.run_id})", expand=True)

    table.add_column("Group", style="cyan")
    table.add_column("Method", style="magenta")
    table.add_column("Avg vs Orig (Time)", justify="right")
    table.add_column("Avg vs Orig (%)", justify="right")
    table.add_column("Med vs Orig (Time)", justify="right")
    table.add_column("Med vs Orig (%)", justify="right")
    table.add_column("Avg vs Prev (Time)", justify="right")
    table.add_column("Avg vs Prev (%)", justify="right")
    table.add_column("Med vs Prev (Time)", justify="right")
    table.add_column("Med vs Prev (%)", justify="right")

    def format_val(val: float | None, is_pct: bool = False) -> str:
        if val is None:
            return "N/A"
        color = "green" if val > 0 else "red" if val < 0 else "white"
        suffix = "%" if is_pct else "s"
        return f"[{color}]{val:+.4f}{suffix}[/{color}]"

    for imp in improvements:
        table.add_row(
            imp.group,
            imp.method,
            format_val(imp.avg_vs_orig_time),
            format_val(imp.avg_vs_orig_pct, is_pct=True),
            format_val(imp.med_vs_orig_time),
            format_val(imp.med_vs_orig_pct, is_pct=True),
            format_val(imp.avg_vs_prev_time),
            format_val(imp.avg_vs_prev_pct, is_pct=True),
            format_val(imp.med_vs_prev_time),
            format_val(imp.med_vs_prev_pct, is_pct=True),
        )

    if improvements:
        summary = build_overall_improvement_summary(improvements)

        def _sv(key: str, is_pct: bool = False) -> str:
            return format_val(summary.get(key), is_pct=is_pct)  # type: ignore[arg-type]

        table.add_section()
        table.add_row(
            "Overall",
            "All Methods",
            _sv("avg_vs_orig_time"),
            _sv("avg_vs_orig_pct", is_pct=True),
            _sv("med_vs_orig_time"),
            _sv("med_vs_orig_pct", is_pct=True),
            _sv("avg_vs_prev_time"),
            _sv("avg_vs_prev_pct", is_pct=True),
            _sv("med_vs_prev_time"),
            _sv("med_vs_prev_pct", is_pct=True),
            style="bold",
        )

    console.print(table)


def _select_previous_run(runs, candidate_run):
    candidate_index = next((index for index, run in enumerate(runs) if run.run_id == candidate_run.run_id), None)
    if candidate_index is None:
        raise ValueError(f"Candidate run not found: {candidate_run.run_id}")
    if candidate_index == 0:
        raise ValueError("No previous reference run available before candidate run")
    return runs[candidate_index - 1]


def _run_interactive(parser: argparse.ArgumentParser) -> int:
    if not sys.stdin.isatty():
        parser.print_help()
        print("No command provided. Run in a TTY for interactive mode.")
        return 2

    print("pytest-park interactive mode")
    print("1) analyze")
    print("2) serve")
    print("3) version")

    try:
        selection = input("Choose command [1-3]: ").strip()
    except EOFError:
        return 1

    command_map = {
        "1": "analyze",
        "2": "serve",
        "3": "version",
    }
    command = command_map.get(selection)
    if command is None:
        print("Invalid selection")
        return 1

    if command == "version":
        return main(["version"])

    try:
        benchmark_folder = input("Benchmark folder [./.benchmarks]: ").strip() or "./.benchmarks"
    except EOFError:
        return 1

    command_args: list[str] = [command, benchmark_folder]

    if command in {"analyze", "serve"}:
        group_by = _read_csv_prompt("Group-by tokens (comma separated, optional): ")
        for token in group_by:
            command_args.extend(["--grouping", token])

        distinct = _read_csv_prompt("Distinct params (comma separated, optional): ")
        for token in distinct:
            command_args.extend(["--distinct-param", token])

        orig_postfix = _read_optional_prompt("Original postfix (optional): ")
        if orig_postfix:
            command_args.extend(["--original-postfix", orig_postfix])

        ref_postfix = _read_optional_prompt("Reference postfix (optional): ")
        if ref_postfix:
            command_args.extend(["--reference-postfix", ref_postfix])

    if command == "analyze":
        exclude = _read_csv_prompt("Exclude params (comma separated, optional): ")
        for token in exclude:
            command_args.extend(["--exclude-param", token])

        reference = _read_optional_prompt("Reference run/tag (optional): ")
        if reference:
            command_args.extend(["--reference", reference])
        candidate = _read_optional_prompt("Candidate run/tag (optional): ")
        if candidate:
            command_args.extend(["--candidate", candidate])

    if command == "serve":
        reference = _read_optional_prompt("Reference run/tag (optional): ")
        if reference:
            command_args.extend(["--reference", reference])

        host = _read_optional_prompt("Host [127.0.0.1]: ") or "127.0.0.1"
        port = _read_optional_prompt("Port [8080]: ") or "8080"
        command_args.extend(["--host", host, "--port", port])

    return main(command_args)


def _read_optional_prompt(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def _read_csv_prompt(prompt: str) -> list[str]:
    value = _read_optional_prompt(prompt)
    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]
