from __future__ import annotations

from pytest_park.data import load_benchmark_folder, load_profiler_folder
from pytest_park.utils import attach_profiler_data


def test_attach_profiler_data_to_runs(benchmark_folder, profiler_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    profiler_data = load_profiler_folder(profiler_folder)

    attached = attach_profiler_data(runs, profiler_data)
    candidate_run = next(run for run in attached if run.run_id == "run-candidate-v2")

    assert "bench::sort_values" in candidate_run.profiler
    assert candidate_run.profiler["bench::sort_values"]["total_time"] == 0.11
