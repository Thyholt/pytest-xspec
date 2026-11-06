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


def test_encoding_failure_preserves_an_existing_json_report(tmp_path: Path) -> None:
    report = build_report({}, {}, ExecutionStatus(), metadata={"run_id": "\ud800"})
    path = tmp_path / "report.json"
    path.write_text("previous report", encoding="utf-8")

    with pytest.raises(pytest.UsageError) as error:
        write_json(report, path)

    assert str(path) in str(error.value)
    assert path.read_text(encoding="utf-8") == "previous report"
