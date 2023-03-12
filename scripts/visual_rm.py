#!/usr/bin/env python3
import os
import subprocess
import sys
from typing import Callable, Any

import click
import time
from threading import Thread
from elevate import elevate
from pathlib import Path
from rich import get_console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, TextColumn, SpinnerColumn, MofNCompleteColumn


# noinspection DuplicatedCode
class Main:
    def __init__(self, *, path: Path = None, skip_confirm: bool, dry: bool, quiet: bool, threaded: bool):
        self.path = path
        self.yes = skip_confirm
        self.dry = dry
        self.quiet = quiet
        self.threaded = threaded
        self.start = None
        self.root = path
        self.deleted_files = self.deleted_directories = self.found_files = self.found_directories = 0
        self.failed_files = self.failed_directories = 0
        self.console = get_console()

    def log_if_not_quiet(self, message: str):
        if not self.quiet:
            self.console.log(message)

    def delete(self, path: Path, *, callback: Callable[[], Any]) -> bool:
        try:
            if path.is_dir():
                if not self.dry:
                    path.rmdir()
                self.deleted_directories += 1
                self.log_if_not_quiet(f"[green]Removed directory {path!s}.")
            else:
                if not self.dry:
                    path.unlink(missing_ok=True)
                self.deleted_files += 1
                self.log_if_not_quiet(f"[green]Removed file {path!s}.")
            return True
        except OSError as err:
            if err.errno == 20:
                self.log_if_not_quiet(f"[yellow]Detected wrong file type for {path!s} - trying absolute removal.")
                try:
                    command = ["rm", "-f"] if os.name != "nt" else ["del", "/f"]
                    subprocess.run((*command, str(path.absolute())), check=True)
                except subprocess.CalledProcessError:
                    pass
                else:
                    self.log_if_not_quiet(f"[green]Removed object {path!s}.")
                    return True
            self.console.log(f"[red]Error removing {path}: {err}")
            if path.is_dir():
                self.failed_directories += 1
            else:
                self.failed_files += 1
            return False
        finally:
            callback()

    def get_root(self):
        while self.root is None or self.root.exists() is False:
            p = Prompt.ask("Root directory", console=self.console)
            _p_r = Path(p)
            if _p_r.exists() is False:
                self.console.log("[red]Directory not found.")
            elif _p_r.is_file():
                self.console.log("[red]Is file - this tool is only effective with large directories.")
            else:
                try:
                    accessible = os.access(_p_r, os.W_OK)
                    assert accessible
                except IOError as e:
                    if e.errno == 13:
                        self.console.log("[red]Unable to access file: Permission denied.")
                        continue
                self.root = _p_r
                break

    def walk_root(self) -> tuple:
        with self.console.status("Walking directory", spinner="bouncingBar") as status:
            tree = tuple(
                os.walk(
                    self.root,
                    topdown=False,
                    onerror=lambda err: self.console.log("[red]:warning: Warning while walking: " + repr(err)),
                    followlinks=False,
                )
            )
            status.update("Counting files and directories")
            for _, dirs, files in tree:
                self.found_directories += len(dirs)
                self.found_files += len(files)
        return tree

    def confirm_deletion(self) -> bool:
        if self.yes is False:
            sure = Confirm.ask(
                "Are you sure you want to delete {:,} things ({:,} files and {:,} directories) from {!s}?".format(
                    self.found_files + self.found_directories,
                    self.found_files,
                    self.found_directories,
                    self.root.absolute(),
                ),
                console=self.console,
            )
            if not sure:
                self.console.log("[red]Aborting.")
                return False
        return True

    def create_progress(self) -> Progress:
        columns = list(Progress.get_default_columns())
        columns.insert(0, SpinnerColumn("bouncingBall"))
        columns.insert(-1, MofNCompleteColumn())
        columns.insert(-2, TextColumn("[bold blue]{task.fields[threads]:,}thr"))
        columns.insert(-2, TextColumn("[bold gold]{task.fields[per_sec]}/s"))
        return Progress(*columns, console=self.console, expand=True, refresh_per_second=24, transient=True)

    def per_second(self) -> int:
        return round((self.deleted_files + self.deleted_directories) / (time.time() - self.start))

    def run(self):
        self.get_root()
        tree = self.walk_root()
        if not self.confirm_deletion():
            return
        with self.create_progress() as progress:
            self.start = time.time()
            task = progress.add_task(
                f"Deleting {self.found_directories:,} dirs & {self.found_files:,} files",
                total=self.found_directories + self.found_files,
                deleted=0,
                threads=1,
                per_sec=self.per_second(),
            )
            threads_task = progress.add_task(
                "Waiting for IO threads to finish",
                start=False,
                total=0,
                visible=self.threaded,
                deleted=0,
                threads=0,
                per_sec=self.per_second(),
            )
            for _root, subdirectories, files in tree:
                threads = []

                def updater():
                    progress.update(
                        task,
                        completed=self.deleted_directories + self.deleted_files,
                        per_sec=self.per_second(),
                        deleted=self.deleted_directories + self.deleted_files,
                    )
                    done_threads = len(threads) - sum(t.is_alive() for t in threads)
                    if done_threads >= 1000:
                        self.log_if_not_quiet("[dim i]Cleaning up dead threads")
                        for thread in threads:
                            if thread.is_alive() is False:
                                threads.remove(thread)
                                del thread
                                # Thread is dead, remove it from the list
                    progress.update(
                        threads_task,
                        total=len(threads),
                        threads=len(threads),
                        completed=done_threads,
                        deleted=done_threads,
                        per_sec=self.per_second(),
                    )

                for file in files:
                    path = Path(_root) / file
                    if self.threaded:
                        threads.append(
                            Thread(
                                target=self.delete,
                                args=(path,),
                                kwargs={"callback": updater},
                            )
                        )
                        threads[-1].start()
                    updater()
                    [x.join() for x in threads]

                for subdir in subdirectories:
                    self.delete(Path(_root) / subdir, callback=updater)

            self.console.log()
            self.console.log(
                f"[green]Deleted {self.deleted_files:,} files and {self.deleted_directories:,} directories.\n"
                f"[red]Failed to delete {self.failed_files:,} files and {self.failed_directories:,} directories.\n"
                f"[white]Finished in {round(time.time() - self.start)} seconds.\n"
                f"[white dim] Average speed: {round(self.per_second())}/s"
            )


# noinspection DuplicatedCode
@click.command()
@click.option("-d", "--dry", is_flag=True, help="Dry run, don't actually remove anything.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("-n", "--no-threads", is_flag=True, help="Don't use threads (may be slower for large files).")
@click.option("-q", "--quiet", is_flag=True, help="Don't print anything other than the progress bar.")
@click.argument("path", type=click.Path(file_okay=False, dir_okay=True), default=None)
def main(dry: bool, yes: bool, no_threads: bool, quiet: bool, path: str = None):
    """Visually remove files and directories with verbose logging and rich progress information.

    Note that the built-in `rm` is much faster and more reliable than this program."""
    try:
        if os.getuid() != 0:
            get_console().log(
                "[yellow bold]You are not root. Some files and directories may not be able to be indexed or deleted.[/]"
            )
            if Confirm.ask("Would you like to elevate to root? (may call `sudo`)", default=True):
                try:
                    elevate()
                except Exception as e:
                    get_console().log(f"[red]Failed to elevate to root: {e}[/]")
    except AttributeError:
        pass
    _runner = Main(path=Path(path), skip_confirm=yes, dry=dry, quiet=quiet, threaded=not no_threads)
    try:
        _runner.run()
    except Exception as e:
        _runner.console.print("\n\n\n")
        _runner.console.print("[red]:warning: An error occurred while running the program!")
        _runner.console.print(f"[black on red]{e!r}")
        if not yes:
            if not Confirm.ask("Would you like to see the traceback for bug reporting?", console=_runner.console):
                sys.exit(1)

        with _runner.console.status("Rendering detailed traceback"):
            _runner.console.print_exception(show_locals=True)
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
