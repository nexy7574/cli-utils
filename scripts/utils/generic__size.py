import re


__all__ = (
    "CAPACITY_REGEX",
    "CAPACITY_VALUES",
    "CAPACITY_REGEX_RAW",
    "convert_soft_data_value_to_hard_data_value",
)

CAPACITY_VALUES = {
    "b": 1,
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
    "t": 1024**4,
    # Who the hell has a terabyte or more of ram?
}
CAPACITY_REGEX_RAW = r"(\d+)\s*([bkmgtBKMGT])*b*"
CAPACITY_REGEX = re.compile(CAPACITY_REGEX_RAW, re.IGNORECASE)

def convert_soft_data_value_to_hard_data_value(value: str, return_in: str = "b") -> float:
    INVALID_ERR = ValueError(
        "Invalid value. Make sure you specify a value in the format of `NNN C`, with C being"
        " one of the following: b, kb, mb, gb, tb, and NNN being the number. E.g: "
        "`1024M` == `1G`"
    )
    _match = CAPACITY_REGEX.match(value)
    if _match is None:
        raise INVALID_ERR

    try:
        _value, _unit = _match.groups()
    except ValueError:
        # No unit specified, default to bytes
        _value = _match.group()
        _unit = "b"
    _value = int(_value)
    _unit = _unit.lower()
    value_in_bytes = _value * CAPACITY_VALUES[_unit]
    return value_in_bytes / CAPACITY_VALUES[return_in.lower()]
