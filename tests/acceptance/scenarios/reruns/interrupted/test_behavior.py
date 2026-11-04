from collections.abc import Iterator

import pytest

attempts: dict[str, int] = {}


@pytest.fixture
def attempt(request: pytest.FixtureRequest) -> int:
    name = request.node.name
    attempts[name] = attempts.get(name, 0) + 1
    print(f"attempt {attempts[name]} started")
    return attempts[name]


@pytest.fixture
def finish_attempt(attempt: int, interruption: str) -> Iterator[None]:
    yield
    print(f"attempt {attempt} teardown started")
    if attempt == 2 and interruption == "teardown":
        raise KeyboardInterrupt

    print(f"attempt {attempt} teardown completed")


@pytest.mark.xspec("REQ-001")
@pytest.mark.parametrize("interruption", ["call", "teardown", "none"])
@pytest.mark.usefixtures("finish_attempt")
def test_behavior(attempt: int, interruption: str) -> None:
    assert attempt > 1
    if interruption == "call":
        raise KeyboardInterrupt

    print(f"attempt {attempt} call completed")
