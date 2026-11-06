import pytest


@pytest.fixture(autouse=True)
def record_execution() -> None:
    print("RUN ID SCENARIO: fixture")


@pytest.mark.xspec("REQ-001")
@pytest.mark.xspec("REQ-002")
@pytest.mark.parametrize("value", [1, 2], ids=["first", "second"])
def test_shared_behavior(value: int) -> None:
    print(f"RUN ID SCENARIO: shared {value}")
    assert value > 0


@pytest.mark.xspec("REQ-001")
def test_other_behavior() -> None:
    print("RUN ID SCENARIO: other")
    assert 2 + 2 == 4
