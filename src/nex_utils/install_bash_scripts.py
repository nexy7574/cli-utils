# This script only exists because I can't include the bash scripts in the pipx package.
# It's a bit hacky however it works.
import os
import subprocess
import sys
from glob import glob
from pathlib import Path
from shutil import copy, move

from .utils.generic__shell import command_exists, home, stderr, temp_dir


def main():
    print("Checking for dependencies...")
    if not command_exists("git"):
        stderr("ERROR: git is not installed.")
        sys.exit(1)

    print("Temporary directory: " + str(temp_dir()))
    clone_dir = temp_dir() / ("cli-utils-bash-scripts-" + os.urandom(8).hex())
    clone_dir.mkdir()
    print("Cloning git repo into " + str(clone_dir))
    try:
        subprocess.run(
            ("git", "clone", "-q", "--depth=1", "https://github.com/EEKIM10/cli-utils.git", str(clone_dir)), check=True
        )
    except subprocess.CalledProcessError:
        stderr("ERROR: git clone failed.")
        clone_dir.rmdir()
        sys.exit(1)

    if os.name != "posix":
        stderr("WARNING: This script is only for POSIX systems.")
        try:
            bin_dir = input("Please enter a directory (like /usr/local/bin) to install the scripts to: ")
            bin_dir = Path(bin_dir).expanduser().resolve()
        except (KeyboardInterrupt, EOFError):
            stderr("ERROR: User cancelled.")
            clone_dir.rmdir()
            sys.exit(1)
    else:
        bin_dir = home() / ".local/bin"
        print("Installing to " + str(bin_dir))

    bin_dir.mkdir(exist_ok=True, parents=True)
    to_copy = glob(str(clone_dir / "scripts") + "/*.bash", recursive=False)
    for file in to_copy:
        if file.startswith(("_", ".")):
            continue
        new_name = Path(file)
        print("Copying " + file)
        copy(file, bin_dir)

        new_path = bin_dir / new_name.name
        print("Making " + str(new_path) + " executable")
        new_path.chmod(0o755)

        print("Renaming " + str(new_path) + " to " + str(new_name.name[:-5]))
        move(new_path, bin_dir / new_name.name[:-5])
    print("Done.")


if __name__ == "__main__":
    main()
