from __future__ import annotations

from pytest_park.models import BenchmarkRun


class RunSelector:
    """Selects benchmark runs from a run history by ID, tag, or position."""

    def __init__(self, runs: list[BenchmarkRun]) -> None:
        self.runs = runs

    def select_reference(self, reference_id_or_tag: str) -> BenchmarkRun:
        """Select a run by explicit run_id or tag."""
        for run in self.runs:
            if run.run_id == reference_id_or_tag or run.tag == reference_id_or_tag:
                return run
        raise ValueError(f"No run found for reference identifier: {reference_id_or_tag}")

    def select_candidate(
        self,
        candidate_id_or_tag: str | None,
        reference_run: BenchmarkRun,
    ) -> BenchmarkRun:
        """Select candidate run or default to the latest non-reference run."""
        if candidate_id_or_tag:
            for run in self.runs:
                if run.run_id == candidate_id_or_tag or run.tag == candidate_id_or_tag:
                    return run
            raise ValueError(f"No run found for candidate identifier: {candidate_id_or_tag}")

        non_reference = [run for run in self.runs if run.run_id != reference_run.run_id]
        if not non_reference:
            raise ValueError("No candidate run available besides the selected reference run")
        return non_reference[-1]

    def select_latest_and_previous(self) -> tuple[BenchmarkRun, BenchmarkRun]:
        """Return the second-to-last and last run as a (reference, candidate) pair."""
        if len(self.runs) < 2:
            raise ValueError("At least two runs are required for comparison")
        return self.runs[-2], self.runs[-1]

    def list_methods(self) -> list[str]:
        """Return sorted unique benchmark method names seen across all runs."""
        methods = {case.normalized_name for run in self.runs for case in run.cases}
        return sorted(methods)


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def attach_profiler_data(
    runs: list[BenchmarkRun],
    profiler_by_run: dict[str, dict[str, dict[str, object]]],
) -> list[BenchmarkRun]:
    """Attach profiler records to matching benchmark runs."""
    for run in runs:
        run.profiler = profiler_by_run.get(run.run_id, {})
    return runs


def select_reference_run(runs: list[BenchmarkRun], reference_id_or_tag: str) -> BenchmarkRun:
    """Select a run by explicit run_id or tag."""
    return RunSelector(runs).select_reference(reference_id_or_tag)


def select_candidate_run(
    runs: list[BenchmarkRun],
    candidate_id_or_tag: str | None,
    reference_run: BenchmarkRun,
) -> BenchmarkRun:
    """Select candidate run or default to the latest non-reference run."""
    return RunSelector(runs).select_candidate(candidate_id_or_tag, reference_run)


def select_latest_and_previous_runs(runs: list[BenchmarkRun]) -> tuple[BenchmarkRun, BenchmarkRun]:
    """Select previous and latest run as a (reference, candidate) pair."""
    return RunSelector(runs).select_latest_and_previous()


def list_methods(runs: list[BenchmarkRun]) -> list[str]:
    """List unique benchmark methods seen across runs."""
    return RunSelector(runs).list_methods()
