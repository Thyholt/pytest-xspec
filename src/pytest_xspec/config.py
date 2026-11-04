"""Load requirement declarations from the selected project-file source."""

import configparser
import sys
from importlib import import_module
from pathlib import Path

import pytest

from pytest_xspec.validation import validate_document, validate_inventory

toml = import_module("tomllib" if sys.version_info >= (3, 11) else "tomli")


def load_requirements(config: pytest.Config) -> list[str]:
    try:
        pyproject = _load_pyproject_inventory(config.rootpath / "pyproject.toml")
        ini = _load_ini_inventory(config.rootpath / "pytest.ini")
    except (OSError, ValueError, configparser.Error) as error:
        raise pytest.UsageError(f"Cannot read xspec requirements: {error}") from error

    if pyproject is not None and ini is not None:
        raise pytest.UsageError("Declare requirements in only one of pyproject.toml and pytest.ini")

    inventory = pyproject or ini
    if inventory is not None:
        source, requirements = inventory
        return validate_inventory(source, requirements)

    return _load_document(config.rootpath / "xspec.toml")


def _load_pyproject_inventory(path: Path) -> tuple[str, object] | None:
    if not path.is_file():
        return None

    with path.open("rb") as stream:
        section = toml.load(stream).get("tool", {}).get("xspec", {})

    if not isinstance(section, dict):
        raise pytest.UsageError("pyproject.toml: xspec must be a table")

    if "requirements" not in section:
        return None

    return path.name, section["requirements"]


def _load_ini_inventory(path: Path) -> tuple[str, object] | None:
    if not path.is_file():
        return None

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    if not parser.has_option("pytest", "xspec"):
        return None

    requirements = [
        line.strip() for line in parser.get("pytest", "xspec").splitlines() if line.strip()
    ]
    return path.name, requirements


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

    return validate_document(path.name, requirements)
