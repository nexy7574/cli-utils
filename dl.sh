#!/usr/bin/env bash
git clone git@github.com:EEKIM10/cli-utils && cd cli-utils && \
virtualenv -p python3 venv && venv/bin/pip3 install -Ur requirements.txt & echo "Download complete, installing dependencies in the background."
