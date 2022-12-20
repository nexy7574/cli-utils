#!/usr/bin/env python3
"""
WARNING!
This script is not tested on other laptops.
My current laptop model is `Asus FX504GD`, running Arch Linux.

DISCLAIMER THAT I DO NOT ACCEPT LIABILITY FOR ANY DAMAGES THIS SCRIPT MAY CAUSE TO YOUR COMPUTER!
THE DEFAULT FAN CONTROL SETTINGS ARE ALWAYS THE BEST, AND LOWERING THEM MAY RESULT IN THERMAL DAMAGE TO COMPONENTS
AND MAY CAUSE YOUR COMPUTER TO OVERHEAT AND BURN DOWN YOUR HOUSE AND MAKE YOU LOSE ALL YOUR LEMONS!

Seriously though, while it is unlikely to cause any damage, I am not responsible for any damage this script may cause.
Lowering the fan "boost" mode and then doing something CPU/GPU intensive over a long period of time may raise
temperatures beyond their safe operating limit, even with thermal throttling, which may result in damage to your computer.

Use at your own risk.

If your computer does not support the interface that this script uses, it will not make any modifications.
The first thing the script does is check for the existence of the interface, and if it does not exist, it will exit.

UPDATE: it appears that, while the boost mode *is* settable, it's not as effective as it is via the Windows software.
It appears that overboost always slows the fans at around 40c to that of the normal mode. Silent will also rev up,
however does not exceed a lower than "balanced" RPM, even when the CPU is overheating. Balanced mode is the default,
so not much to say there.
"""
import io
import os
import sys
import subprocess

import click
from pathlib import Path

__PATH__ = Path("/sys/devices/platform/asus-nb-wmi/fan_boost_mode")

import elevate

MODES = ["balanced", "overboost", "silent"]
MODES_AND_ALIASES = {
    "balanced": ["balanced", "b", "ba", "normal", "n", "default", "d", "0"],
    "overboost": ["overboost", "o", "boost", "bo", "1"],
    "silent": ["silent", "s", "quiet", "q", "2"],
}


@click.group()
def main():
    """
    ASUS FX504 fan control script.
    """
    if not __PATH__.exists():
        click.echo("This script is not supported on your computer (fan_boost_mode not found in FS).")
        sys.exit(4)


@main.command(name="get-mode")
def get_mode():
    """
    Get the current fan mode.
    """
    cur = __PATH__.read_text().strip()
    click.echo(f"Current fan mode: {MODES[int(cur)]} ({cur})")


@main.command(name="set-mode")
@click.argument("mode", type=click.Choice([x for x in MODES_AND_ALIASES.values() for x in x]))
def set_mode(mode: str):
    """
    Sets the current fan mode.

    Note that changes may take a few minutes to fully apply.
    """
    # Get mode from alias
    for k, v in MODES_AND_ALIASES.items():
        if mode in v:
            mode = k
            break
    if os.getuid() != 0:
        click.echo("This script must be run as root to modify the fan mode.")
        old_argv = sys.argv[:]
        if sys.argv[0].endswith(".py"):
            sys.argv[0] = os.getcwd() + "/" + sys.argv[0]
        elevate.elevate()
        sys.argv = old_argv
    click.echo(f"Setting fan mode to {mode}...")
    try:
        __PATH__.write_text(str(MODES.index(mode)))
    except (IOError, PermissionError, subprocess.CalledProcessError) as e:
        click.echo(f"Failed to set fan mode: {e}")
        sys.exit(1)
    click.echo(f"Current fan mode: {MODES[int(__PATH__.read_text().strip())]}")
    click.echo("Done. Note that changes may take a few minutes to apply.")


if __name__ == "__main__":
    main()
