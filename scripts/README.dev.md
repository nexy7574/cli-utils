# Developing
If you're getting import errors (like top level package crap) you need to run scripts in module mode.
You can do this by running `python3 -m scripts.xyz` rather than `python3 scripts/xyz.py`.

Imports via `from scripts.xyz import ...` are no longer used and all should use relative imports
(`from .xyz import ...`).