def calculateBar(cur: int, total: int = 100, fill: str = "#", empty: str = " ", *, disable_safety: bool = False) -> str:
    """
    Generates a progress bar, with fills included!

    :param cur: The current value.
    :param total: The total value (100%)
    :param fill: The fill character to use. Defaults to #
    :param empty: The character to use for empty places. Defaults to space.
    :param disable_safety: Whether to disable simple checks to ensure this function doesn't break.
    :return: A formatted progress bar.
    """
    if total % 100 and not disable_safety:
        raise ValueError("Total must be a value of 100.")
    if cur > total and not disable_safety:
        raise ValueError("Current value is too large.")
    _fill = int((cur / total) * 100)
    _pct = _fill * total
    text = "[{}] {}% ({}/{})".format(
        (fill * _fill + empty * (100 - _fill))[:100], str(round((cur / total) * 100)), cur, total
    )
    return text
