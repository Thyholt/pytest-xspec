from collections.abc import Iterator

import pytest


@pytest.fixture
def interrupted() -> Iterator[None]:
    yield
    raise KeyboardInterrupt


@pytest.mark.xspec("REQ-001")
@pytest.mark.usefixtures("interrupted")
def test_behavior() -> None:
    pass
