import base64
import os
import random
import shutil
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Literal, Tuple
from urllib.parse import urlparse

import click
import httpx
import psutil
import rich
from rich.markup import escape
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm

from . import __version__ as version
from .utils.generic__rendering import Emoji
from .utils.generic__size import (
    bytes_to_human,
    convert_soft_data_value_to_hard_data_value,
)

SPINNERS = ("arc", "arrow3", "bouncingBall", "bouncingBar", "dots", "dots12", "earth", "pong", "line", "aesthetic")


def supported_download_protocol(proto: str) -> bool:
    """Checks if the protocol is supported."""
    return proto.lower() in ("http", "https")


def supported_proxy_protocol(proto: str) -> bool:
    """Checks if the proxy protocol is supported."""
    return proto.lower() in ("http", "https", "socks4", "socks5")


def user_agent(name: str = "default") -> str:
    """Returns the default user agent"""
    names = {
        "default": "Mozilla/5.0 (compatible; cli-utils/{}, +https://github.com/EEKIM10/cli-utils)".format(version),
        "firefox": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0",
        "chrome": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/92.0.4515.159 Safari/537.36",
        "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_5_2) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.1.2 Safari/605.1.15",
        "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.84",
        "opera": "Opera/9.80 (X11; Linux x86_64; U; en) Presto/2.10.289 Version/12.02",
        "ie": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Trident/7.0; rv:11.0) like Gecko",
    }
    if name.lower() in names:
        return names[name.lower()]
    return name


def log_debug(message: str, console: rich.console.Console) -> None:
    """Logs a debug message."""
    context = click.get_current_context()
    if context is not None:
        if context.params["debug"]:
            console.print(f"[dim i]Debug[/]: {message}")


class Meta:
    """Meta container to use for HTTP related functions."""

    def __init__(self, session: httpx.Client, console: rich.console.Console, compression: bool):
        self.session = session
        self.console = console
        self.compression = compression
        if not compression:
            # 'Identity' disables compression. Fall back to accepting compressed files.
            self.session.headers["Accept-Encoding"] = "identity;q=0.9, *;q=0.1"
        self.content_size = 0
        self._response: Dict[str, None | int | Dict[str, str]] = {"status": None, "headers": None}

    @staticmethod
    def params(step: str) -> Dict[str, str] | None:
        """Returns debug params if debugging is enabled."""
        context = click.get_current_context()
        if context is not None:
            if context.params["debug"]:
                return {"x-step": step}
        return

    def detect_content_size(self, url: str, method: str = "HEAD") -> int:
        """Tries to detect the size of the target download.
        If no result can be found, returns 0."""
        # check cache first
        if self.content_size:
            return self.content_size
        if self._response["status"] is not None and self._response["headers"] is not None:
            if self._response["headers"].get("content-length"):
                return int(self._response["headers"]["content-length"])

        with self.session.stream(method, url, params=self.params("detect-content-size")) as response:
            if response.status_code == 405 and method == "HEAD":
                log_debug("(HEAD method not allowed, trying GET", self.console)
                return self.detect_content_size(url, "GET")
            self._response["status"] = response.status_code
            self._response["headers"] = response.headers
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

    def check_for_basic_authentication(self, url: str, method: str) -> Tuple[str, str] | None | Literal[False]:
        """Checks if the URL requires basic authentication.

        If the URL responds with 401 and has www-authenticate with basic, the function will pause and ask for a username
        and password. If either are not given, none is returned.
        If authentication is not required, False is returned.
        If authentication is required but is not Basic, or not found, RuntimeError is raised.
        If 403 is returned, it is assumed authentication cannot continue.
        Any status code other than 401 or 403 is treated as okay and unauthenticated."""
        with self.session.stream(
            method,
            url,
            params=self.params("check-for-basic-authentication"),
        ) as response:
            if response.status_code == 405:
                assert method == "HEAD", "HEAD is not supported."
            self._response["status"] = response.status_code
            self._response["headers"] = response.headers
            if response.status_code == 401:
                header = response.headers.get("www-authenticate")
                if not header:
                    raise RuntimeError("Server responded with 401 but did not provide a www-authenticate header.")
                if header.lower().startswith("basic"):
                    self.console.print(Emoji.WARNING + "This URL requires basic authentication.")
                    self.console.print(Emoji.INFO + "Please enter your username and password below.")
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
            auth = self.check_for_basic_authentication(url, "HEAD")
        except AssertionError:
            if click.get_current_context().params["debug"]:
                self.console.log(f"[yellow]{Emoji.WARNING} Server does not support HEAD, falling back to streamed GET.")
            auth = self.check_for_basic_authentication(url, "GET")
        except RuntimeError as e:
            self.console.print(
                f"{Emoji.WARNING} Unable to verify authentication requirement: [red]{escape(str(e))}[/red]"
            )
            return
        if auth and isinstance(auth, tuple):
            self.session.auth = auth

    def download(self, url: str, file: Path, chunk_size: int, rate_limit: int):
        """Actual downloading logic.

        This function is a generator that yields the amount of bytes downloaded.
        """
        last_chunk_unchoked = 0
        with self.session.stream("GET", url, params=self.params("download")) as response:
            response: httpx.Response
            response.raise_for_status()
            self._response["status"] = response.status_code
            self._response["headers"] = response.headers
            log_debug(f"[gray]Response headers:\n{response.headers}", self.console)
            with file.open("wb") as file:
                function = response.iter_bytes if self.compression else response.iter_raw
                # noinspection PyArgumentList
                for n, chunk in enumerate(function(chunk_size=chunk_size)):
                    log_debug("[gray]Chunk #{:,}: {}".format(n, bytes_to_human(len(chunk))), self.console)
                    file.write(chunk)
                    yield len(chunk)
                    last_chunk_unchoked += len(chunk)

                    if rate_limit:
                        if last_chunk_unchoked >= rate_limit:
                            log_debug(f"[gray]{last_chunk_unchoked} vs {rate_limit}, waiting 1 second.", self.console)
                            time.sleep(0.5)
                            last_chunk_unchoked = 0
                        elif last_chunk_unchoked + chunk_size >= rate_limit:
                            log_debug(
                                f"{last_chunk_unchoked}+{chunk_size} vs {rate_limit}, waiting .5 seconds.", self.console
                            )
                            time.sleep(0.5)


def determine_filename_from_url(url: str) -> str:
    """Determine the filename from a URL, returning a filesystem safe file name."""
    parsed_url = urlparse(url)
    return parsed_url.path.split("/")[-1]


@click.command()
@click.option(
    "--custom-user-agent", "--user-agent", "-U", type=str, default="default", help="Custom user agent to use."
)
@click.option("--keep-temp-files", "-K", is_flag=True, help="Keeps any temporary files after download.")
@click.option("--disable-compression", "-D", is_flag=True, help="Disables gz/br/deflate compression.")
@click.option("--reserve/--no-reserve", default=True, help="Reserves the file size before downloading.")
@click.option("--timeout", "-T", type=int, default=60, help="Request timeout in seconds.")
@click.option("--disable-timeout", is_flag=True, help="Disables request timeout.")
@click.option("--follow-redirects/--no-follow-redirects", default=True, help="Follow redirects.")
@click.option("--max-redirects", "-R", type=int, default=10, help="Maximum number of redirects to follow.")
@click.option("--ssl/--no-ssl", default=True, help="Toggles verifying SSL certs.")
@click.option("--h2/--no-h2", default=True, help="Use HTTP/2 if available.")
@click.option("--proxy-uri", "-p", type=str, help="Proxy URI to use. HTTP/SOCKS supported.", default=None)
@click.option("--output", "-o", type=click.Path(allow_dash=True), default="auto", help="Output file or directory.")
@click.option("--chunk-size", "-c", default="4K", help="The chunk size to download with.")
@click.option("--debug", is_flag=True, help="Enables debug mode.")
@click.option("--rate-limit", "-r", type=str, default="0", help="Rate limit in bytes per second. 0 for unlimited.")
@click.argument("url")
def main(
    custom_user_agent: str,
    keep_temp_files: bool,
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
    debug: bool,
    rate_limit: str,
    url: str,
):
    """Naive HTTP file downloader.

    By default, all downloads are saved to $HOME/Downloads.
    If that directory does not exist, the current working directory is used.
    You can, however, pass a directory or fully qualified path to --output instead.

    User agent can either be a browser name (e.g. chrome, firefox, edge, ie, safari, opera, etc.), or a custom string.

    Note on disabling compression: Disabling compression will mean that the data is not decompressed before being
    written to disk. This can help downloading pre-compressed files, as remote servers will report the size of
    the compressed file, not the decompressed amount.
    On the contrary, this means you will have to manually de-compress the file, if the server even lets you.
    Disabling compression ONLY DISABLES ON-THE-FLY DECOMPRESSION! Compressed files may still be downloaded.

    Warning on disabling SSL verification: Disabling SSL verification is a bad idea. It is recommended to only do this
    if you know what you are doing. This option is provided for convenience, not for security.
    """
    _tf = None
    if timeout != 60 and disable_timeout:
        raise click.UsageError("You cannot specify both --timeout and --disable-timeout.")

    try:
        chunk_size_bytes = round(convert_soft_data_value_to_hard_data_value(chunk_size))
    except ValueError as e:
        click.secho(str(e), err=True, fg="red")
        sys.exit(1)

    console = rich.get_console()
    _parsed = urlparse(url)
    if not supported_download_protocol(_parsed.scheme):
        raise click.UsageError(f"Unsupported protocol in URL: {_parsed.scheme!r} (supported: http/s)")

    remove_file_on_failure = False
    if output == "auto":
        if (Path.home() / "Downloads").exists():
            directory = Path.home() / "Downloads"
        else:
            directory = Path.cwd()
        file = directory / determine_filename_from_url(url)
    elif output == "-":
        _tf = NamedTemporaryFile(mode="wb", delete=not keep_temp_files)
        file = Path(_tf.name)
        console.print("[dim i]Downloading to temporary file [cyan]{}[/] before writing to stdout.".format(file))
    else:
        file = Path(output)
        if file.is_dir():
            file = file / determine_filename_from_url(url)

    file = file.resolve().absolute()
    if file.exists():
        new_file = file
        if not Confirm.ask(
            f"{Emoji.WARNING} File [cyan]{escape(str(new_file))}[/] already exists. Overwrite?", default=False
        ):
            parts = new_file.name.split(".")
            parts.insert(-1, str(len(list(file.glob("*")))))
            file = new_file.with_name(".".join(parts))
            console.print(f"{Emoji.INFO} Saved to enumerated file name {escape(file.name)!r}.")

    console.print(f"{Emoji.INFO} [blue]Downloading [cyan]{escape(url)}[/] to [cyan]{escape(str(file))}[/].")
    kwargs = {
        "headers": {"User-Agent": user_agent(custom_user_agent)},
        "http2": h2,
        "follow_redirects": follow_redirects,
        "max_redirects": max_redirects,
        "verify": ssl,
        "timeout": httpx.Timeout(None if disable_timeout else timeout),
    }
    if proxy_uri:
        _parsed = urlparse(proxy_uri)
        if not supported_proxy_protocol(_parsed.scheme):
            raise click.UsageError(f"Unsupported proxy protocol: {_parsed.scheme!r} (supported: http/s, socks4/5)")
        kwargs["proxies"] = proxy_uri
    session = httpx.Client(**kwargs)
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
                default=False,
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
                        expand=True,
                    ) as progress:
                        task = progress.add_task("Reserving space", filename=str(file), total=meta.content_size)
                        bytes_remaining = meta.content_size
                        while bytes_remaining > 0:
                            chunk_size = min(bytes_remaining, 1024 * 1024 * 4)
                            try:
                                progress.advance(task, _file.write(os.urandom(chunk_size)))
                                # Writing urandom should bypass disks' caches to some extent, opposed to zeros.
                            except OSError as e:
                                if e.errno == 28:
                                    console.print(f"{Emoji.WARNING} [red]Disk is full.")
                                    _file.close()
                                    file.unlink()
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
        expand=True,
    ) as progress:
        fn = str(file) if len(file.parents) <= 4 else file.name
        task_id = progress.add_task("download", filename=fn, total=meta.content_size or None)
        try:
            rl = round(convert_soft_data_value_to_hard_data_value(rate_limit))
            for chunk in meta.download(url, file, chunk_size_bytes, rl):
                progress.update(task_id, advance=chunk)
        except httpx.HTTPError as e:
            if remove_file_on_failure:
                file.unlink()
            console.print(f"{Emoji.CROSS} [bold red]HTTP Error[/] occurred while downloading [cyan]{escape(url)}[/].")
            console.print(f"Error: [red]{e!r}")
            if remove_file_on_failure:
                file.unlink()
                if _tf:
                    _tf.close()
            sys.exit(1)
        except Exception:
            if remove_file_on_failure:
                file.unlink()
                if _tf:
                    _tf.close()
            raise
        else:
            console.print(
                f"[green]\N{white heavy check mark} Downloaded [cyan]{escape(url)}[/cyan] to "
                f"[cyan]{escape(str(file))}[/cyan]."
            )

    if _tf:
        stat = file.stat()
        try:
            if psutil.virtual_memory().available < stat.st_size:
                console.print(f"{Emoji.WARNING} [gold]File is larger than available RAM.")
                raise MemoryError
            _text = file.read_text()
            console.print(f"{Emoji.INFO} [blue]File is text, writing to pager.[/]")
            click.echo_via_pager(_text)
        except UnicodeDecodeError:
            _text = file.read_bytes()
            # echo base64 encoded file
            with console.status("Encoding file to base64", spinner=random.choice(SPINNERS)):
                b64 = base64.b64encode(_text).decode("utf-8")
            click.echo(b64, err=True)
            console.print(f"{Emoji.INFO} [blue]File is binary, displayed base64 encoded.[/]")
        except MemoryError:
            console.print(f"{Emoji.WARNING} [gold]File is too large to display.")
            if os.access(Path.cwd(), os.W_OK):
                save_dir = Path.cwd() / file.name
            elif Path.home() / "Downloads" and os.access(Path.home(), os.W_OK):
                save_dir = Path.home() / "Downloads" / file.name
            elif os.access(Path.home(), os.W_OK):
                save_dir = Path.home() / file.name
            else:
                console.log(f"{Emoji.CROSS} [bold red]Unable to find a suitable directory to save the file.")
                save_dir = None
            if save_dir:
                with console.status(f"Copying temporary file to {save_dir.parent}", spinner=random.choice(SPINNERS)):
                    shutil.copy2(_tf.name, Path.cwd() / file.name)
                console.print(f"{Emoji.INFO} [blue]Temporary file [cyan]{file}[/cyan] is available at {save_dir}.[/]")
        finally:
            _tf.close()
            # try:file.unlink()
            # except:pass


if __name__ == "__main__":
    main()
