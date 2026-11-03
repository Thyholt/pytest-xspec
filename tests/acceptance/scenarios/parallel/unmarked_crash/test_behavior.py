import os

import pytest


@pytest.mark.xspec("REQ-001")
def test_behavior() -> None:
    pass


def test_crash() -> None:
    os._exit(1)
