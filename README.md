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

```bash
# Print version
pytest-park version

# Start interactive mode (no arguments)
pytest-park

# Inspect a benchmark folder
pytest-park load ./benchmarks

# Analyze grouping distribution
pytest-park analyze ./benchmarks --group-by group --group-by param:device

# Compare a candidate run against a named reference tag/run id
pytest-park compare ./benchmarks --reference reference --candidate candidate-v2 --group-by custom:scenario

# Compare latest run against second-latest run when --reference/--candidate are omitted
# By default, this will compare and print details for all methods.
pytest-park compare ./benchmarks

# Compare a specific method only
pytest-park compare ./benchmarks --method test_func1

# Normalize method names by removing configured postfixes
pytest-park analyze ./benchmarks --original-postfix _orig --reference-postfix _ref

# Launch interactive dashboard
pytest-park serve ./benchmarks --reference reference --original-postfix _orig --reference-postfix _ref --host 127.0.0.1 --port 8080
```

### Benchmark folder expectations

- Input artifacts are pytest-benchmark JSON files (`--benchmark-save` output) stored anywhere under a folder.
- Reference selection uses explicit run id or tag metadata (`metadata.run_id`, `metadata.tag`, or fallback identifiers).
- Default comparison baseline is latest vs second-latest run when `--reference` and `--candidate` are omitted.
- Grouping defaults to: custom groups > benchmark group > marks > params.
- Custom grouping tokens include `custom:<key>`, `group`, `marks`, `params`, and `param:<name>`.
- Method normalization supports optional `--original-postfix` and `--reference-postfix` to align benchmark names across implementations.

### pytest-benchmark group stats override

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
