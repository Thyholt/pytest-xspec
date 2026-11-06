"""Invalid report inputs produce diagnostics without destroying reports."""

import json

import pytest

from tests.acceptance.combine_support import combine, record_run
from tests.acceptance.scenarios.combine_reports import complementary
from tests.acceptance.types import UserProject


@pytest.mark.parametrize(
    ("contents", "diagnostic"),
    [
        pytest.param("{", "*JSON*", id="malformed-json"),
        pytest.param("[]", "*object*", id="wrong-document-type"),
        pytest.param(
            '{"run_id": "run-a", "summary": {"requirements": 0, "passed": 0, '
            '"unverified": 0, "coverage": 0.0, "verified": true, "collection_errors": 0}}',
            "*requirements*",
            id="missing-requirements",
        ),
    ],
)
def test_invalid_report_files_are_identified_without_creating_output(
    pytester: pytest.Pytester, contents: str, diagnostic: str
) -> None:
    source = pytester.makefile(".json", invalid=contents)

    result = combine(pytester, str(source), "--output=combined.json")

    assert result.ret == 2
    assert "invalid.json" in result.stderr.str()
    result.stderr.fnmatch_lines([diagnostic])
    assert source.read_text(encoding="utf-8") == contents
    assert not (pytester.path / "combined.json").exists()


def test_invalid_input_preserves_an_existing_output_report(pytester: pytest.Pytester) -> None:
    pytester.makefile(".json", invalid="{")
    output = pytester.path / "combined.json"
    output.write_text("previous report", encoding="utf-8")

    result = combine(pytester, "invalid.json", "--output=combined.json")

    assert result.ret == 2
    assert "invalid.json" in result.stderr.str()
    assert output.read_text(encoding="utf-8") == "previous report"


def test_missing_input_is_named_in_the_diagnostic(pytester: pytest.Pytester) -> None:
    result = combine(pytester, "missing.json", "--output=combined.json")

    assert result.ret == 2
    assert "missing.json" in result.stderr.str()
    assert not (pytester.path / "combined.json").exists()


def test_unlabeled_reports_explain_how_to_supply_run_identity(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    source_run = project.runpytest_subprocess("--xspec-json=unlabeled.json")
    assert source_run.ret == pytest.ExitCode.OK
    source = project.path / "unlabeled.json"
    original = source.read_bytes()

    result = combine(project, "unlabeled.json", "--output=combined.json")

    assert result.ret == 2
    assert "unlabeled.json" in result.stderr.str()
    assert "--xspec-run-id" in result.stderr.str()
    assert source.read_bytes() == original
    assert not (project.path / "combined.json").exists()


@pytest.mark.parametrize("second_input", ["source.json", "copy.json"])
def test_repeated_run_ids_are_rejected_even_in_different_files(
    user_project: UserProject, second_input: str
) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "source")
    original = (project.path / "source.json").read_bytes()
    (project.path / "copy.json").write_bytes(original)

    result = combine(project, "source.json", second_input, "--output=combined.json")

    assert result.ret == 2
    diagnostic = result.stderr.str().lower()
    assert "source" in diagnostic
    assert any(word in diagnostic for word in ("duplicate", "repeat", "unique"))
    assert not (project.path / "combined.json").exists()
    assert (project.path / "source.json").read_bytes() == original
    assert (project.path / "copy.json").read_bytes() == original


def test_different_inventories_are_rejected(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "run-a")
    user_project(["REQ-001", "REQ-002"], complementary)
    record_run(project, "run-b")
    (project.path / "combined.json").write_text("previous report", encoding="utf-8")

    result = combine(project, "run-a.json", "run-b.json", "--output=combined.json")

    assert result.ret == 2
    assert "REQ-002" in result.stderr.str()
    diagnostic = result.stderr.str().lower()
    assert any(name in diagnostic for name in ("run-a.json", "run-b.json"))
    assert (project.path / "combined.json").read_text(encoding="utf-8") == "previous report"


@pytest.mark.parametrize("outcome", ["UNKNOWN", "MISSING"])
def test_invalid_test_outcomes_are_rejected(user_project: UserProject, outcome: str) -> None:
    project = user_project(["REQ-001"], complementary)
    report = record_run(project, "source")
    report["requirements"]["REQ-001"]["tests"][0]["outcome"] = outcome
    project.makefile(".json", invalid=json.dumps(report))

    result = combine(project, "invalid.json", "--output=combined.json")

    assert result.ret == 2
    assert "invalid.json" in result.stderr.str()
    assert outcome in result.stderr.str()
    assert not (project.path / "combined.json").exists()


def test_inconsistent_summary_is_rejected(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    report = record_run(project, "source")
    report["summary"]["passed"] = 0
    project.makefile(".json", invalid=json.dumps(report))

    result = combine(project, "invalid.json", "--output=combined.json")

    assert result.ret == 2
    assert "invalid.json" in result.stderr.str()
    assert "passed" in result.stderr.str()
    assert not (project.path / "combined.json").exists()


def test_duplicate_test_identities_within_a_run_are_rejected(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    report = record_run(project, "source")
    report["requirements"]["REQ-001"]["tests"].append(
        {"nodeid": "test_behavior.py::test_first_behavior", "outcome": "PASSED"}
    )
    project.makefile(".json", invalid=json.dumps(report))

    result = combine(project, "invalid.json", "--output=combined.json")

    assert result.ret == 2
    assert "invalid.json" in result.stderr.str()
    assert "test_behavior.py::test_first_behavior" in result.stderr.str()
    assert not (project.path / "combined.json").exists()


@pytest.mark.parametrize("output", ["source.json", "./source.json"])
def test_output_cannot_overwrite_an_input(user_project: UserProject, output: str) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "source")
    original = (project.path / "source.json").read_bytes()

    result = combine(project, "source.json", f"--output={output}")

    assert result.ret == 2
    assert "source.json" in result.stderr.str()
    assert (project.path / "source.json").read_bytes() == original


def test_output_write_failure_names_the_destination(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "source")
    original = (project.path / "source.json").read_bytes()
    (project.path / "destination.json").mkdir()

    result = combine(project, "source.json", "--output=destination.json")

    assert result.ret == 2
    assert "destination.json" in result.stderr.str()
    assert (project.path / "destination.json").is_dir()
    assert (project.path / "source.json").read_bytes() == original


def test_help_does_not_require_input_reports(pytester: pytest.Pytester) -> None:
    result = combine(pytester, "--help")

    assert result.ret == 0
    result.stdout.fnmatch_lines(["*--output*", "*--xspec-strict*"])


def test_missing_output_argument_is_explained(pytester: pytest.Pytester) -> None:
    result = combine(pytester, "source.json")

    assert result.ret == 2
    result.stderr.fnmatch_lines(["*usage:*", "*--output*"])


def test_missing_input_arguments_are_explained(pytester: pytest.Pytester) -> None:
    result = combine(pytester, "--output=combined.json")

    assert result.ret == 2
    assert "usage:" in result.stderr.str().lower()
    assert "required" in result.stderr.str().lower()
    assert not (pytester.path / "combined.json").exists()
