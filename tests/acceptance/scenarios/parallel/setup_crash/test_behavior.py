import os
from pathlib import Path

import pytest


@pytest.fixture
def crashed(request: pytest.FixtureRequest, value: int) -> None:
    Path(f"crashed-{value}.txt").write_text(request.node.nodeid, encoding="utf-8")
    os._exit(1)


@pytest.mark.xspec("REQ-001")
@pytest.mark.usefixtures("crashed")
@pytest.mark.parametrize("value", [0, 1, 2, 3])
def test_behavior(value: int) -> None:
    assert value >= 0
