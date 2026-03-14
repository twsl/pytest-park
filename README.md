# pytest-park

[![Build](https://github.com/twsl/pytest-park/actions/workflows/build.yaml/badge.svg)](https://github.com/twsl/pytest-park/actions/workflows/build.yaml)
[![Documentation](https://github.com/twsl/pytest-park/actions/workflows/docs.yaml/badge.svg)](https://github.com/twsl/pytest-park/actions/workflows/docs.yaml)
[![PyPI - Package Version](https://img.shields.io/pypi/v/pytest-park?logo=pypi&style=flat&color=orange)](https://pypi.org/project/pytest-park/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytest-park?logo=pypi&style=flat&color=blue)](https://pypi.org/project/pytest-park/)
[![Docs with MkDocs](https://img.shields.io/badge/MkDocs-docs?style=flat&logo=materialformkdocs&logoColor=white&color=%23526CFE)](https://squidfunk.github.io/mkdocs-material/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![linting: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Semantic Versions](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--versions-e10079.svg)](https://github.com/twsl/pytest-park/releases)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-border.json)](https://github.com/copier-org/copier)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Organise and analyse your pytest benchmarks

## Features

- Load pytest-benchmark JSON artifact folders and normalize runs, groups, marks, params, and custom grouping metadata.
- Compare reference runs against candidate runs over time with per-case and per-group delta summaries.
- Build custom grouping views with precedence across custom groups, benchmark groups, marks, and params.
- Associate optional profiler artifacts with benchmark runs for code-level analysis context.
- Serve an interactive local NiceGUI dashboard for exploratory benchmark comparison.

## Installation

With `pip`:

```bash
python -m pip install pytest-park
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv add --group test pytest-park
```

## How to use it

### Recommended default workflow

For most projects, the recommended setup is:

1. add `pytest_park.pytest_plugin` to your test suite,
2. run benchmarked unit tests with `pytest`, and
3. read the `pytest-park` summary printed in the test output.

Use `pytest-park analyze` or `pytest-park serve` when you want more specific historical analysis across saved benchmark artifacts.

```bash
# Print version
pytest-park version

# Analyze and compare latest run (candidate) against second-latest run (reference)
pytest-park analyze ./.benchmarks --group-by group --group-by param:device

# Compare a named candidate run against a named reference tag/run id
pytest-park analyze ./.benchmarks --reference reference --candidate candidate-v2 --group-by custom:scenario

# When only --candidate is given, the run immediately before it in the list is used as reference
pytest-park analyze ./.benchmarks --candidate candidate-v2

# Exclude specific parameters from the comparison
pytest-park analyze ./.benchmarks --exclude-param device

# Keep a parameter distinct (not collapsed) during grouping
pytest-park analyze ./.benchmarks --group-by group --distinct-param device

# Normalize method names by stripping configured postfixes
pytest-park analyze ./.benchmarks --original-postfix _orig --reference-postfix _ref

# Include profiler artifacts alongside benchmark data
pytest-park analyze ./.benchmarks --profiler-folder ./.profiler --group-by group

# Launch interactive dashboard
pytest-park serve ./.benchmarks --reference reference --original-postfix _orig --reference-postfix _ref --host 127.0.0.1 --port 8080

# Launch dashboard with profiler data
pytest-park serve ./.benchmarks --profiler-folder ./.profiler --host 127.0.0.1 --port 8080

# Start interactive mode (no arguments) when you specifically want guided CLI analysis or dashboard startup
pytest-park
```

### Benchmark folder expectations

- Input artifacts are pytest-benchmark JSON files (`--benchmark-save` output) stored anywhere under a folder.
- Reference selection uses explicit run id or tag metadata (`metadata.run_id`, `metadata.tag`, or fallback identifiers).
- Default comparison baseline is latest run (candidate) vs second-latest run (reference) when `--reference` and `--candidate` are both omitted.
- When only `--candidate` is provided, the run immediately preceding it in the list is used as the reference.
- Grouping defaults to: custom groups > benchmark group > marks > params.
- Grouping tokens for `--group-by` (alias for `--grouping`): `custom:<key>`, `custom` (all custom keys), `group` / `benchmark_group`, `mark` / `marks`, `params`, `param:<name>`, `name` / `method`, `fullname` / `nodeid`.
- Use `--distinct-param` to treat a parameter as a separate dimension rather than collapsing it during grouping.
- Method normalization supports optional `--original-postfix` and `--reference-postfix` to align benchmark names across implementations.
- Profiler artifacts can be linked via `--profiler-folder` (both `analyze` and `serve` subcommands).

### Recommended pytest workflow: enable the plugin and read the summary

To print inline comparisons against the latest saved pytest-benchmark run, opt in to the
pytest plugin from your top-level `conftest.py` (or another top-level pytest plugin module):

```python
# tests/conftest.py
pytest_plugins = ["pytest_park.pytest_plugin"]
```

With that plugin enabled:

- `pytest` becomes the default way to use `pytest-park` during normal development.
- `pytest` will automatically compare each current benchmark against the latest saved run found in pytest-benchmark storage.
- `pytest --benchmark-compare` keeps using pytest-benchmark storage selection, so you can target a specific saved baseline when needed.
- `pytest --benchmark-save NAME` or `pytest --benchmark-autosave` are only needed if you also want to persist the current run as a future baseline.
- Benchmark comparison output is emitted as a dedicated `pytest-park` terminal summary section after the pytest-benchmark tables, using the same comparison table shown by the CLI.
- When tests are run from the VS Code Python Test Explorer, that summary section is still shown in the test run output.
- If the run looks like VS Code's default single-shot benchmark execution, `pytest-park` prints a warning so the output is not mistaken for a real benchmark comparison.

In short: enable the plugin once, run your benchmarked unit tests, and read the `pytest-park` section in the test output. Use the CLI and dashboard only when you need deeper or more targeted analysis.

### How `--benchmark-compare` works with pytest-park

`pytest-park` does not invent a second baseline format here. It reuses the baseline that
`pytest-benchmark` resolves from its configured storage.

That means the following commands keep the usual pytest-benchmark meaning, while also
powering inline `pytest-park` comparison output:

```bash
# Compare against the latest saved benchmark run automatically
pytest

# Compare against the latest saved benchmark run in storage
pytest --benchmark-compare

# Compare against a specific saved run number or id/prefix
pytest --benchmark-compare=0001
pytest --benchmark-compare=8d530304

# Save the current run and compare it against a chosen baseline in the same invocation
pytest --benchmark-save candidate-v2 --benchmark-compare=0001
```

Behavior summary:

- Registering `pytest_plugins = ["pytest_park.pytest_plugin"]` is enough to enable inline comparison output.
- With no extra benchmark arguments, pytest-park uses the latest saved benchmark run from the configured storage as the baseline.
- `--benchmark-compare` with no value means "compare against the latest saved run".
- `--benchmark-compare=<value>` means "compare against the saved run selected by pytest-benchmark storage".
- If you also pass `--benchmark-save` or `--benchmark-autosave`, the current run is still saved normally after execution.
- If you do **not** save the current run, `pytest-park` can still print inline comparison output for the current session; it just will not persist that run as a future baseline.
- Baseline lookup follows `--benchmark-storage`, so if you point pytest-benchmark at a different storage location, `pytest-park` will compare against that same location.

In practice, use:

- `--benchmark-autosave` when you want a rolling "compare against latest" workflow.
- `--benchmark-compare=<saved-id>` when you want to pin comparisons to a known historical baseline.
- `--benchmark-save <name> --benchmark-compare=<baseline>` when you want both a stable reference and a newly saved candidate artifact.

If your benchmark method names encode postfixes and parameter segments, you can override
`pytest_benchmark_group_stats` using the helper from this package:

```python
# tests/conftest.py
from pytest_park.pytest_benchmark import default_pytest_benchmark_group_stats


def pytest_benchmark_group_stats(config, benchmarks, group_by):
	return default_pytest_benchmark_group_stats(
		config,
		benchmarks,
		group_by,
		original_postfix="_orig",
		reference_postfix="_ref",
		group_values_by_postfix={
			"_orig": "original",
			"_ref": "reference",
			"none": "unlabeled",
		},
	)
```

This stores parsed parts in `extra_info["pytest_park_name_parts"]` with `base_name`, `parameters`, and `postfix`.

If you use postfixes in benchmark names, expose matching pytest-benchmark options in the same `conftest.py`:

```python
def pytest_addoption(parser):
	parser.addoption("--benchmark-original-postfix", action="store", default="")
	parser.addoption("--benchmark-reference-postfix", action="store", default="")
```

## Docs

```bash
uv run mkdocs build -f ./mkdocs.yml -d ./_build/
```

## Update template

```bash
copier update --trust -A --vcs-ref=HEAD
```

## Credits

This project was generated with [![🚀 python project template.](https://img.shields.io/badge/python--project--template-%F0%9F%9A%80-brightgreen)](https://github.com/twsl/python-project-template)
