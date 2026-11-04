"""Validate requirement IDs, document entries, and uniqueness."""

import pytest


def validate_inventory(source: str, requirements: object) -> list[str]:
    diagnostic = f"{source}: requirements must be a list of string IDs"
    if not isinstance(requirements, list):
        raise pytest.UsageError(diagnostic)

    identifiers: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, str):
            raise pytest.UsageError(diagnostic)

        identifiers.append(requirement)

    _validate_unique_ids(source, identifiers)
    return identifiers


def validate_document(source: str, requirements: object) -> list[str]:
    if not isinstance(requirements, list):
        raise pytest.UsageError(f"{source}: requirements must be a list of tables")

    identifiers = [
        _validate_requirement(source, requirement, position)
        for position, requirement in enumerate(requirements, start=1)
    ]
    _validate_unique_ids(source, identifiers)
    return identifiers


def _validate_requirement(source: str, requirement: object, position: int) -> str:
    if not isinstance(requirement, dict):
        raise pytest.UsageError(f"{source}: requirement {position} must be a table")

    identifier = requirement.get("id")
    if not isinstance(identifier, str):
        raise pytest.UsageError(f"{source}: requirement {position} must have a string id")

    for field in ("description", "rationale"):
        if not isinstance(requirement.get(field, ""), str):
            raise pytest.UsageError(
                f"{source}: requirement {identifier!r}: {field} must be a string"
            )

    return identifier


def _validate_unique_ids(source: str, identifiers: list[str]) -> None:
    seen: set[str] = set()
    for identifier in identifiers:
        if identifier in seen:
            raise pytest.UsageError(f"{source}: duplicate requirements ID {identifier!r}")

        seen.add(identifier)
