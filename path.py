#!/usr/bin/env python
"""
This simple meta script just adds the `script` directory to path.
"""
import userpath
from rich.console import Console
from pathlib import Path

us = Path(__file__)
scripts_dir = (us / ".." / "scripts").resolve()
scripts = str(scripts_dir)
console = Console()
print = console.print

with console.status("Checking if scripts directory is in path") as status:
    if not userpath.in_current_path(scripts):
        status.update("Adding scripts directory to path")
        userpath.append(scripts)
        status.update("Checking if scripts directory is now in path")
        if userpath.in_new_path(scripts):
            print("Added scripts directory to path.")
    else:
        print("Scripts directory is already in path.")

    status.update("Checking if shell needs restarting")
    if userpath.need_shell_restart(scripts):
        print("You need to restart your shell for this to take effect.")
