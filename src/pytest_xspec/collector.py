"""Validate requirement associations before pytest filters collected tests."""

from collections.abc import Collection

import pytest


def requirement_ids(item: pytest.Item, inventory: Collection[str]) -> tuple[str, ...]:
    identifiers: dict[str, None] = {}

    for marker in item.iter_markers("xspec"):
        identifier = _marker_id(marker, item.nodeid)
        if identifier not in inventory:
            raise pytest.UsageError(f"{item.nodeid}: unknown xspec requirement ID {identifier!r}")

        identifiers[identifier] = None

    return tuple(identifiers)


def _marker_id(marker: pytest.Mark, nodeid: str) -> str:
    diagnostic = f"{nodeid}: xspec requires exactly one positional string ID and no keywords"
    if len(marker.args) != 1 or marker.kwargs:
        raise pytest.UsageError(diagnostic)

    identifier = marker.args[0]
    if not isinstance(identifier, str):
        raise pytest.UsageError(diagnostic)

    return identifier
