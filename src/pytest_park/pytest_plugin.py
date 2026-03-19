from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pytest_park.core import build_postfix_comparison, build_regression_improvements
from pytest_park.core.reporting import (
    build_benchmark_header_label,
    build_postfix_comparison_table,
    build_regression_table,
)
from pytest_park.data import build_benchmark_run, load_benchmark_payload
from pytest_park.pytest_benchmark import _read_postfix, _read_postfixes


@dataclass(slots=True)
class _PluginState:
    reference_run: Any | None = None
    candidate_payloads: list[dict[str, Any]] = field(default_factory=list)
    benchmark_test_count: int = 0


_BENCHMARK_DISABLED_WARNING = (
    "Warning: Benchmarking appears disabled for this run. "
    "Detected single-shot benchmark execution, which commonly happens in VS Code Test Explorer. "
    "Enable pytest-benchmark to collect real benchmark measurements."
)


class PytestParkBenchmarkPlugin:
    """Opt-in pytest plugin for inline pytest-benchmark comparisons."""

    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.state = _PluginState()

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        self.state.reference_run = self._load_reference_run()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo[Any]) -> Any:
        outcome = yield
        outcome.get_result()

        if call.when != "call":
            return

        benchmark = getattr(item, "funcargs", {}).get("benchmark")
        if benchmark is not None:
            self.state.benchmark_test_count += 1

        stats = getattr(benchmark, "stats", None)
        if stats is None:
            return

        payload = self._build_current_benchmark_payload(stats)
        if not payload:
            return

        self.state.candidate_payloads.append(payload)

    @pytest.hookimpl(trylast=True)
    def pytest_terminal_summary(self, terminalreporter: Any) -> None:
        output_lines = self._build_summary_output_lines()
        if not output_lines:
            return

        if terminalreporter is not None:
            terminalreporter.section("pytest-park")
            for line in output_lines:
                terminalreporter.write_line(line)
            return

        self._write_fallback_summary("\n".join(output_lines))

    def _build_summary_output_lines(self) -> list[str]:
        output: list[str] = []

        warning_text = self._build_benchmark_warning_text()
        if warning_text:
            output.extend(warning_text.splitlines())

        debug_lines = self._build_debug_lines()
        if debug_lines:
            if output:
                output.append("")
            output.extend(debug_lines)

        table_text = self._build_summary_table_text()
        if table_text:
            if output:
                output.append("")
            output.extend(table_text.splitlines())

        return output

    def _build_debug_lines(self) -> list[str]:
        lines: list[str] = []

        benchmarksession = getattr(self.config, "_benchmarksession", None)
        if benchmarksession is None:
            lines.append("debug: pytest-benchmark session: not found (plugin may not be active)")
        else:
            storage = getattr(benchmarksession, "storage", None)
            storage_path = str(getattr(storage, "path", "<unknown>")) if storage else "<no storage>"
            lines.append(f"debug: benchmark storage: {storage_path}")

        ref = self.state.reference_run
        if ref is None:
            lines.append("debug: reference file: none (no saved benchmark file found)")
        else:
            lines.append(f"debug: reference file: {ref.source_file}")
            lines.append(f"debug: reference run_id: {ref.run_id}  cases: {len(ref.cases)}")

        n_payloads = len(self.state.candidate_payloads)
        lines.append(f"debug: candidate payloads collected: {n_payloads}")

        candidate_run = self._build_candidate_run()
        if candidate_run is None:
            lines.append("debug: candidate run: none")
        else:
            lines.append(f"debug: candidate run_id: {candidate_run.run_id}  cases: {len(candidate_run.cases)}")

        orig_postfixes = _read_postfixes(self.config, "benchmark_original_postfix")
        ref_postfixes = _read_postfixes(self.config, "benchmark_reference_postfix")
        lines.append(f"debug: original_postfixes: {orig_postfixes}")
        lines.append(f"debug: reference_postfixes: {ref_postfixes}")
        lines.append("debug: group_by: ['custom', 'group']")
        lines.append(f"debug: benchmark_compare: {self.config.getoption('benchmark_compare', default=None)}")
        lines.append(f"debug: benchmark_save: {self.config.getoption('benchmark_save', default=None)}")

        return lines

    def _build_summary_table_text(self) -> str | None:
        reference_run = self.state.reference_run
        candidate_run = self._build_candidate_run()
        if candidate_run is None:
            return None

        orig_postfixes = _read_postfixes(self.config, "benchmark_original_postfix")
        ref_postfixes = _read_postfixes(self.config, "benchmark_reference_postfix")
        sections: list[str] = []

        # 1. Regression table: flat per-method comparison vs previous run
        if reference_run is not None:
            regression = build_regression_improvements(candidate_run, reference_run)
            if regression:
                candidate_label = build_benchmark_header_label(candidate_run.source_file, candidate_run.run_id)
                reference_label = build_benchmark_header_label(reference_run.source_file, reference_run.run_id)
                sections.append(
                    build_regression_table(
                        regression,
                        candidate_label=candidate_label,
                        reference_label=reference_label,
                    )
                )
        else:
            sections.append(
                "Warning: No reference benchmark file found. "
                "Run with --benchmark-save or --benchmark-autosave first to enable regression comparison."
            )

        # 2. Postfix comparison: compare original-postfix vs reference-postfix methods
        #    This works within the candidate run itself, so no reference run is needed.
        if orig_postfixes and ref_postfixes:
            postfix_improvements = build_postfix_comparison(
                candidate_run,
                original_postfixes=orig_postfixes,
                reference_postfixes=ref_postfixes,
            )
            if postfix_improvements:
                sections.extend(
                    build_postfix_comparison_table(
                        postfix_improvements,
                        original_postfixes=orig_postfixes,
                        reference_postfixes=ref_postfixes,
                    )
                )
        else:
            missing = []
            if not orig_postfixes:
                missing.append("--benchmark-original-postfix")
            if not ref_postfixes:
                missing.append("--benchmark-reference-postfix")
            sections.append(f"Warning: Postfix comparison table skipped. Provide {' and '.join(missing)} to enable it.")

        return "\n\n".join(sections) if sections else None

    def _build_benchmark_warning_text(self) -> str | None:
        if not self._should_warn_about_disabled_benchmarking():
            return None
        return _BENCHMARK_DISABLED_WARNING

    def _should_warn_about_disabled_benchmarking(self) -> bool:
        if self.config.getoption("benchmark_disable", default=False):
            return True

        if self.state.benchmark_test_count > 0 and not self.state.candidate_payloads:
            return True

        return bool(self.state.candidate_payloads) and all(
            _is_single_shot_benchmark_payload(payload) for payload in self.state.candidate_payloads
        )

    def _write_fallback_summary(self, table_text: str) -> None:
        import sys

        stream = getattr(sys, "__stdout__", None) or sys.stdout
        stream.write("\npytest-park\n")
        stream.write(f"{table_text}\n")
        stream.flush()

    def _build_candidate_run(self) -> Any | None:
        if not self.state.candidate_payloads:
            return None

        return build_benchmark_run(
            self.state.candidate_payloads,
            run_id=self._current_run_id(),
            source_file="<live>",
            created_at=datetime.now(tz=UTC),
            original_postfix=_read_postfixes(self.config, "benchmark_original_postfix"),
            reference_postfix=_read_postfixes(self.config, "benchmark_reference_postfix"),
        )

    def _build_current_benchmark_payload(self, metadata: Any) -> dict[str, Any]:
        as_dict = getattr(metadata, "as_dict", None)
        if not callable(as_dict):
            return {}

        payload = as_dict(include_data=False)
        return payload if isinstance(payload, dict) else {}

    def _load_reference_run(self) -> Any | None:
        benchmark_session = getattr(self.config, "_benchmarksession", None)
        if benchmark_session is None:
            return None

        selected_payloads = _select_reference_payloads(self.config, benchmark_session)
        if not selected_payloads:
            return None

        path, payload = selected_payloads[-1]
        if not isinstance(payload, dict):
            return None

        return load_benchmark_payload(
            payload,
            source_file=str(path),
            original_postfix=_read_postfixes(self.config, "benchmark_original_postfix"),
            reference_postfix=_read_postfixes(self.config, "benchmark_reference_postfix"),
        )

    def _current_run_id(self) -> str:
        saved_name = self.config.getoption("benchmark_save", default=None)
        if isinstance(saved_name, str) and saved_name:
            return saved_name

        autosave_name = self.config.getoption("benchmark_autosave", default=None)
        if isinstance(autosave_name, str) and autosave_name:
            return autosave_name

        return "current"


def _select_reference_payloads(config: pytest.Config, benchmark_session: Any) -> list[tuple[Path | str, Any]]:
    compare_value = config.getoption("benchmark_compare", default=[])

    if compare_value not in (None, [], False):
        loaded = benchmark_session.storage.load(None if compare_value is True else compare_value)
        return list(loaded)

    loaded = list(benchmark_session.storage.load())
    if not loaded:
        loaded = list(benchmark_session.storage.load("*"))
    return loaded[-1:]


def _is_single_shot_benchmark_payload(payload: dict[str, Any]) -> bool:
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        return False

    try:
        rounds = int(stats.get("rounds", 0))
        iterations = int(stats.get("iterations", 0))
    except (TypeError, ValueError):
        return False

    return rounds == 1 and iterations == 1


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("pytest-park", "pytest-park benchmark comparison options")
    group.addoption(
        "--benchmark-original-postfix",
        action="store",
        default="",
        dest="benchmark_original_postfix",
        help="Comma-separated postfixes identifying original/baseline implementations (e.g. '_np,_numpy').",
    )
    group.addoption(
        "--benchmark-reference-postfix",
        action="store",
        default="",
        dest="benchmark_reference_postfix",
        help="Comma-separated postfixes identifying reference/new implementations (e.g. '_pt,_torch').",
    )
    parser.addini(
        "benchmark_original_postfix",
        default="",
        help="Comma-separated postfixes identifying original/baseline implementations (e.g. '_np,_numpy').",
    )
    parser.addini(
        "benchmark_reference_postfix",
        default="",
        help="Comma-separated postfixes identifying reference/new implementations (e.g. '_pt,_torch').",
    )


def pytest_configure(config: pytest.Config) -> None:
    if getattr(config, "_pytest_park_benchmark_plugin", None) is not None:
        return

    plugin = PytestParkBenchmarkPlugin(config)
    config._pytest_park_benchmark_plugin = plugin
    config.pluginmanager.register(plugin, "pytest-park-benchmark-plugin")


def pytest_unconfigure(config: pytest.Config) -> None:
    plugin = getattr(config, "_pytest_park_benchmark_plugin", None)
    if plugin is None:
        return

    config.pluginmanager.unregister(plugin)
    delattr(config, "_pytest_park_benchmark_plugin")
