"""Validate requirement inventories without reading configuration files."""

import pytest

from pytest_xspec.validation import validate_inventory


@pytest.mark.parametrize("inventory", [[], ["REQ-002", "REQ-001"], ["Krav / æøå : 1"]])
def test_valid_requirement_inventory_preserves_ids_and_order(inventory: list[str]) -> None:
    result = validate_inventory("configuration", inventory)

    assert result == inventory


@pytest.mark.parametrize(
    ("inventory", "diagnostic"),
    [
        pytest.param("REQ-001", "requirements must be a list of string IDs", id="scalar"),
        pytest.param([123], "requirements must be a list of string IDs", id="non-string"),
        pytest.param(("REQ-001",), "requirements must be a list of string IDs", id="tuple"),
        pytest.param([b"REQ-001"], "requirements must be a list of string IDs", id="bytes"),
        pytest.param(
            ["REQ-001", "REQ-001", 123],
            "requirements must be a list of string IDs",
            id="invalid-entry-after-duplicate",
        ),
        pytest.param(["REQ-001", "REQ-001"], "duplicate requirements ID 'REQ-001'", id="duplicate"),
    ],
)
def test_invalid_requirement_inventory_is_rejected(inventory: object, diagnostic: str) -> None:
    with pytest.raises(pytest.UsageError) as error:
        validate_inventory("configuration", inventory)

    assert str(error.value) == f"configuration: {diagnostic}"
