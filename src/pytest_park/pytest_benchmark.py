from collections import defaultdict
import operator
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
    ignore_params: list[str] | None = None,
) -> list[tuple[str, list[Any]]]:
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

    groups: dict[str | None, list[Any]] = defaultdict(list)
    for benchmark in benchmarks:
        benchmark_name = _read_benchmark_name(benchmark)
        parts = parse_method_name(benchmark_name, postfixes)
        _store_name_parts(benchmark, parts.base_name, parts.parameters, parts.postfix)

        key = []
        for grouping in group_by.split(","):
            if grouping in {"group", "name", "method", "func"}:
                key.append(parts.base_name)
            elif grouping == "fullname":
                fullname = _read_benchmark_attr(benchmark, "fullname") or benchmark_name
                prefix, separator, _ = fullname.rpartition("::")
                fullname_base = prefix + separator + parts.base_name
                if "[" in fullname:
                    fullname_base += fullname[fullname.index("[") :]
                key.append(fullname_base)
            elif grouping == "fullfunc":
                fullname = _read_benchmark_attr(benchmark, "fullname") or benchmark_name
                prefix, separator, _ = fullname.rpartition("::")
                fullname_base = prefix + separator + parts.base_name
                key.append(fullname_base)
            elif grouping == "param":
                key.append(_filter_ignored_params(benchmark, ignore_params))
            elif grouping.startswith("param:"):
                param_name = grouping[len("param:") :]
                if not ignore_params or param_name not in ignore_params:
                    params_dict = _read_benchmark_attr(benchmark, "params") or {}
                    if param_name in params_dict:
                        key.append(f"{param_name}={params_dict[param_name]}")
            elif grouping in {"postfix", "benchmark_postfix"}:
                fallback = parts.postfix or "none"
                key.append(postfix_value_map.get(fallback, fallback))
            else:
                # Fallback for unknown groupings
                key.append(benchmark_name)

        group_key = " ".join(str(p) for p in key if p is not None) or None
        groups[group_key].append(benchmark)

    for grouped_benchmarks in groups.values():
        grouped_benchmarks.sort(
            key=lambda b: _read_benchmark_attr(b, "fullname" if "full" in group_by else "name") or ""
        )

    return sorted(
        ((k, v) for k, v in groups.items() if k is not None),
        key=operator.itemgetter(0),
    )


def _read_benchmark_attr(benchmark: Any, attr: str) -> Any:
    if isinstance(benchmark, dict):
        return benchmark.get(attr)
    return getattr(benchmark, attr, None)


def _filter_ignored_params(bench: Any, ignore_params: list[str] | None) -> str:
    param_str = _read_benchmark_attr(bench, "param") or ""
    params_dict = _read_benchmark_attr(bench, "params") or {}

    if not ignore_params or not params_dict:
        return str(param_str)

    filtered_parts = str(param_str).split("-") if param_str else []
    for param_name in ignore_params:
        if param_name in params_dict:
            param_value = str(params_dict[param_name])
            filtered_parts = [p for p in filtered_parts if p != param_value]

    return "-".join(filtered_parts) if filtered_parts else str(param_str)


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
