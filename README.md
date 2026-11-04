# pytest-xspec

[![PyPI version][pypi-version-badge]][pypi]
[![Python versions][python-versions-badge]][pypi]
[![Tests][tests-badge]][tests]
[![Code coverage][codecov-badge]][codecov]
[![CodeScene Average Code Health][codescene-average-code-health-badge]][codescene]
[![CodeScene Hotspot Code Health][codescene-hotspot-code-health-badge]][codescene]

**Executable specifications and verification with pytest.**

Link specifications to your existing pytest tests, organize your test suite your way, and see
which specifications your test suite verifies. Detect missing tests and enforce verification in CI.

## Why pytest-xspec?

As software engineers, we like code. Ask us what the software does, and we might say,
"Just read the code." But stakeholders need a shared understanding of what the software
should do. We turn to acceptance tests to make those expectations precise, using examples
in the language of the business.

For many of us, making a whole test suite read as a clear specification is costly.
It takes time and practice, and the work continues as the codebase grows. Related behavior
spreads across files, implementation checks sit beside acceptance tests, and the overall
requirements become harder to see.

`pytest-xspec` connects a readable overview of your requirements to the tests that verify them.
Keep specifications in a document your team can discuss, put tests where they make sense,
and link them with IDs. The report shows which requirements are verified, which remain
unverified and which have no tests. When business asks what is covered, you have an answer
they can read.

## Usage

Install `pytest-xspec` into your pytest environment. The plugin is discovered
automatically. Python 3.10+ and pytest 8+ are supported.

```sh
pip install pytest-xspec
```

### Write your specifications

Create `xspec.toml` in pytest's project root, usually the top-level project directory.
Keep each specification, its description and the reason it matters together in one document.

```toml
[[requirements]]
id = "REQ-001"
description = "Adding two integers returns their sum."
rationale = "Calculations must give predictable results."

[[requirements]]
id = "REQ-002"
description = "Adding zero leaves the value unchanged."
```

Use one `[[requirements]]` entry per specification. Each entry needs an `id`.
The `description` states the requirement, and the `rationale` explains why it matters.
Both are optional and can be empty strings. This text stays in the document,
while tests and reports refer only to the IDs.

See the [specification document example][specification-document] for a complete runnable project.

For specifications maintained in other documents or tables,
[declare just their IDs](#use-an-existing-specification).

### Mark tests

Associate tests with specifications, using one marker per specification.

```python
import pytest


@pytest.mark.xspec("REQ-001")
@pytest.mark.xspec("REQ-002")
def test_adding_zero_preserves_the_value() -> None:
    assert 2 + 0 == 2
```

### Run pytest

Plain `pytest` checks specification configuration and markers without printing
a specification report. Add `--xspec-report` to see the report, or `--xspec-strict`
to also fail the run when a specification is unverified.

```sh
pytest --xspec-report             # Print the verification report
pytest --xspec-json=report.json   # Export statuses and individual test outcomes
pytest --xspec-strict             # Report and fail on unverified specifications
pytest -m xspec --xspec-strict    # Run only marked specification tests
```

The report is green when all specifications are verified and red when verification fails.
The first report shows the example above; the second shows a specification without tests.

![Terminal reports showing verified specifications in green and a missing specification in red.](https://raw.githubusercontent.com/Thyholt/pytest-xspec/master/docs/images/terminal-reports.png)

### Select specifications

Use `--xspec-select=ID` to run tests linked to one specification. Repeat the option
to select several specifications. A test linked to several selected IDs runs once.

```sh
pytest --xspec-select=REQ-001
pytest --xspec-select=REQ-001 --xspec-select=REQ-002
```

Each option takes one exact ID, including any spaces or commas. Quote IDs when the
shell requires it. Unmarked tests are excluded. Collection paths, `-k` and `-m`
further narrow the selection. An undeclared selected ID is a usage error.
Selecting only IDs without matching tests produces an empty selection.

Strict mode still evaluates every declared specification. Selecting one ID keeps
other specifications in the report and the coverage calculation. Excluded tests
remain `DESELECTED`, and tests shared with other specifications keep all their links.
With selection active, terminal reports and the JSON `scope` field show selected
IDs, collection paths, `-k`, `-m` and whether the run only discovers tests.

### Discover tests without running them

Add `--collect-only -q` to list the selected test IDs, including parameterized cases.

```sh
pytest --xspec-select=REQ-001 --collect-only -q
```

Discovery runs neither fixtures nor test bodies. It still imports collected modules,
which need their normal dependencies. Reports mark discovered tests as `SKIPPED`,
so discovery does not verify their specifications. Strict mode fails when any
specification remains unverified. Without strict mode, an empty selection keeps
pytest's no-tests exit code, 5.

### Read specification statuses

Reports label specifications as requirements.

A specification is verified when every test marked with its ID passes. One passing
test is not enough if another test for the same specification fails or skips.

When those tests have different results, the report uses the first matching
status in this table, reading from top to bottom.

| Status | Meaning |
| --- | --- |
| `ERROR` | A test's setup or cleanup failed. |
| `FAILED` | A test failed. |
| `XPASSED` | A test marked as an expected failure passed instead. |
| `XFAILED` | A test failed as expected. |
| `SKIPPED` | A test was skipped or never ran. |
| `DESELECTED` | A test was excluded by a filter such as `-k` or `-m`. |
| `PASSED` | Every test for the specification passed. |

For example, if one test passes and another skips, the specification is `SKIPPED`
and remains unverified. If one test fails and another skips, it is `FAILED`.

### Missing and unfinished tests

Pytest first finds tests, then runs them. If it finds no marked tests for a
declared specification, that specification is `MISSING`. Tests that were found but
never ran are `SKIPPED`, including runs that only find tests or stop early.
If pytest encounters an error while finding tests, such as a broken import,
the verification check cannot succeed.

### Tests without markers

Tests without a specification marker do not change specification statuses. They
can still make pytest fail. In [the duck example][acceptance-only],
the specification passes, but the unmarked cheese test fails the pytest run.

### Check coverage

Coverage is the percentage of declared specifications that are verified. With
no declared specifications and no errors while finding tests, the verification
check succeeds and coverage is 0.0%.

Errors while finding tests make verification fail, even at 100% coverage. The report follows
pytest's color settings, so `--color=no` disables color.

For a complete report, let pytest find the whole test suite. With `-k` or `-m`,
the plugin still knows about the tests excluded by the filter and reports marked
ones as `DESELECTED`. If you run only one folder, it cannot see tests in other
folders.

## Use an existing specification

If you maintain specifications elsewhere, declare their IDs in `pyproject.toml`
or `pytest.ini`. Your original document remains the source for descriptions and context.
The markers, commands and reports work the same way with either configuration format.

In `pyproject.toml`, use a list of IDs:

```toml
[tool.xspec]
requirements = ["REQ-001", "REQ-002"]
```

In `pytest.ini`, use one ID per line:

```ini
[pytest]
xspec =
    REQ-001
    REQ-002
```

### How the source is chosen

An ID list in either configuration file takes precedence over `xspec.toml`.
Declaring IDs in both `pyproject.toml` and `pytest.ini` is an error.
Specifications from different sources are never merged.

When neither configuration file declares IDs, `pytest-xspec` reads `xspec.toml`
from the project root. Those configuration files can still contain other settings.
An explicitly empty ID list also takes precedence, so it declares zero specifications
even when `xspec.toml` contains entries. An unused `xspec.toml` is not read or validated.

### Empty specifications and validation

IDs are strings and are used exactly as written. Duplicate IDs and markers referring
to undeclared IDs are rejected. In `xspec.toml`, supplied descriptions and rationales
must also be strings. Additional fields are ignored.

To declare zero specifications in `xspec.toml`, write `requirements = []`.
A document without `requirements`, including an empty file, is a configuration error.
Invalid documents produce an error before tests run.
If no source exists, there are zero declared specifications.

## Run tests in parallel

Install `pytest-xdist` alongside `pytest-xspec` to distribute tests across workers:

```sh
pip install pytest-xdist
pytest -n 2 --xspec-strict --xspec-json=report.json
```

Parallel runs produce one combined report and use the same verification rules as serial
runs. Every test associated with a specification must pass. If the same test runs on
multiple workers, a pass on one worker cannot cancel a failure or skip on another.

A worker crash or interrupted run prevents overall verification, even if all reported
tests passed. `pytest-xdist` is optional and is only needed for parallel execution.

## Retry failed tests

Install `pytest-rerunfailures` to retry failed tests:

```sh
pip install 'pytest-rerunfailures>=16.7'
pytest --reruns=1 --xspec-strict
```

The final attempt determines the test outcome. A successful retry can verify its
specifications only after teardown completes. An interrupted retry stays unverified,
and failures from other associated tests or workers still contribute to the result.
Reports retain one record per test, without an attempt history.
`pytest-rerunfailures` controls the retry policy and remains an optional dependency.

## Runnable examples

Start with [the pizza][pizza], then try the other
examples to see what makes a specification pass or remain unverified.

Run the commands below from the repository root. Dependencies are installed automatically.

| Example | With `--xspec-strict` | Exit code |
| --- | --- | --- |
| [Quickstart][quickstart] - Two slices of pizza | `PASSED`, 100% coverage | 0 |
| [Specification document][specification-document] - Addition rules in TOML | `PASSED`, 100% coverage | 0 |
| [Missing specification][missing-requirement] - A lost sock | `MISSING`, 50% coverage | 1 |
| [Partial verification][partial-verification] - Cat skips a meeting | `SKIPPED`, 0% coverage | 1 |
| [Acceptance only][acceptance-only] - Duck versus cheese | `PASSED` with `-m xspec` | 0 |

### Run an example

Run the `Quickstart` example, then replace `quickstart` with another example folder.

```sh
uv run --locked pytest examples/quickstart --xspec-strict
```

For `specification_document`, the requirements live in
[xspec.toml](examples/specification_document/xspec.toml).
Its `pyproject.toml` only sets test discovery, leaving the document as the requirement source.

For `acceptance_only`, add `-m xspec` to run only the marked test.
Without that filter, the unmarked test makes pytest fail.
Add `--reruns=1` to retry that failure once. It still fails, while the marked
specification remains verified.

### Select and discover example tests

Use the same example command with `--xspec-select=REQ-001` to select the pizza test.
Add `--collect-only -q` to discover it without running it:

```sh
uv run --locked pytest examples/quickstart --xspec-select=REQ-001 --collect-only -q
```

For `missing_requirement`, repeat `--xspec-select=REQ-002` to select both declared IDs.
Only the existing sock test runs. With `--xspec-strict`, the missing sock still
makes verification fail.

### Inspect the JSON report

Export the example results to see the specification status and individual test outcomes.

```sh
uv run --locked pytest examples/quickstart --xspec-json=examples/quickstart/report.json
```

Open [examples/quickstart/report.json][report] after running the command.

### Verify all examples

Check that every example behaves as described.

```sh
uv run --locked pytest examples/test_examples.py -n 0
```

All six checks should pass, including checks for the examples that deliberately
fail. The examples are also verified in CI.

## Development disclosure

This package is developed by AI agents under human direction.
See [AI_DISCLOSURE.md](AI_DISCLOSURE.md) for details on authorship, human review
and repository workflows.

This README was written by AI.

## Contributing

Bring difficult, realistic examples of executable specification or feedback problems.
See [CONTRIBUTING.md][contributing] for proposing changes, setup, tests and pull requests.

[acceptance-only]: https://github.com/Thyholt/pytest-xspec/tree/master/examples/acceptance_only
[pizza]: https://github.com/Thyholt/pytest-xspec/blob/master/examples/quickstart/test_behavior.py
[quickstart]: https://github.com/Thyholt/pytest-xspec/tree/master/examples/quickstart
[specification-document]: https://github.com/Thyholt/pytest-xspec/tree/master/examples/specification_document
[missing-requirement]: https://github.com/Thyholt/pytest-xspec/tree/master/examples/missing_requirement
[partial-verification]: https://github.com/Thyholt/pytest-xspec/tree/master/examples/partial_verification
[report]: https://github.com/Thyholt/pytest-xspec/blob/master/examples/quickstart/report.json
[contributing]: https://github.com/Thyholt/pytest-xspec/blob/master/CONTRIBUTING.md

[pypi]: https://pypi.org/project/pytest-xspec/
[pypi-version-badge]: https://img.shields.io/pypi/v/pytest-xspec.svg
[python-versions-badge]: https://img.shields.io/badge/python-3.10%2B-blue
[tests]: https://github.com/Thyholt/pytest-xspec/actions/workflows/check.yml
[tests-badge]: https://img.shields.io/github/actions/workflow/status/Thyholt/pytest-xspec/check.yml?branch=master&label=tests

[codecov]: https://app.codecov.io/gh/Thyholt/pytest-xspec
[codecov-badge]: https://codecov.io/gh/Thyholt/pytest-xspec/branch/master/graph/badge.svg
[codescene]: https://codescene.io/projects/87264
[codescene-average-code-health-badge]: https://codescene.io/projects/87264/status-badges/average-code-health
[codescene-hotspot-code-health-badge]: https://codescene.io/projects/87264/status-badges/hotspot-code-health
