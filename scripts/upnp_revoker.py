#!/usr/bin/env python3
"""
This script will use the upnpc client to detect & revoke all/select upnp forwards.

Dependencies:
* miniupnp/upnpc must be installed (apt install miniupnpc, or whatever your package man. is.)

Usage:
[python3] upnp-revoker.py

1. Wait for the script to load
2. It may take some time for the script to get a list of upnp ports, especially if you have a lot.
   This is only because it is wrapping the output of the upnpc command, which itself is slow.
3. A menu should pop up in the format of "(number): port=(port number), connection_type=(TCP or UDP).
   3.1: Type in the number before each port that you'd like to revoke. If you want to revoke multiple at once,
        provide a list of numbers, separated by spaces.
   3.2: If you lost the list of ports, just reply "PRINT".
4. Once the script has finished, it'll say done. You should also make sure it successfully did this by
   running "upnpc -l" yourself.
"""
import socket
import sys
import time
import os
from subprocess import run
import re
from socket import gethostbyaddr

from rich.console import Console
from rich.progress import track
from rich.prompt import Confirm
from rich.table import Table
from rich.traceback import install

console = Console()
if os.name == "nt":
    console.print("This tool is not supported on windows.")
    sys.exit(1)
install(console=console, extra_lines=5, show_locals=True)


def print_ports(rem):
    t = Table("ID", "Port", "Protocol", "Connection Target")
    n = 0
    for _port, conn_type, ext in rem:
        ip, extp = ext.split(":")
        try:
            ext2 = "%s:%s (%s)" % (gethostbyaddr(ip), extp, ext)
        except socket.herror:
            ext2 = ext
        t.add_row(str(n), str(_port), conn_type, ext2)
        n += 1
    console.print(t)


# noinspection PyPep8Naming
def main():
    lineRegex = re.compile(
        r"^\s*\d+\s(TCP|UDP)\s+(?P<port>\d{1,5})->(?P<ext>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}).+$",
        re.IGNORECASE + re.VERBOSE,
    )

    console.log("Detecting UPNP ports...")
    with console.status("Getting UPnP Port Listings", spinner="bouncingBall") as status:
        start = time.time()
        try:
            detection = run(("upnpc", "-L"), capture_output=True, encoding="utf-8")
        except KeyboardInterrupt:
            console.log("Listing cancelled.")
            sys.exit(1)
        if "(Invalid Action)" in detection.stdout:
            # Doesn't have support for IGD:2
            status.update("Fetching existing UPNP ports (IGD:2 unavailable)")
            result = run(("upnpc", "-l"), capture_output=True, encoding="utf-8")
        end = time.time()

    if detection.returncode != 0:
        console.log(
            f"Got return code [red]{detection.returncode}[/] on UPnP List request. Please ensure UPnP is "
            f"enabled on your network."
        )
        sys.exit(detection.returncode)

    removable = []

    for line in detection.stdout.splitlines():
        _match: re.Match = lineRegex.match(line)
        if not _match:
            continue
        removable.append((int(_match.group("port")), _match.group(1), _match.group("ext")))

    removable.sort(key=lambda g: g[0])
    console.log(
        "Detected [{}]{!s}[/] ports in {!s}s.".format(
            "green" if len(removable) else "red", len(removable), round(end - start, 2)
        )
    )

    print_ports(removable)
    values = ...
    while True:
        value = input("Please enter an ID, an IP, or list of IDs (separated by space), to revoke: ")
        if value == "PRINT":
            print_ports(removable)
            continue
        if value == "ALL":
            if Confirm.ask("Are you sure you want to delete all upnp entries?"):
                values = list(range(len(removable)))
                break
            continue
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
            values = [x[0] for x in removable if x[-1].split(":")[0].strip() == value.strip()]
            break
        else:
            try:
                values = list(map(int, value.split(" ")))
            except (ValueError, TypeError):
                console.log(
                    "[red]Invalid argument[/]. Please make sure it is `PRINT`, `ALL`, an IP, or a number/list "
                    "of numbers."
                )
                continue
            else:
                break

    console.log("Removing ports...")
    assert values is not ..., "Values is undefined somehow."
    failed = []
    for port_id in track(values, description=f"Removing {len(values)} ports", console=console, transient=True):
        result = run(["upnpc", "-d", *[str(x) for x in removable[port_id]]], capture_output=True)
        if result.returncode != 0:
            failed.append((port_id, result.returncode))

    for port_id, code in failed:
        console.log(f"[red]Failed to delete port [b]{port_id}[/]: Got return code {code}.[/]")

    console.log("Done!")


if __name__ == "__main__":
    try:
        run(("upnpc", "--help"), capture_output=True)
    except FileNotFoundError:
        console.print("upnpc is not installed. Please install it (usually with a package called `miniupnpc`.")
        sys.exit(1)
    else:
        main()
