import pytest

attempts = 0


@pytest.mark.xspec("REQ-001")
def test_recovered() -> None:
    global attempts
    attempts += 1
    print(f"recovered attempt {attempts}")
    assert attempts > 1


@pytest.mark.xspec("REQ-001")
def test_failed() -> None:
    pytest.fail("This distinct test never passes")
