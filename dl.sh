#!/bin/bash
pipx >/dev/null 2>/dev/null || pip install pipx || python3 -m pip install pipx || (echo 'pip is not installed.' && exit 1)
pipx ensurepath
pipx install git+https://github.com/EEKIM10/cli-utils.git
