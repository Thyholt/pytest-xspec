"""Combine saved reports without collecting or executing tests."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from pytest_xspec.combination import combine_reports, combined_test_counts
from pytest_xspec.report_input import validate_report
from pytest_xspec.reporting import (
    CombinedReport,
    Report,
    requirement_lines,
    summary_lines,
    write_json,
)


class _Arguments(argparse.Namespace):
    inputs: list[Path]
    output: Path
    xspec_strict: bool


def _read_report(path: Path) -> Report:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
        return validate_report(value)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Cannot read xspec JSON report {path}: {error}") from error


def _check_output(inputs: Sequence[Path], output: Path) -> None:
    if not output.exists():
        return

    for path in inputs:
        if output.samefile(path):
            raise ValueError(f"Output {output} must not overwrite input {path}")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pytest_xspec")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("combine", help="Combine labeled single-run JSON reports")
    command.add_argument("inputs", nargs="+", type=Path, metavar="REPORT")
    command.add_argument("--output", type=Path, required=True, metavar="PATH")
    command.add_argument(
        "--xspec-strict", action="store_true", help="Fail on unverified requirements"
    )
    return parser


def _combine_files(inputs: Sequence[Path], output: Path) -> CombinedReport:
    runs = [_read_report(path) for path in inputs]
    _check_output(inputs, output)
    try:
        report = combine_reports(runs)
    except ValueError as error:
        sources = ", ".join(str(path) for path in inputs)
        raise ValueError(f"Cannot combine {sources}: {error}") from error

    write_json(report, output)
    return report


def _print_report(report: CombinedReport) -> None:
    counts = combined_test_counts(report)
    rows = [
        (identifier, result["status"], counts[identifier])
        for identifier, result in report["requirements"].items()
    ]
    print("==================== xspec ====================")
    for line in requirement_lines(rows):
        print(line)

    for line in summary_lines(report["summary"]):
        print(line)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    arguments = _Arguments()
    parser.parse_args(argv, namespace=arguments)

    try:
        report = _combine_files(arguments.inputs, arguments.output)
    except (OSError, ValueError, pytest.UsageError) as error:
        parser.error(str(error))

    _print_report(report)
    if report["summary"]["verified"]:
        return 0

    return int(arguments.xspec_strict)


if __name__ == "__main__":
    raise SystemExit(main())
