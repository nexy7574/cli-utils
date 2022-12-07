#!/usr/bin/env python3
import getpass
import subprocess
import sys
import pwd
import os
from tempfile import TemporaryFile
from elevate import elevate
from rich import get_console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.syntax import Syntax

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
