import os

import pytest


@pytest.fixture
def crashed() -> None:
    os._exit(1)


@pytest.mark.xspec("REQ-001")
@pytest.mark.usefixtures("crashed")
@pytest.mark.parametrize("value", [0, 1, 2, 3])
def test_behavior(value: int) -> None:
    assert value >= 0
