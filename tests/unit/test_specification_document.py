"""Validate document contents independently of TOML parsing and pytest execution."""

import pytest

from pytest_xspec.validation import validate_document


def test_document_preserves_opaque_ids_and_their_order() -> None:
    requirements = [{"id": "Krav / æøå : 1"}, {"id": " REQ-002 "}, {"id": "requirement.item"}]

    result = validate_document("xspec.toml", requirements)

    assert result == ["Krav / æøå : 1", " REQ-002 ", "requirement.item"]


def test_invalid_document_entry_is_reported_before_duplicate_ids() -> None:
    requirements = [
        {"id": "REQ-001"},
        {"id": "REQ-001"},
        {"id": "REQ-002", "description": 123},
    ]

    with pytest.raises(pytest.UsageError) as error:
        validate_document("xspec.toml", requirements)

    assert str(error.value) == "xspec.toml: requirement 'REQ-002': description must be a string"


@pytest.mark.parametrize(
    ("requirements", "diagnostic"),
    [
        pytest.param({"id": "REQ-001"}, "requirements must be a list of tables", id="not-a-list"),
        pytest.param(["REQ-001"], "requirement 1 must be a table", id="not-a-table"),
    ],
)
def test_invalid_document_inventory_structure_is_rejected(
    requirements: object, diagnostic: str
) -> None:
    with pytest.raises(pytest.UsageError) as error:
        validate_document("xspec.toml", requirements)

    assert str(error.value) == f"xspec.toml: {diagnostic}"


@pytest.mark.parametrize(
    ("requirement", "diagnostic"),
    [
        pytest.param({}, "requirement 1 must have a string id", id="missing-id"),
        pytest.param({"id": 123}, "requirement 1 must have a string id", id="non-string-id"),
        pytest.param({"id": b"REQ-001"}, "requirement 1 must have a string id", id="bytes-id"),
        pytest.param(
            {"id": "REQ-001", "description": None},
            "requirement 'REQ-001': description must be a string",
            id="null-description",
        ),
        pytest.param(
            {"id": "REQ-001", "rationale": b"reason"},
            "requirement 'REQ-001': rationale must be a string",
            id="bytes-rationale",
        ),
        pytest.param(
            {"id": "REQ-001", "description": 123},
            "requirement 'REQ-001': description must be a string",
            id="non-string-description",
        ),
        pytest.param(
            {"id": "REQ-001", "rationale": False},
            "requirement 'REQ-001': rationale must be a string",
            id="non-string-rationale",
        ),
    ],
)
def test_invalid_document_requirement_contents_are_rejected(
    requirement: dict[str, object], diagnostic: str
) -> None:
    with pytest.raises(pytest.UsageError) as error:
        validate_document("xspec.toml", [requirement])

    assert str(error.value) == f"xspec.toml: {diagnostic}"
