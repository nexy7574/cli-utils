#!/bin/bash
PIPX_EXISTS=$(command -v pipx &> /dev/null; echo $?)
PIP_EXISTS=$(command -v pip &> /dev/null; echo $?)
PYTHON3_EXISTS=$(command -v python3 &> /dev/null; echo $?)
if [[ PIPX_EXISTS -ne 0 ]]; then
    echo 'pipx does not exist. Finding out how to install it.'
    if [[ PIP_EXISTS -eq 0 ]]; then
        # shellcheck disable=SC2016
        echo 'Installing pipx with `pip install pipx`'
        RESULT=pip install pipx
        if [[ $RESULT -ne 0 ]]; then
            echo 'Failed to install pipx. Aborting.'
            exit "$RESULT"
        fi
    elif [[ PYTHON3_EXISTS -eq 0 ]]; then
        # shellcheck disable=SC2016
        echo 'Installing pipx with `python3 -m pip install pipx`'
        RESULT=$(python3 -m pip install pipx)
        if [[ $RESULT -ne 0 ]]; then
            echo 'Failed to install pipx. Aborting.'
            exit "$RESULT"
        fi
    else
        echo 'pip is not installed.'
        echo 'On Debian, run: sudo apt install python3-pip'
        echo 'On Arch, run: sudo pacman -S python-pip'
        echo 'On anything else, you can figure it out yourself.'
        exit 1
    fi
else
    echo 'Pipx is already installed.'
fi
# shellcheck disable=SC2016
printf 'Running `pipx ensurepath` (adding scripts to PATH)'
pipx ensurepath
# shellcheck disable=SC2016
printf 'Installing cli-utils with `pipx install`'
pipx install git+https://github.com/EEKIM10/cli-utils.git
echo 'All done!'
$SHELL
