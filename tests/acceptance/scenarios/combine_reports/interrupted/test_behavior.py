import pytest


@pytest.mark.xspec("REQ-001")
def test_first_behavior() -> None:
    assert 2 + 3 == 5


def test_interruption() -> None:
    raise KeyboardInterrupt
