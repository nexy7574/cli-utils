import subprocess
import sys
import os
from functools import partial
from pathlib import Path
from tempfile import gettempdir


__all__ = ("command_exists", "is_windows", "home", "temp_dir", "stderr")


def command_exists(command: str) -> bool:
    """Checks if a command is installed & usable."""
    try:
        subprocess.run(["which", command], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return False
    else:
        return True


stderr = partial(print, file=sys.stderr)


def is_windows() -> bool:
    """Checks if the current OS is Windows."""
    return os.name == "nt"


def home() -> Path:
    """Returns the home directory."""
    return Path.home()


def temp_dir() -> Path:
    """Returns the temp directory."""
    return Path(gettempdir())
