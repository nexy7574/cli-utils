#!/usr/bin/env python
import sys
text = \
"""
This script is now deprecated.
Please install cli-utils with the following command, and get all of the scripts on your path automatically:

    pipx install git+https://github.com/EEKIM10/cli-utils.git

===========================================================================================================

If you don't have pipx installed, you can install it with the following command:

    pip install pipx

~nex
"""
print(text, file=sys.stderr)
sys.exit(1)  # non-zero exit code in case someone's using this in a shell script for whatever reason
