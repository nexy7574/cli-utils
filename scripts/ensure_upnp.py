"""
This script is designed to be run by a crontab every 30 minutes or so.
It reads a list configuration file to forward, with the below syntax:

internal_port [external_port] protocol
"""
import subprocess
import sys
import time
from rich.console import Console
from rich.progress import track
from rich.traceback import install

console = Console()
install(console=console, extra_lines=5, show_locals=True)

try:
    with open("./upnpc-redirects.txt") as redirects_raw:
        data = redirects_raw.readlines()
except FileNotFoundError:
    console.log("No file called 'upnpc-redirects.txt' exists. Please create it.")
    sys.exit()


def parse_data(l):
    if len(l.split(" ")) == 3:
        internal_port, external_port, protocol = l.split(" ")
        assert external_port.isdigit(), f"{external_port!r} is not an integer!"
    elif len(l.split(" ")) == 2:
        internal_port, protocol = l.split(" ")
    else:
        raise ValueError(f"Too many arguments, got {len(l.split(' '))}, expected 2-3.")
    assert internal_port.isdigit(), f"{internal_port!r} is not an integer!"
    assert protocol.lower().strip() in ("tcp", "udp"), f"{protocol!r} is not TCP or UDP."
    try:
        return internal_port, external_port, protocol.lower().strip()
    except NameError:  # duck typing gang
        return internal_port, ..., protocol.lower().strip()

entries = []

for line_number, line in enumerate(data):
    try:
        i, e, p = parse_data(line)
    except AssertionError as e:
        console.log(f"Invalid argument on line {line_number+1}: [red bright]`{e!s}`[/]")
    except ValueError as e:
        console.log(f"Invalid argument count on line {line_number+1}: [bright red]`{e!s}`[/]")
    except Exception as e:
        console.log(f"[red bright]Fatal exception while parsing line {line_number+1}: `{e!s}`[/]")
    else:
        arguments = ["upnpc", "-r", i, p]
        if e is not ...:
            arguments.insert(3, e)
        entries.append(arguments)

for entry in track(entries, description=f"Forwarding {len(entries)} ports.", transient=True):
    if "--dry" in sys.argv:
        time.sleep(2.5)
        continue
    subprocess.run(entry, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

