from rich import get_console
from rich.progress import (
    Progress,
    SpinnerColumn,
    FileSizeColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskID,
    TotalFileSizeColumn,
    TransferSpeedColumn,
)
import hashlib
import click
from pathlib import Path

# from multiprocessing import Pool
from threading import Thread
from io import BytesIO
from typing import BinaryIO
import psutil
import signal
import os

# Multiprocessing would be used, however you can't pass IO buffers between processes.
# This means if someone were to want to multi-hash a file, they would have to either read the file into memory n times
# (n being number of processes), or read the file n times; either way, this is really wasteful.
# At least with threading, it will be ever so slightly faster than single-threaded, despite the GIL limitations.

types = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha224": hashlib.sha224,
    "sha256": hashlib.sha256,
    "sha384": hashlib.sha384,
    "sha512": hashlib.sha512,
}
kill = False  # global kill for threads
for _k in types.copy().keys():
    if "sha" in _k:
        types[_k.strip("sha")] = types[_k]


def generate_hash(obj: BinaryIO, name: str, task: TaskID, progress: Progress, chunk_size: int) -> str:
    """Generate hash from file object"""
    hash_obj = types[name]()

    progress.start_task(task)
    bytes_read = 0
    for chunk in iter(lambda: obj.read(chunk_size), b""):
        if kill:
            progress.stop_task(task)
            del hash_obj
            progress.update(
                task,
                description=f"Generating {name} hash (Cancelled)"
            )
            return "cancelled"
        hash_obj.update(chunk)
        progress.update(task, advance=len(chunk))
        bytes_read += len(chunk)
    if progress.tasks[task].total != progress.tasks[task].completed:
        progress.update(task, completed=bytes_read, total=bytes_read)

    return hash_obj.hexdigest()


@click.command()
@click.option("--no-ram", is_flag=True, help="Disable loading file into RAM beforehand.")
@click.option(
    "--single-thread",
    "--single",
    is_flag=True,
    default=False,
    help="Forces single-thread behaviour. May be slower than multi-threaded.",
)
@click.option("--block-size", "--bs", default=1024, help="Block size for hashing (in KiB).", type=click.INT)
@click.option("--md5", is_flag=True, default=False, help="Use MD5 hashing algorithm.")
@click.option("--sha1", is_flag=True, default=False, help="Use SHA1 hashing algorithm.")
@click.option("--sha224", is_flag=True, default=False, help="Use SHA224 hashing algorithm.")
@click.option("--sha256", is_flag=True, default=False, help="Use SHA256 hashing algorithm.")
@click.option("--sha384", is_flag=True, default=False, help="Use SHA384 hashing algorithm.")
@click.option("--sha512", is_flag=True, default=False, help="Use SHA512 hashing algorithm.")
@click.argument("file", type=click.Path(exists=True, file_okay=True, readable=True, allow_dash=True))
def main(
    no_ram: bool,
    single_thread: bool,
    block_size: int,
    md5: bool,
    sha1: bool,
    sha224: bool,
    sha256: bool,
    sha384: bool,
    sha512: bool,
    file: str,
):
    """Generates a hash for a specified file.

    This tool is most useful for generating hashes of large files, as it includes progress."""
    global kill
    _fn = file
    multi_core = not single_thread
    if os.name != "nt" and multi_core:

        def signal_handler(*_):
            global kill
            for _task in progress.tasks:
                if _task.completed != _task.total:
                    progress.update(
                        _task.id,
                        description=_task.description + " (Cancelling)"
                    )
            kill = True
            console.print("Interrupt handled, stopping threads.")

        signal.signal(signal.SIGINT, signal_handler)

    chunk_size = block_size * 1024
    console = get_console()
    hashes_to_gen = {"md5": md5, "sha1": sha1, "sha224": sha224, "sha256": sha256, "sha384": sha384, "sha512": sha512}
    generated_hashes = {"md5": None, "sha1": None, "sha224": None, "sha256": None, "sha384": None, "sha512": None}
    [generated_hashes.update({k: "incomplete"}) for k in hashes_to_gen.keys() if hashes_to_gen[k]]
    [generated_hashes.pop(k) for k in hashes_to_gen.keys() if not hashes_to_gen[k]]

    if not any(hashes_to_gen.values()):
        console.print("No hash types specified. Exiting.")
        return

    for name, value in hashes_to_gen.copy().items():
        if not value:
            del hashes_to_gen[name]

    if file == "-":
        path = Path("stdin")
        file = click.open_file("-", "rb")
        size = None
    else:
        path = Path(file).absolute().resolve()
        file = path.open("rb")
        stat = path.stat(follow_symlinks=True)
        size = stat.st_size

    if not no_ram:
        free_ram = psutil.virtual_memory().available
        if size is not None and size > free_ram:
            console.print(
                f"[red]:warning: File is larger than available RAM. Disabling RAM caching (reading straight from disk)."
            )
            no_ram = True
        elif size is None:
            console.print(
                f"[red]:warning: File size is unknown as reading from stdin. If the file is larger than available"
                f" free RAM ({free_ram:,} bytes), this may cause issues."
            )

    if len(hashes_to_gen) == 1:
        multi_core = False
        console.print("[yellow]:information: Disabled multi-threading as only one hash type was specified.")

    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBar"))
    columns.insert(-1, FileSizeColumn())
    columns.insert(-1, TotalFileSizeColumn())
    columns.insert(-1, TransferSpeedColumn())
    columns.insert(-1, TimeElapsedColumn())
    columns[-1] = TimeRemainingColumn(True)

    console.print(
        f"Generating {len(hashes_to_gen)} hash{'es' if len(hashes_to_gen) > 1 else ''} for {file.name} "
        f"with a block size of {block_size} KiB ({chunk_size} chunk size in bytes)."
    )

    with Progress(*columns, console=console, refresh_per_second=12, expand=True) as progress:
        if not no_ram:
            task = progress.add_task("Loading file into RAM...", total=size)
            _t = 0
            buffer = BytesIO()
            for block in iter(lambda: file.read(chunk_size), b""):
                if kill:
                    del buffer
                    progress.update(task, description="Loading file into ram (cancelled)")
                    progress.stop_task(task)
                    return
                buffer.write(block)
                _t += len(block)
                progress.update(task, advance=len(block))
            buffer.seek(0)
            progress.update(task, total=_t)
            size = _t
        else:
            buffer = file

        tasks = {}
        for hash_name in hashes_to_gen.keys():
            tasks[hash_name] = progress.add_task(f"Generating {hash_name} hash", total=size, start=False)

        if multi_core:
            threads = []
            for hash_name in hashes_to_gen.keys():
                thread = Thread(
                    target=lambda: generated_hashes.update(
                        {hash_name: generate_hash(buffer, hash_name, tasks[hash_name], progress, chunk_size)}
                    )
                )
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        else:
            for hash_name in hashes_to_gen.keys():
                generated_hashes[hash_name] = generate_hash(buffer, hash_name, tasks[hash_name], progress, chunk_size)

    console.log(f"Hashes for {path}:")
    for hash_name, hash_value in generated_hashes.items():
        console.print(f"[cyan]{hash_name}[/]: [code]{hash_value}[/]")


if __name__ == "__main__":
    main()
