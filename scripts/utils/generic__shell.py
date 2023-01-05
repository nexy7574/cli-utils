import subprocess
import sys
import os
import warnings
from functools import partial
from pathlib import Path
from tempfile import gettempdir


__all__ = ("command_exists", "is_windows", "home", "temp_dir", "stderr", "config_dir")


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


def config_dir() -> Path:
    """Returns the project's production config directory."""
    if os.name != "nt":
        directory = home() / ".config" / "cli-utils"
    else:
        _appdata = os.getenv("LOCALAPPDATA")
        if not _appdata:
            _appdata = os.getenv("APPDATA")
            if not _appdata:
                warnings.warn(RuntimeWarning("Failed to find %APPDATA% - Defaulting to user documents folder"))
                _appdata = "Documents"
        directory = home() / _appdata / "cli-utils"

    directory = directory.expanduser().resolve().absolute()
    directory.mkdir(parents=True, exist_ok=True)
    if not (directory / "README.txt").exists():
        x = directory / "README.txt"
        try:
            x.touch()
            warnings.warn(ResourceWarning(f"May not have write access to {str(directory)!r}"))
        except OSError:
            pass
        else:
            x.write_bytes(
                b"You should not need to edit these files, as they are managed by each tool they're used by.\n"
                b"You should only edit these files if you know what you're doing, as doing so incorrectly will "
                b"(at best) prevent the tools using said configuration files from working."
            )
    return directory
