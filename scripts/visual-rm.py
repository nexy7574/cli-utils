import os
import sys
from threading import Thread
from functools import partial
from pathlib import Path
from rich import get_console
from rich.prompt import Prompt
from rich.progress import Progress, track

deleted_files = deleted_directories = found_files = found_directories = 0
failed_files = failed_directories = 0
root = None
threads = []
if len(sys.argv) == 2:
    root = Path(sys.argv[1])
    if not root.exists() or root.is_file():
        root = None
console = get_console()

while root is None:
    p = Prompt.ask(
        "Root directory",
        console=console
    )
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
            onerror=lambda err: console.log('[red]Error walking: ' + repr(err)),
            followlinks=False
        )
    )
    status.update("Counting files and directories")
    for _, dirs, files in tree:
        found_directories += len(dirs)
        found_files += len(files)


def remove(_path: Path, callback: callable) -> bool:
    global deleted_directories, deleted_files, failed_directories, failed_files
    try:
        if _path.is_dir():
            _path.rmdir()
            deleted_directories += 1
            console.log(f"[green]Removed directory {_path!s}.")
        else:
            _path.unlink(missing_ok=True)
            deleted_files += 1
            console.log(f"[green]Removed file {_path!s}.")
        return True
    except (IOError, OSError) as err:
        console.log(f"[red]Error removing {_path}: {err}")
        if _path.is_dir():
            failed_directories += 1
        else:
            failed_files += 1
        return False
    finally:
        callback()


def start_thread(_path: Path, callback: callable):
    t = Thread(target=remove, args=(_path, callback))
    t.start()
    threads.append(t)
    return t


with Progress(console=console) as progress:
    task = progress.add_task(
        f"Deleting {found_directories:,} dirs & {found_files:,} files",
        total=found_directories + found_files
    )
    for _root, subdirectories, files in tree:
        # noinspection DuplicatedCode
        for file in files:
            path = Path(_root) / file
            while True:
                try:
                    start_thread(path, partial(progress.advance, task))
                except RuntimeError:
                    console.log("[red]Thread limit reached, waiting for 10 threads to finish.")
                    for t in threads[:10]:
                        t.join()
                    console.log("[gold]10 threads finished, continuing.")
                else:
                    break

        # noinspection DuplicatedCode
        for directory in subdirectories:
            path = Path(_root) / directory
            while True:
                try:
                    start_thread(path, partial(progress.advance, task))
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
