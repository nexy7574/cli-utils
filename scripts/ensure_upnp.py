import socket
import click
import os
import subprocess
import time
import random
import json
from rich import get_console
from rich.prompt import IntPrompt, Prompt, Confirm
from rich.progress import track
from pathlib import Path
from scripts.utils import ensure_upnp_utils as utils


CONFIG_FILE = Path.home() / ".config" / "cli-utils" / "ensure_upnp.json"
CONSOLE = get_console()


@click.group()
def main():
    pass


@main.command()
def config():
    cfg = []
    try:
        CONFIG_FILE.parent.mkdir(parents=True)
        CONFIG_FILE.touch()
    except OSError as e:
        CONSOLE.log(f"[yellow](WARN) Failed to create config file: {e}")

    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        CONSOLE.log(f"[yellow](WARN) Failed to load config - likely corrupted.")
    except OSError as e:
        CONSOLE.log(f"[yellow](WARN) Failed to load config - {e}")
    else:
        CONSOLE.log(f"[green]Successfully loaded config from {CONFIG_FILE.absolute()}")

    CONSOLE.log(
        "[yellow](WARN) Any edits made to the configuration in this program are saved in-memory until explicitly "
        "saved. Pressing CTRL+C will abort any changes!"
    )
    while True:
        CONSOLE.print(utils.render_mapping_table(cfg))
        options = [
            "Re-render table",
            "Inspect rule",
            "New rule",
            "Edit rule",
            "Remove rule",
            "Save",
            "Quit",
            "Save & Quit",
        ]
        for n, opt in enumerate(options):
            CONSOLE.print("{!s}: {}".format(n, opt))
        try:
            choice = IntPrompt.ask(
                "What would you like to do?", console=CONSOLE, choices=list(map(str, range(len(options))))
            )
        except KeyboardInterrupt:
            return
        else:
            # I can't wait until support for 3.8 and 3.9 is dropped, so I can use match cases here
            if choice == 0:
                CONSOLE.print(utils.render_mapping_table(cfg))
            elif choice == 1:
                rule = IntPrompt.ask("Which rule would you like to inspect?", choices=list(map(str, range(len(cfg)))))
                CONSOLE.print(utils.generate_rule_info(cfg[rule]))
            elif choice == 2:
                name = CONSOLE.input("Name for this new rule: ")
                internal_port = IntPrompt.ask("Internal port")
                external_port = IntPrompt.ask("WAN Facing (external) port", default=internal_port, show_default=True)
                protocol = Prompt.ask("Protocol", choices=["tcp", "udp", "both"]).upper()
                lease_time = IntPrompt.ask("Lease time (in seconds, 0 for infinity)")
                entry = {
                    "name": name,
                    "internal_port": internal_port,
                    "external_port": external_port,
                    "protocol": protocol,
                    "lease_time": lease_time,
                }

                for _entry in cfg:
                    if utils.resolve_name(_entry) == utils.resolve_name(entry):
                        entry["name"] = Prompt.ask("[red]Name is taken. Please choose a different one[/]")
                    elif entry["internal_port"] == _entry:
                        if not Confirm.ask(
                            f"Port {entry['internal_port']} appears to be in use by rule "
                            f"{utils.resolve_name(_entry)!r} (which is forwarded to {_entry['external_port']} "
                            f"externally)\nAre you sure you want to continue, this may cause conflicts!"
                        ):
                            CONSOLE.log("[dim](WARN) Rule creator aborted.")
                            break
                else:
                    cfg.append(entry)
                    CONSOLE.log("[green]Created new rule.")
            elif choice == 3:
                rule = IntPrompt.ask("Which rule would you like to edit?", choices=list(map(str, range(len(cfg)))))
                entry = cfg[rule]
                CONSOLE.print(utils.generate_rule_info(entry))
                while True:
                    keys = list(entry.keys())
                    for n, k in enumerate(keys):
                        CONSOLE.print(f"{n}: {k}")
                    edit_choice = IntPrompt.ask(
                        "Which value do you want to edit?", choices=list(map(str, range(len(keys))))
                    )
                    key = keys[edit_choice]
                    if key == "name":
                        entry[key] = Prompt.ask("New name")
                        break
                    elif "port" in key:
                        entry[key] = IntPrompt.ask(key.replace("_", " ").title())
                        break
                    elif key == "lease_time":
                        entry[key] = IntPrompt.ask("Lease time in seconds")
                    else:
                        entry[key] = Prompt.ask("Protocol", choices=["tcp", "udp", "both"])
                        break
            elif choice == 4:
                rule = IntPrompt.ask("Which rule would you like to remove?", choices=list(map(str, range(len(cfg)))))
                entry = cfg[rule]
                CONSOLE.print(utils.generate_rule_info(cfg[rule]))
                if Confirm.ask("Are you sure you want to remove this rule?"):
                    cfg.pop(rule)
                    CONSOLE.print(f"[green]Removed {utils.resolve_name(entry)!r}.")
                else:
                    CONSOLE.print("[yellow]Cancelled")
            elif choice == 5:
                CONFIG_FILE.write_text(json.dumps(cfg))
                CONSOLE.log("[green]Saved config.")
            elif choice == 6:
                return
            elif choice == 7:
                CONSOLE.print(cfg)
                CONFIG_FILE.write_text(json.dumps(cfg))
                CONSOLE.log("[green]Saved config.")
                return


@main.command()
@click.option("--headless", is_flag=True, help="Runs headless, meaning script will not ask for input.")
@click.option(
    "--config-file",
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
    default=CONFIG_FILE.absolute().__str__(),
    help="The config file location.",
)
@click.option("--verbose", "-v", is_flag=True, help="Increases verbosity.")
@click.option("--ip", default=None, help="The IP to forward to. If not specified, is automatically detected.")
@click.option("--dry-run", "--dry", is_flag=True, help="Makes no changes to forwarded ports, just simulates.")
@click.option("--ignore-errors", "-i", is_flag=True, help="Sames as `upnpc -i`")
@click.option("--ipv6", "-6", is_flag=True, help="Uses IPv6 instead of IPv4.")
@click.option(
    "--description", "-d", "-e", default="https://github.com/EEKIM10/cli-utils", help="Description for port forwarding."
)
def run(
    headless: bool,
    config_file: str,
    verbose: bool,
    ip: str,
    dry_run: bool,
    ignore_errors: bool,
    ipv6: bool,
    description: str,
):
    if ip is None:
        ip = os.getenv("IP")
        if ip is None:
            if headless is False:
                ip = Prompt.ask("Your local IP")

    if not ip:
        CONSOLE.log("[yellow](WARN) Guessing IP based on hostname.")
        ip = socket.gethostbyname(socket.gethostname() + ".local")
        CONSOLE.log("[yellow](WARN) Detected IP: {} | 5 seconds to interrupt script before continuing.".format(ip))
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            raise click.Abort() from None

    conf_file = Path(config_file).absolute()
    cfg = json.loads(conf_file.read_text())
    exec_queue = []
    for entry in cfg:
        command = ["upnpc", "-e", description, "-a", ip, entry["internal_port"], entry["external_port"]]

        if entry["protocol"] in ["TCP", "UDP"]:
            command.append(entry["protocol"])
            exec_queue.append(command)
        else:
            _c = command[:]
            _c.append("tcp")
            exec_queue.append(_c)
            _c2 = command[:]
            _c2.append("udp")
            exec_queue.append(_c2)

    if ipv6:
        for command in exec_queue:
            command.insert(1, "-6")
    if ignore_errors:
        for command in exec_queue:
            command.insert(1, "-i")

    for entry in track(exec_queue, description="Forwarding ports", console=CONSOLE):
        CONSOLE.log("Running", f"[dim]{' '.join(map(str, entry))!r}[/]")
        if dry_run:
            time.sleep(random.random())
            CONSOLE.log(f"[green]Forwarded internal port {entry[-3]} to {entry[-2]}")
        else:
            process = subprocess.run(tuple(map(str, entry)), capture_output=True, encoding="utf-8")
            if verbose:
                if process.returncode != 0:
                    CONSOLE.log(f"[yellow]Non-zero exit code[/]: [red]{process.returncode}")
                else:
                    CONSOLE.log(f"[green]Forwarded internal port {entry[-3]} to {entry[-2]}")


if __name__ == "__main__":
    main()
