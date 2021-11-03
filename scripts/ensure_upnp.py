"""
This script is designed to be run by a crontab every 30 minutes or so.
It reads a list configuration file to forward, with the below syntax:

internal_port [external_port] protocol
"""
import subprocess
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.progress import track
from rich.traceback import install

console = Console()
install(console=console, extra_lines=5, show_locals=True)
home_dir = Path(__file__).parent

try:
    with open(home_dir / "upnpc-redirects.txt") as redirects_raw:
        data = redirects_raw.readlines()
except FileNotFoundError:
    console.log("No file called 'upnpc-redirects.txt' exists at %s. Please create it." % home_dir)
    sys.exit()


def parse_data(l):
    arguments = l.split(" ")
    if len(arguments) == 3:
        internal_port, external_port, protocol = arguments
        assert external_port.isdigit(), f"{external_port!r} is not an integer!"
    elif len(arguments) == 2:
        internal_port, protocol = arguments
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
    if not bool(line) or line.startswith("#"):
        continue
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

for entry in track(entries, description=f"Forwarding {len(entries)} ports.", transient=True, console=console):
    if "--dry" in sys.argv:
        time.sleep(2.5)
        continue
    result = subprocess.run(entry, encoding="utf-8", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        console.log(f"[red]Got status code `{result.returncode}` on command {' '.join(entry)!r}.")
