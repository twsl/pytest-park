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

- Inline benchmark comparison printed directly in `pytest` output — no extra commands needed.
- Load pytest-benchmark JSON artifact folders and normalize runs, groups, marks, params, and custom grouping metadata.
- Compare reference runs against candidate runs with per-case and per-group delta and speedup summaries.
- Flexible grouping: custom keys, benchmark groups, marks, params, and postfix-based name normalization.
- Associate optional profiler artifacts with benchmark runs for code-level context.
- Serve an interactive local NiceGUI dashboard for historical exploration.

## Installation

With `pip`:

```bash
python -m pip install pytest-park
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv add --group test pytest-park
```

## Usage

### Step 1 — Run your tests

```bash
pytest
```

After the normal pytest-benchmark tables, a `pytest-park` summary section is printed automatically. It compares the current run against the latest saved benchmark artifact found in pytest-benchmark storage. No extra arguments are needed.

> The plugin is registered automatically via the `pytest11` entry point when `pytest-park` is installed — no `conftest.py` changes are required.

### Step 2 — Save runs to build a history (optional)

```bash
# Save and keep comparing against the latest saved run automatically
pytest --benchmark-autosave

# Save with a meaningful name for a stable reference point
pytest --benchmark-save baseline

# Compare against a specific saved run
pytest --benchmark-compare=0001
pytest --benchmark-compare=8d530304

# Save a candidate and compare it against a specific baseline
pytest --benchmark-save candidate-v2 --benchmark-compare=0001
```

`pytest-park` reuses the baseline that `pytest-benchmark` resolves from its configured storage — it does not require a second format. `--benchmark-storage` is respected as usual.

> **VS Code Test Explorer**: if the run looks like a single-shot execution (benchmark timing disabled or reduced), `pytest-park` prints a warning so the output is not mistaken for a real comparison.

### Name normalization and grouping (optional)

If your benchmark names encode variant postfixes (e.g. `test_func_orig`, `test_func_ref`, `test_func_np`, `test_func_pt`), add the `pytest_benchmark_group_stats` hook to group and label variants together:

```python
# tests/conftest.py
from pytest_park.pytest_benchmark import default_pytest_benchmark_group_stats


def pytest_benchmark_group_stats(config, benchmarks, group_by):
    return default_pytest_benchmark_group_stats(
        config,
        benchmarks,
        group_by,
        original_postfix="_orig",      # or a list: ["_np", "_numpy"]
        reference_postfix="_ref",       # or a list: ["_pt", "_torch"]
        group_values_by_postfix={
            "orig": "original",         # leading underscores are stripped for matching
            "ref": "reference",
        },
    )
```

This stores parsed parts in `extra_info["pytest_park_name_parts"]` (`base_name`, `parameters`, `postfix`) and groups paired variants under the same row in the comparison table.

Multiple postfixes can be specified as a list or comma-separated string. Postfix matching is underscore-agnostic: `"_original"`, `"original"`, and `"__original"` all match the same postfix.

### CLI postfix options

`pytest-park` registers `--benchmark-original-postfix` and `--benchmark-reference-postfix` automatically. These accept comma-separated values and **override** any postfixes passed directly to `default_pytest_benchmark_group_stats`:

```bash
# Single postfix
pytest --benchmark-original-postfix="_original" --benchmark-reference-postfix="_new"

# Multiple postfixes (comma-separated)
pytest --benchmark-original-postfix="_np,_numpy" --benchmark-reference-postfix="_pt,_torch"
```

When postfixes are configured, three output sections are produced:

1. **Regression table** — flat per-method comparison of the current run vs the previous saved run (requires a reference benchmark file).
2. **Postfix comparison table** — compares original-postfix methods vs reference-postfix methods within the current run (no saved reference needed).
3. **Grouped comparison table** — the existing detailed comparison with grouping.

Debug information (file names, postfixes, options) is always printed in the `pytest-park` section.

Postfixes can also be set persistently in `pyproject.toml`, `pytest.ini`, or `setup.cfg` so you don't have to pass them on every run:

```toml
# pyproject.toml
[tool.pytest.ini_options]
benchmark_original_postfix = "_orig,_numpy"
benchmark_reference_postfix = "_ref,_torch"
```

CLI flags always override ini-file values.

### Custom grouping metadata (optional)

Store arbitrary metadata on a benchmark for richer grouping:

```python
def test_compute_optimized(benchmark):
    benchmark.extra_info["custom_groups"] = {
        "technique": "vectorization",
        "scenario": "large-batch",
    }
    benchmark(compute)
```

Group by any key with `--group-by custom:technique` in the CLI.

---

## CLI — deeper analysis across saved artifacts

Use the CLI when you want to compare specific saved runs, apply advanced grouping, or include profiler data.

```bash
# Compare latest run (candidate) against second-latest run (reference)
pytest-park analyze ./.benchmarks

# Compare named runs
pytest-park analyze ./.benchmarks --reference baseline --candidate candidate-v2

# When only --candidate is given, the preceding run is used as reference
pytest-park analyze ./.benchmarks --candidate candidate-v2

# Group by benchmark group and a specific parameter
pytest-park analyze ./.benchmarks --group-by group --group-by param:device

# Group by custom metadata key
pytest-park analyze ./.benchmarks --group-by custom:scenario

# Exclude a parameter from comparison
pytest-park analyze ./.benchmarks --exclude-param device

# Keep a parameter as a separate dimension
pytest-park analyze ./.benchmarks --group-by group --distinct-param device

# Normalize method names by stripping postfixes
pytest-park analyze ./.benchmarks --original-postfix _orig --reference-postfix _ref

# Include profiler artifacts
pytest-park analyze ./.benchmarks --profiler-folder ./.profiler --group-by group

# Print installed version
pytest-park version
```

### Grouping reference

Default precedence (when no `--group-by` is given): `custom > benchmark_group > marks > params`

| Token          | Alias(es)         | Resolves to                            |
| -------------- | ----------------- | -------------------------------------- |
| `custom:<key>` | —                 | `extra_info["custom_groups"]["<key>"]` |
| `custom`       | `custom_group`    | All custom group keys combined         |
| `group`        | `benchmark_group` | Benchmark group label                  |
| `marks`        | `mark`            | Comma-joined pytest marks              |
| `params`       | —                 | All parameter key=value pairs          |
| `param:<name>` | —                 | Value of a specific parameter          |
| `name`         | `method`          | Normalized method name                 |
| `fullname`     | `nodeid`          | Full test node path                    |

Multiple `--group-by` tokens can be combined; the resulting label is joined with `|`.

### Artifact folder expectations

- Input files are pytest-benchmark JSON files (`--benchmark-save` output) stored anywhere under the folder.
- Default comparison: latest run as candidate, second-latest as reference.
- When only `--candidate` is given, the run immediately preceding it is used as reference.
- Run identity uses `metadata.run_id`, `metadata.tag`, or fallback datetime identifiers.

---

## Interactive dashboard

For exploratory, visual analysis across many saved runs:

```bash
pytest-park serve ./.benchmarks --reference baseline --host 127.0.0.1 --port 8080

# With profiler data
pytest-park serve ./.benchmarks --profiler-folder ./.profiler --port 8080
```

Access the dashboard at `http://127.0.0.1:8080`. Features include run selection, history charts, delta distribution, and method-level drill-down.

To launch a guided interactive CLI session instead:

```bash
pytest-park
```

---

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
