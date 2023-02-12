import copy
import subprocess
import sys
import typing
from functools import partial

import rich
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
from rich.table import Table
from rich.prompt import Confirm
import hashlib
import click
from click_aliases import ClickAliasedGroup
from pathlib import Path
from humanize import naturalsize

# from multiprocessing import Pool
from threading import Thread
from io import BytesIO
from typing import BinaryIO, List, Tuple
import psutil
import signal
import os

if typing.TYPE_CHECKING:
    from rich.console import Console

# Multiprocessing would be used, however you can't pass IO buffers between processes.
# This means if someone were to want to multi-hash a file, they would have to either read the file into memory n times
# (n being number of processes), or read the file n times; either way, this is really wasteful.
# At least with threading, it will be ever so slightly faster than single-threaded, despite the GIL limitations.

DEFAULT_WGET_OPTIONS = "-c -O /tmp/.hashgen.download.part -t 5 --compression=auto -q --show-progress --progress=bar" \
                       " --no-cache "


def get_hasher(name: str) -> callable:
    try:
        func = hashlib.new(name)
    except ValueError:

        class _Dummy:
            def __init__(self):
                self.name = name

            def update(self, *args, **kwargs):
                pass

            def hexdigest(self):
                return "not supported"

        return _Dummy
    return func


types = {x: None for x in hashlib.algorithms_available}
for __t in types.keys():
    types[__t] = get_hasher(__t)

kill = False  # global kill for threads
for _k in types.copy().keys():
    _k: str
    if "sha" in _k:
        types[_k.replace("sha", "", 1)] = types[_k]


def generate_hash(obj: BinaryIO, name: str, task: TaskID, progress: Progress, chunk_size: int) -> str:
    """Generate hash from file object"""
    hash_obj = types[name]

    progress.start_task(task)
    bytes_read = 0
    for chunk in iter(lambda: obj.read(chunk_size), b""):
        if kill:
            progress.stop_task(task)
            del hash_obj
            progress.update(task, description=f"Generating {name} hash (Cancelled)")
            return "cancelled"
        hash_obj.update(chunk)
        progress.update(task, advance=len(chunk))
        bytes_read += len(chunk)
    if progress.tasks[task].total != progress.tasks[task].completed:
        progress.update(task, completed=bytes_read, total=bytes_read)

    try:
        return hash_obj.hexdigest()
    except TypeError:
        if "shake" in name:
            return hash_obj.hexdigest(128)


def generate_progress(console: "Console" = None, verbose: bool = False) -> Progress:
    """Generates a progress"""
    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBar"))
    columns.insert(-1, FileSizeColumn())
    columns.insert(-1, TotalFileSizeColumn())
    columns.insert(-1, TransferSpeedColumn())
    columns.insert(-1, TimeElapsedColumn())
    columns[-1] = TimeRemainingColumn(True)
    return Progress(*columns, console=console, refresh_per_second=12, expand=True, transient=not verbose)


def can_use_ram(
    size: int, count: int, *, default: bool = False, console: "Console", multi_core: bool = True
) -> Tuple[bool, bool, bool]:
    no_ram = default
    switched_to_single = False
    hashes_to_gen = count
    free_ram = psutil.virtual_memory().available
    proc_used_ram = psutil.Process().memory_info().vms
    _size = partial(naturalsize, binary=True)
    if size is None:
        console.print(
            f"[red]:warning: File size is unknown as reading from stdin. If the file is larger than available"
            f" free RAM ({_size(free_ram)}), this may cause issues."
        )
        return default, False, True
    else:
        resolved_size = size * hashes_to_gen
        if resolved_size >= free_ram:
            switched_to_single = False

            console.print(
                f"[red]:warning: File ({_size(size)}, {_size(resolved_size)} for "
                f"{hashes_to_gen} threads) is larger than available free RAM ({_size(free_ram)})."
            )

            if size < free_ram:
                console.print(
                    "[yellow]Multihashing can still take place via RAM if the program runs single threaded.\n"
                    "Single threaded multi-hashing is slower, as it only processes one hash at a time, however"
                    " as it is reading from RAM, is still faster than multi-hashing from direct disk.\n"
                    "Your options here are to either *switch to single thread hashing*, or *switch to direct disk*."
                )
                if Confirm.ask("Continue with single-threaded hashing? (if not, will switch to direct disk)"):
                    multi_core = False
                    switched_to_single = True

            if not switched_to_single:
                table = Table(title=f"RAM Requirements for this {'multi-' if count > 1 else ''}hash")
                table.add_column("Type", justify="left")
                table.add_column("RAM Required", justify="center")
                table.add_column("RAM Available", justify="center")
                table.add_column("Sufficient?", justify="center")
                yes = "\N{white heavy check mark}"
                no = "\N{cross mark}"
                _yn = {
                    True: yes,
                    False: no,
                }

                table.add_row(
                    "Multi-threaded, from RAM",
                    f"{_size(resolved_size)}",
                    f"{_size(free_ram)}",
                    _yn[resolved_size < free_ram],
                )
                table.add_row("Single-threaded, from RAM", f"{_size(size)}", f"{_size(free_ram)}", _yn[size < free_ram])
                table.add_row(
                    "Multi-threaded, from disk",
                    f"~{_size((proc_used_ram + 10240) * hashes_to_gen)}",
                    f"{_size(free_ram)}",
                    _yn[proc_used_ram + 100 * hashes_to_gen < free_ram],
                )
                table.add_row(
                    "Single-threaded, from disk",
                    f"~{_size(proc_used_ram + 10240)}",
                    f"{_size(free_ram)}",
                    _yn[proc_used_ram + 100 < free_ram],
                )
                console.print(table)
                console.print(
                    "[yellow]Caching to RAM is disabled. Consider using a smaller file, "
                    "or switching to single-threaded hashing. Direct disk causes high IO wait on slow disks, and"
                    " is overall significantly slower than RAM cached."
                )
                console.print(
                    "[yellow]For more information: https://gist.github.com/EEKIM10/4677140e36a528243fa277091954adcb"
                )
                no_ram = True

    return not no_ram, multi_core, switched_to_single


@click.group(cls=ClickAliasedGroup)
def main():
    """File hashing utility.

    This utility can be used to generate a vast selection of file hashes, comparing files via their hashes, and hash validation.
    Hashgen is useful for hashing large files, which may take a long time, as you can see what the program is doing in real time.
    Hashgen is also highly configurable."""
    pass


@main.command(name="generate", aliases=["gen", "g"])
@click.option("--no-ram", is_flag=True, help="Disable loading file into RAM beforehand.")
@click.option(
    "--single-thread",
    "--single",
    is_flag=True,
    default=False,
    help="Forces single-thread behaviour. May be slower than multi-threaded, but lighter on RAM.",
)
@click.option("--block-size", "--bs", default=10240, help="Block size for hashing (in KiB).", type=click.INT)
@click.option("--md5", is_flag=True, default=False, help="Use MD5 hashing algorithm.")
@click.option("--sha1", is_flag=True, default=False, help="Use SHA1 hashing algorithm.")
@click.option("--sha224", is_flag=True, default=False, help="Use SHA224 hashing algorithm.")
@click.option("--sha256", is_flag=True, default=False, help="Use SHA256 hashing algorithm.")
@click.option("--sha384", is_flag=True, default=False, help="Use SHA384 hashing algorithm.")
@click.option("--sha512", is_flag=True, default=False, help="Use SHA512 hashing algorithm.")
@click.option("--sha3_224", "--sha3-224", is_flag=True, default=False, help="Use SHA3_224 hashing algorithm.")
@click.option("--sha3_256", "--sha3-256", is_flag=True, default=False, help="Use SHA3_256 hashing algorithm.")
@click.option("--sha3_384", "--sha3-384", is_flag=True, default=False, help="Use SHA3_384 hashing algorithm.")
@click.option("--sha3_512", "--sha3-512", is_flag=True, default=False, help="Use SHA3_512 hashing algorithm.")
@click.option("--sm3", is_flag=True, default=False, help="Use SM3 hashing algorithm.")
@click.option("--blake2b", is_flag=True, default=False, help="Use BLAKE2b hashing algorithm.")
@click.option("--blake2s", is_flag=True, default=False, help="Use BLAKE2s hashing algorithm.")
@click.option("--ripe-md-160", "--ripemd160", is_flag=True, default=False, help="Use RIPEMD160 hashing algorithm.")
@click.option("--shake_128", "--shake-128", is_flag=True, default=False, help="Use SHAKE_128 hashing algorithm.")
@click.option("--shake_256", "--shake-256", is_flag=True, default=False, help="Use SHAKE_256 hashing algorithm.")
@click.option(
    "--all-hashes", is_flag=True, default=False, help="Use all hashing algorithms. Overrules previous hash options."
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output.")
@click.argument("file", type=click.Path(exists=True, file_okay=True, readable=True, allow_dash=True))
def generate(
    no_ram: bool,
    single_thread: bool,
    block_size: int,
    md5: bool,
    sha1: bool,
    sha224: bool,
    sha256: bool,
    sha384: bool,
    sha512: bool,
    sha3_224: bool,
    sha3_256: bool,
    sha3_384: bool,
    sha3_512: bool,
    sm3: bool,
    blake2b: bool,
    blake2s: bool,
    ripe_md_160: bool,
    shake_128: bool,
    shake_256: bool,
    all_hashes: bool,
    verbose: bool,
    file: str,
):
    """Generates a hash for a specified file.

    This tool is most useful for generating hashes of large files, as it includes progress."""
    console = get_console()
    global kill
    _fn = file
    multi_core = not single_thread
    if os.name != "nt" and multi_core:

        def signal_handler(*_):
            global kill
            try:
                for _task in progress.tasks:
                    if _task.completed != _task.total:
                        progress.update(_task.id, description=_task.description + " (Cancelling)")
            except NameError:
                # Killed before progress bar was created
                pass
            kill = True
            console.print("Interrupt handled, stopping threads (ctrl+d to force exit).")

        signal.signal(signal.SIGINT, signal_handler)

    if all_hashes:
        if not no_ram:
            console.print(
                ":warning: If you intend to load the file into RAM before hashing with all hashes, you're insane."
            )
            console.print(":warning: If you want to cancel this behaviour, you should pass `--no-ram`.")
            console.print(
                ":warning: If the file you're trying to hash is too big, RAM caching will be automatically mitigated."
            )
            console.print(
                "[yellow]:warning: If the file you're trying to hash doesn't have a size value, "
                "then this will crash your computer if you let it load. [red]You have been warned."
            )
            console.print("[i yellow]No action taken.")
            console.print()
        md5 = sha1 = sha224 = sha256 = sha384 = sha512 = blake2b = blake2s = sha3_224 = sha3_256 = sha3_384 = True
        sha3_512 = sm3 = ripe_md_160 = shake_128 = shake_256 = True

    chunk_size = block_size * 1024
    hashes_to_gen = {
        "md5": md5,
        "sha1": sha1,
        "sha224": sha224,
        "sha256": sha256,
        "sha384": sha384,
        "sha512": sha512,
        "blake2b": blake2b,
        "blake2s": blake2s,
        "sha3_224": sha3_224,
        "sha3_256": sha3_256,
        "sha3_384": sha3_384,
        "sha3_512": sha3_512,
        "sm3": sm3,
        "ripemd160": ripe_md_160,
        "shake_128": shake_128,
        "shake_256": shake_256,
    }

    if (hash_count := list(hashes_to_gen.values()).count(True)) > (cpu_count := os.cpu_count()):
        console.print(
            f"[yellow]:warning: You have selected {hash_count} hashing algorithms, and enabled multi-threaded hashing, "
            f"however you only have {cpu_count} CPU cores. This may cause performance issues.\n"
            f"[i]No action taken.[/][/yellow]\n"
        )

    generated_hashes = {k: None for k in hashes_to_gen.keys()}
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

    no_ram, multi_core, switched_to_single = can_use_ram(
        size, len(hashes_to_gen), default=no_ram is False, console=console, multi_core=multi_core
    )

    if len(hashes_to_gen) == 1:
        multi_core = False
        if verbose:
            console.print("[yellow]:information: Disabled multi-threading as only one hash type was specified.")

    if verbose:
        console.print(
            f"Generating {len(hashes_to_gen)} hash{'es' if len(hashes_to_gen) > 1 else ''} for {file.name} "
            f"with a block size of {block_size} KiB ({chunk_size} chunk size in bytes)."
        )

    with generate_progress(console, verbose) as progress:
        if not no_ram:
            task = progress.add_task("Loading file into RAM...", total=size)
            _t = 0
            buffer = BytesIO()
            for block in iter(lambda: file.read(chunk_size), b""):
                if kill:
                    del buffer
                    progress.update(task, description="Loading file into RAM (cancelled)")
                    progress.stop_task(task)
                    return
                buffer.write(block)
                _t += len(block)
                progress.update(task, advance=len(block))
            buffer.seek(0)
            progress.update(task, total=_t)
            size = _t
        else:
            if path == Path("stdin"):
                # We need to read the whole of stdin to allow for seeking
                buffer = BytesIO(file.read())
            else:
                buffer = file

        tasks = {}
        for hash_name in hashes_to_gen.keys():
            tasks[hash_name] = progress.add_task(f"Generating {hash_name} hash", total=size, start=False)

        if multi_core:
            threads = []
            for hash_name in hashes_to_gen.keys():
                if not no_ram:
                    buffer_copy = copy.copy(buffer)
                else:
                    buffer_copy = click.open_file(_fn, "rb")
                thread = Thread(
                    target=lambda: generated_hashes.update(
                        {hash_name: generate_hash(buffer_copy, hash_name, tasks[hash_name], progress, chunk_size)}
                    )
                    and buffer_copy.close()
                )
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        else:
            for hash_name in hashes_to_gen.keys():
                generated_hashes[hash_name] = generate_hash(buffer, hash_name, tasks[hash_name], progress, chunk_size)
                buffer.seek(0)

    console.log(f"Hashes for {path}:")
    for hash_name, hash_value in generated_hashes.items():
        console.print(f"[cyan]{hash_name}[/]: {hash_value}")


@main.command(name="verify", aliases=["v"])
@click.option(
    "--hash-type",
    "--type",
    "-T",
    "hash_type",
    type=click.Choice([x for x in types.keys() if "blake" not in x] + ["auto"]),
    default="auto",
)
@click.argument("hash_value", type=str, required=True)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, readable=True, allow_dash=True))
def verify(hash_type: str, hash_value: str, file: str):
    """Verifies a file's hash. You're better off using an external tool to do this because this is really inefficient"""
    _hash = hash_value
    console = get_console()
    sizes = {
        "md5": 32,
        "sha1": 40,
        "sha224": 56,
        "sha256": 64,
        "sha384": 96,
        "sha512": 128,
    }
    if hash_type == "auto":
        for _type, _size in sizes.items():
            if len(_hash) == _size:
                hash_type = _type
                break
        else:
            console.print("[red]:x: Error: Could not determine hash type. Please specify manually via --hash-type")
            return

    if file == "-":
        path = Path("stdin")
        file = click.open_file("-", "rb")
        size = None
    else:
        path = Path(file).absolute().resolve()
        file = path.open("rb")
        stat = path.stat(follow_symlinks=True)
        size = stat.st_size

    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBar"))
    columns.insert(-1, FileSizeColumn())
    columns.insert(-1, TotalFileSizeColumn())
    columns.insert(-1, TransferSpeedColumn())
    columns.insert(-1, TimeElapsedColumn())
    columns[-1] = TimeRemainingColumn(True)

    with Progress(*columns, console=console, refresh_per_second=12, expand=True) as progress:
        buffer = file
        task = progress.add_task(f"Checking {hash_type} hash", total=size)
        file_hash = generate_hash(buffer, hash_type, task, progress, 1024 * 1024 * 32)

    if file_hash == _hash:
        console.print(f"[green]Hashes match![/]")
    else:
        console.print(f"[red]Hashes do not match![/]")
        console.print(f"[cyan]{hash_type} Provided[/]: {_hash}")
        console.print(f"[cyan]{hash_type} Calculated[/]: {file_hash}")


@main.command(name="compare", aliases=["c", "vs"])
@click.option("--hash-type", "--type", "-T", "hash_type", type=click.Choice(list(types.keys())), default="sha256")
@click.option("--block-size", "--block", "-B", "block_size", type=int, default=10240)
@click.option("--no-ram", is_flag=True, help="Disable loading files into RAM beforehand.")
@click.option(
    "--single-thread",
    "--single",
    is_flag=True,
    default=False,
    help="Only hashes one file at a time.",
)
@click.argument("files", nargs=2, type=click.Path(exists=True, dir_okay=False, readable=True))
def compare_files(hash_type: str, block_size: int, no_ram: bool, single_thread: bool, files: List[str]):
    """Compares the hashes of given files."""
    console = get_console()

    global kill
    if len(files) != 2:
        console.log("[red]:x: Error: You must provide exactly two files to compare.")
        return
    if files[0] == files[1]:
        console.log("[red]:x: Error: Cannot compare a file to itself.")
        return

    if os.name != "nt" and not single_thread:

        def signal_handler(*_):
            global kill
            try:
                for _task in progress.tasks:
                    if _task.completed != _task.total:
                        progress.update(_task.id, description=_task.description + " (Cancelling)")
            except NameError:
                # Killed before progress bar was created
                pass
            kill = True
            console.print("Interrupt handled, stopping threads (ctrl+d to force exit).")

        signal.signal(signal.SIGINT, signal_handler)

    if block_size == 0:
        console.print("[red]:x: Error: Block size must be greater than 0.")
        return

    file_stats = [os.stat(file, follow_symlinks=True) for file in files]

    no_ram, multi_core, switched_to_single = can_use_ram(
        sum(x.st_size for x in file_stats),
        count=2,
        default=no_ram is True,
        console=console,
        multi_core=not single_thread,
    )
    if no_ram is False:
        console.log(
            "[yellow]:information: Info: RAM pre-loading is disabled due to bugs that will be removed in a future update."
        )

    if single_thread:
        console.log("[yellow]:warning: Warning: Single-threaded mode is slow and inefficient.")

    with generate_progress(console) as progress:
        meta = {
            file: {
                "path": Path(file),
                "stat": file_stats[files.index(file)],
                "buffer": open(file, "rb"),
                "task_id": None,
                "hash": None,
            }
            for file in files
        }

        for file in files:
            pth: Path = meta[file]["path"]
            size = meta[file]["stat"].st_size
            if not no_ram:
                task = progress.add_task(f"Loading file {pth.name!r} into RAM...", total=size)
                _t = 0
                buffer = BytesIO()
                for block in iter(lambda: meta[file]["buffer"].read(block_size), b""):
                    if kill:
                        del buffer
                        progress.update(task, description=f"Loading file {pth.name!r} into RAM (cancelled)")
                        progress.stop_task(task)
                        return
                    buffer.write(block)
                    _t += len(block)
                    progress.update(task, advance=len(block))
                buffer.seek(0)
                progress.update(task, total=_t)
                size = _t
                meta[file]["buffer"].close()
                meta[file]["buffer"] = buffer
                progress.remove_task(task)
            meta[file]["task_id"] = progress.add_task(f"Generating hash for {pth.name!r}", total=size, start=False)

        if multi_core:
            threads = []
            for file in files:
                if not no_ram:
                    buffer_copy = copy.copy(buffer)
                else:
                    buffer_copy = click.open_file(file, "rb")
                thread = Thread(
                    target=lambda: meta[file].update(
                        {"hash": generate_hash(buffer_copy, hash_type, meta[file]["task_id"], progress, block_size)}
                    )
                    and buffer_copy.close()
                )
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        else:
            for file in files:
                meta[file]["hash"] = generate_hash(buffer, hash_type, meta[file]["task_id"], progress, block_size)
                buffer.seek(0)

    hashes = [x["hash"] for x in meta.values()]
    if hashes[0] == hashes[1]:
        console.print("[green]Hashes match![/]")
    else:
        console.print("[red]Hashes do not match![/]")
    for file in files:
        console.print(f"[cyan]{hash_type} {meta[file]['path'].name}[/]: {meta[file]['hash']}")


@main.command(name="download", aliases=["dl", "d"])
@click.option("--hash-type", "--type", "-T", "hash_type", type=click.Choice(list(types.keys()) + ["auto"]), default="auto")
@click.option("--wget-options", default=DEFAULT_WGET_OPTIONS)
@click.option(
    "--output-file",
    "-o",
    "output_file",
    type=click.Path(),
    default="/tmp/.hashgen.download.part"
)
@click.argument("url", type=str)
@click.argument("expected_hash", type=str)
def download_file(hash_type: str, wget_options: str, output_file: str, url: str, expected_hash: str):
    """Wrapper for wget and then checking the hash afterwards."""
    console = get_console()
    console.log("Begging download of file...")
    if os.name != "nt":

        def signal_handler(*_):
            global kill
            try:
                for _task in progress.tasks:
                    if _task.completed != _task.total:
                        progress.update(_task.id, description=_task.description + " (Cancelling)")
            except NameError:
                # Killed before progress bar was created
                pass
            kill = True
            console.print("Interrupt handled, stopping threads (ctrl+d to force exit).")

        signal.signal(signal.SIGINT, signal_handler)
    try:
        subprocess.run(["wget", *wget_options.split(), "-O", output_file, url], check=True)
    except subprocess.CalledProcessError:
        console.log("[red]:x: Error: wget returned non-zero exit code.")
        return
    console.log("Download complete, checking hash...")
    _hash = expected_hash
    console = get_console()
    sizes = {
        "md5": 32,
        "sha1": 40,
        "sha224": 56,
        "sha256": 64,
        "sha384": 96,
        "sha512": 128,
    }
    if hash_type == "auto":
        for _type, _size in sizes.items():
            if len(_hash) == _size:
                hash_type = _type
                break
        else:
            console.print("[red]:x: Error: Could not determine hash type. Please specify manually via --hash-type")
            return

    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBar"))
    columns.insert(-1, FileSizeColumn())
    columns.insert(-1, TotalFileSizeColumn())
    columns.insert(-1, TransferSpeedColumn())
    columns.insert(-1, TimeElapsedColumn())
    columns[-1] = TimeRemainingColumn(True)

    with Progress(*columns, console=console, refresh_per_second=12, expand=True) as progress:
        stat = os.stat(output_file)
        buffer = open(output_file, "rb")
        task = progress.add_task(f"Checking {hash_type} hash", total=stat.st_size)
        file_hash = generate_hash(buffer, hash_type, task, progress, 1024 * 1024 * 32)

    if file_hash == _hash:
        console.print(f"[green]Hashes match![/]")
    else:
        console.print(f"[red]Hashes do not match![/]")
        console.print(f"[cyan]{hash_type} Provided[/]: {_hash}")
        console.print(f"[cyan]{hash_type} Calculated[/]: {file_hash}")
    try:
        os.remove(output_file)
    except (FileNotFoundError, OSError) as e:
        console.print(f"[red]:x: Error: Could not remove temporary file {output_file!r} due to error {e!r}[/]")


@main.command(name="flash", aliases=["f", "image", "i"])
@click.option("--hash-type", "--type", "-T", "hash_type", type=click.Choice(list(types.keys()) + ["auto"]), default="auto")
@click.option("--sync-writes", "-s", is_flag=True)
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.argument("output_file", type=click.Path(writable=True, dir_okay=False))
def flash_image(hash_type: str, sync_writes: bool, input_file: str, output_file: str):
    """Wrapper for `dd` and then verifying the hash"""
    console = get_console()
    if hash_type == "auto":
        hash_type = "sha256"
    console.log("Begging flash of image...")

    if os.name != "nt":

        def signal_handler(*_):
            global kill
            try:
                for _task in progress.tasks:
                    if _task.completed != _task.total:
                        progress.update(_task.id, description=_task.description + " (Cancelling)")
            except NameError:
                # Killed before progress bar was created
                pass
            kill = True
            console.print("Interrupt handled, stopping threads (ctrl+d to force exit).")

        signal.signal(signal.SIGINT, signal_handler)

    stat = os.stat(input_file)
    block_size = stat.st_blksize
    console.log("Block size:", block_size)
    columns = list(Progress.get_default_columns())
    columns.insert(0, SpinnerColumn("bouncingBar"))
    columns.insert(-1, FileSizeColumn())
    columns.insert(-1, TotalFileSizeColumn())
    columns.insert(-1, TransferSpeedColumn())
    columns.insert(-1, TimeElapsedColumn())
    columns[-1] = TimeRemainingColumn(True)

    with Progress(*columns, console=console, refresh_per_second=12, expand=True) as progress:
        with open(input_file, "rb") as input_buffer, open(output_file, "wb") as output_buffer:
            task = progress.add_task(f"Flashing {input_file}->{output_file}", total=stat.st_size)
            while True:
                data = input_buffer.read(block_size)
                if not data:
                    break
                output_buffer.write(data)
                if sync_writes:
                    output_buffer.flush()
                    os.fsync(output_buffer.fileno())
                progress.advance(task, len(data))
        task2 = progress.add_task(f"Generating hash for {input_file}", total=stat.st_size)
        with open(input_file, "rb") as input_buffer:
            _hash = generate_hash(input_buffer, hash_type, task2, progress, block_size)
        console.log("Hash generated:", _hash)
        console.log("Verifying hash...")
        task3 = progress.add_task(f"Verifying hash for {output_file}", total=stat.st_size)
        with open(output_file, "rb") as output_buffer:
            file_hash = generate_hash(output_buffer, hash_type, task3, progress, block_size)
        console.log("Hash generated:", file_hash)
    if file_hash == _hash:
        console.print(f"[green]Hashes match![/]")
    else:
        console.print(f"[red]Hashes do not match![/]")
        console.print(f"[cyan]{hash_type} Source[/]: {_hash}")
        console.print(f"[cyan]{hash_type} Target[/]: {file_hash}")



if __name__ == "__main__":
    if sys.argv[1] == "verify":
        sys.argv.pop(1)
        verify()
    else:
        main()
