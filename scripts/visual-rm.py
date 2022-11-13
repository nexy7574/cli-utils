import os
import sys
from pathlib import Path
from rich import get_console
from rich.prompt import Prompt
from rich.progress import Progress

deleted_files = deleted_directories = found_files = found_directories = 0
failed_files = failed_directories = 0
root = None
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
        console.print("[red]Directory not found.")
    elif _p_r.is_file():
        console.print("[red]Is file - this tool is only effective with large directories.")
    else:
        root = _p_r

with console.status("Walking directory", spinner="bouncingBar") as status:
    tree = list(
        os.walk(
            root,
            topdown=False,
            onerror=lambda err: console.print('[red]Error walking: ' + repr(err)),
            followlinks=False
        )
    )
    status.update("Counting files and directories")
    for _, dirs, files in tree:
        found_directories += len(dirs)
        found_files += len(files)


with Progress(console=console) as progress:
    task = progress.add_task(
        f"Deleting {found_directories:,} dirs & {found_files:,} files",
        total=found_directories + found_files
    )
    for _root, subdirectories, files in tree:
        for file in files:
            path = Path(_root) / file
            try:
                os.remove(path)
            except OSError as e:
                console.print(f"[red]Failed to remove file {path.absolute()}: {e}")
                failed_files += 1
            else:
                console.print(f"[green]Removed file {path.absolute()}")
                progress.advance(task)
                deleted_files += 1

        for directory in subdirectories:
            path = Path(_root) / directory
            try:
                os.rmdir(path)
            except OSError as e:
                console.print(f"[red]Failed to remove directory {path.absolute()}: {e}")
                failed_directories += 1
            else:
                console.print(f"[green]Removed directory {path.absolute()}")
                progress.advance(task)
                deleted_directories += 1

console.print()
console.print(
    f"[green]Deleted {deleted_files:,} files and {deleted_directories:,} directories.\n"
    f"[red]Failed to delete {failed_files:,} files and {failed_directories:,} directories."
)
