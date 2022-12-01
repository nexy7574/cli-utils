import io
import click
import os
import tempfile
import pathlib
import random


@click.command()
@click.option("--passes", default=100, help="Number of passes to run.")
@click.option(
    "--safety-boundary",
    "--boundary",
    default=5,
    help="Percentage of the start & end of file to leave untouched."
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
def main(passes: int, safety_boundary: int, file: str):
    """Ruins different parts of a file. Not much use here, however can be used to create cool effects with media."""
    fp = file
    with click.open_file(file, "rb") as file:
        print("Reading file...", end="\r")
        buffer = io.BytesIO(file.read())
        buffer.seek(0)

        size = len(buffer.read())
        buffer.seek(0)

        bound_pct = size * (0.01 * safety_boundary)
        bound_start = round(bound_pct)
        bound_end = round(size - bound_pct)

        print("Creating temporary file...", end="\r")
        _p = pathlib.Path(fp).name
        # noinspection PyPep8Naming
        TEMP_FN = f"CORRUPTED-{os.urandom(3).hex()}-{_p}"
        with open(TEMP_FN, "wb+") as temp:
            for pass_no in range(passes):
                print(f"Corrupting file buffer... ({pass_no+1:,}/{passes:,} passes)", end="\r")
                buffer.seek(random.randint(bound_start, bound_end))
                buffer.write(os.urandom(random.randint(64, 2048)))
                buffer.seek(0)
            buffer.seek(0)
            print(f"Corrupted file buffer! ({pass_no+1:,}/{passes})" + ("\u200b" * 30))
            print("Writing file...", end="\r")
            temp.write(buffer.read())
        print("Written corrupted file to ./" + TEMP_FN)


if __name__ == "__main__":
    main()
