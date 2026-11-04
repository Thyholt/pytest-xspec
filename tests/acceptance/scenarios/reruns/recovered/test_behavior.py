from collections.abc import Iterator

import pytest

attempts: dict[str, int] = {}


@pytest.fixture
def attempt(request: pytest.FixtureRequest) -> int:
    name = request.node.name
    attempts[name] = attempts.get(name, 0) + 1
    print(f"{name}: attempt {attempts[name]}")
    return attempts[name]


@pytest.fixture
def setup_succeeds_on_retry(attempt: int) -> None:
    assert attempt > 1


@pytest.fixture
def teardown_succeeds_on_retry(attempt: int) -> Iterator[None]:
    yield
    assert attempt > 1


@pytest.mark.xspec("REQ-001")
def test_call(attempt: int) -> None:
    assert attempt > 1


@pytest.mark.xspec("REQ-001")
@pytest.mark.usefixtures("setup_succeeds_on_retry")
def test_setup() -> None:
    pass


@pytest.mark.xspec("REQ-001")
@pytest.mark.usefixtures("teardown_succeeds_on_retry")
def test_teardown() -> None:
    pass
