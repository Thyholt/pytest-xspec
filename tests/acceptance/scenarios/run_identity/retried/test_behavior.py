import pytest

attempts = 0


@pytest.fixture
def attempt() -> int:
    global attempts
    attempts += 1
    return attempts


@pytest.mark.xspec("REQ-001")
def test_behavior(attempt: int) -> None:
    print(f"RUN ID SCENARIO: attempt {attempt}")
    assert attempt == 2
