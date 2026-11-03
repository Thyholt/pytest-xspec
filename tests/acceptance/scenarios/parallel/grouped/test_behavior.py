import pytest


@pytest.mark.xspec("REQ-001")
@pytest.mark.xdist_group("shared@group")
@pytest.mark.parametrize("value", [1, 2], ids=["first@case", "second"])
def test_behavior(value: int) -> None:
    assert value > 0


@pytest.mark.xspec("REQ-002")
@pytest.mark.xdist_group("shared@group")
def test_excluded() -> None:
    pytest.fail("The keyword filter must exclude this test")
