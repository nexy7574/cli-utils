#!/usr/bin/env python3
import getpass
import re
import subprocess
import sys
import pwd
import os
from pathlib import Path
from tempfile import TemporaryFile
from elevate import elevate
from rich import get_console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.syntax import Syntax
from scripts.utils.generic__size import convert_soft_data_value_to_hard_data_value
if os.name == "nt":
    print("This script is not supported on Windows.", file=sys.stderr)
    sys.exit(1)

console = get_console()



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


def main():
    console.print("[link=https://wiki.archlinux.org/title/Systemd#Writing_unit_files]This may be of use (hyperlink)[/]")
    console.print("[dim i](https://wiki.archlinux.org/title/Systemd#Writing_unit_files link for bad terminals)")
    _uname = getpass.getuser()
    types = ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"]
    if os.getuid() != 0:
        console.print(
            "This script requires root privileges in order to write to /etc/systemd/system. Do you want to "
            "attempt to elevate to root?"
        )
        console.print(
            "If you do not elevate permissions, all configs will be written to your systemd user directory "
            "($HOME/.config/systemd/user)."
        )
        if Confirm.ask(
            "Do you want to elevate permissions? (this will re-launch the script as root)"
        ):
            console.log("[gray italics]Attempting to elevate program permissions...[/]")
            elevate()

    while True:
        name = Prompt.ask("Please enter a name for this service")
        # name cannot contain spaces or any special characters
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            console.log("[red]Service name cannot contain spaces or special characters![/]")
            continue
        else:
            break
    description = Prompt.ask("Please enter a description of this service")
    _type = Prompt.ask(f"What type is this service?", choices=types).lower().strip()
    restart_on_death = Confirm.ask("Should this service be automatically restarted on process exit?", default=False)
    max_restarts = time_between_restarts = 0
    if restart_on_death:
        max_restarts = IntPrompt.ask("How many times can this service restart before systemd gives up?", default=10)
        time_between_restarts = IntPrompt.ask(
            "How long, in seconds, should systemd wait between restarts?", default=5
        )
    exec_path = Prompt.ask(
        f"What command should this service run? (e.g. /usr/bin/python3 /home/{_uname}/my_script.py --arg1)"
    )
    requires_network = Confirm.ask("Should the service wait until network connectivity is established before starting?")
    user = None
    while user is None:
        user = Prompt.ask("What user should this service run as? (e.g. root, default, nobody, etc.)", default=_uname)
        if user.lower() in ["root", "default", "none", " ", ""]:
            user = None
            break
        else:
            try:
                pwd.getpwnam(user)
            except KeyError:
                console.log(f"[red]User {user!r} does not exist![/]")
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

    if Confirm.ask(
            "Would you like to restrict the system resources this unit can use? (you probably only need this if "
            "you're running on a low-end server or VPS)"
    ):
        console.print("All inputs are optional here - just hit enter if you want to skip a value!")
        console.print(
            ":warning: Note that if you specify a value that is too low, the service may not work as expected, at all,"
            " or it may not even start. Apply at your own risk!"
        )
        console.print(
            "CPU Quota, as per [ul]"
            "[link=https://www.freedesktop.org/software/systemd/man/systemd.resource-control.html#CPUQuota=]"
            "https://www.freedesktop.org/software/systemd/man/systemd.resource-control.html[/link][/ul], "
            "limits the amount of CPU time a unit can use per"
            " CPU."
        )
        try:
            cpu_quota = IntPrompt.ask("What CPU quota should this unit have in percent? (e.g. 50 or 100)", default=100)
        except KeyboardInterrupt:
            console.print(":x: CPU Limiting disabled.")
        else:
            if cpu_quota and cpu_quota > 0:
                service["CPUAccounting"] = "true"
                service["CPUQuota"] = f"{cpu_quota}%"
                console.print(":white_heavy_check_mark: CPU Limiting enabled.")
            else:
                console.print(":x: CPU Limiting disabled.")

        while True:
            try:
                memory_limit = Prompt.ask("What memory limit should this unit have? (e.g. 512M or 1G)", default="1G")
            except KeyboardInterrupt:
                console.print(":x: Memory Limiting disabled.")
                break
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
                    break
            else:
                console.print(":x: Memory limiting disabled.")
                break

            if service.get("MemoryAccounting") == "True":
                if Confirm.ask("Do you want to reserve memory for this unit?"):
                    while True:
                        try:
                            memory_reserve = Prompt.ask(
                                "What memory reserve should this unit have? (e.g. 512M or 1G, or 10%)", default="128M"
                            )
                        except KeyboardInterrupt:
                            console.print(":x: Memory Reservation disabled.")
                            break
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
                        try:
                            memory_pressure = Prompt.ask(
                                "At how much used memory should memory pressure be raised? (e.g. 512M or 1G, or 10%)",
                                default="1G",
                            )
                        except KeyboardInterrupt:
                            console.print(":x: Memory Pressure disabled.")
                            break
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
                wfile.write(content)
                USER_SERVICE = False
        except PermissionError:
            console.print_exception()
            console.log("Unable to write configuration file. Writing to user config directory.")
            user_systemd = Path.home() / ".config" / "systemd" / "user"
            user_systemd.mkdir(parents=True, exist_ok=True)
            path = user_systemd / "{}.service".format(name)
            with path.open("w+") as wfile:
                wfile.write(content)
                USER_SERVICE = True
            console.log(
                f"Wrote service file to '{path}'. You can do `sudo mv {path} "
                f"/etc/systemd/system/{name}.service` to move it to system-wide units, or use "
                f"'systemd --user ...' to manage it."
            )
        system_ctl = ["systemctl"]
        if USER_SERVICE is True:
            system_ctl.append("--user")
        if Confirm.ask("Would you like to start this service now?"):
            try:
                cmd = [*system_ctl, "start", name + ".service"]
                console.print("$ " + " ".join(cmd))
                subprocess.run(cmd, check=True)
            except subprocess.SubprocessError:
                console.log("[red]Failed to start service! Check journal.")
        else:
            console.log(
                "Finished writing configuration file.\nTo start the service, run `sudo service {name} start`."
            )
        if Confirm.ask("Would you like to start this service on reboot?"):
            try:
                cmd = [*system_ctl, "enable", name + ".service"]
                console.print("$ " + " ".join(cmd))
                subprocess.run(cmd, check=True)
            except subprocess.SubprocessError:
                console.log("[red]Failed to enable service! Check journal.")


if __name__ == "__main__":
    main()
