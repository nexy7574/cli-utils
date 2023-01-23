import io
import math

import click
import os
import pathlib
import random
from rich import get_console
from rich.progress import track, wrap_file


def scramble(
    buffer: io.BytesIO,
    bound_start: int,
    bound_end: int,
    min_chunk_size: int,
    max_chunk_size: int,
    passes: int,
    method: str,
):
    written = 0
    buffer.seek(0)
    for pass_no in range(passes):
        buffer.seek(random.randint(bound_start, bound_end))
        if method == "scramble":
            chunk = os.urandom(random.randint(min_chunk_size, max_chunk_size))
        elif method == "reverse":
            chunk = buffer.read(random.randint(min_chunk_size, max_chunk_size))[::-1]
        elif method == "zero":
            chunk = b"\x00" * random.randint(min_chunk_size, max_chunk_size)
        else:
            raise ValueError("Invalid method")
        written += len(chunk)
        buffer.write(chunk)
        buffer.seek(0)
        yield pass_no, written
    return buffer


@click.command()
@click.option("--passes", "-P", default=100, help="Number of passes to run.")
@click.option(
    "--by-percent", "-p", default=None, type=float, help="Percent of file to overwrite. Alternative to --passes."
)
@click.option(
    "--safety-boundary",
    "--boundary",
    "-S",
    default=5.0,
    help="Percentage of the start & end of file to leave untouched.",
)
@click.option("--min-chunk-size", "-I", default=64, help="The minimum size of a chunk to be overwritten in bytes.")
@click.option("--max-chunk-size", "-A", default=4096, help="The maximum size of a chunk to be overwritten in bytes.")
@click.option("--verbose", "-V", is_flag=True, help="Prints the progress of the operation.")
@click.option(
    "--silent",
    "-Q",
    is_flag=True,
    help="Silences all output during scrambling. Takes precedence over --verbose. Speeds up scrambling.",
)
@click.option(
    "--method",
    "-M",
    default="scramble",
    type=click.Choice(["scramble", "reverse", "zero"]),
    help="The method to use for scrambling the file.",
)
@click.argument(
    "file",
    type=click.Path(
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
)
def main(
    passes: int,
    safety_boundary: int,
    file: str,
    min_chunk_size: int,
    max_chunk_size: int,
    verbose: bool,
    by_percent: float,
    silent: bool,
    method: str,
):
    """
    Ruins different parts of a file. Not much use here, however can be used to create cool effects with media.

    Ruin methods:\n
        * scramble: Overwrites chunks with random data from /dev/urandom.\n
        * reverse: Reverses chunks (e.g. text goes from "abc[def]g" to "abc[fed]g").\n
        * zero: Overwrites chunks with null bytes.\n

    """
    console = get_console()
    fp = file
    path = pathlib.Path(fp).expanduser().resolve()
    stat = path.stat()

    with path.open("rb") as file:
        console.print("Reading file...")
        buffer = io.BytesIO()
        with wrap_file(file, stat.st_size, transient=not verbose) as _file:
            while True:
                chunk = _file.read(stat.st_blksize or 1024)
                if not chunk:
                    break
                buffer.write(chunk)
        buffer.seek(0)

        size = len(buffer.read())
        buffer.seek(0)
        if by_percent is not None:
            by_percent = by_percent * 0.01
            if by_percent == 0:
                raise ValueError("Percent must be >0%.")
            elif by_percent >= 0.95:
                raise ValueError("Percent cannot be greater than 95%")
            passes = math.floor(size * by_percent)
            console.log(f"By percent calculated that {passes:,} are needed.")

        bound_pct = size * (0.01 * safety_boundary)
        bound_start = round(bound_pct)
        bound_end = round(size - bound_pct)

        console.print("Creating temporary file...")
        _p = pathlib.Path(fp).name
        # noinspection PyPep8Naming
        TEMP_FN = f"CORRUPTED-{os.urandom(3).hex()}-{_p}"
        written = 0
        with open(TEMP_FN, "wb+") as temp:
            if silent:
                console.print("Scrambling...")
                for _ in scramble(buffer, bound_start, bound_end, min_chunk_size, max_chunk_size, passes):
                    continue
            else:
                for pass_no, written in track(
                    scramble(buffer, bound_start, bound_end, min_chunk_size, max_chunk_size, passes, method),
                    description="Scrambling chunks",
                    console=console,
                    transient=not verbose,
                    total=passes,
                ):
                    if verbose:
                        console.print("[i dim]Pass {:,}: scrambled {:,} bytes.".format(pass_no + 1, written))
            buffer.seek(0)
            console.print(f"Corrupted file buffer! ({pass_no+1:,}/{passes:,})" + (" " * 10))
            console.print("Writing file...")
            chunks = math.ceil(size / 1024)
            for _ in track(range(chunks), description="Writing file", console=console, transient=not verbose):
                chunk = buffer.read(stat.st_blksize or 1024)
                temp.write(chunk)
        console.print("Written corrupted file to ./" + TEMP_FN)
        console.print("Corrupted {!s}/{!s} ({:.2f}%) of file.".format(written, size, (written / size) * 100))


if __name__ == "__main__":
    main()
