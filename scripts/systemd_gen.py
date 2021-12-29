#!/usr/bin/env python3
import argparse
import subprocess
import sys
import pwd
import os

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax

    console = Console()
except ImportError as e:
    print("Rich is not installed. Please install rich.", file=sys.stderr)
    sys.exit(4)


def generate_unit_file(unit: dict, service: dict, install: dict):
    unit_section = "[Unit]\n"
    for key, value in unit.items():
        unit_section += f"{key}={value}\n"

    service_section = "\n[Service]\n"
    for key, value in service.items():
        service_section += f"{key}={value}\n"

    install_section = "\n[Install]\n"
    for key, value in install.items():
        install_section += f"{key}={value}\n"

    return unit_section + service_section + install_section


if __name__ == "__main__":
    types = ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"]
    restart_on = ["always", "on-failure", "on-success", "on-abnormal", "on-abort", "on-watchdog", "no"]

    parser = argparse.ArgumentParser(description="Simple tool to assist with generation of systemd services.")
    parser.add_argument(
        "--interactive",
        "-I",
        action="store_true",
        help="Whether to do this interactively. Defaults to true.",
        default=None,
    )
    parser.add_argument(
        "--description",
        "-D",
        action="store",
        help="The description of the service.",
        required=False,
        default="Automatically generated service via systemd-gen.py",
    )
    parser.add_argument(
        "--type",
        "-T",
        action="store",
        choices=types,
        help="The type of service. See https://www.freedesktop.org/software/systemd/man/systemd.service.html for more"
        " detail.",
        required=False,
        default="simple",
    )
    parser.add_argument(
        "--remain-after-exit",
        "-R",
        action="store_true",
        required=False,
        default=False,
        help="Whether to consider the service alive if all the processes are dead.",
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
        help="The command to actually run.",
    )
    parser.add_argument("--name", "-N", action="store", required=False, default=None, help="The name of the service.")
    parser.add_argument("--user", action="store_true", help="If true, this will stop the script elevating itself.", default=False)

    args = parser.parse_args()

    if os.getuid() != 0 and args.user is False:
        try:
            from elevate import elevate

            console.log("[gray italics]Attempting to elevate program permissions...[/]")
            elevate()
        except ImportError:
            elevate = None
            console.log(
                r"[yellow][Warning][/] Program is not running as root!"
                r" This will be unable to write your configuration files, only print them."
            )

    if args.interactive in [True, None]:
        name = Prompt.ask("Please enter a name for this service: ")
        description = Prompt.ask("Please enter a description of this service:\n")
        _type = Prompt.ask(f"What type is this service?", choices=types).lower().strip()
        remain_after_exit = Confirm.ask(
            "Should this service be considered offline when all of its processes are exited?", default=True
        )
        restart_on_death = Confirm.ask("Should this service be automatically restarted on death?", default=False)
        max_restarts = int(Prompt.ask("If enabled, how many times can this service restart before systemd gives up? "))
        exec_path = Prompt.ask(
            "What command should this service run? (e.g. /usr/local/opt/python-3.9.0/bin/python3.9 /root/thing.py)\n"
        )
        requires_network = Confirm.ask("Should the service wait until network connectivity is established?")
        user = None
        while user is None:
            user = Prompt.ask("What user should this service run as? (e.g. root, nobody, etc.)", default="default")
            if user.lower() in ["root", "default", "none", " "]:
                user = None
                break
            else:
                console.log("Checking user...")
                try:
                    pwd.getpwnam(user)
                except KeyError:
                    console.log(f"[red]User {user} does not exist![/]")
                    user = None
                else:
                    break
    else:
        name = args.name
        description = args.description
        _type = args.type
        remain_after_exit = args.remain_after_exit
        exec_path = args.exec_path
        restart_on_death = True
        max_restarts = 10
        requires_network = False
        user = None

    console.log("Generating file...")

    # data
    unit = {
        "Description": description,
    }
    if max_restarts:
        unit["StartLimitBurst"] = str(max_restarts)

    if requires_network:
        unit["Wants"] = "network-online.target"
        unit["After"] = "network.target network-online.target"

    service = {
        "Type": _type,
        "RemainAfterExit": "yes" if remain_after_exit else "no",
        "ExecStart": exec_path,
    }
    if restart_on_death:
        service["Restart"] = "always"
        service["RestartSec"] = "5"
    
    if user is not None:
        service["User"] = user

    install = {
        "WantedBy": "multi-user.target",
    }

    content = generate_unit_file(unit, service, install)
    console.print("===== BEGIN CONFIGURATION FILE =====")
    console.print(Syntax(content, "toml"))
    console.print("=====  END CONFIGURATION FILE  =====")
    if Confirm.ask("Does this configuration look right?"):
        try:
            with open("/etc/systemd/system/{}.service".format(name), "w+") as wfile:
                console.log("[gray italics]Writing file...[/]")
                written = wfile.write(content)
                console.log(f"[gray italics]Wrote {written} bytes to `/etc/systemd/system/{name}.service`.")
        except PermissionError as e:
            console.print_exception()
            console.log("Unable to write configuration file. Try sudo.")
            sys.exit(1)
        else:
            if Confirm.ask("Would you like to start this service now?"):
                subprocess.run(["systemctl", "start", name + ".service"])
            else:
                console.log(
                    "Finished writing configuration file.\nTo start the service, run `sudo service {name} start`."
                )
                sys.exit()
            if Confirm.ask("Would you like to start this service on reboot?"):
                subprocess.run(["systemctl", "enable", name + ".service"])
    else:
        console.log("Ok, cancelled.")
        console.log("[red dim italics]User cancelled[/]")
        sys.exit(2)
