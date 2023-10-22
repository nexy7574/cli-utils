import logging
import re

__all__ = (
    "CAPACITY_REGEX",
    "CAPACITY_VALUES",
    "CAPACITY_REGEX_RAW",
    "convert_soft_data_value_to_hard_data_value",
    "bytes_to_human",
    "humanise_time",
)

import typing

CAPACITY_VALUES = {
    "b": 1,
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
    "t": 1024**4,
    # Who the hell has a terabyte or more of ram?
}
CAPACITY_REGEX_RAW = r"(\d+)\s*([bkmgtBKMGT])?b*"
CAPACITY_REGEX = re.compile(CAPACITY_REGEX_RAW, re.IGNORECASE)


def convert_soft_data_value_to_hard_data_value(value: str, return_in: str = "b") -> float:
    """
    Converts a human-readable value (e.g. 1G) to a hard value (e.g. 1073741824)

    :param value: The human string
    :param return_in: The unit to return in (e.g. (b)ytes)
    :return:
    """
    INVALID_ERR = ValueError(
        "Invalid value. Make sure you specify a value in the format of `NNN C`, with C being"
        " one of the following: b, kb, mb, gb, tb, and NNN being the number. E.g: "
        "`1024M` == `1G`"
    )
    _match = CAPACITY_REGEX.match(value)
    if _match is None:
        raise INVALID_ERR

    logging.getLogger(__name__).debug(f"Match: {_match}")
    logging.getLogger(__name__).debug(f"Groups: {_match.groups()}")

    try:
        _value, _unit = _match.groups()
        _unit = _unit or "b"
    except ValueError:
        # No unit specified, default to bytes
        _value = _match.group()
        _unit = "b"
    _value = int(_value)
    _unit = _unit.lower()
    value_in_bytes = _value * CAPACITY_VALUES[_unit]
    return value_in_bytes / CAPACITY_VALUES[return_in.lower()]


def bytes_to_human(n: int) -> str:
    """Converts bytes into a human value (such as 1GB)"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024.0:
            return f"{n:3.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def humanise_time(seconds: float, stop_at: typing.Literal["minutes", "hours", "days", "weeks", "years"] = None) -> str:
    """
    Converts a given time in seconds into a human-readable format (i.e. 1 hour, 1 hour & 30 minutes, etc.).

    :param seconds: The number of seconds to start with.
    :param stop_at: The unit to stop at. E.g. if `minutes` is specified, the function will stop at minutes.
    :return: The humanised value
    """
    units = {
        "years": 60 * 60 * 24 * 365,
        "weeks": 60 * 60 * 24 * 7,
        "days": 60 * 60 * 24,
        "hours": 60 * 60,
        "minutes": 60,
        "seconds": 1,
    }
    result = []
    for name, amount in units.items():
        value = int(seconds // amount)
        is_plural = value > 1
        key = name[:-1] if not is_plural else name
        if value:
            seconds -= value * amount
            result.append(f"{value} {key}")
        if stop_at and name == stop_at:
            break
    if len(result) <= 2:
        return " and ".join(result)
    return ", ".join(result[:-1]) + f", and {result[-1]}"
