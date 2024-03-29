"""
This script allows you to visually flash any file (usually disk images) to a drive.

Basically, `dd`, but with a colourful progress bar, and a few utilities and failsafe things.
"""
import io

import rich
import os
import click
from pathlib import Path
from rich.prompt import Confirm
from rich.progress import *


@click.command()
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.argument("target", type=click.Path(exists=True, dir_okay=False, writable=True))
@click.option(
    "--zero-first",
    "-Z",
    is_flag=True,
    help="Fills the device with null data first. May speed it up."
)
@click.option(
    "--buffer/--no-buffer",
    "-B/-NB",
    default=True,
    help="Buffer the input into RAM. This may be useful if your IO speed is slow."
)
@click.option(
    "--verify/--skip-verify", "-V/-SV",
    default=True,
    help="Verify the written data after writing."
)
def main(
        zero_first: bool,
        buffer: bool,
        source: str,
        target: str
):
    """Flashes a given file (usually disk image) to a block device. Fancy DD."""
    block_size = int(os.getenv("BLOCK_SIZE", 1024 * 1024 * 4))  # 4MB
    console = rich.get_console()
    source = Path(source)
    target = Path(target)

    if not target.is_block_device():
        if not Confirm.ask("'%s' does not appear to be a block device. Do you want to write to it anyway?" % target):
            return

    try:
        source_size = source.stat().st_size
    except PermissionError as e:
        rich.print(f"[red]Permission denied while reading {source}: {e}")
        return

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TransferSpeedColumn(),
    )

    with progress:
        task1 = progress.add_task("Writing '%s' to '%s'" % (source, target), total=source_size, start=False)
        if zero_first:
            task2 = progress.add_task("Zeroing '%s'" % target)
            zero = b"\0" * block_size
            with target.open("wb") as f:
                written = 0
                while True:
                    try:
                        written += f.write(zero)
                    except OSError:
                        break
                    progress.update(task2, advance=written-1, total=written)
            progress.update(task2, completed=written)

        if buffer:
            task3 = progress.add_task("Buffering '%s' into memory" % source, total=source_size)
            source_2 = io.BytesIO()
            with source.open("rb") as f:
                for chunk in iter(lambda: f.read(block_size), b""):
                    source_2.write(chunk)
                    progress.update(task3, advance=len(chunk))
            source_2.seek(0)
            source = source_2

        with open(source, "rb") as src:
            with target.open("wb") as tgt:
                progress.update(task1, total=source_size, completed=0, start=True)
                while True:
                    try:
                        data = src.read(block_size)
                        if not data:
                            break
                        written = tgt.write(data)
                        progress.update(task1, advance=written)
                    except OSError:
                        break
    with console.status("Flushing writes to physical disk (this may take some time)", spinner="dots"):
        os.sync()
    rich.print("[green]Done writing.")
