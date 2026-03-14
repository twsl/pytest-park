from __future__ import annotations

import json
from pathlib import Path

import pytest_park.cli as cli_module
from pytest_park.cli import main


def _write_single_run(path: Path) -> None:
    payload = {
        "datetime": "2026-02-12T10:00:00Z",
        "metadata": {"run_id": "run-candidate-v2", "tag": "candidate-v2"},
        "machine_info": {"node": "test-node", "python_version": "3.12.2"},
        "commit_info": {"id": "run-candidate-v2-commit"},
        "benchmarks": [
            {
                "name": "reduce_sum",
                "fullname": "bench::reduce_sum",
                "group": "reduction",
                "params": {"device": "cpu", "implementation": "candidate"},
                "marks": ["algo"],
                "extra_info": {"custom_groups": {"scenario": "cpu-candidate", "implementation": "candidate"}},
                "stats": {
                    "mean": 0.58,
                    "median": 0.58,
                    "min": 0.55,
                    "max": 0.61,
                    "stddev": 0.01,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 1.7241,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


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
    assert "Current Run vs Comparison Run (Candidate: run-candidate-v2)" in captured.out
    assert "run_candidate_v2.json" in captured.out
    assert "run_reference.json" in captured.out
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
    assert "Current Run vs Comparison Run (Candidate: run-candidate-v2)" in captured.out
    assert "run_candidate_v2.json" in captured.out
    assert "run_candidate_v1.json" in captured.out


def test_cli_analyze_with_exclude_param(benchmark_folder, capsys) -> None:
    exit_code = main(["analyze", str(benchmark_folder), "--grouping", "group", "--exclude-param", "device"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Current Run vs Comparison Run (Candidate: run-candidate-v2)" in captured.out


def test_cli_analyze_shows_message_when_no_comparison_benchmark_exists(tmp_path: Path, capsys) -> None:
    benchmark_folder = tmp_path / "benchmarks"
    benchmark_folder.mkdir()
    _write_single_run(benchmark_folder / "run_candidate_v2.json")

    exit_code = main(["analyze", str(benchmark_folder), "--candidate", "candidate-v2"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No comparison benchmark found. Run with --benchmark-save first to create a benchmark file." in captured.out
    assert "Current Run vs Comparison Run" not in captured.out


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
