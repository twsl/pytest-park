from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ProfilerLoadError(ValueError):
    """Raised when profiler artifacts cannot be loaded."""


def load_profiler_folder(folder: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Load profiler JSON files and return data grouped by run_id and case key."""
    root = Path(folder)
    if not root.exists() or not root.is_dir():
        raise ProfilerLoadError(f"Profiler folder does not exist: {root}")

    profiler_by_run: dict[str, dict[str, dict[str, Any]]] = {}
    for artifact in sorted(root.rglob("*.json")):
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue

        run_id = str(payload.get("run_id") or artifact.stem)
        cases_payload = payload.get("cases")
        if not isinstance(cases_payload, list):
            continue

        run_cases = profiler_by_run.setdefault(run_id, {})
        for case_payload in cases_payload:
            if not isinstance(case_payload, dict):
                continue
            case_key = str(case_payload.get("case_key") or case_payload.get("fullname") or "")
            if not case_key:
                continue
            run_cases[case_key] = {
                "function": str(case_payload.get("function") or ""),
                "file": str(case_payload.get("file") or ""),
                "line": int(case_payload.get("line") or 0),
                "total_time": float(case_payload.get("total_time") or 0.0),
            }

    return profiler_by_run
