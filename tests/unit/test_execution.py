"""Final attempts contribute independent evidence before worker aggregation."""

import pytest

from pytest_xspec.execution import ExecutionResults


def test_discarded_attempt_teardown_cannot_complete_an_unreported_retry() -> None:
    results = ExecutionResults()
    results.collect("test")

    results.record("test", "setup", None)
    results.record("test", "call", "RERUN")
    results.record("test", "teardown", None)

    assert results.outcomes() == {"test": "SKIPPED"}


def test_retry_replaces_all_evidence_from_the_previous_attempt() -> None:
    results = ExecutionResults()
    results.collect("test")
    results.record("test", "setup", None)
    results.record("test", "call", "FAILED")
    results.record("test", "teardown", "RERUN")

    results.record("test", "setup", None)
    results.record("test", "call", "PASSED")
    results.record("test", "teardown", None)

    assert results.outcomes() == {"test": "PASSED"}


@pytest.mark.parametrize("worker_order", [("first", "second"), ("second", "first")])
@pytest.mark.parametrize("status", ["FAILED", "ERROR", "SKIPPED"])
def test_success_cannot_erase_another_workers_final_outcome(
    worker_order: tuple[str, str], status: str
) -> None:
    results = ExecutionResults()
    results.collect("test")

    results.record("test", "setup", None, worker="first")
    results.record("test", "setup", None, worker="second")
    results.record("test", "call", status, worker="first")
    results.record("test", "call", "RERUN", worker="second")
    results.record("test", "teardown", None, worker="second")
    results.record("test", "setup", None, worker="second")
    results.record("test", "call", "PASSED", worker="second")
    for worker in worker_order:
        results.record("test", "teardown", None, worker=worker)

    assert results.outcomes() == {"test": status}


@pytest.mark.parametrize("worker_order", [("first", "second"), ("second", "first")])
def test_workers_cannot_borrow_completion_from_one_another(
    worker_order: tuple[str, str],
) -> None:
    results = ExecutionResults()
    results.collect("test")

    for worker in worker_order:
        results.record("test", "setup", None, worker=worker)
        results.record("test", "call", "PASSED", worker=worker)
        if worker == "first":
            results.record("test", "teardown", None, worker=worker)

    assert results.outcomes() == {"test": "SKIPPED"}


def test_a_worker_crash_after_a_discarded_attempt_preserves_the_error() -> None:
    results = ExecutionResults()
    results.collect("test")
    results.record("test", "call", "RERUN", worker="worker")

    results.record("test", "???", "ERROR", worker="worker")

    assert results.outcomes() == {"test": "ERROR"}


def test_repeated_execution_without_a_retry_preserves_an_earlier_failure() -> None:
    results = ExecutionResults()
    results.collect("test")
    results.record("test", "setup", None)
    results.record("test", "call", "FAILED")
    results.record("test", "teardown", None)

    results.record("test", "setup", None)
    results.record("test", "call", "PASSED")
    results.record("test", "teardown", None)

    assert results.outcomes() == {"test": "FAILED"}
