import time

import click
import httpx
import random
import json

import rich
from rich.progress import *
from .utils.generic__shell import config_dir


ISO_URLS = [
    ("https://mirror.lon.macarne.com/ubuntu-releases/24.04/ubuntu-24.04-desktop-amd64.iso", 20),
    ("https://releases.ubuntu.com/noble/ubuntu-24.04-desktop-amd64.iso", 20),
    ("https://ask4.mm.fcix.net/ubuntu-releases/24.04/ubuntu-24.04-desktop-amd64.iso", 10),
    ("http://mirror.vorboss.net/ubuntu-releases/24.04/ubuntu-24.04-desktop-amd64.iso", 10),
    ("https://mirrors.20i.com/pub/releases.ubuntu.com/24.04/ubuntu-24.04-desktop-amd64.iso", 10),
    ("https://mirrors.vinters.com/ubuntu-releases/24.04/ubuntu-24.04-desktop-amd64.iso", 10),
    ("https://www.mirrorservice.org/sites/releases.ubuntu.com/24.04/ubuntu-24.04-desktop-amd64.iso", 10)
]
if (cfg := config_dir() / "speedtest-urls.json").exists():
    with open(cfg, "r") as f:
        ISO_URLS = json.load(f)


LAST_RESULT = config_dir() / "speedtest.last-result"
if LAST_RESULT.exists():
    last_result = json.loads(LAST_RESULT.read_text())
else:
    last_result = {"url": "", "speed": 1000}


def bytes_to_megabits(b: int | float) -> float:
    return b * 8 / 1024 / 1024


@click.command()
@click.option("--max-time", default=10, help="The maximum time to run the speedtest for in seconds.")
def main(max_time: int = 10):
    url, gbps = random.choices(
        ISO_URLS,
        weights=[x[1] for x in ISO_URLS]  # weight towards higher-capacity servers
    )[0]
    p = Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn()
    )

    with httpx.Client() as client:
        with p:
            p.console.print(f"Using server: {url} ({gbps} Gbps capacity)")
            start_connect = time.time()
            with client.stream("GET", url) as r:
                r.raise_for_status()
                cl = int(r.headers.get("Content-Length", 6114656256))
                end_connect = time.time()
                p.console.print("Took %.2fms to connect" % ((end_connect - start_connect) * 1000))
                task = p.add_task("Running speedtest", total=cl)
                for chunk in r.iter_bytes():
                    p.update(
                        task,
                        description=f"Running speedtest ({max_time - (time.time() - start_connect):.0f} seconds left)",
                        advance=len(chunk)
                    )
                    if (time.time() - start_connect) > max_time:
                        break
            end_time = time.time()
            speed = bytes_to_megabits(p.tasks[task].completed / (end_time - start_connect))
        rich.print(f"Average speed: {speed:.2f} Mbps ({speed / 8:.2f}MiB/s)")


if __name__ == "__main__":
    main()
