from __future__ import annotations

import pytest

from pytest_park.data import load_benchmark_folder
from pytest_park.models import BenchmarkCase, BenchmarkStats
from pytest_park.utils import (
    build_group_label,
    select_candidate_run,
    select_reference_run,
)


def _make_stats(mean: float = 1.0) -> BenchmarkStats:
    return BenchmarkStats(
        mean=mean,
        median=mean,
        min=mean * 0.95,
        max=mean * 1.05,
        stddev=mean * 0.01,
        rounds=5,
        iterations=1,
        ops=1.0 / mean if mean else 0.0,
    )


def _make_case(
    *,
    name: str = "my_bench",
    fullname: str = "module::my_bench",
    normalized_name: str | None = None,
    normalized_fullname: str | None = None,
    base_name: str | None = None,
    method_parameters: str | None = None,
    method_postfix: str | None = None,
    benchmark_group: str | None = None,
    marks: tuple[str, ...] = (),
    params: dict[str, str] | None = None,
    custom_groups: dict[str, str] | None = None,
    mean: float = 1.0,
) -> BenchmarkCase:
    return BenchmarkCase(
        name=name,
        fullname=fullname,
        normalized_name=normalized_name or name,
        normalized_fullname=normalized_fullname or fullname,
        base_name=base_name or name,
        method_parameters=method_parameters,
        method_postfix=method_postfix,
        benchmark_group=benchmark_group,
        marks=marks,
        params=params or {},
        custom_groups=custom_groups or {},
        stats=_make_stats(mean),
    )


def test_grouping_priority_uses_custom_then_group(benchmark_folder) -> None:
    runs = load_benchmark_folder(benchmark_folder)
    case = runs[0].cases[0]

    default_label = build_group_label(case)
    custom_label = build_group_label(case, ["custom:scenario", "param:device"])

    assert default_label.startswith("custom:")
    assert custom_label == "custom:scenario=cpu-baseline | param:device=cpu"


# ---------------------------------------------------------------------------
# build_group_label – individual token types
# ---------------------------------------------------------------------------


class TestBuildGroupLabelTokens:
    """Each supported token type resolves to the correct label."""

    def test_benchmark_group_token(self) -> None:
        case = _make_case(benchmark_group="sorting")
        assert build_group_label(case, ["benchmark_group"]) == "sorting"

    def test_group_alias_token(self) -> None:
        case = _make_case(benchmark_group="io")
        assert build_group_label(case, ["group"]) == "io"

    def test_marks_token(self) -> None:
        case = _make_case(marks=("slow", "algo"))
        assert build_group_label(case, ["marks"]) == "marks:slow,algo"

    def test_mark_alias_token(self) -> None:
        case = _make_case(marks=("baseline",))
        assert build_group_label(case, ["mark"]) == "marks:baseline"

    def test_params_token_all_params(self) -> None:
        case = _make_case(params={"device": "gpu", "size": "large"})
        assert build_group_label(case, ["params"]) == "params:device=gpu,size=large"

    def test_param_specific_key_token(self) -> None:
        case = _make_case(params={"device": "cpu", "size": "small"})
        assert build_group_label(case, ["param:device"]) == "param:device=cpu"

    def test_param_specific_key_whitespace_tolerance(self) -> None:
        case = _make_case(params={"batch": "32"})
        assert build_group_label(case, ["param: batch"]) == "param:batch=32"

    def test_custom_all_groups_token(self) -> None:
        case = _make_case(custom_groups={"env": "prod", "tier": "fast"})
        assert build_group_label(case, ["custom"]) == "custom:env=prod,tier=fast"

    def test_custom_group_alias_token(self) -> None:
        case = _make_case(custom_groups={"scenario": "baseline"})
        assert build_group_label(case, ["custom_group"]) == "custom:scenario=baseline"

    def test_custom_specific_key_token(self) -> None:
        case = _make_case(custom_groups={"env": "staging", "tier": "medium"})
        assert build_group_label(case, ["custom:env"]) == "custom:env=staging"

    def test_name_token(self) -> None:
        case = _make_case(normalized_name="sort_values[n=1000]")
        assert build_group_label(case, ["name"]) == "sort_values[n=1000]"

    def test_method_alias_token(self) -> None:
        case = _make_case(normalized_name="encode")
        assert build_group_label(case, ["method"]) == "encode"

    def test_benchmark_name_alias_token(self) -> None:
        case = _make_case(normalized_name="decode")
        assert build_group_label(case, ["benchmark_name"]) == "decode"

    def test_fullname_token(self) -> None:
        case = _make_case(normalized_fullname="tests/bench.py::encode[fast]")
        assert build_group_label(case, ["fullname"]) == "tests/bench.py::encode[fast]"

    def test_nodeid_alias_token(self) -> None:
        case = _make_case(normalized_fullname="test_mod::my_func")
        assert build_group_label(case, ["nodeid"]) == "test_mod::my_func"


# ---------------------------------------------------------------------------
# build_group_label – "ungrouped" fallback behaviour
# ---------------------------------------------------------------------------


class TestBuildGroupLabelUngrouped:
    """Tokens that find no value fall through to 'ungrouped'."""

    def test_marks_token_no_marks_returns_ungrouped(self) -> None:
        case = _make_case(marks=())
        assert build_group_label(case, ["marks"]) == "ungrouped"

    def test_params_token_no_params_returns_ungrouped(self) -> None:
        case = _make_case(params={})
        assert build_group_label(case, ["params"]) == "ungrouped"

    def test_param_missing_key_returns_ungrouped(self) -> None:
        case = _make_case(params={"device": "cpu"})
        assert build_group_label(case, ["param:missing"]) == "ungrouped"

    def test_custom_token_no_custom_groups_returns_ungrouped(self) -> None:
        case = _make_case(custom_groups={})
        assert build_group_label(case, ["custom"]) == "ungrouped"

    def test_custom_specific_key_missing_returns_ungrouped(self) -> None:
        case = _make_case(custom_groups={"env": "prod"})
        assert build_group_label(case, ["custom:tier"]) == "ungrouped"

    def test_unknown_token_returns_ungrouped(self) -> None:
        case = _make_case()
        assert build_group_label(case, ["nonexistent_token"]) == "ungrouped"

    def test_empty_group_by_uses_default_precedence_not_ungrouped(self) -> None:
        # group_by=[] is falsy → triggers default precedence path
        case = _make_case(benchmark_group="sorting")
        assert build_group_label(case, []) == "sorting"

    def test_benchmark_group_none_token_returns_ungrouped(self) -> None:
        case = _make_case(benchmark_group=None)
        assert build_group_label(case, ["benchmark_group"]) == "ungrouped"


# ---------------------------------------------------------------------------
# build_group_label – multiple tokens (composite groups)
# ---------------------------------------------------------------------------


class TestBuildGroupLabelMultipleTokens:
    """Multiple tokens are joined with ' | '; absent tokens are skipped."""

    def test_two_resolving_tokens_joined(self) -> None:
        case = _make_case(benchmark_group="sorting", params={"device": "cpu"})
        label = build_group_label(case, ["benchmark_group", "param:device"])
        assert label == "sorting | param:device=cpu"

    def test_first_token_missing_second_used(self) -> None:
        case = _make_case(benchmark_group=None, params={"device": "gpu"})
        label = build_group_label(case, ["benchmark_group", "param:device"])
        assert label == "param:device=gpu"

    def test_three_tokens_only_first_two_resolve(self) -> None:
        case = _make_case(marks=("algo",), params={"device": "cpu"})
        label = build_group_label(case, ["marks", "param:device", "param:missing"])
        assert label == "marks:algo | param:device=cpu"

    def test_all_tokens_missing_returns_ungrouped(self) -> None:
        case = _make_case()
        assert build_group_label(case, ["marks", "param:missing"]) == "ungrouped"

    def test_custom_and_param_combination(self) -> None:
        case = _make_case(custom_groups={"scenario": "fast"}, params={"device": "cpu"})
        label = build_group_label(case, ["custom:scenario", "param:device"])
        assert label == "custom:scenario=fast | param:device=cpu"


# ---------------------------------------------------------------------------
# build_group_label – default precedence ordering
# ---------------------------------------------------------------------------


class TestBuildGroupLabelDefaultPrecedence:
    """group_by=None uses custom → benchmark_group → marks → params."""

    def test_custom_beats_benchmark_group(self) -> None:
        case = _make_case(benchmark_group="sorting", custom_groups={"scenario": "fast"})
        assert build_group_label(case).startswith("custom:")

    def test_benchmark_group_beats_marks_when_no_custom(self) -> None:
        case = _make_case(benchmark_group="sorting", marks=("algo",), custom_groups={})
        assert build_group_label(case) == "sorting"

    def test_marks_beat_params_when_no_custom_or_group(self) -> None:
        case = _make_case(benchmark_group=None, marks=("slow",), params={"device": "cpu"}, custom_groups={})
        assert build_group_label(case) == "marks:slow"

    def test_params_used_when_no_custom_group_or_marks(self) -> None:
        case = _make_case(benchmark_group=None, marks=(), params={"device": "cpu"}, custom_groups={})
        assert build_group_label(case) == "params:device=cpu"

    def test_all_absent_returns_ungrouped(self) -> None:
        case = _make_case(benchmark_group=None, marks=(), params={}, custom_groups={})
        assert build_group_label(case) == "ungrouped"

    def test_token_matching_is_case_insensitive(self) -> None:
        case = _make_case(benchmark_group="sorting")
        assert build_group_label(case, ["BENCHMARK_GROUP"]) == "sorting"
        assert build_group_label(case, ["Group"]) == "sorting"
