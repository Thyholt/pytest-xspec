import os

import pytest


@pytest.fixture
def behavior(request: pytest.FixtureRequest) -> str:
    outcome = os.environ.get("XSPEC_SCENARIO_OUTCOME", "PASSED")
    if outcome == "ERROR":
        raise RuntimeError("scenario setup failed")

    if outcome in ("XFAILED", "XPASSED"):
        request.node.add_marker(pytest.mark.xfail(reason="scenario expected failure", strict=False))

    return outcome


@pytest.mark.xspec("REQ-001")
def test_first_behavior(behavior: str) -> None:
    if behavior == "SKIPPED":
        pytest.skip("scenario unavailable")

    assert behavior not in ("FAILED", "XFAILED")


@pytest.mark.xspec("REQ-001")
def test_second_behavior() -> None:
    assert 2 + 3 == 5
