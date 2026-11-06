import pytest


@pytest.mark.xspec("REQ-001")
def test_first_behavior() -> None:
    print("EXECUTED: first behavior")
    assert 2 + 3 == 5


@pytest.mark.xspec("REQ-001")
def test_second_behavior() -> None:
    print("EXECUTED: second behavior")
    assert "second".upper() == "SECOND"
