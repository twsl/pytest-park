from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

SRC_PATH = Path(__file__).resolve().parents[2] / "src"


def _env_with_src_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(part for part in (str(SRC_PATH), env.get("PYTHONPATH", "")) if part)
    return env


def _write_reference_run(path: Path) -> None:
    payload = {
        "datetime": "2026-03-12T10:00:00Z",
        "metadata": {"run_id": "run-reference", "tag": "reference"},
        "machine_info": {"node": "test-node", "python_version": "3.12.2"},
        "commit_info": {"id": "run-reference-commit"},
        "benchmarks": [
            {
                "name": "test_inline_benchmark",
                "fullname": "test_inline.py::test_inline_benchmark",
                "group": "inline",
                "params": None,
                "param": None,
                "extra_info": {},
                "stats": {
                    "mean": 0.02,
                    "median": 0.02,
                    "min": 0.019,
                    "max": 0.021,
                    "stddev": 0.001,
                    "rounds": 5,
                    "iterations": 1,
                    "ops": 50.0,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pytest_plugin_emits_inline_terminal_output(tmp_path: Path) -> None:
    project = tmp_path / "inline-project"
    project.mkdir()

    benchmark_storage = project / ".benchmarks"
    benchmark_storage.mkdir()
    _write_reference_run(benchmark_storage / "0001_reference.json")

    (project / "conftest.py").write_text('pytest_plugins = ["pytest_park.pytest_plugin"]\n', encoding="utf-8")
    (project / "test_inline.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import time\n"
        "\n"
        "def test_inline_benchmark(benchmark):\n"
        "    benchmark(time.sleep, 0.002)\n",
        encoding="utf-8",
    )

    env = _env_with_src_pythonpath()

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    assert "pytest-park" in result.stdout
    assert "Current Run vs Comparison Run (Candidate: current)" in result.stdout
    assert "0001_reference.json" in result.stdout
    assert "inline" in result.stdout
    assert "test_inline_benchmark" in result.stdout
    assert "PASSEDpytest-park" not in result.stdout
    assert result.stdout.index("pytest-park") > result.stdout.index("benchmark: 1 tests")


def test_pytest_plugin_warns_for_benchmark_disable_mode(tmp_path: Path) -> None:
    project = tmp_path / "inline-project-disabled"
    project.mkdir()

    benchmark_storage = project / ".benchmarks"
    benchmark_storage.mkdir()
    _write_reference_run(benchmark_storage / "0001_reference.json")

    (project / "conftest.py").write_text('pytest_plugins = ["pytest_park.pytest_plugin"]\n', encoding="utf-8")
    (project / "test_inline.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import time\n"
        "\n"
        "def test_inline_benchmark(benchmark):\n"
        "    benchmark(time.sleep, 0.002)\n",
        encoding="utf-8",
    )

    env = _env_with_src_pythonpath()

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--benchmark-disable",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    assert "pytest-park" in result.stdout
    assert "Benchmarking appears disabled for this run" in result.stdout
    assert "VS Code Test Explorer" in result.stdout
