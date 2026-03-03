from __future__ import annotations

import pytest_park.cli as cli_module
from pytest_park.cli import main


def test_cli_analyze_command(benchmark_folder, capsys, monkeypatch) -> None:
    exit_code = main(
        [
            "analyze",
            str(benchmark_folder),
            "--reference",
            "reference",
            "--candidate",
            "candidate-v2",
            "--group-by",
            "custom:scenario",
            "--group-by",
            "param:device",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Benchmark Analysis (Candidate: run-candidate-v2)" in captured.out
    assert "param:device=cpu" in captured.out
    assert "reduce_sum" in captured.out


def test_cli_analyze_defaults_to_latest_vs_previous(benchmark_folder, capsys) -> None:
    exit_code = main(
        [
            "analyze",
            str(benchmark_folder),
            "--group-by",
            "group",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Benchmark Analysis (Candidate: run-candidate-v2)" in captured.out


def test_cli_analyze_with_exclude_param(benchmark_folder, capsys) -> None:
    exit_code = main(["analyze", str(benchmark_folder), "--grouping", "group", "--exclude-param", "device"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Benchmark Analysis (Candidate: run-candidate-v2)" in captured.out


def test_cli_no_args_starts_interactive_mode(monkeypatch) -> None:
    called = {"interactive": False}

    def _fake_interactive(_parser) -> int:
        called["interactive"] = True
        return 0

    monkeypatch.setattr("pytest_park.cli._run_interactive", _fake_interactive)

    exit_code = main([])

    assert exit_code == 0
    assert called["interactive"]


def test_cli_interactive_quick_serve_uses_defaults(monkeypatch) -> None:
    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    prompts = iter(["2", "./.benchmarks", "", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(prompts))

    captured: dict[str, list[str] | None] = {"argv": None}

    def _fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cli_module, "main", _fake_main)

    exit_code = cli_module._run_interactive(cli_module._build_parser())

    assert exit_code == 0
    assert captured["argv"] == ["serve", "./.benchmarks", "--host", "127.0.0.1", "--port", "8080"]
