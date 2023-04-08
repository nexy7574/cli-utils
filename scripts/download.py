import os
import sys
from typing import Tuple, Literal

import rich
import click
import httpx
import random
import logging
from urllib.parse import urlparse
from pathlib import Path
from rich.markup import escape
from rich.prompt import Confirm
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn, DownloadColumn, SpinnerColumn, track
from .utils.generic__rendering import Emoji
from .utils.generic__size import convert_soft_data_value_to_hard_data_value, bytes_to_human

SPINNERS = ("arc", "arrow3", "bouncingBall", "bouncingBar", "dots", "dots12", "earth", "pong", "line", "aesthetic")


class Meta:
    """Meta container to use for HTTP related functions."""
    def __init__(self, session: httpx.Client, console: rich.console.Console, compression: bool):
        self.session = session
        self.console = console
        self.compression = compression
        if not compression:
            self.session.headers["Accept-Encoding"] = "identity;q=0.9, *;q=0.1"
        self.content_size = 0

    def detect_content_size(self, url: str) -> int:
        """Tries to detect the size of the target download.
        If no result can be found, returns 0."""
        with self.session.stream("GET", url) as response:  # HEAD might not be supported.
            if response.status_code in range(200, 300):
                header = response.headers.get("content-length")
                if header:
                    return int(header)
                else:
                    self.console.print(
                        f"{Emoji.WARNING} Unable to detect content size, server did not tell us.\n"
                        f"{Emoji.INFO} Continuing without reserving space.\n"
                        f"{Emoji.INFO} ETA and progress will not be available."
                    )
                    return 0
            else:
                self.console.print(
                    f"{Emoji.WARNING} Unable to detect content size, server responded with {response.status_code}.\n"
                    f"{Emoji.INFO} Continuing without reserving space.\n"
                    f"{Emoji.INFO} ETA and progress will not be available."
                )
                return 0

    def check_for_basic_authentication(self, url: str) -> Tuple[str, str] | None | Literal[False]:
        """Checks if the URL requires basic authentication.

        If the URL responds with 401 and has www-authenticate with basic, the function will pause and ask for a username
        and password. If either are not given, none is returned.
        If authentication is not required, False is returned.
        If authentication is required but is not Basic, or not found, RuntimeError is raised.
        If 403 is returned, it is assumed authentication cannot continue.
        Any status code other than 401 or 403 is treated as okay and unauthenticated."""
        # Send a preliminary GET request to check if the URL requires authentication.
        with self.session.stream("GET", url) as response:
            if response.status_code == 401:
                header = response.headers.get("www-authenticate")
                if not header:
                    raise RuntimeError("Server responded with 401 but did not provide a www-authenticate header.")
                if header.lower().startswith("basic"):
                    self.console.print(Emoji.WARNING+ "This URL requires basic authentication.")
                    self.console.print(Emoji.INFO+ "Please enter your username and password below.")
                    username = self.console.input("Username: ")
                    password = self.console.input("Password (will not echo): ", password=True)
                    if not username or not password:
                        self.console.print(
                            Emoji.WARNING + "One or more credentials were not provided. Continuing anyway."
                        )
                    return username, password
                else:
                    raise RuntimeError("Only Basic authentication is supported. Got %r" % header)
            elif response.status_code == 403:
                raise RuntimeError(
                    "Server responded with 403 (Forbidden). You may not have permission to access this resource."
                )
            else:
                return False

    def set_auth_if_needed(self, url: str):
        """Sets the authentication for the session if needed."""
        try:
            auth = self.check_for_basic_authentication(url)
        except RuntimeError as e:
            self.console.print(
                f"{Emoji.WARNING} Unable to verify authentication requirement: [red]{escape(str(e))}[/red]"
            )
        else:
            if auth and isinstance(auth, tuple):
                self.session.auth = auth

    def download(self, url: str, file: Path, chunk_size: int):
        """Actual downloading logic.

        This function is a generator that yields the amount of bytes downloaded.
        """
        with self.session.stream("GET", url) as response:
            response: httpx.Response
            response.raise_for_status()
            with file.open("wb") as file:
                function = response.iter_bytes if self.compression else response.iter_raw
                # noinspection PyArgumentList
                for chunk in function(chunk_size=chunk_size):
                    file.write(chunk)
                    yield len(chunk)


def determine_filename_from_url(url: str) -> str:
    """Determine the filename from a URL, returning a filesystem safe file name."""
    parsed_url = urlparse(url)
    return parsed_url.path.split("/")[-1]

@click.command()
@click.option("--disable-compression", "-D", is_flag=True, help="Disables gz/br/deflate compression.")
@click.option("--reserve/--no-reserve", default=True, help="Reserves the file size before downloading.")
@click.option("--timeout", "-T", type=int, default=60, help="Request timeout in seconds.")
@click.option("--disable-timeout", is_flag=True, help="Disables request timeout.")
@click.option("--follow-redirects/--no-follow-redirects", default=True, help="Follow redirects.")
@click.option("--max-redirects", "-R", type=int, default=10, help="Maximum number of redirects to follow.")
@click.option("--ssl/--no-ssl", default=True, help="Toggles verifying SSL certs.")
@click.option("--h2/--no-h2", default=True, help="Use HTTP/2 if available.")
@click.option("--proxy-uri", "-p", type=str, help="Proxy URI to use. HTTP/SOCKS supported.", default=None)
@click.option("--output", "-o", type=click.Path(), default="auto", help="Output file or directory.")
@click.option("--chunk-size", "-c", default="4M", help="The chunk size to download with.")
@click.argument("url")
def main(
        disable_compression: bool,
        reserve: bool,
        timeout: int,
        disable_timeout: bool,
        follow_redirects: bool,
        max_redirects: int,
        ssl: bool,
        h2: bool,
        output: str,
        proxy_uri: str | None,
        chunk_size: str,
        url: str
):
    """Naive HTTP file downloader.

    By default, all downloads are saved to $HOME/Downloads.
    If that directory does not exist, the current working directory is used.
    You can, however, pass a directory or fully qualified path to --output instead.

    Note on disabling compression: Disabling compression will mean that the data is not decompressed before being
    written to disk. This can help downloading pre-compressed files, as remote servers will report the size of
    the compressed file, not the decompressed amount.
    On the contrary, this means you will have to manually de-compress the file, if the server even lets you.
    Disabling compression ONLY DISABLES ON-THE-FLY DECOMPRESSION! Compressed files may still be downloaded.

    Warning on disabling SSL verification: Disabling SSL verification is a bad idea. It is recommended to only do this
    if you know what you are doing. This option is provided for convenience, not for security.
    """
    if timeout != 60 and disable_timeout:
        raise click.UsageError("You cannot specify both --timeout and --disable-timeout.")

    try:
        chunk_size_bytes = round(convert_soft_data_value_to_hard_data_value(chunk_size))
    except ValueError as e:
        click.secho(str(e), err=True, fg="red")
        sys.exit(1)

    console = rich.get_console()
    remove_file_on_failure = False
    if output == "auto":
        if (Path.home() / "Downloads").exists():
            directory = Path.home() / "Downloads"
        else:
            directory = Path.cwd()
        file = directory / determine_filename_from_url(url)
    else:
        file = Path(output)
        if file.is_dir():
            new_file = file / determine_filename_from_url(url)
            if new_file.exists():
                if not Confirm.ask(
                        f"{Emoji.WARNING} File [cyan]{escape(str(new_file))}[/] already exists. Overwrite?",
                        default=False
                ):
                    parts = new_file.name.split(".")
                    parts.insert(-1, str(len(list(file.glob("*")))))
                    new_file = new_file.with_name(".".join(parts))
            file = new_file

    file = file.resolve().absolute()

    console.print(f"{Emoji.INFO} [blue]Downloading [cyan]{escape(url)}[/] to [cyan]{escape(str(file))}[/].")
    kwargs = {
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; cli-utils/{}, +https://github.com/EEKIM10/cli-utils)"
        },
        "http2": h2,
        "follow_redirects": follow_redirects,
        "max_redirects": max_redirects,
        "verify": ssl,
        "timeout": httpx.Timeout(None if disable_timeout else timeout),
    }
    if proxy_uri:
        kwargs["proxies"] = proxy_uri
    session = httpx.Client(
        **kwargs
    )
    meta = Meta(session, console, not disable_compression)
    with console.status("Checking for authentication requirements", spinner=random.choice(SPINNERS)) as status:
        meta.set_auth_if_needed(url)
        status.update("Checking download size")
        meta.content_size = meta.detect_content_size(url)
    if meta.content_size:
        # if the content is >50 megabytes ask the user if they're sure they want to save
        if meta.content_size > 50 * 1024 * 1024:
            if not Confirm.ask(
                    f"{Emoji.WARNING} File size is [bold red]{bytes_to_human(meta.content_size)}[/]. "
                    f"Are you sure you want to download it?",
                    default=False
            ):
                sys.exit(0)
        if reserve:
            skip = False
            if not file.exists():
                remove_file_on_failure = True
            else:
                stat = file.stat()
                if stat.st_size >= meta.content_size:
                    console.print(f"{Emoji.INFO} [green i]Space already reserved.")
                    skip = True
            if not skip:
                with file.open("wb+") as _file:
                    # Write meta.content_size bytes to the file, in chunks of 4MB.
                    with Progress(
                        SpinnerColumn(random.choice(SPINNERS)),
                        TextColumn("[bold blue]Reserving space"),
                        BarColumn(bar_width=None),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        "[bold]|[/bold]",
                        TransferSpeedColumn(),
                        "[bold]|[/bold]",
                        TimeRemainingColumn(),
                        "left [bold]|[/bold]",
                        DownloadColumn(binary_units=os.name != "nt"),
                        console=console,
                        transient=True,
                        expand=True
                    ) as progress:
                        task = progress.add_task("Reserving space", filename=str(file), total=meta.content_size)
                        bytes_remaining = meta.content_size
                        while bytes_remaining > 0:
                            chunk_size = min(bytes_remaining, chunk_size_bytes)
                            try:
                                progress.advance(task, _file.write(os.urandom(chunk_size)))
                                # Writing urandom should bypass disks' caches to some extent, opposed to zeros.
                            except OSError as e:
                                if e.errno == 28:
                                    console.print(f"{Emoji.WARNING} [red]Disk is full.")
                                    sys.exit(1)
                                else:
                                    raise e
                            bytes_remaining -= chunk_size
                        _file.flush()
                        _file.close()

                        if progress.tasks[task].completed != meta.content_size:
                            written = progress.tasks[task].completed
                            console.print(
                                f"{Emoji.WARNING} [gold]Discrepancy between reserved space and actual size ("
                                f"{written:,} bytes written, {meta.content_size:,} bytes expected)."
                            )
                            if written > meta.content_size:
                                console.print(f"{Emoji.WARNING} [gold]Over-allocated. This should not be an issue.")
                            else:
                                console.print(
                                    f"{Emoji.WARNING} [gold]Under-allocation detected. "
                                    f"This may cause issues if you don't have enough free disk space."
                                )

    with Progress(
        SpinnerColumn(random.choice(SPINNERS)),
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "[bold]|[/bold]",
        TransferSpeedColumn(),
        "[bold]|[/bold]",
        TimeRemainingColumn(),
        "left [bold]|[/bold]",
        DownloadColumn(binary_units=os.name != "nt"),
        console=console,
        transient=True,
        expand=True
    ) as progress:
        fn = str(file) if len(file.parents) <= 4 else file.name
        task_id = progress.add_task("download", filename=fn, total=meta.content_size or None)
        try:
            for chunk in meta.download(url, file, chunk_size_bytes):
                progress.update(task_id, advance=chunk)
        except httpx.HTTPError as e:
            if remove_file_on_failure:
                file.unlink()
            console.print(f"{Emoji.CROSS} [bold red]HTTP Error[/] occurred while downloading [cyan]{escape(url)}[/].")
            console.print(f"Error: [red]{e!r}")
        except Exception:
            if remove_file_on_failure:
                file.unlink()
            raise
        else:
            console.print(
                f"[green]\N{white heavy check mark} Downloaded [cyan]{escape(url)}[/cyan] to "
                f"[cyan]{escape(str(file))}[/cyan]."
            )


if __name__ == '__main__':
    main()
