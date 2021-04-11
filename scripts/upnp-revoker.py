#!/usr/bin/env python3
"""
This script will use the upnpc client to detect & revoke all/select upnp forwards.
"""

from subprocess import run, PIPE, DEVNULL
import re

from utils.loader import calculateBar

lineRegex = re.compile(r"^\s+?[0-9]+\s(TCP|UDP)\s+(?P<port>[0-9]{1,5}).+$", re.IGNORECASE + re.VERBOSE)


print("Detecting UPNP ports...", end="\r")
detection = run(["upnpc", "-l"], stdout=PIPE, stderr=DEVNULL)
print("Finished. Finishing up menus...")

removable = []

for line in detection.stdout.decode().splitlines():
    match: re.Match = lineRegex.match(line)
    if not match:
        continue
    removable.append((match.group(2), match.group(1)))


def printPorts(rem):
    n = 0
    for _port, conn_type in rem:
        print(f"{n}: port={_port}, connection_type={conn_type}")
        n += 1


printPorts(removable)
while True:
    value = input("Please enter a number, or list of numbers (separated by space), to revoke: ")
    if value == "PRINT":
        printPorts(removable)
    else:
        try:
            values = list(map(int, value.split(" ")))
        except (ValueError, TypeError):
            print('Invalid argument. Please make sure it is "PRINT", or a number/list of numbers.')
        else:
            break


print("Deleting ports... ")
deleted = 0
for entry_id in values:
    print(calculateBar(deleted, len(values), disable_safety=True), end="\r")
    run(["upnpc", "-d", *removable[entry_id]], stdout=DEVNULL, stderr=DEVNULL)
    deleted += 1
    print(calculateBar(deleted, len(values), disable_safety=True), end="\r")
print()
print("Done!")
