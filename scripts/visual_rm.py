#!/usr/bin/env python3
import os
import subprocess

import click
import time
from threading import Thread
from functools import partial
from pathlib import Path
from rich import get_console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, track, TextColumn, SpinnerColumn, MofNCompleteColumn

deleted_files = deleted_directories = found_files = found_directories = failed_files = failed_directories = 0
root = None
threads = []
console = get_console()


try:
    if os.getuid() != 0:
        console.log(
            "[yellow bold]You are not root. Some files and directories may not be able to be" " indexed or deleted.[/]"
        )
except AttributeError:
    pass


def log_if_not_quiet(message: str, quiet: bool):
    if not quiet:
        console.log(message)


def remove(_path: Path, callback: callable, dry: bool, quiet: bool) -> bool:
    global deleted_directories, deleted_files, failed_directories, failed_files
    try:
        if _path.is_dir():
            if not dry:
                _path.rmdir()
            deleted_directories += 1
            log_if_not_quiet(f"[green]Removed directory {_path!s}.", quiet)
        else:
            if not dry:
                _path.unlink(missing_ok=True)
            deleted_files += 1
            log_if_not_quiet(f"[green]Removed file {_path!s}.", quiet)
        return True
    except OSError as err:
        if err.errno == 20:
            log_if_not_quiet(f"[yellow]Detected wrong file type for {_path!s} - trying absolute removal.", quiet)
            try:
                command = ["rm", "-f"] if os.name != "nt" else ["del", "/f"]
                subprocess.run((*command, str(_path.absolute())), check=True)
            except subprocess.CalledProcessError:
                pass
            else:
                log_if_not_quiet(f"[green]Removed object {_path!s}.", quiet)
                return True
        console.log(f"[red]Error removing {_path}: {err}", quiet)
        if _path.is_dir():
            failed_directories += 1
        else:
            failed_files += 1
        return False
    finally:
        callback()


def per_second(value: int, start: float) -> str:
    return f"{value / (time.time() - start):.0f}/s"


def start_thread(_path: Path, callback: callable, dry: bool, quiet: bool):
    t = Thread(target=remove, args=(_path, callback, dry, quiet))
    t.start()
    threads.append(t)
    return t


# noinspection DuplicatedCode
@click.command()
@click.option("-d", "--dry", is_flag=True, help="Dry run, don't actually remove anything.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("-n", "--no-threads", is_flag=True, help="Don't use threads (may be slower).")
@click.option("-q", "--quiet", is_flag=True, help="Don't print anything other than the progress bar.")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=None)
def main(dry: bool, yes: bool, no_threads: bool, quiet: bool, path: str = None):
    """Visually remove files and directories with verbose logging and rich progress information.

    Note that the built-in `rm` is much faster and more reliable than this program."""
    global root, found_files, found_directories
    if path is not None:
        path = Path(path)
        if path.exists() and path.is_dir():
            root = path

    while root is None:
        p = Prompt.ask("Root directory", console=console)
        _p_r = Path(p)
        if _p_r.exists() is False:
            console.log("[red]Directory not found.")
        elif _p_r.is_file():
            console.log("[red]Is file - this tool is only effective with large directories.")
        else:
            root = _p_r

    with console.status("Walking directory", spinner="bouncingBar") as status:
        tree = list(
            os.walk(
                root,
                topdown=False,
                onerror=lambda err: console.log("[red]:warning: Warning while walking: " + repr(err)),
                followlinks=False,
            )
        )
        status.update("Counting files and directories")
        for _, dirs, files in tree:
            found_directories += len(dirs)
            found_files += len(files)

    if not yes:
        sure = Confirm.ask(
            "Are you sure you want to delete {:,} things ({:,} files and {:,} directories) from {!s}?".format(
                found_files + found_directories, found_files, found_directories, root.absolute()
            )
        )
        if not sure:
            console.log("[red]Aborting.")
            return

    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBall"))
    columns.insert(-1, MofNCompleteColumn())
    columns.insert(-2, TextColumn("[bold blue]{task.fields[threads]:,}thr"))
    columns.insert(-2, TextColumn("[bold gold]{task.fields[per_sec]}"))
    with Progress(*columns, console=console, expand=True) as progress:
        start = time.time()
        task = progress.add_task(
            f"Deleting {found_directories:,} dirs & {found_files:,} files",
            total=found_directories + found_files,
            deleted=0,
            threads=0,
            per_sec=per_second(deleted_files + deleted_directories, start),
        )
        for _root, subdirectories, files in tree:
            updater = partial(
                progress.update,
                task,
                advance=1,
                threads=len(threads),
                deleted=deleted_directories + deleted_files,
                per_sec=per_second(deleted_files + deleted_directories, start),
            )

            for file in files:
                path = Path(_root) / file
                while True:
                    if no_threads:
                        remove(path, updater, dry, quiet)
                        break
                    else:
                        try:
                            start_thread(path, updater, dry, quiet)
                            time.sleep(0)
                            progress.refresh()
                        except RuntimeError:
                            console.log("[red]Thread limit reached, waiting for 10 threads to finish.")
                            for t in threads[:10]:
                                t.join()
                            console.log("[gold]10 threads finished, continuing.")
                        else:
                            break

            for directory in subdirectories:
                path = Path(_root) / directory
                while True:
                    if no_threads:
                        remove(path, updater, dry, quiet)
                        break
                    else:
                        try:
                            start_thread(path, updater, dry, quiet)
                            time.sleep(0)
                            progress.refresh()
                        except RuntimeError:
                            console.log("[red]Thread limit reached, waiting for 10 threads to finish.")
                            for t in threads[:10]:
                                t.join()
                            console.log("[gold]10 threads finished, continuing.")
                        else:
                            break

    console.log()
    console.log(
        f"[green]Deleted {deleted_files:,} files and {deleted_directories:,} directories.\n"
        f"[red]Failed to delete {failed_files:,} files and {failed_directories:,} directories."
    )
    if threads:
        for thread in track(threads, description="Waiting for threads to finish", console=console):
            thread.join()


if __name__ == "__main__":
    main()
