from __future__ import annotations

from dataclasses import dataclass

AUTO_POSTFIXES = (
    "_original",
    "_reference",
    "_baseline",
    "_orig",
    "_ref",
    "_old",
    "_new",
    "_candidate",
    "_cand",
)


@dataclass(slots=True)
class MethodNameParts:
    raw_name: str
    base_name: str
    parameters: str | None
    postfix: str | None

    @property
    def normalized_name(self) -> str:
        if self.parameters is None:
            return self.base_name
        return f"{self.base_name}[{self.parameters}]"


def parse_method_name(name: str, postfixes: list[str] | tuple[str, ...] | None = None) -> MethodNameParts:
    raw_name = str(name)
    candidate_postfixes = _normalize_postfixes(postfixes)
    candidate_postfixes = _normalize_postfixes([*candidate_postfixes, *AUTO_POSTFIXES])

    name_without_params, parameters = _split_parameters(raw_name)
    base_name = name_without_params
    postfix: str | None = None

    for suffix in candidate_postfixes:
        if not base_name.endswith(suffix):
            continue
        trimmed = base_name[: -len(suffix)]
        if not trimmed:
            continue
        base_name = trimmed
        postfix = suffix
        break

    return MethodNameParts(raw_name=raw_name, base_name=base_name, parameters=parameters, postfix=postfix)


def normalize_fullname(fullname: str, postfixes: list[str] | tuple[str, ...] | None = None) -> str:
    raw_fullname = str(fullname)
    prefix, separator, method_name = raw_fullname.rpartition("::")
    parts = parse_method_name(method_name or raw_fullname, postfixes)
    if not separator:
        return parts.normalized_name
    return f"{prefix}{separator}{parts.normalized_name}"


def _split_parameters(name: str) -> tuple[str, str | None]:
    if not name.endswith("]"):
        return name, None

    open_bracket = name.rfind("[")
    if open_bracket < 0:
        return name, None

    return name[:open_bracket], name[open_bracket + 1 : -1]


def _normalize_postfixes(postfixes: list[str] | tuple[str, ...] | None) -> list[str]:
    if not postfixes:
        return []

    unique = {postfix.strip() for postfix in postfixes if postfix and postfix.strip()}
    return sorted(unique, key=len, reverse=True)
