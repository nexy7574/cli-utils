#!/usr/bin/env python3
import getpass
import re
import subprocess
import sys
import pwd
import os
from tempfile import TemporaryFile
from elevate import elevate
from rich import get_console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.syntax import Syntax
from typing import Literal

if os.name == "nt":
    print("This script is not supported on Windows.", file=sys.stderr)
    sys.exit(1)

console = get_console()
CAPACITY_VALUES = {
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
    # Who the hell has a terabyte or more of ram?
}
CAPACITY_REGEX = re.compile(r"(\d+)\s*([bkmgt])", re.IGNORECASE)


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


def convert_soft_data_value_to_hard_data_value(value: str, return_in: str = "b") -> float:
    INVALID_ERR = ValueError(
        "Invalid value. Make sure you specify a value in the format of `NNN C`, with C being"
        " one of the following: b, kb, mb, gb, tb, and NNN being the number. E.g: "
        "`1024M` == `1G`"
    )
    _match = CAPACITY_REGEX.match(value)
    if _match is None:
        raise INVALID_ERR

    _value, _unit = _match.groups()
    _value = int(_value)
    _unit = _unit.lower()
    value_in_bytes = _value * CAPACITY_VALUES[_unit]
    return value_in_bytes / CAPACITY_VALUES[return_in.lower()]


def main():
    _uname = getpass.getuser()
    types = ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"]
    if os.getuid() != 0:
        if Confirm.ask(
            "This script requires root privileges in order to write to /etc/systemd/system. Do you want to "
            "attempt to elevate to root?"
        ):
            console.log("[gray italics]Attempting to elevate program permissions...[/]")
            elevate()

    name = Prompt.ask("Please enter a name for this service")
    description = Prompt.ask("Please enter a description of this service")
    _type = Prompt.ask(f"What type is this service?", choices=types).lower().strip()
    restart_on_death = Confirm.ask("Should this service be automatically restarted on death?", default=False)
    max_restarts = time_between_restarts = 0
    if restart_on_death:
        max_restarts = IntPrompt.ask("How many times can this service restart before systemd gives up?")
        time_between_restarts = IntPrompt.ask(
            "How long, in seconds, should systemd wait before automatically restarting the service?", default=5
        )
    exec_path = Prompt.ask(
        "What command should this service run? (e.g. /usr/local/opt/python-3.9.0/bin/python3.9 /root/thing.py)"
    )
    requires_network = Confirm.ask("Should the service wait until network connectivity is established?")
    user = None
    while user is None:
        user = Prompt.ask("What user should this service run as? (e.g. root, default, nobody, etc.)", default=_uname)
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
        "RemainAfterExit": "no",
        "ExecStart": exec_path,
    }
    if restart_on_death:
        service["Restart"] = "always"
        service["RestartSec"] = str(time_between_restarts)

    if user is not None:
        service["User"] = user

    install = {
        "WantedBy": "multi-user.target",
    }

    if Confirm.ask("Would you like to restrict the system resources this unit can use?"):
        console.print("All inputs are optional here - just hit enter if you want to skip a value!")
        console.print(
            ":warning: Note that if you specify a value that is too low, the service may not work as expected, at all,"
            " or it may not even start. Apply at your own risk!"
        )
        console.print(
            "CPU Quota, as per [ul][link]https://www.freedesktop.org/software/systemd/man/"
            "systemd.resource-control.html#CPUQuota=[/link][/ul], limits the amount of CPU time a unit can use per"
            " CPU."
        )
        cpu_quota = IntPrompt.ask("What CPU quota should this unit have in percent? (e.g. 50 or 100)", default="100")
        if cpu_quota > 0:
            service["CPUAccounting"] = "true"
            service["CPUQuota"] = f"{cpu_quota}%"
            console.print(":white_heavy_check_mark: CPU Limiting enabled.")
        else:
            console.print(":x: CPU Limiting disabled.")

        while True:
            memory_limit = Prompt.ask("What memory limit should this unit have? (e.g. 512M or 1G)", default="1G")
            if memory_limit:
                try:
                    if not memory_limit.endswith("%"):
                        value = round(convert_soft_data_value_to_hard_data_value(memory_limit, return_in="M"))
                        service["MemoryAccounting"] = "true"
                        service["MemoryMax"] = f"{value}M"
                    else:
                        service["MemoryAccounting"] = "true"
                        service["MemoryMax"] = memory_limit
                except ValueError as e:
                    console.print(f"[red]{e}[/]")
                else:
                    console.print(":white_heavy_check_mark: Memory Limiting enabled.")
            else:
                console.print(":x: Memory limiting disabled.")
                break

            if service.get("MemoryAccounting") == "True":
                if Confirm.ask("Do you want to reserve memory for this unit?"):
                    while True:
                        memory_reserve = Prompt.ask(
                            "What memory reserve should this unit have? (e.g. 512M or 1G, or 10%)", default="128M"
                        )
                        if memory_reserve:
                            try:
                                if not memory_reserve.endswith("%"):
                                    value = round(
                                        convert_soft_data_value_to_hard_data_value(memory_reserve, return_in="M")
                                    )
                                    service["MemoryMin"] = f"{value}M"
                                else:
                                    service["MemoryMin"] = memory_reserve
                            except ValueError as e:
                                console.print(f"[red]{e}[/]")
                            else:
                                console.print(":white_heavy_check_mark: Memory Reservation enabled.")
                                break
                        else:
                            console.print(":x: Memory Reservation disabled.")
                            break

                if Confirm.ask(
                    "Do you want to set the 'high memory pressure' level? "
                    "(at which point memory throttling kicks in)"
                ):
                    while True:
                        memory_pressure = Prompt.ask(
                            "At how much used memory should memory pressure be raised? (e.g. 512M or 1G, or 10%)",
                            default="1G",
                        )
                        if memory_pressure:
                            try:
                                if not memory_pressure.endswith("%"):
                                    value = round(
                                        convert_soft_data_value_to_hard_data_value(memory_pressure, return_in="M")
                                    )
                                    service["MemoryHigh"] = f"{value}M"
                                else:
                                    service["MemoryHigh"] = memory_pressure
                            except ValueError as e:
                                console.print(f"[red]{e}[/]")
                            else:
                                console.print(":white_heavy_check_mark: Memory Pressure enabled.")
                                break
                        else:
                            console.print(":x: Memory Pressure disabled.")
                            break

        task_limit = IntPrompt.ask("What task limit should this unit have? (e.g. 100)", default="1000")
        if task_limit > 0:
            service["TasksAccounting"] = "true"
            service["TasksMax"] = str(task_limit)
            console.print(":white_heavy_check_mark: Task Limiting enabled.")
        else:
            console.print(":x: Task Limiting disabled.")

    console.log("Generating file...")
    content = generate_unit_file(unit, service, install)
    console.print("===== BEGIN CONFIGURATION FILE =====")
    console.print(Syntax(content, "toml", line_numbers=True, indent_guides=True))
    console.print("=====  END CONFIGURATION FILE  =====")
    with TemporaryFile() as file:
        file.write(content.encode("utf-8"))
        if not Confirm.ask("Does this configuration look right?"):
            if Confirm.ask("Do you want to manually edit it?"):
                default_editors = ["nano", "vim", "vi", "emacs"]
                editor = os.environ.get("EDITOR")
                if not editor:
                    editor = Prompt.ask("What editor do you want to use?", choices=default_editors)
                x = subprocess.run([editor, file.name])
                if x.returncode == 0:
                    file.seek(0)
                    content = file.read().decode("utf-8")
            else:
                console.log("Cancelled.")
                return
        try:
            with open("/etc/systemd/system/{}.service".format(name), "w+") as wfile:
                console.log("[gray italics]Writing file...[/]")
                written = wfile.write(content)
                console.log(f"[gray italics]Wrote {written} bytes to `/etc/systemd/system/{name}.service`.")
        except PermissionError:
            console.print_exception()
            console.log("Unable to write configuration file. Try sudo.")
            with open("./{}.service".format(name), "w+") as wfile:
                wfile.write(content)
            console.log(
                f"Wrote service file to './{name}.service'. You can do `sudo mv {name}.service "
                f"/etc/systemd/system/{name}.service` to move it."
            )
            sys.exit(1)
        else:
            if Confirm.ask("Would you like to start this service now?"):
                try:
                    subprocess.run(["systemctl", "start", name + ".service"], check=True)
                except subprocess.SubprocessError:
                    console.log("[red]Failed to start service! Check journal.")
            else:
                console.log(
                    "Finished writing configuration file.\nTo start the service, run `sudo service {name} start`."
                )
            if Confirm.ask("Would you like to start this service on reboot?"):
                try:
                    subprocess.run(["systemctl", "enable", name + ".service"], check=True)
                except subprocess.SubprocessError:
                    console.log("[red]Failed to enable service! Check journal.")


if __name__ == "__main__":
    main()
