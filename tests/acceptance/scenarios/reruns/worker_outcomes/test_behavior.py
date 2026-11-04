from collections.abc import Iterator

import pytest

attempts: dict[str, int] = {}


@pytest.fixture
def attempt(request: pytest.FixtureRequest) -> int:
    name = request.node.name
    attempts[name] = attempts.get(name, 0) + 1
    return attempts[name]


@pytest.fixture
def finish_attempt(attempt: int, worker_id: str, final_outcome: str) -> Iterator[None]:
    yield
    if attempt != 2:
        return

    if worker_id != "gw0":
        return

    if final_outcome == "interrupted":
        raise KeyboardInterrupt

    if final_outcome == "teardown_error":
        pytest.fail("This worker's final teardown fails")


@pytest.mark.xspec("REQ-001")
@pytest.mark.parametrize("final_outcome", ["failed", "skipped", "interrupted", "teardown_error"])
@pytest.mark.usefixtures("finish_attempt")
def test_behavior(attempt: int, worker_id: str, final_outcome: str) -> None:
    assert attempt > 1
    if worker_id == "gw0":
        if final_outcome == "failed":
            pytest.fail("This worker exhausts its retries")

        if final_outcome == "skipped":
            pytest.skip("This worker cannot complete verification")
