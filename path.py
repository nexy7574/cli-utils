#!/usr/bin/env python
"""
This simple meta script just adds the `script` directory to path.
"""
import userpath
from pathlib import Path

us = Path(__file__)
scripts_dir = (us / ".." / "scripts").resolve()
scripts = str(scripts_dir)
if not userpath.in_current_path(scripts):
    userpath.append(scripts)
else:
    print("Scripts directory is already in path.")

if userpath.in_new_path(scripts):
    print("Scripts directory is now in path.")

if userpath.need_shell_restart(scripts):
    print("You need to restart your shell for this to take effect.")
