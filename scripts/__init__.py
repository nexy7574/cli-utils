import sys


__version__ = "0.3.0a1"


if sys.version_info.major != 3 or sys.version_info.minor <= 9:
    print("You have an unsupported python version! Please upgrade.")
    sys.exit(1)
