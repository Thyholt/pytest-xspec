"""Validate requirement inventories independently of their project-file source."""

import configparser
import sys
from importlib import import_module
from pathlib import Path
from typing import cast

import pytest

toml = import_module("tomllib" if sys.version_info >= (3, 11) else "tomli")


def load_requirements(config: pytest.Config) -> list[str]:
    try:
        inventories = _load_pyproject_inventory(config.rootpath / "pyproject.toml")
        inventories.update(_load_ini_inventory(config.rootpath / "pytest.ini"))
    except (OSError, ValueError, configparser.Error) as error:
        raise pytest.UsageError(f"Cannot read xspec requirements: {error}") from error

    if len(inventories) > 1:
        raise pytest.UsageError("Declare requirements in only one of pyproject.toml and pytest.ini")

    if inventories:
        source, requirements = next(iter(inventories.items()))
        return _validate_inventory(requirements, source)

    return _load_document(config.rootpath / "xspec.toml")


def _load_pyproject_inventory(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}

    with path.open("rb") as stream:
        section = toml.load(stream).get("tool", {}).get("xspec", {})

    if not isinstance(section, dict):
        raise pytest.UsageError("pyproject.toml: xspec must be a table")

    if "requirements" not in section:
        return {}

    return {path.name: section["requirements"]}


def _load_ini_inventory(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    if not parser.has_option("pytest", "xspec"):
        return {}

    requirements = [
        line.strip() for line in parser.get("pytest", "xspec").splitlines() if line.strip()
    ]
    return {path.name: requirements}


def _load_document(path: Path) -> list[str]:
    if not path.is_file():
        return []

    try:
        with path.open("rb") as stream:
            requirements = toml.load(stream).get("requirements")
    except (OSError, ValueError) as error:
        raise pytest.UsageError(
            f"Cannot read xspec requirements from {path.name}: {error}"
        ) from error

    return _validate_document(requirements, path.name)


def _validate_document(requirements: object, source: str) -> list[str]:
    if not isinstance(requirements, list):
        raise pytest.UsageError(f"{source}: requirements must be a list of tables")

    identifiers = [
        _validate_requirement(requirement, position, source)
        for position, requirement in enumerate(requirements, start=1)
    ]
    return _validate_inventory(identifiers, source)


def _validate_requirement(requirement: object, position: int, source: str) -> str:
    if not isinstance(requirement, dict):
        raise pytest.UsageError(f"{source}: requirement {position} must be a table")

    identifier = requirement.get("id")
    if not isinstance(identifier, str):
        raise pytest.UsageError(f"{source}: requirement {position} must have a string id")

    for field in ("description", "rationale"):
        if not isinstance(requirement.get(field, ""), str):
            raise pytest.UsageError(
                f"{source}: requirement {identifier!r}: {field} must be a string"
            )

    return identifier


def _validate_inventory(requirements: object, source: str) -> list[str]:
    if not isinstance(requirements, list) or any(
        not isinstance(requirement, str) for requirement in requirements
    ):
        raise pytest.UsageError(f"{source}: requirements must be a list of string IDs")

    seen: set[str] = set()
    for requirement in requirements:
        if requirement in seen:
            raise pytest.UsageError(f"{source}: duplicate requirements ID {requirement!r}")

        seen.add(requirement)

    # The element checks above establish the list's type, which ty cannot narrow.
    return cast(list[str], requirements)
