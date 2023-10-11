#!/usr/bin/env python3
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import shlex
import textwrap
import typing
from configparser import ConfigParser

import click
import rich
from rich.align import Align
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt, IntPrompt

from .utils.generic__size import convert_soft_data_value_to_hard_data_value, bytes_to_human

console = rich.get_console()
ABOUT = textwrap.dedent(
    """
    This tool is designed to help you create quick and functional, yet still customisable Systemd service units.
    
    You can read more about these unit files here: https://wiki.archlinux.org/title/Systemd#Writing_unit_files
    
    Note that this tool does not handle complex cases, and only has a few of the common customisation options.
    You are welcome to edit the service files after generation. After generation, they are yours.
    """
)

if not pathlib.Path("/usr/bin/systemctl").exists():
    console.print("! You do not have systemd.", style="red")
    sys.exit(255)


def find_executable(name: typing.Union[str, pathlib.Path], direct: bool = False) -> typing.Optional[pathlib.Path]:
    """
    Attempts to locate an executable by name.

    This function extends the which() function by ensuring that the given path is actually executable.
    :param name: The name or path to the 'executable'
    :param direct: If True, will also ensure the target has a shebang if it's not a binary.
    :return: an absolute path to the executable, if one exists.
    """
    name = str(name)
    if not os.getenv("PATH"):
        raise EnvironmentError("You have no $PATH.")
    if not name.startswith("/"):
        # Assume relative command name (e.g. python3 instead of /bin/python3)
        file = shutil.which(name)
        if not file:
            console.print(f"[red]:x: Unable to resolve '{name}' to an executable (like /bin/python3).")
            return
        file = pathlib.Path(file).absolute()
        console.print(f"[green dim]Resolved name '{name}' to executable: {file}")
    else:
        # Assume is a path
        file = pathlib.Path(name).absolute()
        if not file.exists():
            console.print(f"[red]:x: File '{name}' does not exist.")
            return

    if os.access(file, os.R_OK | os.X_OK) is False:
        try:
            stat = file.stat()
        except PermissionError:
            perms = "-??-??-??"
        else:
            perms = oct(stat.st_mode)[-3:]
        # console.print(
        #     f"[red]! You specified an executable '{file}', however you do not have permission to execute it"
        #     f" (Permissions were [code]{perms}[/], but need at least [code]r-x------[/]).\n"
        #     f"[i dim]Try: [code]chmod +rx {file}[/]."
        # )
        # return
        # ^ This has caused some problems with false triggers with new files. For now, I'll just specify it as a warning
        console.print(
            f"[yellow]:warning: You specified an executable '{file}', however you do not have permission to execute it"
            f" (Permissions were [code]{perms}[/], but need at least [code]r-x------[/]).\n"
            f"[i dim]Try: [code]chmod +rx {file}[/]."
        )

    if direct:
        with file.open(encoding="utf-8") as fd:
            try:
                first_line = fd.readline()
            except UnicodeDecodeError:
                # Assume it's a binary
                pass
            else:
                if first_line.startswith("#!"):
                    shebang = first_line[2:].strip()
                    if not find_executable(shebang, direct=True):
                        console.print(
                            f"[red]:x: You specified '{file}' as an executable, and it's shebang points to '{shebang}', "
                            f"however that shebang is not a valid executable (see above errors, if any), and by "
                            f"extension, neither is `{file.name}`."
                        )
                else:
                    console.print(
                        f"[red]:x: You specified '{file}' as an executable, however it has no shebang, so it cannot be "
                        f"executed."
                    )
                    return
    return file


def list_available_targets(user: bool = False) -> list[dict[str, str]]:
    """
    Lists all available systemd targets.

    :param user: User mode
    :return: A list of active targets
    """
    command = ["systemctl", "list-units", "--type=target", "--no-pager", "--output=json"]
    if user:
        command.insert(1, "--user")
    out = subprocess.run(command, check=True, text=True, capture_output=True)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        console.print("[yellow]:warning: Failed to decode systemctl output.")
        return []


def list_units(user: bool = False) -> list[dict[str, str]]:
    """
    Lists all (active) systemd.

    :param user: User mode
    :return: A list of units
    """
    command = ["systemctl", "list-units", "--type=target", "--no-pager", "--output=json"]
    if user:
        command.insert(1, "--user")
    out = subprocess.run(command, check=True, text=True, capture_output=True)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        console.print("[yellow]:warning: Failed to decode systemctl output.")
        return []


def reload_daemon(user: bool = False):
    """
    Reloads the systemd daemon.

    :param user: User mode
    :return:
    """
    command = ["systemctl", "daemon-reload"]
    if user:
        command.insert(1, "--user")
    subprocess.run(command, check=True, text=True, capture_output=True)


def start_service(user: bool, service_name: str):
    """
    Starts a service.

    :param user: User mode
    :param service_name: The name of the service to start
    :return:
    """
    command = ["systemctl", "start", service_name]
    if user:
        command.insert(1, "--user")
    subprocess.run(command, check=True, text=True, capture_output=True)


def enable_service(user: bool, service_name: str, start: bool = False):
    """
    Enables a service and optionally starts it immediately.

    :param user: User mode
    :param service_name: The name of the service to enable
    :param start: Whether to start the service immediately
    :return:
    """
    command = ["systemctl", "enable", service_name]
    if user:
        command.insert(1, "--user")
    subprocess.run(command, check=True, text=True, capture_output=True)
    if start:
        start_service(user, service_name)


@click.command()
def main():
    config = ConfigParser()
    config.optionxform = str
    config["Unit"] = {}
    config["Service"] = {}
    config["Install"] = {}

    console.clear()
    panel = Panel(
        Align(ABOUT, "center"),
        title="[bold]systemd gen[/]",
        title_align="center",
        highlight=True,
        style="white on black",
    )
    console.print(panel)

    console.print(
        ":information_source: There are two types of services: user, and system.\n"
        "User-based services are run as the user, and are owned by the user. This means you can use `systemctl` without"
        " `sudo` and friends, albeit with the `--user` flag. This means you can do `systemctl --user restart`, etc, "
        "without needing sudo. [b]This is recommended unless you need root privileges in your program.[/b]\n\n"
        "Alternatively, you have system services, which are privileged services that can run as any user or group, and"
        " can start earlier in the boot process than user-based services. "
        "[b underline]You can only create system services if you're running as root or have write access to "
        "`/etc/systemd/services`![/]\n"
    )
    user_mode = Prompt.ask(
        "Would you like to create a user service, or system service?",
        console=console,
        choices=["user", "system"],
        default="user" if os.getuid() != 0 else "system",
    )
    if user_mode == "system":
        save_to = pathlib.Path("/etc/systemd/system")
    else:
        save_to = pathlib.Path.home() / ".config" / "systemd" / "user"
        save_to.mkdir(parents=True, exist_ok=True)

    targets_raw = list_available_targets(user_mode == "user")
    targets = [x["unit"] for x in targets_raw]
    for target in targets_raw:
        colour = 'green' if target["load"] == "loaded" and target["active"] == "active" else 'red'
        console.print(f"* {target['unit']}", style=colour)
    desired_target = Prompt.ask(
        "Please select a target (the thing that'll trigger your service to start)",
        choices=targets,
        default="multi-user.target" if "multi-user.target" in targets else "default.target",
        show_choices=False
    )
    config["Install"]["WantedBy"] = desired_target

    service_name = "$$"
    while not re.match(r"^[\w.\-_]{1,255}$", service_name):
        service_name = Prompt.ask("Give your service a name ([code]A-Z0-9-_.[/] only)")

    description = Prompt.ask("And give your service a short description")
    config["Unit"]["Description"] = description

    if user_mode != "user":
        if Confirm.ask("Does your service depend on the network being configured?"):
            after = "network.target"
            if Confirm.ask("Does your service depend on a working network connection?"):
                after += " network-online.target"
            config["Unit"]["Requires"] = after
            config["Unit"]["After"] = after

    if Confirm.ask("Does your service depend on anything else in the system (e.g. removable media)?"):
        av = [x["unit"] for x in list_units(user_mode == "user")]
        console.print("Available units to depend on:", ", ".join(av))
        wants = []
        while True:
            try:
                v = Prompt.ask(
                    "Please input the name of a unit to depend on (e.g. my-drive.mount)",
                )
                if v.startswith("!"):
                    match v.lower():
                        case '!list':
                            console.print("Available units to depend on:", ", ".join(av))
                            continue
                        case '!show':
                            console.print("Currently depending on:", ", ".join(wants))
                            continue
                        case _:
                            pass
                if not v:
                    break
                if v not in av and not Confirm.ask(
                    f"[yellow]:warning: {v!r} was not found. Add it anyway?"
                ):
                    continue
                wants.append(v)
            except KeyboardInterrupt:
                break
        config["Unit"]["Wants"] = " ".join(wants)

    while True:
        exec_start = Prompt.ask(
            "Please input the command that will start your service (e.g. python3 /home/user/my-service.py)",
        )
        _command, *_args = shlex.split(exec_start)
        command = find_executable(_command, direct=True)
        if command:
            break
    config["Service"]["Type"] = "simple"
    config["Service"]["ExecStart"] = exec_start

    if Confirm.ask("Do you want your services to be restart if it exits?"):
        if Prompt.ask(
                "Do you want the service to *always* restart, or only when it exits abnormally (with an exit code other"
                " than 0)?",
                choices=["always", "abnormal"],
        ) == "abnormal":
            config["Service"]["Restart"] = "on-failure"
        else:
            config["Service"]["Restart"] = "always"
        console.print(
            "You can limit how many times the service will restart in a row. In the event one restart fails, the "
            "restart counter will increment. If the counter reaches the limit, the service will be stopped.\n"
            "If it successfully restarts, the counter is reset."
        )
        if Confirm.ask("Do you want to limit the number of times it restarts? (recommended)"):
            config["Service"]["StartLimitBurst"] = str(IntPrompt.ask("How many times should it restart?", default=10))
        if Confirm.ask("Do you want to ratelimit and space-out the restarts?"):
            config["Service"]["StartLimitInterval"] = Prompt.ask(
                "How long should systemd wait between restarts? (e.g. 1min, 1h, 5s)",
                default="5s"
            )

    if Confirm.ask("Do you want to limit how much CPU this service can use?", default=False):
        config["Service"]["CPUAccounting"] = "yes"
        count = os.cpu_count()
        console.print(f"100% = one core. You have {count} cores, which means up to {count * 100}% is allowed.")
        val = IntPrompt.ask("How much CPU should this service be allowed to use?", default=100)
        config["Service"]["CPUQuota"] = f"{val}%"
    if Confirm.ask("Do you want to limit how much RAM this service can use?", default=False):
        config["Service"]["MemoryAccounting"] = "yes"
        val = Prompt.ask("How much RAM should this service be allowed to use? (e.g. 1G, 512M, 1T)", default="1G")
        converted = convert_soft_data_value_to_hard_data_value(val, "M")
        config["Service"]["MemoryMax"] = f"{converted}M"

    console.log("Generating...")
    save_to = (save_to / (service_name + ".service")).absolute()
    _file = io.StringIO()
    config.write(_file, False)
    _file.seek(0)
    panel = Panel.fit(
        Syntax(
            _file.read(),
            "ini",
            theme="ansi_dark",
            line_numbers=True
        ),
        title=f"[bold]{service_name}.service[/]",
        title_align="center",
        subtitle="Saving to " + str(save_to),
        subtitle_align="center"
    )
    console.print(panel)
    if Confirm.ask("Save?"):
        with save_to.open("w+") as fd:
            config.write(fd, False)

        with console.status("Reloading daemon (this will take a few seconds)..."):
            reload_daemon(user_mode == "user")

        if Confirm.ask("Do you want to start the service at boot?"):
            enable_service(user_mode == "user", service_name, start=True)

        if Confirm.ask("Do you want to start the service now?"):
            start_service(user_mode == "user", service_name)
    else:
        console.print("Aborting.", style="red")


if __name__ == "__main__":
    main()
