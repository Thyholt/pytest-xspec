"""Report-writing failures produce actionable usage errors."""

from pathlib import Path

import pytest

from pytest_xspec.reporting import ExecutionStatus, build_report, write_json


def test_a_directory_cannot_be_used_as_the_json_report_file(tmp_path: Path) -> None:
    report = build_report({}, {}, ExecutionStatus())
    path = tmp_path / "report.json"
    path.mkdir()

    with pytest.raises(pytest.UsageError) as error:
        write_json(report, path)

    assert f"Cannot write xspec JSON report {path}:" in str(error.value)
