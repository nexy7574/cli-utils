"""
This script is designed to be run by a crontab every 30 minutes or so.
It reads a list configuration file to forward, with the below syntax:

internal_port [external_port] protocol
"""
import re
import subprocess
import sys
import textwrap
import time
import os
import random
import socket
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.progress import track


def main():
    console = Console()
    console.log("Interactive terminal." if sys.__stdin__.isatty() else "Non-interactive terminal.")
    home_dir = Path(__file__).parent


    our_ip = os.getenv("IP", socket.gethostbyname(socket.gethostname() + ".local"))

    console.log("Forwarding traffic to %s." % our_ip)
    file = home_dir / "upnpc-redirects.txt"
    if not file.exists():
        cfg = Path.home() / ".config" / "cli-utils"
        cfg.mkdir(exist_ok=True, parents=True)
        example_txt = textwrap.dedent(
            """# Example configuration file
            # The format for this file is: internal_port [external_port?] protocol
            #
            # Protocol can be any of the following (case insensitive):
            # * TCP
            # * UDP
            # * BOTH (creates two rules for TCP and UDP()
            #
            # Internal port must be the port that your service is listening to on this machine
            # External port may be excluded, and if not provided, defaults to internal_port
            #
            # For example:
            # 22 2222 TCP  -> Forwards whatever service is on localhost:22 to your_public_ip:2222
            # 80 tcp  -> Forwards whatever service is on localhost:80 to your_public_ip:80
            # You can also specify a rule multiple times (but be careful not to overlap)
            # 80 8080 tcp
            # 80 80 tcp
            # 80 8000 tcp
            # All of those redirect localhost:80 to public:[80/8080/8000]"""
        )
        file = cfg / "upnpc-redirects.txt"
        if not file.exists():
            file.write_text(example_txt)
            console.log(f"No config file found. Please edit {file.absolute()}.")
            sys.exit()

    try:
        with file.open() as redirects_raw:
            data = redirects_raw.readlines()
    except FileNotFoundError:
        if "--dry" not in sys.argv:
            console.log("No file called 'upnpc-redirects.txt' exists at %s. Please create it." % home_dir)
            sys.exit()
        else:
            data = ["22 both", "200 tcp", "80 tcp", "443 tcp", "8080 tcp", "2222 tcp", "6969 udp"]

    existing_map: Dict[str, set] = {}

    if "--dry" not in sys.argv:
        lineRegex = re.compile(
            r"^\s*\d+\s(TCP|UDP)\s+(?P<port>\d{1,5})->(?P<ext>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}).+$",
            re.IGNORECASE + re.VERBOSE,
        )
        with console.status("Fetching existing UPNP entries", spinner="bouncingBall") as status:
            result = subprocess.run(("upnpc", "-L"), capture_output=True, encoding="utf-8")
            if "(Invalid Action)" in result.stdout:
                # Doesn't have support for IGD:2
                status.update("Fetching existing UPNP ports (IGD:2 unavailable)")
                result = subprocess.run(("upnpc", "-l"), capture_output=True, encoding="utf-8")
            for line in result.stdout.splitlines():
                if lineMatch := lineRegex.match(line):
                    ip, ext_port = lineMatch.group("ext").split(":")
                    int_port = lineMatch.group("port")
                    if not existing_map.get(ip):
                        existing_map[ip] = {int_port, ext_port}
                    else:
                        existing_map[ip].update({int_port, ext_port})
        console.log(
            f"Logged {len(existing_map)} IP ports with {sum(len(existing_map[x]) for x in existing_map.keys())}"
            f" used ports."
        )


    # NOTE: Some of the following code has been taken from my in-house modification of this script
    # and consequently may not work properly on all systems.
    def parse_data(_line, *, force_protocol: str = ...):
        if _line.startswith("#") or not line.strip():  # comment or whitespace line
            return ..., ..., ...
        if len(_line.split(" ")) == 3:
            internal_port, external_port, protocol = _line.split(" ")
            assert external_port.isdigit(), f"{external_port!r} is not an integer!"
        elif len(_line.split(" ")) == 2:
            internal_port, protocol = _line.split(" ")
        else:
            raise ValueError(f"Too many arguments, got {len(_line.split(' '))}, expected 2-3.")
        if force_protocol is not ...:
            protocol = force_protocol
        assert internal_port.isdigit(), f"{internal_port!r} is not an integer!"
        assert protocol.lower().strip() in ("tcp", "udp", "both"), f"{protocol!r} is not TCP, UDP, or BOTH."
        try:
            # noinspection PyUnboundLocalVariable
            return internal_port, external_port, protocol.lower().strip()
        except NameError:  # duck typing gang
            return internal_port, ..., protocol.lower().strip()


    entries = []

    for line_number, line in enumerate(data):
        if not bool(line) or line.startswith("#"):
            continue
        try:
            i, e, p = parse_data(line)
            if i is ... and e is ... and p is ...:
                continue  # empty or comment line
            assert i is not ...
            assert p is not ...
            for ip_addr, ports in existing_map.items():
                if e and e in ports:
                    try:
                        hostname = socket.gethostbyaddr(ip_addr)
                    except socket.herror:
                        hostname = "%s-unknown-hostname" % ip_addr
                    console.log(f"External port {e} is [red]already in use[/] by {ip_addr} ({hostname}). Ignoring.")
                    # In the future we will have the option to automatically override
                    continue
        except AssertionError as e:
            console.log(f"Invalid argument on line {line_number+1}: [red bright]`{e!s}`[/]")
        except ValueError as e:
            console.log(f"Invalid argument count on line {line_number+1}: [bright red]`{e!s}`[/]")
        except Exception as e:
            console.log(f"[red bright]Fatal exception while parsing line {line_number+1}: `{e!s}`[/]")
        else:
            arguments = ["upnpc", "-a", our_ip, i]
            if e is ...:
                arguments.append(i)
            else:
                arguments.append(e)

            if p == "both":
                arguments.append("tcp")
                entries.append(arguments.copy())
                arguments[-1] = "udp"
                entries.append(arguments.copy())
            else:
                arguments.append(p)
                entries.append(arguments.copy())

    for entry in track(entries, description=f"Forwarding {len(entries)} ports.", transient=True, console=console):
        if "--dry" in sys.argv:
            console.print("Running", "{!r}".format(" ".join(entry)))
            time.sleep(random.randint(5, 20) / 10)
            continue
        if not sys.__stdout__.isatty():
            console.log("Running %r" % " ".join(entry))
        result = subprocess.run(entry, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode != 0:
            console.log(f"[red]Got status code `{result.returncode}` on command {' '.join(entry)!r}.")


if __name__ == "__main__":
    main()
