#!/usr/bin/env bash
printf "Generating 1GB hashgen test file...\n"
dd if=/dev/random of=hashgen-test-1g.bin bs=16M count=64 status=progress

RAM_SIZE=$(($(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024))  # gets system RAM count in MB
RAM_SIZE_GB=$(("$RAM_SIZE" / 1024))
printf "Generating %dGB hashgen test file (%d x 16M blocks)...\n" $(("$RAM_SIZE_GB" / 2)) "$(("$RAM_SIZE" / 16 / 2))"
dd if=/dev/random of=hashgen-test-"$RAM_SIZE_GB"g.bin bs=16M count=$(("$RAM_SIZE" / 16 / 2)) status=progress

printf "Done!\n"
