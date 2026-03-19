from __future__ import annotations

import json
from pathlib import Path


def _write_run_payload(path: Path, run_id: str, tag: str, dt: str, cases: list[dict]) -> None:
    payload = {
        "datetime": dt,
        "metadata": {"run_id": run_id, "tag": tag},
        "benchmarks": cases,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
