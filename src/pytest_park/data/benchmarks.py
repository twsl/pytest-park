from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from pytest_park.core.naming import normalize_fullname, parse_method_name
from pytest_park.models import BenchmarkCase, BenchmarkRun, BenchmarkStats


class BenchmarkLoadError(ValueError):
    """Raised when a benchmark artifact cannot be parsed."""


def load_benchmark_payload(
    payload: dict[str, Any],
    *,
    source_file: str = "<memory>",
    original_postfix: str | None = None,
    reference_postfix: str | None = None,
) -> BenchmarkRun | None:
    """Load one in-memory pytest-benchmark payload into a run model."""
    postfixes = _configured_postfixes(original_postfix, reference_postfix)
    return _load_payload(payload, source_file=source_file, postfixes=postfixes)


def build_benchmark_run(
    benchmarks: list[dict[str, Any]],
    *,
    run_id: str,
    source_file: str = "<memory>",
    created_at: datetime | None = None,
    tag: str | None = None,
    commit_id: str | None = None,
    machine: str | None = None,
    python_version: str | None = None,
    metadata: dict[str, Any] | None = None,
    original_postfix: str | None = None,
    reference_postfix: str | None = None,
) -> BenchmarkRun:
    """Build a run model from live pytest-benchmark entries."""
    postfixes = _configured_postfixes(original_postfix, reference_postfix)
    return _build_benchmark_run(
        benchmarks,
        run_id=run_id,
        source_file=source_file,
        created_at=created_at,
        tag=tag,
        commit_id=commit_id,
        machine=machine,
        python_version=python_version,
        metadata=metadata,
        postfixes=postfixes,
    )


def load_benchmark_folder(
    folder: str | Path,
    original_postfix: str | None = None,
    reference_postfix: str | None = None,
) -> list[BenchmarkRun]:
    """Load pytest-benchmark JSON artifacts from a folder recursively."""
    root = Path(folder)
    if not root.exists() or not root.is_dir():
        raise BenchmarkLoadError(f"Benchmark folder does not exist: {root}")

    runs: list[BenchmarkRun] = []
    for artifact in sorted(root.rglob("*.json")):
        maybe_run = _load_artifact(
            artifact,
            original_postfix=original_postfix,
            reference_postfix=reference_postfix,
        )
        if maybe_run is not None:
            runs.append(maybe_run)

    if not runs:
        raise BenchmarkLoadError(f"No pytest-benchmark JSON files found under: {root}")

    runs.sort(key=lambda run: (run.created_at or datetime.min, run.run_id))
    return runs


def _load_artifact(
    artifact: Path,
    *,
    original_postfix: str | None = None,
    reference_postfix: str | None = None,
) -> BenchmarkRun | None:
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkLoadError(f"Invalid JSON in artifact: {artifact}") from exc

    return load_benchmark_payload(
        payload,
        source_file=str(artifact),
        original_postfix=original_postfix,
        reference_postfix=reference_postfix,
    )


def _load_payload(payload: dict[str, Any], *, source_file: str, postfixes: list[str]) -> BenchmarkRun | None:
    if not isinstance(payload, dict) or "benchmarks" not in payload:
        return None

    if not isinstance(payload["benchmarks"], list):
        raise BenchmarkLoadError(f"Malformed benchmark list in artifact: {source_file}")

    commit_info = _as_dict(payload.get("commit_info"))
    machine_info = _as_dict(payload.get("machine_info"))
    metadata = _as_dict(payload.get("metadata"))

    run_id = str(
        metadata.get("run_id")
        or payload.get("run_id")
        or payload.get("datetime")
        or commit_info.get("id")
        or Path(source_file).stem
    )
    created_at = _parse_datetime(payload.get("datetime") or metadata.get("datetime"))
    tag = _first_non_empty(metadata.get("tag"), metadata.get("label"), payload.get("tag"))

    return _build_benchmark_run(
        payload["benchmarks"],
        run_id=run_id,
        source_file=source_file,
        created_at=created_at,
        tag=str(tag) if tag is not None else None,
        commit_id=str(commit_info.get("id")) if commit_info.get("id") else None,
        machine=str(machine_info.get("node")) if machine_info.get("node") else None,
        python_version=str(machine_info.get("python_version")) if machine_info.get("python_version") else None,
        metadata=metadata,
        postfixes=postfixes,
    )


def _build_benchmark_run(
    benchmarks: list[dict[str, Any]],
    *,
    run_id: str,
    source_file: str,
    created_at: datetime | None,
    tag: str | None,
    commit_id: str | None,
    machine: str | None,
    python_version: str | None,
    metadata: dict[str, Any] | None,
    postfixes: list[str],
) -> BenchmarkRun:
    run = BenchmarkRun(
        run_id=run_id,
        source_file=source_file,
        created_at=created_at,
        tag=tag,
        commit_id=commit_id,
        machine=machine,
        python_version=python_version,
        metadata=metadata or {},
        cases=[],
    )

    for case_payload in benchmarks:
        if not isinstance(case_payload, dict):
            continue
        run.cases.append(_parse_case(case_payload, postfixes))

    return run


def _parse_case(payload: dict[str, Any], postfixes: list[str]) -> BenchmarkCase:
    stats_payload = _as_dict(payload.get("stats"))
    raw_name = str(payload.get("name") or payload.get("fullname") or "unknown")
    raw_fullname = str(payload.get("fullname") or payload.get("name") or "unknown")
    name_parts = parse_method_name(raw_name, postfixes)
    case = BenchmarkCase(
        name=raw_name,
        fullname=raw_fullname,
        normalized_name=name_parts.normalized_name,
        normalized_fullname=normalize_fullname(raw_fullname, postfixes),
        base_name=name_parts.base_name,
        method_parameters=name_parts.parameters,
        method_postfix=name_parts.postfix,
        benchmark_group=_string_or_none(payload.get("group")),
        marks=_extract_marks(payload),
        params=_extract_params(payload),
        custom_groups=_extract_custom_groups(payload),
        stats=BenchmarkStats(
            mean=_as_float(stats_payload.get("mean"), 0.0),
            median=_as_float(stats_payload.get("median"), 0.0),
            min=_as_float(stats_payload.get("min"), 0.0),
            max=_as_float(stats_payload.get("max"), 0.0),
            stddev=_as_float(stats_payload.get("stddev"), 0.0),
            rounds=_as_int(stats_payload.get("rounds"), 0),
            iterations=_as_int(stats_payload.get("iterations"), 1),
            ops=_as_float(stats_payload.get("ops"), 0.0),
        ),
    )
    return case


def _extract_marks(payload: dict[str, Any]) -> tuple[str, ...]:
    extra_info = _as_dict(payload.get("extra_info"))
    candidates = [payload.get("marks"), payload.get("markers"), extra_info.get("marks")]
    marks: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, list):
            marks.extend(str(item) for item in candidate)
        elif isinstance(candidate, str):
            marks.append(candidate)
    deduped = sorted({mark.strip() for mark in marks if mark and mark.strip()})
    return tuple(deduped)


def _extract_params(payload: dict[str, Any]) -> dict[str, str]:
    params_payload = payload.get("params")
    if not isinstance(params_payload, dict):
        return {}
    return {str(key): str(value) for key, value in params_payload.items()}


def _extract_custom_groups(payload: dict[str, Any]) -> dict[str, str]:
    extra_info = _as_dict(payload.get("extra_info"))
    group_payload = extra_info.get("custom_groups") or extra_info.get("groupings")
    if not isinstance(group_payload, dict):
        return {}
    return {str(key): str(value) for key, value in group_payload.items()}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _configured_postfixes(original_postfix: str | None, reference_postfix: str | None) -> list[str]:
    postfixes = []
    if original_postfix and original_postfix.strip():
        postfixes.append(original_postfix.strip())
    if reference_postfix and reference_postfix.strip():
        postfixes.append(reference_postfix.strip())
    return postfixes
