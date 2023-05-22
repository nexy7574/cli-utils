import time

import click
import os
from pathlib import Path
from typing import Literal
from rich import get_console
from rich.progress import (
    Progress,
    SpinnerColumn,
    FileSizeColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from .utils.generic__size import convert_soft_data_value_to_hard_data_value


@click.command()
@click.option("--size", "-S", help="Size of the file to generate. Must end in B, KB, MB, GB, or TB.", required=True)
@click.option("--block-size", "--bs", "-B", "-S", default="0", help="Block size to use for writing. 0 indicates auto.")
@click.option(
    "--source", "--src", help="How to generate the file.", type=click.Choice(["urandom", "zero"]), default="zero"
)
@click.option("--sync", is_flag=True, help="Clears buffer on each block write.")
@click.option("--verbose", "-V", is_flag=True, help="Prints more information.")
@click.argument("output", type=click.Path(dir_okay=False))
def main(size: str, output: str, block_size: int, source: Literal["urandom", "zero"], sync: bool, verbose: bool):
    """Generates a file of x size."""
    console = get_console()

    try:
        if verbose:
            console.log(f"[i dim]Converting {size!r} to bytes...[/i dim]")
        size_in_bytes = convert_soft_data_value_to_hard_data_value(size, "b")
    except ValueError as e:
        print(e)
        return

    if block_size == 0:
        loc = Path(output)
        if loc.exists():
            block_size = loc.stat().st_blksize
        else:
            block_size = loc.parent.stat().st_blksize
        console.log(f"[i dim]Using block size of {block_size:,} bytes[/i dim]")

    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBar"))
    columns.insert(-1, FileSizeColumn())
    columns.insert(-1, TotalFileSizeColumn())
    columns.insert(-1, TransferSpeedColumn())
    columns.insert(-1, TimeElapsedColumn())
    columns[-1] = TimeRemainingColumn(True)

    with Progress(*columns, console=console, expand=True) as progress:
        task = progress.add_task("Write data", total=size_in_bytes)
        bytes_written = 0
        with click.open_file(output, "wb") as f:
            start = time.time_ns()
            while bytes_written < size_in_bytes:
                next_block = block_size
                if bytes_written + block_size > size_in_bytes:
                    next_block = size_in_bytes - bytes_written
                    if verbose:
                        console.log(
                            f"[i dim]Approaching last block. Block size has been adjusted to "
                            f"{next_block:,} bytes[/i dim]"
                        )

                if source == "urandom":
                    data = os.urandom(next_block)
                else:
                    data = b"\x00" * next_block

                f.write(data)
                if sync:
                    if verbose:
                        task2 = progress.add_task("Flushing block...")
                    f.flush()
                    if verbose:
                        progress.remove_task(task2)
                bytes_written += len(data)
                progress.update(task, advance=len(data))
                if verbose and bytes_written % (block_size * 100) == 0:
                    console.log(f"[i dim]Wrote {bytes_written:,} bytes (last block was {next_block:,} bytes)[/i dim]")
            end = time.time_ns()

    time_in_seconds = (end - start) / 1_000_000_000
    seconds, minutes = divmod(time_in_seconds, 60)
    fmt = []
    if time_in_seconds > 60:
        fmt.append(f"{seconds} seconds")
        fmt.append(f"{minutes} minutes")
    else:
        fmt.append(f"{time_in_seconds} seconds")
    if minutes > 60:
        minutes, hours = divmod(minutes, 60)
        if fmt[-1].endswith("minutes"):
            fmt.pop()
            fmt.append(f"{minutes} minutes")
        fmt.append(f"{hours} hours")

    console.log("[green]Done![/green] Wrote {} bytes in {}".format(bytes_written, ", ".join(fmt)))
