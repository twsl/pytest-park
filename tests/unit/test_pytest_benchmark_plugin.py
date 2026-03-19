from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast

import pytest

from pytest_park.data import load_benchmark_payload
from pytest_park.pytest_plugin import PytestParkBenchmarkPlugin, _select_reference_payloads


class _Storage:
    def __init__(self, entries: list[tuple[Path, dict[str, Any]]]) -> None:
        self.entries = entries
        self.calls: list[Any] = []

    def load(self, value: Any = None):
        self.calls.append(value)
        if value == "*":
            return iter(self.entries)
        if value in (None, True):
            return iter(self.entries)
        return iter(self.entries[:1])


class _FallbackStorage(_Storage):
    def load(self, value: Any = None):
        self.calls.append(value)
        if value == "*":
            return iter(self.entries)
        return iter([])


class _TerminalReporter:
    def __init__(self) -> None:
        self.sections: list[str] = []
        self.lines: list[str] = []
        self._tw = type("Writer", (), {"fullwidth": 200})()

    def section(self, title: str, sep: str = "=", **kwargs: bool) -> None:
        del sep, kwargs
        self.sections.append(title)

    def write_line(self, message: str) -> None:
        self.lines.append(message)


class _PluginManager:
    def __init__(self, **plugins: Any) -> None:
        self._plugins = plugins

    def getplugin(self, name: str) -> Any:
        return self._plugins.get(name)

    def hasplugin(self, name: str) -> bool:
        return name in self._plugins


class _Config:
    def __init__(self, pluginmanager: _PluginManager | None = None, **options: Any) -> None:
        self._options = {
            "benchmark_disable": False,
            "benchmark_compare": [],
            "benchmark_save": None,
            "benchmark_autosave": None,
            "benchmark_original_postfix": "",
            "benchmark_reference_postfix": "",
            **options,
        }
        self.pluginmanager = pluginmanager or _PluginManager()

    def getoption(self, name: str, default: Any = None) -> Any:
        return self._options.get(name, default)


def _reference_payload(run_id: str = "run-reference") -> dict[str, Any]:
    return {
        "datetime": "2026-03-12T10:00:00Z",
        "metadata": {"run_id": run_id, "tag": "reference"},
        "machine_info": {"node": "test-node", "python_version": "3.12.0"},
        "commit_info": {"id": "abc123"},
        "benchmarks": [
            {
                "name": "sort_values[cpu]",
                "fullname": "tests/test_demo.py::test_sort_values[cpu]",
                "group": "sorting",
                "params": {"device": "cpu"},
                "param": "cpu",
                "extra_info": {},
                "stats": {
                    "mean": 1.0,
                    "median": 1.0,
                    "min": 0.9,
                    "max": 1.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 1.0,
                },
            }
        ],
    }


def _ungrouped_reference_payload(run_id: str = "run-reference") -> dict[str, Any]:
    return {
        "datetime": "2026-03-12T10:00:00Z",
        "metadata": {"run_id": run_id, "tag": "reference"},
        "machine_info": {"node": "test-node", "python_version": "3.12.0"},
        "commit_info": {"id": "abc123"},
        "benchmarks": [
            {
                "name": "test_func1_original",
                "fullname": "tests/unit/examples/test_func1.py::test_func1_original",
                "group": None,
                "params": None,
                "param": None,
                "extra_info": {},
                "stats": {
                    "mean": 3.0,
                    "median": 3.0,
                    "min": 2.9,
                    "max": 3.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 1.0 / 3.0,
                },
            },
            {
                "name": "test_func1_new[cpu]",
                "fullname": "tests/unit/examples/test_func1.py::test_func1_new[cpu]",
                "group": None,
                "params": {"device": "cpu"},
                "param": "cpu",
                "extra_info": {},
                "stats": {
                    "mean": 2.0,
                    "median": 2.0,
                    "min": 1.9,
                    "max": 2.1,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 0.5,
                },
            },
        ],
    }


class _Metadata:
    def __init__(self, *, rounds: int = 5, iterations: int = 1) -> None:
        self.rounds = rounds
        self.iterations = iterations

    def as_dict(self, include_data: bool = False) -> dict[str, Any]:
        assert include_data is False
        return {
            "name": "sort_values[cpu]",
            "fullname": "tests/test_demo.py::test_sort_values[cpu]",
            "group": "sorting",
            "params": {"device": "cpu"},
            "param": "cpu",
            "extra_info": {},
            "stats": {
                "mean": 0.8,
                "median": 0.8,
                "min": 0.75,
                "max": 0.85,
                "stddev": 0.01,
                "rounds": self.rounds,
                "iterations": self.iterations,
                "ops": 1.25,
            },
        }


def test_select_reference_payloads_uses_explicit_compare() -> None:
    storage = _Storage([(Path("baseline.json"), _reference_payload())])
    config = _Config(benchmark_compare="0001")

    selected = _select_reference_payloads(cast(pytest.Config, config), type("Session", (), {"storage": storage})())

    assert len(selected) == 1
    assert storage.calls == ["0001"]


def test_select_reference_payloads_uses_latest_saved_run_when_saving() -> None:
    storage = _Storage(
        [
            (Path("old.json"), _reference_payload("run-old")),
            (Path("latest.json"), _reference_payload("run-latest")),
        ]
    )
    config = _Config(benchmark_autosave="autosave-tag")

    selected = _select_reference_payloads(cast(pytest.Config, config), type("Session", (), {"storage": storage})())

    assert len(selected) == 1
    assert selected[0][0] == Path("latest.json")
    assert storage.calls == [None]


def test_select_reference_payloads_uses_latest_saved_run_without_extra_options() -> None:
    storage = _Storage(
        [
            (Path("old.json"), _reference_payload("run-old")),
            (Path("latest.json"), _reference_payload("run-latest")),
        ]
    )
    config = _Config()

    selected = _select_reference_payloads(cast(pytest.Config, config), type("Session", (), {"storage": storage})())

    assert len(selected) == 1
    assert selected[0][0] == Path("latest.json")
    assert storage.calls == [None]


def test_select_reference_payloads_falls_back_to_generic_json_artifacts() -> None:
    storage = _FallbackStorage(
        [
            (Path("benchmark-20260222T213534Z.json"), _reference_payload("run-latest")),
        ]
    )
    config = _Config()

    selected = _select_reference_payloads(cast(pytest.Config, config), type("Session", (), {"storage": storage})())

    assert len(selected) == 1
    assert selected[0][0] == Path("benchmark-20260222T213534Z.json")
    assert storage.calls == [None, "*"]


def test_plugin_builds_summary_table_from_reference_run() -> None:
    plugin = PytestParkBenchmarkPlugin(cast(pytest.Config, _Config()))
    plugin.state.reference_run = load_benchmark_payload(_reference_payload(), source_file="baseline.json")
    plugin.state.candidate_payloads = [_Metadata().as_dict()]

    table_text = plugin._build_summary_table_text()

    assert table_text is not None
    assert "Regression: current vs baseline.json" in table_text
    assert "current" in table_text
    assert "baseline.json" in table_text
    assert "sort_values" in table_text
    assert "-0.2000s" in table_text
    assert "-20.0000%" in table_text


def test_plugin_writes_summary_section_to_terminal_reporter() -> None:
    reporter = _TerminalReporter()
    plugin = PytestParkBenchmarkPlugin(cast(pytest.Config, _Config()))
    plugin.state.reference_run = load_benchmark_payload(_reference_payload(), source_file="baseline.json")
    plugin.state.candidate_payloads = [_Metadata().as_dict()]

    plugin.pytest_terminal_summary(reporter)

    assert reporter.sections == ["pytest-park"]
    assert any("Regression: current vs baseline.json" in line for line in reporter.lines)
    assert any("sort_values" in line for line in reporter.lines)


def test_plugin_writes_fallback_summary_without_terminal_reporter(monkeypatch) -> None:
    stream = io.StringIO()
    plugin = PytestParkBenchmarkPlugin(cast(pytest.Config, _Config()))
    plugin.state.reference_run = load_benchmark_payload(_reference_payload(), source_file="baseline.json")
    plugin.state.candidate_payloads = [_Metadata().as_dict()]
    monkeypatch.setattr("sys.__stdout__", stream)

    plugin.pytest_terminal_summary(None)

    output = stream.getvalue()
    assert output.startswith("\npytest-park\n")
    assert "Regression: current vs baseline.json" in output
    assert "sort_values" in output


def test_plugin_summary_uses_strict_logical_groups_instead_of_param_fallback() -> None:
    plugin = PytestParkBenchmarkPlugin(cast(pytest.Config, _Config()))
    plugin.state.reference_run = load_benchmark_payload(
        _ungrouped_reference_payload(),
        source_file="baseline.json",
        original_postfix="original",
        reference_postfix="new",
    )
    plugin.state.candidate_payloads = _ungrouped_reference_payload("current")["benchmarks"]

    table_text = plugin._build_summary_table_text()

    assert table_text is not None
    assert "Regression: current vs baseline.json" in table_text
    assert "params:device=cpu" not in table_text


def test_plugin_warns_when_benchmarking_is_disabled() -> None:
    reporter = _TerminalReporter()
    plugin = PytestParkBenchmarkPlugin(cast(pytest.Config, _Config(benchmark_disable=True)))
    plugin.state.benchmark_test_count = 1
    plugin.state.candidate_payloads = [_Metadata(rounds=1, iterations=1).as_dict()]

    plugin.pytest_terminal_summary(reporter)

    assert reporter.sections == ["pytest-park"]
    assert any("Benchmarking appears disabled for this run" in line for line in reporter.lines)
    assert any("VS Code Test Explorer" in line for line in reporter.lines)


def test_plugin_warns_when_only_single_shot_benchmarks_are_collected() -> None:
    reporter = _TerminalReporter()
    plugin = PytestParkBenchmarkPlugin(cast(pytest.Config, _Config()))
    plugin.state.benchmark_test_count = 1
    plugin.state.candidate_payloads = [_Metadata(rounds=1, iterations=1).as_dict()]

    plugin.pytest_terminal_summary(reporter)

    assert reporter.sections == ["pytest-park"]
    assert any("Benchmarking appears disabled for this run" in line for line in reporter.lines)
