from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pytest_park.__about__ import __version__
from pytest_park.core import (
    attach_profiler_data,
    build_method_statistics,
    build_overview_statistics,
    compare_method_to_all_prior_runs,
    compare_runs,
    list_methods,
    select_candidate_run,
    select_latest_and_previous_runs,
    select_reference_run,
    summarize_groups,
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

    if args.command == "load":
        _cmd_load(runs)
        return 0

    if args.command == "analyze":
        _cmd_analyze(runs, args.grouping, args.distinct_param, args.method)
        return 0

    if args.command == "compare":
        _cmd_compare(runs, args.reference, args.candidate, args.grouping, args.distinct_param, args.method)
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

    load_parser = subparsers.add_parser("load", parents=[shared])
    load_parser.set_defaults(command="load")

    analyze_parser = subparsers.add_parser("analyze", parents=[shared])
    analyze_parser.add_argument("--grouping", action="append", default=[], help="Grouping token, repeatable")
    analyze_parser.add_argument("--group-by", dest="grouping", action="append", help=argparse.SUPPRESS)
    analyze_parser.add_argument(
        "--distinct-param", action="append", default=[], help="Distinct parameter key, repeatable"
    )
    analyze_parser.add_argument("--method", default=None, help="Optional method/benchmark name for details")
    analyze_parser.set_defaults(command="analyze")

    compare_parser = subparsers.add_parser("compare", parents=[shared])
    compare_parser.add_argument("--reference", default=None, help="Reference run_id or tag (defaults to oldest run)")
    compare_parser.add_argument("--candidate", default=None, help="Candidate run_id or tag")
    compare_parser.add_argument("--grouping", action="append", default=[], help="Grouping token, repeatable")
    compare_parser.add_argument("--group-by", dest="grouping", action="append", help=argparse.SUPPRESS)
    compare_parser.add_argument(
        "--distinct-param", action="append", default=[], help="Distinct parameter key, repeatable"
    )
    compare_parser.add_argument("--method", default=None, help="Optional method/benchmark name for details")
    compare_parser.set_defaults(command="compare")

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


def _cmd_load(runs) -> None:
    case_count = sum(len(run.cases) for run in runs)
    print(f"Loaded {len(runs)} runs and {case_count} benchmark cases")
    for run in runs:
        print(f"- {run.run_id} ({len(run.cases)} cases) from {run.source_file}")


def _cmd_analyze(runs, grouping: list[str], distinct_params: list[str], method: str | None) -> None:
    reference_run, candidate_run = select_latest_and_previous_runs(runs)
    deltas = compare_runs(reference_run, candidate_run, grouping or None, distinct_params or None)
    _print_overview(deltas, reference_run.run_id, candidate_run.run_id)
    selected_method = method or _select_method_interactively(runs)
    if selected_method:
        _print_method_details(runs, reference_run, candidate_run, deltas, selected_method, distinct_params)


def _cmd_compare(
    runs,
    reference: str | None,
    candidate: str | None,
    grouping: list[str],
    distinct_params: list[str],
    method: str | None,
) -> None:
    if reference is None and candidate is None:
        reference_run, candidate_run = select_latest_and_previous_runs(runs)
    elif candidate and reference is None:
        candidate_run = select_reference_run(runs, candidate)
        reference_run = _select_previous_run(runs, candidate_run)
    else:
        reference_run = select_reference_run(runs, reference) if reference else select_latest_and_previous_runs(runs)[0]
        candidate_run = select_candidate_run(runs, candidate, reference_run)

    deltas = compare_runs(reference_run, candidate_run, grouping or None, distinct_params or None)
    _print_overview(deltas, reference_run.run_id, candidate_run.run_id)

    selected_method = method or _select_method_interactively(runs)
    if selected_method:
        _print_method_details(runs, reference_run, candidate_run, deltas, selected_method, distinct_params)


def _print_overview(deltas, reference_id: str, candidate_id: str) -> None:
    summaries = summarize_groups(deltas)
    overview = build_overview_statistics(deltas)

    print(f"Compared run {candidate_id} against reference {reference_id}")
    print(
        "Accumulated: "
        f"count={overview['count']}, avg_delta={overview['avg_delta_pct']:.2f}%, "
        f"median_delta={overview['median_delta_pct']:.2f}%, avg_speedup={overview['avg_speedup']:.3f}, "
        f"improved={overview['improved']}, regressed={overview['regressed']}, unchanged={overview['unchanged']}"
    )
    for summary in summaries:
        print(
            f"- {summary.label}: count={summary.count}, avg_delta={summary.average_delta_pct:.2f}%, "
            f"median_delta={summary.median_delta_pct:.2f}%, improved={summary.improvements}, regressed={summary.regressions}"
        )


def _select_method_interactively(runs) -> str | None:
    methods = list_methods(runs)
    if not methods:
        return None
    print("Available methods:")
    for item in methods:
        print(f"- {item}")

    if not sys.stdin.isatty():
        print("Use --method <name> to show method-level statistics")
        return None

    try:
        selected = input("Method to inspect (leave empty to skip): ").strip()
    except EOFError:
        return None

    if not selected:
        return None
    return selected


def _print_method_details(runs, reference_run, candidate_run, deltas, method: str, distinct_params: list[str]) -> None:
    method_stats = build_method_statistics(deltas, method)
    if not method_stats:
        print(f"No matching method data found for: {method}")
        return

    print(
        f"Method {method}: count={method_stats['count']}, avg_delta={method_stats['avg_delta_pct']:.2f}%, "
        f"median_delta={method_stats['median_delta_pct']:.2f}%, avg_speedup={method_stats['avg_speedup']:.3f}"
    )
    history = compare_method_to_all_prior_runs(runs, candidate_run, method, distinct_params or None)
    for item in history:
        print(
            f"  current={item['candidate_run_id']} vs={item['reference_run_id']} distinct={item['distinct']} "
            f"mean={float(item['mean']):.6f} vs_ref={float(item['reference_mean']):.6f} "
            f"delta={float(item['delta_pct']):.2f}%"
        )


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
    print("2) compare")
    print("3) serve (quick defaults)")
    print("4) serve (custom options)")
    print("5) load")
    print("6) version")

    try:
        selection = input("Choose command [1-6]: ").strip()
    except EOFError:
        return 1

    command_map = {
        "1": "analyze",
        "2": "compare",
        "3": "serve_quick",
        "4": "serve",
        "5": "load",
        "6": "version",
    }
    command = command_map.get(selection)
    if command is None:
        print("Invalid selection")
        return 1

    if command == "version":
        return main(["version"])

    try:
        benchmark_folder = input("Benchmark folder [./benchmarks]: ").strip() or "./benchmarks"
    except EOFError:
        return 1

    if command == "serve_quick":
        return main(["serve", benchmark_folder])

    command_args: list[str] = [command, benchmark_folder]

    if command in {"analyze", "compare", "serve"}:
        group_by = _read_csv_prompt("Group-by tokens (comma separated, optional): ")
        for token in group_by:
            command_args.extend(["--grouping", token])

        distinct = _read_csv_prompt("Distinct params (comma separated, optional): ")
        for token in distinct:
            command_args.extend(["--distinct-param", token])

    if command in {"analyze", "compare"}:
        method = _read_optional_prompt("Method (optional): ")
        if method:
            command_args.extend(["--method", method])

    if command == "compare":
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
