import io
import click
import os
import tempfile
import pathlib
import random
from rich import get_console
from rich.progress import track


@click.command()
@click.option("--passes", "-P", default=100, help="Number of passes to run.")
@click.option(
    "--safety-boundary",
    "--boundary",
    "-S",
    default=5,
    help="Percentage of the start & end of file to leave untouched."
)
@click.option(
    "--min-chunk-size",
    "-I",
    default=64,
    help="The minimum size of a chunk to be overwritten in bytes."
)
@click.option(
    "--max-chunk-size",
    "-A",
    default=4096,
    help="The maximum size of a chunk to be overwritten in bytes."
)
@click.argument(
    "file",
    type=click.Path(
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    )
)
def main(
        passes: int,
        safety_boundary: int,
        file: str,
        min_chunk_size: int,
        max_chunk_size: int
):
    """Ruins different parts of a file. Not much use here, however can be used to create cool effects with media."""
    console = get_console()
    fp = file
    with click.open_file(file, "rb") as file:
        console.print("Reading file...", end="\r")
        buffer = io.BytesIO(file.read())
        buffer.seek(0)

        size = len(buffer.read())
        buffer.seek(0)

        bound_pct = size * (0.01 * safety_boundary)
        bound_start = round(bound_pct)
        bound_end = round(size - bound_pct)

        console.print("Creating temporary file...", end="\r")
        _p = pathlib.Path(fp).name
        # noinspection PyPep8Naming
        TEMP_FN = f"CORRUPTED-{os.urandom(3).hex()}-{_p}"
        written = 0
        with open(TEMP_FN, "wb+") as temp:
            for pass_no in track(range(passes), description="Running passes", console=console):
                console.print(f"Corrupting file buffer... ({pass_no+1:,}/{passes:,} passes)", end="\r")
                buffer.seek(random.randint(bound_start, bound_end))
                chunk = os.urandom(random.randint(min_chunk_size, max_chunk_size))
                written += len(chunk)
                buffer.write(chunk)
                buffer.seek(0)
            buffer.seek(0)
            console.print(f"Corrupted file buffer! ({pass_no+1:,}/{passes:,})" + (" " * 10))
            console.print("Writing file...", end="\r")
            temp.write(buffer.read())
        console.print("Written corrupted file to ./" + TEMP_FN)
        console.print("Corrupted {!s}/{!s} ({:.2f}%) of file.".format(written, size, (written / size) * 100))


if __name__ == "__main__":
    main()
