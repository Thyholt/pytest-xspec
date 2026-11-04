# pytest-xspec specification

pytest-xspec connects declared requirements to collected pytest tests and answers:
**Have all declared requirements been verified by successfully executed pytest tests?**

This living specification defines supported behavior and acceptance criteria. The
[architectural principles](architecture_principles.md) define responsibility boundaries.
The [README](../README.md) owns public usage and runnable examples, and
[CONTRIBUTING.md](../CONTRIBUTING.md) owns contributor setup and workflow.

## Supported runtime and naming

Python 3.10+ and pytest 8+ are supported. The distribution and repository are named
`pytest-xspec`, the import package is `pytest_xspec`, the `pytest11` entry point is
`xspec`, and the TOML configuration section is `[tool.xspec]`.
The installed plugin is discovered automatically and requires no runtime dependency beyond pytest.

## Requirement declarations

Requirement IDs are arbitrary, opaque strings, including dotted IDs, Unicode, spaces
and punctuation. Duplicate IDs and non-string IDs are rejected.

An explicit inventory can be declared in either configuration file:

```toml
# pyproject.toml
[tool.xspec]
requirements = ["REQ-001", "REQ-002"]
```

```ini
# pytest.ini
[pytest]
xspec =
    REQ-001
    REQ-002
```

When neither file declares an inventory, the plugin reads `xspec.toml` from pytest's
project root, regardless of the working directory:

```toml
[[requirements]]
id = "REQ-001"
description = "A short statement of the requirement."
rationale = "Why the requirement matters."

[[requirements]]
id = "REQ-002"
```

The document is an array of requirement tables. Each entry requires a string `id`.
Descriptions and rationales are optional strings and may be empty. Unknown fields
are ignored. Only IDs enter verification and reports. Equivalent TOML syntax,
including inline tables inside an array, is accepted.

### Source selection and validation

- Inventories declared in both configuration files produce an error naming both files.
  Sources are never merged. A configuration file without an inventory can coexist with
  an inventory in the other file.
- An explicit inventory takes precedence over `xspec.toml`, including an empty inventory.
  An unused document is neither opened nor validated. Invalid explicit configuration
  remains an error and does not trigger fallback.
- A configuration file without an inventory does not disable the document fallback.
- `requirements = []` declares zero requirements in `xspec.toml`. A selected document
  without `requirements`, including an empty file, is rejected. Invalid document syntax
  or contents produce a configuration error naming `xspec.toml` before tests run.
- With no inventory and no document, there are zero declared requirements.
- No inventory is read from `setup.cfg`, `tox.ini`, JSON, YAML or other files.
  Ordinary pytest may still use its own supported configuration files.

## Test associations

Each `@pytest.mark.xspec("REQ-001")` marker associates a test with one declared ID.
The plugin registers the marker, including for pytest's strict-marker validation.
Each marker requires exactly one positional string ID and no keyword arguments.
Unknown IDs and malformed markers are rejected even without a report option, with
zero declared requirements, and when filtering would exclude the collected test.

One requirement can have multiple tests. One test can support multiple requirements
through multiple markers, and appears under every associated requirement in results.
Repeated markers never count a test twice. Module and class markers apply to individual
tests, and each parameterized case retains its complete pytest node ID.

Associations are recorded before pytest deselection. Collected tests excluded by filters
retain their identities and receive `DESELECTED`. Tests outside the collected paths have
no invented identities or deselected records. A declared requirement without any associated
collected tests is `MISSING`, with an empty test list.

Full collection is required for authoritative verification coverage. Native `-k` and `-m`
filters retain known associations because they act after initial collection.

## Outcomes and requirement statuses

Setup, call and teardown reports produce one final outcome per test node ID.
Requirement statuses aggregate those test outcomes using this precedence, highest first:

`ERROR > FAILED > XPASSED > XFAILED > SKIPPED > DESELECTED > PASSED`

| Status | Definition |
| --- | --- |
| `ERROR` | An associated test encountered a setup or teardown error. |
| `FAILED` | An associated test failed. |
| `XPASSED` | An associated test unexpectedly passed, with strict or non-strict XFAIL. |
| `XFAILED` | An associated test failed as expected, including XFAIL raised by a fixture. |
| `SKIPPED` | An associated test was skipped or was collected but never executed. |
| `DESELECTED` | An associated collected test was excluded by filtering. |
| `PASSED` | Every associated test passed. |
| `MISSING` | No collected test references the requirement. |

`MISSING` applies only when there are no associated collected tests. Fixture skips are
`SKIPPED`. Expected failures raised during setup or teardown are `XFAILED`.
Assertion text containing `[XPASS(strict)]` does not turn an ordinary test failure into
an unexpected pass. Teardown errors take precedence over a passing or failing test call.

Collected tests that never execute retain their node IDs and receive `SKIPPED`, including
collect-only runs and tests left after an early stop. For example, one passed test and one
unexecuted test leave their shared requirement `SKIPPED`, even when an unmarked failure
caused the early stop.

A passing call without a completed teardown is not a completed passing test and remains
`SKIPPED` unless pytest reports a higher-priority outcome. An xdist crash report has no
ordinary execution phase and produces `ERROR` for its associated test.

### Retries

When the user installs `pytest-rerunfailures`, the final attempt determines the test's
outcome. A failed attempt followed by a successful retry produces `PASSED`, provided
the final attempt completes successfully, including teardown. Earlier attempts that
are retried do not contribute failures or errors to the final outcome.

Within the final attempt, the existing phase precedence applies. Exhausted retries
produce `FAILED` for a failing call or `ERROR` for a setup or teardown error. A passing
call followed by a teardown error produces `ERROR`. Skips and expected or unexpected
passes retain their existing meanings and do not verify requirements.

An interrupted retry cannot produce `PASSED`. A final attempt without completed
teardown remains `SKIPPED` unless it reports a higher-priority outcome. A worker crash
produces `ERROR`, and interruptions invalidate the overall verdict as described below.
Completion of an earlier attempt does not establish completion of a later attempt.

Retries retain one result per collected test node ID under each associated requirement,
preserving collection order. Requirement aggregation, coverage, terminal feedback and
strict mode use these final outcomes. `pytest-rerunfailures` remains optional and controls
when and how often tests retry. Pytest-xspec adds no retry configuration or attempt history.

With pytest-xdist, retries are resolved independently for each worker's execution of a
test before outcomes are combined. In `each` mode, one worker's successful retry cannot
erase another worker's exhausted failure, error or incomplete execution. Existing
controller-only reporting and crash rules apply.

Acceptance criteria for retry compatibility:

- A failed call, setup error or teardown error followed by a complete successful retry
  yields one `PASSED` test record and can verify its requirement.
- Exhausted call failures yield `FAILED`; exhausted setup or teardown errors yield `ERROR`.
- Interruption during a retry, including after its passing call but before teardown
  completes, leaves the test unverified and the overall verdict false.
- A successful retry cannot hide an unsuccessful distinct test associated with the same
  requirement, regardless of collection order.
- Serial and distributed runs preserve complete test identities and avoid duplicate
  records. Distributed `load` and `each` examples exercise retry completion and aggregation,
  including different final outcomes for the same test on different workers.
- JSON, terminal feedback and strict-mode exit behavior reflect the same final outcomes,
  while preserving existing pytest error exit codes.

## Verification verdict and coverage

A requirement is verified only when its status is `PASSED`. Unmarked test outcomes do
not contribute to requirement statuses. The overall verdict is true only when every
declared requirement is `PASSED`, there are no collection errors, and execution was not
interrupted by a worker crash, keyboard interrupt or internal error.

Coverage is `PASSED requirements / declared requirements × 100`. Zero declared
requirements produce zero passed, zero unverified and numeric coverage of 0.0%.
The verdict is successful in this case when there are no collection errors or interruptions.

Collection errors prevent successful verification even at 100% requirement coverage.
They are counted separately because an uncollected test cannot always be associated
with a requirement.

The verdict is independent of pytest's ordinary exit status. A failing unmarked test
can fail the pytest command even when every requirement is verified.

## Parallel execution

When the user installs pytest-xdist, a single pytest invocation can distribute tests to
workers using `load`, `loadscope`, `loadfile`, `loadgroup`, `worksteal` or `each`.
`--dist=no` keeps normal serial execution. Pytest-xdist remains optional.
The controller combines collected associations, deselection and execution reports. Each
test appears once under each associated requirement, retaining its full parameterized
node ID and collection order. Group suffixes added by `loadgroup` do not change those
identities or requirement selection. With `each`, outcomes from every worker aggregate
into one record per test using the existing outcome precedence. Strict-mode rules apply.

Collection associations reach the controller before scheduling begins, including tests
excluded by native filters or requirement selection. Tests left unexecuted after an early
stop or worker crash remain `SKIPPED`. Repeated reports of the same collection failure
count once per collected node ID. Collection failures and worker crashes invalidate the
overall verdict even if every associated test otherwise passed, or the inventory is empty.
Worker errors that abort collection or execution also prevent successful verification.

Only the controller writes the requested JSON file and terminal requirement summary.
Workers do not apply strict mode to their partial execution results. Existing pytest error
exit codes are preserved. Combining results from separate invocations is outside this contract.

## Command-line behavior

| Invocation | Behavior |
| --- | --- |
| `pytest` | Validate requirement configuration and markers without printing a requirement report. |
| `pytest --xspec-report` | Print requirement verification feedback. |
| `pytest --xspec-strict` | Print feedback and fail when the verification verdict is false. |
| `pytest --xspec-json=PATH` | Write structured verification results to the requested path. |
| `pytest --xspec-select=ID` | Select tests associated with the exact requirement ID. |
| `pytest -m xspec --xspec-strict` | Select requirement-marked tests and enforce verification. |

Strict mode evaluates the entire declared inventory, including requirements outside
the selected IDs. A false verdict changes pytest exit codes 0 (success) and 5 (no tests)
to 1 (test failure). Existing pytest failures and error exit codes remain intact.

### Requirement selection

Repeated `--xspec-select=ID` options select the union of exact IDs. Repeated IDs and
overlapping associations never execute a test twice. Commas, spaces and Unicode belong
to the ID, with no splitting or prefix matching. Unmarked tests are excluded.
Native collection paths, `-k` and `-m` intersect with requirement selection.

Unknown selected IDs produce a usage error (exit code 4) identifying the ID before
fixtures or tests execute, including a selection mixing known and unknown IDs.
Selecting declared requirements without matching tests produces an empty selection.
Without strict mode, an empty selection preserves pytest's no-tests exit code, 5.

Selection preserves all requirement associations and reports the full inventory.
Unselected requirements remain in the coverage denominator, including results shared
with selected requirements. Filtered tests follow the association and outcome rules above.

### Discovery

`--collect-only -q` lists the selected node IDs without running fixtures or test bodies.
The discovered selection matches execution under the same paths and filters, including
parameterized cases. Collected modules still import and need their normal dependencies.
Configuration and marker validation still apply, and collection errors prevent verification.
The outcome rules above keep discovered tests unverified.

## Structured results

JSON includes every declared requirement, its status, individual associated test node IDs
and outcomes, and the verification summary:

```json
{
  "requirements": {
    "REQ-001": {
      "status": "PASSED",
      "tests": [
        {"nodeid": "test_behavior.py::test_behavior", "outcome": "PASSED"}
      ]
    },
    "REQ-002": {"status": "MISSING", "tests": []}
  },
  "summary": {
    "requirements": 2,
    "passed": 1,
    "unverified": 1,
    "coverage": 50.0,
    "verified": false,
    "collection_errors": 0
  }
}
```

`summary.verified` contains the verification verdict defined above. Coverage is a numeric
percentage. Requirements retain inventory order, and test lists retain collection order.
Interrupted runs add `summary.interrupted: true` and always have `summary.verified: false`.
The `interrupted` key is absent from ordinary completed runs.

### Selection scope

When requirement selection is active, JSON adds one top-level `scope` object:

```json
{
  "selected_requirements": ["REQ-002", "REQ-001"],
  "collection_paths": ["test_behavior.py"],
  "keyword_expression": "shared",
  "marker_expression": "xspec",
  "collect_only": false
}
```

Selected IDs retain first-occurrence order with duplicates removed. Collection paths are
pytest's effective collection arguments, including explicit node IDs, in their original
order. With no explicit paths, pytest uses configured `testpaths`, or `["."]` when none
are configured. Absent `-k` and `-m` expressions are empty strings, and `collect_only`
is a boolean. Without requirement selection, the `scope` key is absent.

## Terminal feedback

The terminal report shows requirement IDs, statuses and associated test counts in inventory
order, followed by total requirements, passed, unverified and coverage rounded to one
decimal place. It includes `Collection errors: 1` for a single collection error.
Interrupted runs include `Execution interrupted`.

With colors enabled, the entire report is green for a successful verification verdict
and red otherwise, both in report and strict mode. This includes successful zero-requirement
verification and successful requirement verification with failing unmarked tests.
Pytest's color settings apply, including `--color=no`.

When requirement selection is active, terminal feedback adds the same scope as JSON:

```text
Selected requirements: ["REQ-002", "REQ-001"]
Collection paths: ["test_behavior.py"]
Keyword filter: shared
Marker filter: xspec
Discovery only: no
```

Arrays use JSON notation to preserve opaque IDs. Empty filter expressions display `(none)`,
and discovery displays `yes` or `no`. Without requirement selection, scope lines are absent.
Counts and coverage always describe the entire declared inventory.

## Executable acceptance criteria

The following tests verify this contract through real pytest runs in isolated projects.
Contributor commands are maintained in [CONTRIBUTING.md](../CONTRIBUTING.md#check-your-work).

| Acceptance tests | Criteria |
| --- | --- |
| [Configuration](../tests/acceptance/test_configuration.py) | Inventory precedence, conflicts, empty inventories and validation. |
| [Specification documents](../tests/acceptance/test_specification_document.py) | Fallback selection, document validation, zero requirements and ID-only output. |
| [Requirement associations](../tests/acceptance/test_requirements.py) | Opaque IDs, shared and inherited markers, parameterized cases, deduplication and marker validation. |
| [Statuses](../tests/acceptance/test_statuses.py) | Execution outcomes, phase errors, XFAIL behavior, unexecuted tests and aggregation precedence. |
| [Native selection](../tests/acceptance/test_selection.py) | Deselected identities, missing requirements and collection boundaries. |
| [Requirement selection and discovery](../tests/acceptance/test_requirement_selection.py) | Exact selection, native filters, shared results, scope and full-inventory verification. |
| [CLI](../tests/acceptance/test_cli.py) | Plain pytest, strict enforcement, unmarked outcomes and collection errors. |
| [Reporting](../tests/acceptance/test_reporting.py) | Terminal feedback, JSON records, requirement coverage and verdicts. |
| [Parallel execution](../tests/acceptance/test_parallel.py) | Real load and worksteal workers, exact identities, outcome precedence, filtering, early stops, crashes and controller-only reporting. |
| [Retries](../tests/acceptance/test_rerunfailures.py) | Final-attempt outcomes, interruption safety, shared-requirement failure preservation and independent worker results. |
