from collections import defaultdict
from typing import Any

import pytest

from pytest_park.core.naming import parse_method_name

# Stash keys: populated by default_pytest_benchmark_group_stats so the plugin
# can read conftest.py-configured postfixes even when pytest-benchmark never
# calls the hook (e.g. VS Code single-shot / debug mode).
_STASH_ORIGINAL_POSTFIXES: pytest.StashKey[list[str]] = pytest.StashKey()
_STASH_REFERENCE_POSTFIXES: pytest.StashKey[list[str]] = pytest.StashKey()


def default_pytest_benchmark_group_stats(
    config: Any,
    benchmarks: list[Any],
    group_by: str,
    *,
    original_postfix: list[str] | str | None = None,
    reference_postfix: list[str] | str | None = None,
    group_values_by_postfix: dict[str, str] | None = None,
    ignore_params: list[str] | None = None,
) -> list[tuple[str | None, list[Any]]]:
    """Group pytest-benchmark entries by split base method name.

    This is intended as a drop-in helper for overriding ``pytest_benchmark_group_stats``
    in a test suite and keeping benchmark name parts available in ``extra_info``.
    """
    cli_original = _read_postfixes(config, "benchmark_original_postfix")
    cli_reference = _read_postfixes(config, "benchmark_reference_postfix")
    configured_original = cli_original or _normalize_postfix_arg(original_postfix)
    configured_reference = cli_reference or _normalize_postfix_arg(reference_postfix)
    # Persist into config.stash so the plugin can read them back even in
    # debug/single-shot mode where pytest-benchmark skips this hook.
    _register_postfixes_in_config(config, configured_original, configured_reference)
    postfixes = configured_original + configured_reference
    postfix_value_map = {
        _normalize_postfix_key(key): value
        for key, value in (group_values_by_postfix or {}).items()
        if key and key.strip()
    }

    groups: dict[str | None, list[Any]] = defaultdict(list)
    for benchmark in benchmarks:
        benchmark_name = _read_benchmark_name(benchmark)
        parts = parse_method_name(benchmark_name, postfixes)
        _store_name_parts(benchmark, parts.base_name, parts.parameters, parts.postfix)

        key: list[str] = []
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
                key.append(postfix_value_map.get(_normalize_postfix_key(fallback), fallback))
            else:
                # Fallback for unknown groupings
                key.append(benchmark_name)

        group_key = " ".join(str(p) for p in key if p is not None) or None
        _store_group_key(benchmark, group_key)
        groups[group_key].append(benchmark)

    for grouped_benchmarks in groups.values():
        grouped_benchmarks.sort(
            key=lambda b: _read_benchmark_attr(b, "fullname" if "full" in group_by else "name") or ""
        )

    return sorted(groups.items(), key=lambda pair: pair[0] or "")


def _register_postfixes_in_config(config: Any, original: list[str], reference: list[str]) -> None:
    """Merge postfixes into config.stash so the plugin can read them back."""
    stash = getattr(config, "stash", None)
    if stash is None:
        return
    try:
        existing_orig: list[str] = stash.get(_STASH_ORIGINAL_POSTFIXES, [])
        existing_ref: list[str] = stash.get(_STASH_REFERENCE_POSTFIXES, [])
        stash[_STASH_ORIGINAL_POSTFIXES] = _merge_unique(existing_orig, original)
        stash[_STASH_REFERENCE_POSTFIXES] = _merge_unique(existing_ref, reference)
    except Exception:
        pass


def _merge_unique(existing: list[str], new: list[str]) -> list[str]:
    seen = set(existing)
    result = list(existing)
    for item in new:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _read_effective_postfixes(config: Any, option_name: str) -> list[str]:
    """Read postfixes with CLI/ini taking precedence; fall back to values
    registered via conftest.py calls to default_pytest_benchmark_group_stats.
    """
    cli_values = _read_postfixes(config, option_name)
    if cli_values:
        return cli_values
    stash = getattr(config, "stash", None)
    if stash is None:
        return []
    stash_key = _STASH_ORIGINAL_POSTFIXES if "original" in option_name else _STASH_REFERENCE_POSTFIXES
    try:
        return list(stash.get(stash_key, []))
    except Exception:
        return []


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

    return "-".join(filtered_parts)


def _read_postfix(config: Any, option_name: str) -> str | None:
    getoption = getattr(config, "getoption", None)
    if callable(getoption):
        value = getoption(option_name, default="")
        if isinstance(value, str) and value.strip():
            return value.strip()

    option = getattr(config, "option", None)
    if option is not None:
        value = getattr(option, option_name, "")
        if isinstance(value, str) and value.strip():
            return value.strip()

    # Fall back to ini-file config (pytest.ini / pyproject.toml / setup.cfg)
    getini = getattr(config, "getini", None)
    if callable(getini):
        try:
            value = getini(option_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        except (ValueError, KeyError):
            pass

    return None


def _read_postfixes(config: Any, option_name: str) -> list[str]:
    """Read a comma-separated list of postfixes from a config option."""
    raw = _read_postfix(config, option_name)
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _normalize_postfix_arg(value: list[str] | str | None) -> list[str]:
    """Normalize a postfix argument that may be a string, list, or None."""
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return [p.strip() for p in value if p and p.strip()]


def _normalize_postfix_key(postfix: str) -> str:
    """Normalize a postfix for comparison: strip whitespace and leading underscores/hyphens."""
    return postfix.strip().lstrip("_").lstrip("-")


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


def _store_group_key(benchmark: Any, group_key: str | None) -> None:
    if isinstance(benchmark, dict):
        benchmark["group"] = group_key
        return

    benchmark.group = group_key
