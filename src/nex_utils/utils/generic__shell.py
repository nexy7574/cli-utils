import os
import subprocess
import sys
import warnings
import shutil
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


def migrate_old_config_dir(src: Path, target: Path) -> None:
    if not src.exists():
        return
    if _is_migrated(src.resolve()):
        return

    import rich
    import hashlib
    with rich.get_console().status("[red]Migrating configuration files...") as status:
        shutil.copytree(src, target, dirs_exist_ok=True)
        status.update("[red]Verifying migration was successful...")
        # Check with md5 sum that every file migrated successfully, recursively
        for root, dirs, files in os.walk(target):
            for file in files:
                file_path = Path(root) / file
                src_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                target_hash = hashlib.md5((src / file_path.relative_to(target)).read_bytes()).hexdigest()
                if src_hash != target_hash:
                    raise RuntimeError(f"Failed to migrate {file_path} to {src / file_path.relative_to(target)}")
        status.update("[red]Removing old configuration directory...")
        shutil.rmtree(src)
        status.update("[red]Creating symlink to new configuration directory...")
        os.symlink(target, src, target_is_directory=True)
        (src.resolve() / ".is-migrated").write_bytes(b"1;%s" % target.absolute())

    rich.print("[green dim i]Successfully migrated configuration files!")


def _is_migrated(directory: Path) -> bool:
    loc = directory.resolve() / ".is-migrated"
    if loc.exists():
        return loc.read_text()[0] == '1'
    return False


def old_config_dir() -> Path:
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
    if directory.exists() and not _is_migrated(directory):
        warnings.warn(
            DeprecationWarning(
                f"The old config dir ({directory}) is deprecated in favour of a more project-agnostic "
                f"config directory ({directory / '..' / 'nexus.i-am'}). Configuration files will automatically migrate."
            )
        )
        migrate_old_config_dir(directory, (directory / ".." / "nexus.i-am").resolve().absolute())
    return (directory / ".." / "nexus.i-am").absolute()


def config_dir() -> Path:
    old_config_dir()
    if os.name != "nt":
        directory = home() / ".config" / "nexus.i-am"
    elif os.name == "darwin":
        directory = home() / "Library" / "Application Support" / "nexus.i-am"
    else:
        _appdata = os.getenv("LOCALAPPDATA")
        if not _appdata:
            _appdata = os.getenv("APPDATA")
            if not _appdata:
                warnings.warn(RuntimeWarning("Failed to find %APPDATA% - Defaulting to user documents folder"))
                _appdata = "Documents"
        directory = home() / _appdata / "nexus.i-am"

    if not directory.exists():
        directory.mkdir(0o711, True, True)
    return directory.absolute()


def cache_dir() -> Path:
    """
    Finds an appropriate cache directory for the current platform.
    If none can be found, a temporary directory will be returned.

    :return:
    """
    if os.name == "nt":
        # Stick to %APPDATA%
        _dir = os.getenv("APPDATA")
    else:
        # Stick to ~/.cache
        _dir = os.getenv("XDG_CACHE_HOME", home() / ".cache")

    if not _dir:
        _dir = temp_dir()
    _dir = (Path(_dir) / "nexus.i-am" / "cli-utils")
    _dir.mkdir(0o711, True, True)
    return _dir.absolute()
