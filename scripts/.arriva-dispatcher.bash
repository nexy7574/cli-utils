#!/usr/bin/env bash
# This file will not be installed by pipx!
# Please run the following command:
#     sudo wget -O /etc/NetworkManager/dispatcher.d/arriva-dispatcher.bash https://github.com/EEKIM10/cli-utils/raw/master/scripts/.arriva-dispatcher.bash \
#     && sudo chmod +x /etc/NetworkManager/dispatcher.d/arriva-dispatcher.bash

if [[ "$2" == "up" && "$1" == "wlan0" ]]; then
  if [ "$CONNECTION_ID" == "arriva-wifi" ]; then
    /home/nex/.local/bin/arriva -YV Laptop
  fi;
fi
