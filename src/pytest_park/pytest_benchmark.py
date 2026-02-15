from __future__ import annotations

from typing import Any

from pytest_park.core.naming import parse_method_name


def default_pytest_benchmark_group_stats(
    config: Any,
    benchmarks: list[Any],
    group_by: str,
    *,
    original_postfix: str | None = None,
    reference_postfix: str | None = None,
    group_values_by_postfix: dict[str, str] | None = None,
) -> dict[str, list[Any]]:
    """Group pytest-benchmark entries by split base method name.

    This is intended as a drop-in helper for overriding ``pytest_benchmark_group_stats``
    in a test suite and keeping benchmark name parts available in ``extra_info``.
    """
    configured_original_postfix = original_postfix or _read_postfix(config, "benchmark_original_postfix")
    configured_reference_postfix = reference_postfix or _read_postfix(config, "benchmark_reference_postfix")
    postfixes = [value for value in (configured_original_postfix, configured_reference_postfix) if value]
    postfix_value_map = {
        key.strip(): value for key, value in (group_values_by_postfix or {}).items() if key and key.strip()
    }

    grouped: dict[str, list[Any]] = {}
    for benchmark in benchmarks:
        benchmark_name = _read_benchmark_name(benchmark)
        parts = parse_method_name(benchmark_name, postfixes)
        if group_by in {"group", "name", "method"}:
            group_name = parts.base_name
        elif group_by in {"postfix", "benchmark_postfix"}:
            fallback = parts.postfix or "none"
            group_name = postfix_value_map.get(fallback, fallback)
        else:
            group_name = benchmark_name
        grouped.setdefault(group_name, []).append(benchmark)
        _store_name_parts(benchmark, parts.base_name, parts.parameters, parts.postfix)

    return grouped


def _read_postfix(config: Any, option_name: str) -> str | None:
    getoption = getattr(config, "getoption", None)
    if callable(getoption):
        value = getoption(option_name, default="")
        if isinstance(value, str) and value.strip():
            return value.strip()

    option = getattr(config, "option", None)
    if option is None:
        return None

    value = getattr(option, option_name, "")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _read_benchmark_name(benchmark: Any) -> str:
    if isinstance(benchmark, dict):
        return str(benchmark.get("name") or benchmark.get("fullname") or "unknown")

    name = getattr(benchmark, "name", None)
    if isinstance(name, str) and name:
        return name

    fullname = getattr(benchmark, "fullname", None)
    if isinstance(fullname, str) and fullname:
        return fullname.rsplit("::", 1)[-1]

    return "unknown"


def _store_name_parts(benchmark: Any, base_name: str, parameters: str | None, postfix: str | None) -> None:
    name_parts = {
        "base_name": base_name,
        "parameters": parameters,
        "postfix": postfix,
    }

    if isinstance(benchmark, dict):
        extra_info = benchmark.get("extra_info")
        if not isinstance(extra_info, dict):
            extra_info = {}
            benchmark["extra_info"] = extra_info
        extra_info["pytest_park_name_parts"] = name_parts
        return

    extra_info = getattr(benchmark, "extra_info", None)
    if not isinstance(extra_info, dict):
        extra_info = {}
        benchmark.extra_info = extra_info
    extra_info["pytest_park_name_parts"] = name_parts
