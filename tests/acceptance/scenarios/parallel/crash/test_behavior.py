import os

import pytest


@pytest.mark.xspec("REQ-001")
@pytest.mark.parametrize("value", [1, 2])
def test_behavior(value: int) -> None:
    os._exit(value)
