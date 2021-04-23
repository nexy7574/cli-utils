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

from subprocess import run, PIPE, DEVNULL
import re

from utils.loader import calculateBar


def printPorts(rem):
    n = 0
    for _port, conn_type in rem:
        print(f"{n}: port={_port}, connection_type={conn_type}")
        n += 1


if __name__ == "__main__":
    lineRegex = re.compile(r"^\s+?[0-9]+\s(TCP|UDP)\s+(?P<port>[0-9]{1,5}).+$", re.IGNORECASE + re.VERBOSE)

    print("Detecting UPNP ports...", end="\r")
    detection = run(["upnpc", "-l"], stdout=PIPE, stderr=DEVNULL)

    removable = []

    for line in detection.stdout.decode().splitlines():
        match: re.Match = lineRegex.match(line)
        if not match:
            continue
        removable.append((int(match.group(2)), match.group(1)))

    removable.sort(key=lambda g: g[0])

    printPorts(removable)
    while True:
        value = input("Please enter a number, or list of numbers (separated by space), to revoke: ")
        if value == "PRINT":
            printPorts(removable)
            continue
        if value == "ALL":
            if input("Are you sure you want to delete all upnp entries? [Y/N]\n").lower().strip() == "y":
                values = list(range(len(removable)))
                break
            continue
        try:
            values = list(map(int, value.split(" ")))
        except (ValueError, TypeError):
            print('Invalid argument. Please make sure it is "PRINT", "ALL", or a number/list of numbers.')
            continue
        else:
            break

    print("Deleting ports... ")
    deleted = 0

    # According to pylint, `values` can be undefined.
    # I call BS.
    # noinspection PyUnboundLocalVariable
    for entry_id in values:
        print(calculateBar(deleted, len(values), disable_safety=True), end="\r")
        run(["upnpc", "-d", *removable[entry_id]], stdout=DEVNULL, stderr=DEVNULL)
        deleted += 1
        print(calculateBar(deleted, len(values), disable_safety=True), end="\r")
    print()
    print("Done!")
