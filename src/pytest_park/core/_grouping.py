from __future__ import annotations

from pytest_park.models import BenchmarkCase

DEFAULT_GROUPING_PRECEDENCE = ("custom", "benchmark_group", "marks", "params")

# Params that identify implementation variants and are excluded from cross-run matching.
IGNORED_COMPARISON_PARAMS = {"implementation", "impl", "variant"}


def _normalize_postfix_key(postfix: str) -> str:
    """Normalize a postfix for comparison: strip whitespace and leading underscores/hyphens."""
    return postfix.strip().lstrip("_").lstrip("-")


def _postfix_matches(postfix: str, candidates: list[str]) -> bool:
    """Check whether a postfix matches any candidate, ignoring leading underscores."""
    normalized = _normalize_postfix_key(postfix)
    return any(_normalize_postfix_key(c) == normalized for c in candidates if c)


def _implementation_role(
    case: BenchmarkCase,
    *,
    original_postfixes: list[str] | None = None,
    reference_postfixes: list[str] | None = None,
) -> str:
    """Determine whether a case plays the 'original', 'new', or 'unknown' role."""
    if case.method_postfix:
        if original_postfixes and _postfix_matches(case.method_postfix, original_postfixes):
            return "original"
        if reference_postfixes and _postfix_matches(case.method_postfix, reference_postfixes):
            return "new"

    if case.method_postfix:
        normalized = case.method_postfix.strip().lower().replace("-", "_").lstrip("_")
        if any(token in normalized for token in ("orig", "old", "baseline", "reference", "ref")):
            return "original"
        if any(token in normalized for token in ("new", "candidate", "cand")):
            return "new"

    for param_key in IGNORED_COMPARISON_PARAMS:
        value = case.params.get(param_key)
        if value is not None:
            norm_val = value.strip().lower().replace("-", "_")
            if any(token in norm_val for token in ("orig", "old", "baseline", "reference", "ref")):
                return "original"
            if any(token in norm_val for token in ("new", "candidate", "cand")):
                return "new"
    return "unknown"


def build_group_label(case: BenchmarkCase, group_by: list[str] | None = None) -> str:
    """Create a logical group label for a benchmark case."""
    if group_by:
        custom_parts: list[str] = []
        for token in group_by:
            maybe_part = _resolve_group_token(case, token)
            if maybe_part:
                custom_parts.append(maybe_part)
        if custom_parts:
            return " | ".join(custom_parts)
        return "ungrouped"

    for token in DEFAULT_GROUPING_PRECEDENCE:
        maybe_part = _resolve_group_token(case, token)
        if maybe_part:
            return maybe_part

    return "ungrouped"


def _resolve_group_token(case: BenchmarkCase, token: str) -> str | None:
    normalized = token.strip().lower()

    if normalized in {"custom", "custom_group"}:
        if not case.custom_groups:
            return None
        bits = [f"{key}={value}" for key, value in sorted(case.custom_groups.items())]
        return "custom:" + ",".join(bits)

    if normalized.startswith("custom:"):
        key = token.split(":", 1)[1].strip()
        value = case.custom_groups.get(key)
        return f"custom:{key}={value}" if value else None

    if normalized in {"group", "benchmark_group"}:
        return case.benchmark_group

    if normalized in {"mark", "marks"}:
        return f"marks:{','.join(case.marks)}" if case.marks else None

    if normalized == "params":
        if not case.params:
            return None
        bits = [f"{key}={value}" for key, value in sorted(case.params.items())]
        return "params:" + ",".join(bits)

    if normalized.startswith("param:"):
        key = token.split(":", 1)[1].strip()
        value = case.params.get(key)
        return f"param:{key}={value}" if value else None

    if normalized in {"name", "benchmark_name", "method"}:
        return case.normalized_name

    if normalized in {"fullname", "nodeid"}:
        return case.normalized_fullname

    return None


class BenchmarkGrouper:
    """Stateful helper that encapsulates group-label and implementation-role logic.

    Hold ``group_by``, ``original_postfixes``, and ``reference_postfixes`` once
    so every call to :meth:`label` and :meth:`role` uses the same configuration.
    """

    def __init__(
        self,
        group_by: list[str] | None = None,
        original_postfixes: list[str] | None = None,
        reference_postfixes: list[str] | None = None,
    ) -> None:
        self.group_by = group_by
        self.original_postfixes = original_postfixes
        self.reference_postfixes = reference_postfixes

    def label(self, case: BenchmarkCase) -> str:
        """Return the group label for *case* using this grouper's ``group_by`` config."""
        return build_group_label(case, self.group_by)

    def role(self, case: BenchmarkCase) -> str:
        """Return ``'original'``, ``'new'``, or ``'unknown'`` for *case*."""
        return _implementation_role(
            case,
            original_postfixes=self.original_postfixes,
            reference_postfixes=self.reference_postfixes,
        )

    @staticmethod
    def normalize_postfix(postfix: str) -> str:
        """Strip whitespace and leading underscores/hyphens from *postfix*."""
        return _normalize_postfix_key(postfix)

    @staticmethod
    def postfix_matches(postfix: str, candidates: list[str]) -> bool:
        """Return ``True`` if *postfix* matches any entry in *candidates*."""
        return _postfix_matches(postfix, candidates)
