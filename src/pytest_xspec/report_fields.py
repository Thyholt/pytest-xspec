"""Validate JSON field types and scalar constraints in saved reports."""

import math
from typing import cast


class InvalidReport(ValueError):
    """The supplied report cannot be used as verification evidence."""


def object_value(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise InvalidReport(f"{field} must be an object with string keys")

    return cast(dict[str, object], value)


def string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise InvalidReport(f"{field} must be a string")

    return value


def array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise InvalidReport(f"{field} must be an array")

    return cast(list[object], value)


def nonnegative_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidReport(f"{field} must be a nonnegative integer")

    if value < 0:
        raise InvalidReport(f"{field} must be a nonnegative integer")

    return value


def boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidReport(f"{field} must be a boolean")

    return value


def percentage(value: object, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidReport(f"{field} must be a finite percentage between 0 and 100")

    if not 0 <= value <= 100 or not math.isfinite(value):
        raise InvalidReport(f"{field} must be a finite percentage between 0 and 100")


def string_list(value: object, field: str) -> list[str]:
    return [string(item, field) for item in array(value, field)]
