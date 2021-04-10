#!/usr/bin/env python3
import argparse
import sys

types = ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"]


parser = argparse.ArgumentParser(
    description="Simple tool to assist with generation of systemd services."
)
parser.add_argument(
    "--interactive",
    "-I",
    action="store_true",
    help="Whether to do this interactively. Defaults to true.",
    default=None
)
parser.add_argument(
    "--description",
    "-D",
    action="store",
    help="The description of the service.",
    required=False,
    default="Automatically generated service via systemd-gen.py"
)
parser.add_argument(
    "--type",
    "-T",
    action="store",
    choices=types,
    help="The type of service. See https://www.freedesktop.org/software/systemd/man/systemd.service.html for more"
         " detail.",
    required=False,
    default="simple"
)
parser.add_argument(
    "--remain-after-exit",
    "-R",
    action="store_true",
    required=False,
    default=False,
    help="Whether to consider the service alive if all the processes are dead."
)
parser.add_argument(
    "--exec-path",
    "--exec-start",
    "--path",
    "--start",
    "--exec",
    "-E",
    action="store",
    required=False,
    default=None,
    help="The command to actually run."
)
parser.add_argument(
    "--name",
    "-N",
    action="store",
    required=False,
    default=None,
    help="The name of the service."
)

args = parser.parse_args()

if args.interactive in [True, None]:
    if not args.interactive:
        print("Did you know you can specify if you want to run this via the command line or not? See `--interactive`.")
    name = input("Please enter a name for this service: ")
    description = input("Please enter a description of this service:\n")
    while True:
        _type = input(f"What type is this service? ({', '.join(types)}):\n").lower().strip()
        if _type not in types:
            print("Invalid Type '{}' Try again.".format(_type))
        else:
            break
    remain_after_exit = input("Should this service be considered offline when all of its processes are exited? [Y/N]\n")
    remain_after_exit = not remain_after_exit.lower().startswith(("y", "1", "t"))
    restart_on_death = input("Should this service be automatically restarted on death? [Y/N]").lower()[0] == "y"
    max_restarts = int(input("If enabled, how many times can this service restart before systemd gives up? "))
    exec_path = input("What command should this service run? (e.g. /usr/local/opt/python-3.9.0/bin/python3.9 /root/"
                      "thing.py)\n")
else:
    name = args.name
    description = args.description
    _type = args.type
    remain_after_exit = args.remain_after_exit
    exec_path = args.exec_path
    restart_on_death = True
    max_restarts = 10

print("Generating file...")
content = \
"""
[Unit]
Description={}
StartLimitBurst={}

[Service]
Type={}
RemainAfterExit={}
ExecStart={}
Restart={}
RestartSec=5s
"""
content = content.format(
    description,
    str(max_restarts),
    _type,
    "yes" if remain_after_exit else "no",
    exec_path,
    "on-failure" if restart_on_death else "no"
)

print("===== BEGIN CONFIGURATION FILE =====")
print(content)
print("=====  END CONFIGURATION FILE  =====")
if input("Does this look right? [Y/N]\n").lower().startswith("y"):
    try:
        with open("/etc/systemd/system/{}.service".format(name), "w+") as wfile:
            wfile.write(content)
    except PermissionError:
        print("Unable to write configuration file. Try sudo.")
        sys.exit(1)
    else:
        print("Finished writing configuration file.\nTo start the service, run "
              f"\"sudo service {name} start\".")
        sys.exit()
else:
    print("Ok, cancelled.")
    sys.exit(2)
