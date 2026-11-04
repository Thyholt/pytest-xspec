import pytest

attempts: dict[str, int] = {}


@pytest.mark.xspec("REQ-001")
@pytest.mark.parametrize("final_outcome", ["SKIPPED", "XFAILED", "XPASSED"])
def test_behavior(final_outcome: str, request: pytest.FixtureRequest) -> None:
    name = request.node.name
    attempts[name] = attempts.get(name, 0) + 1
    print(f"attempt {attempts[name]}")
    assert attempts[name] > 1
    if final_outcome == "SKIPPED":
        pytest.skip("The retry cannot execute")

    if final_outcome == "XFAILED":
        pytest.xfail("The retry fails as expected")

    request.node.add_marker(pytest.mark.xfail(reason="The retry unexpectedly passes"))
