from rich import get_console
from rich.table import Table


__builtin_console = get_console()


__all__ = ("render_as_table", "Emoji")


class Emoji:
    """Emoji container."""
    CHECK_MARK = "\N{white heavy check mark}"
    CROSS = "\N{cross mark}"
    WARNING = "\N{warning sign}"
    INFO = "\N{information source}"


def render_as_table(headers: list[str], values: list[list]) -> Table:
    """Renders a generic table."""
    table = Table()

    if len(values[0]) != len(headers):
        raise ValueError("Headers did not match the length of values.")

    for header in headers:
        table.add_column(header, justify="center", overflow="crop")

    for row in values:
        table.add_row(*map(str, row))

    return table
