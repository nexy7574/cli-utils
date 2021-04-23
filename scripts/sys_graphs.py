"""
####################
WARNING:
    This script is purely just me testing matplotlib.
    You shouldn't use this unless you wanna see some pretty boring stuff.
####################

Requires:
- Matplotlib
- psutil
"""
import sys
import time

try:
    import psutil
    import matplotlib.pyplot as plt
except ImportError as e:
    raise RuntimeError("Make sure you've installed matplotlib and psutil before running this program.") from e


length = int(input("Time to collect mem stats for (in minutes): "))
if length <= 0:
    print("Time must be greater than zero.")
    sys.exit(6)

sleep_time = 60 * length
sleep_time /= 4
collected = [0]


for i in range(4):
    print("Iteration", i, "complete.", end="\r")
    collected.append(round(psutil.virtual_memory().percent, 2))
    time.sleep(sleep_time)
print()
plt.plot(range(len(collected)), collected)
plt.show()
