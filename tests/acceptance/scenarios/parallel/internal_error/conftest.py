from collections.abc import Generator

import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtestloop(session: pytest.Session) -> Generator[None, object, object]:
    result = yield
    if not hasattr(session.config, "workerinput"):
        raise RuntimeError("Intentional plugin error after execution")

    return result
