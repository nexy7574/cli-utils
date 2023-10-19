#!/usr/bin/env python3
import os
import pathlib
import subprocess
import sys
import time
import typing
from pathlib import Path
from threading import Thread
from typing import Any, Callable

import click
import rich
from elevate import elevate
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

console = rich.get_console()


def crawl(target: Path, err_action: typing.Literal["warn", "error", "ignore"], follow_links: bool):
    """Crawl the target and return a list of all files and directories."""
    def _on_error(e: OSError):
        if err_action != "error":
            console.print(f"[red]Error crawling {e.filename!r}: {e}[/]")
        else:
            raise e

    files = []
    for root, dirs, filenames in os.walk(target, True, _on_error, follow_links):
        for filename in filenames:
            yield Path(root) / filename
        for directory in dirs:
            yield Path(root) / directory


def partition_objects(obj: list[Path]) -> tuple[list[Path], list[Path]]:
    """Partition a list of objects into files and directories."""
    files = []
    directories = []
    for path in obj:
        if path.is_dir():
            directories.append(path)
        else:
            files.append(path)
    return files, directories


@click.command()
@click.option(
    "--dry",
    "-d",
    is_flag=True,
    help="Dry run, don't delete anything.",
)
@click.option(
    "--interactive",
    "-i",
    "-I",
    is_flag=True,
    help="Interactive mode. Prompts for each file deletion, unless the file/directory is empty.",
)
@click.option(
    "--directories",
    "-d",
    is_flag=True,
    help="Remove empty directories.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose mode. Prints out the files that are being deleted.",
)
@click.option(
    "--errors",
    "-E",
    type=click.Choice(["ignore", "warn", "error"], case_sensitive=False),
    default="error",
    help="Error handling mode. [default: error]",
)
@click.option(
    "--follow-links/--no-follow-links",
    default=False,
    help="Follow symlinks. [default: False]",
)
@click.argument(
    "targets",
    nargs=-1,
    type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True),
)
def main(
    dry: bool,
    interactive: bool,
    directories: bool,
    verbose: bool,
    errors: typing.Literal["ignore", "warn", "error"],
    follow_links: bool,
    targets: tuple[str],
):
    """
    Visual RM. A version of rm that looks nicer so that you know exactly how slow your disk is going while deleting.

    ----------------

    Dry:
        Dry mode does not delete anything, but instead waits about a 30th of a second for each file or directory.

    Interactive:
        Interactive mode prompts for each file deletion, unless the file/directory is empty. This is the same as rm -i.

    Directories:
        Directories mode removes empty directories. This is the same as rm -d.

    Verbose:
        Verbose mode prints out the files that are being deleted. This is the same as rm -v.

    Follow Links:
        Follow symlinks. By default, this is off to prevent accidental deletion of files.

    Errors:
        Error handling mode. This is the same as rm -E. [default: error]
        Error modes:
            - ignore: Ignore errors, treat as success.
            - warn: Warn on errors and moves on.
            - error: Error on errors and exits. Does not undo files.
    """
    with Progress(
        SpinnerColumn("bouncingBall"),
        *Progress.get_default_columns(),
        console=console,
        expand=True
    ) as progress:
        to_delete = {}
        for target in targets:
            path = Path(target)
            if not path.exists():
                console.print(f"[red]Error: {target!r} does not exist.[/]")
                continue

            task = progress.add_task(f"Preparing to delete {path}", start=False, total=1)
            to_delete[path] = {
                "task": task,
                "files": [path],
            }

            if path.is_dir():
                progress.update(
                    task,
                    description=f"Discovering files in {path}",
                    total=None
                )
                to_delete[path]["files"] += list(crawl(path, errors, follow_links))
                progress.update(
                    task,
                    description=f"Discovered {len(to_delete[path]['files']):,} files & directories in {path}"
                )

        for root, data in to_delete.items():
            if len(data["files"]) > 1:
                _f, _d = partition_objects(data["files"])
                progress.update(
                    task,
                    description="Deleting {:,} objects ({:,} and {:,} directories) from {}".format(
                        len(data["files"]),
                        len(_f),
                        len(_d),
                        root
                    ),
                )
            progress.update(data["task"], start=True, total=len(data["files"]))
            for fp in data["files"]:
                if fp.is_dir():
                    if not directories:
                        progress.advance(data["task"])
                        continue
                    if not fp.is_symlink() and len(list(fp.iterdir())) > 0:
                        progress.advance(data["task"])
                        continue
                if interactive:
                    if not Confirm.ask(f"Delete {fp!r}?"):
                        progress.advance(data["task"])
                        continue
                if not dry:
                    if verbose:
                        console.print(f"Deleting {fp!r}")
                    try:
                        if fp.is_dir():
                            fp.rmdir()
                        else:
                            fp.unlink()
                    except OSError as e:
                        if errors == "ignore":
                            progress.advance(data["task"])
                            continue
                        elif errors == "warn":
                            console.print(f"[red]Error deleting {fp!r}: {e}[/]")
                            progress.advance(data["task"])
                            continue
                        elif errors == "error":
                            raise e
                else:
                    if verbose:
                        console.print(f"Would delete {fp!r}")
                    time.sleep(1 / 3)
                progress.advance(data["task"])


if __name__ == "__main__":
    main()
