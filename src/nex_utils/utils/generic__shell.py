import os
import subprocess
import sys
import warnings
import shutil
import appdirs
import tempfile
from functools import partial
from pathlib import Path

__all__ = ("command_exists", "is_windows", "home", "temp_dir", "stderr", "config_dir", "cache_dir")


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
    return Path(tempfile.gettempdir())


def config_dir() -> Path:
    directory = appdirs.user_config_dir("cli-utils", "nexy7574")

    if not directory.exists():
        directory.mkdir(0o711, True, True)
    return directory.resolve()


def cache_dir() -> Path:
    """
    Finds an appropriate cache directory for the current platform.
    If none can be found, a temporary directory will be returned.

    :return:
    """
    directory = appdirs.user_cache_dir("cli-utils", "nexy7574")
    directory.mkdir(0o711, True, True)
    return directory.resolve()
