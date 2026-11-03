import pytest


@pytest.mark.xspec("REQ-001")
def test_behavior(worker_id: str) -> None:
    if worker_id == "gw0":
        pytest.skip("This worker cannot verify the requirement")
