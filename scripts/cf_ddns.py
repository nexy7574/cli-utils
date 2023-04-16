import json
import re
from typing import List, TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import click
from rich import get_console
from rich.prompt import Confirm
from rich.progress import track
from rich.prompt import IntPrompt
from .utils.generic__shell import config_dir
from .utils.generic__rendering import render_as_table


class ZoneRecord(dict):
    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(f"{self.__class__.__name__!r} has no attribute {item!r}")

    if TYPE_CHECKING:
        id: str
        type: str
        name: str
        content: str
        proxiable: bool
        proxied: bool
        ttl: int
        locked: bool
        zone_id: str
        zone_name: str
        created_on: str
        modified_on: str
        data: dict
        meta: dict


@click.group(invoke_without_command=True)
@click.option("--ip", "--ip-service", "-I", default="https://api.ipify.org")
@click.option("--token", "--api-token", "-T", default=None, allow_from_autoenv=True)
@click.option("--zone", "--zone-id", "-Z", default=None, allow_from_autoenv=True)
@click.option("--old-ip", "-O", default=None)
@click.option("--unless-a-record-is", "-U", default=None)
@click.option("--yes", "-y", default=False, is_flag=True)
@click.option("--verbose", type=bool, default=False, is_flag=True)
@click.option("--timeout", type=float, default=30.0)
@click.pass_context
def main(
    ctx: click.Context,
    *,
    ip: str,
    token: str | None,
    zone: str | None,
    # names: List[str],
    old_ip: str = None,
    yes: bool = False,
    verbose: bool = False,
    unless_a_record_is: str = None,
    timeout: float = 30.0,
):
    names = []
    if ctx.invoked_subcommand is not None:
        return
    names = [name.lower() for name in names]
    console = get_console()

    file = config_dir() / "cf-ddns.json"
    if file.exists():
        cfg = json.loads(file.read_text())
        if cfg.get("token"):
            token = cfg["token"]
        if cfg.get("zone"):
            zone = cfg["zone"]
        if cfg.get("ip"):
            ip = cfg["ip"]
        if cfg.get("timeout"):
            timeout = cfg["timeout"]
        if cfg.get("unless_a_record_is"):
            unless_a_record_is = cfg["unless_a_record_is"]
        if cfg.get("names"):
            names = cfg["names"]
        console.log(f"Loaded configuration file from {file!s}.")

    if token is None:
        console.log("[red]No API token provided. Please run `cf-ddns config`.")
        raise click.Abort
    if zone is None:
        console.log("[red]No zone ID provided. Please run `cf-ddns config`.")
        raise click.Abort

    if verbose:
        console.log(f"Using IP [service]: {ip!r}")
        console.log(f"Using API token: {token!r}")
        console.log(f"Using zone ID: {zone!r}")

    client = httpx.Client(
        base_url="https://api.cloudflare.com/client/v4",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=httpx.Timeout(timeout if timeout > 0 else None),
    )
    with console.status("Loading") as status:
        status.update("Verifying token")
        if verbose:
            console.log("GET /user/tokens/verify")
        response = client.get("/user/tokens/verify")
        if verbose:
            console.print_json(response.text)
        if response.status_code != 200 or response.json().get("success", False) is False:
            console.log("Invalid response code for authentication: %d" % response.status_code)
            console.log("Aborted.")
            return

        if not ip.split(".")[0].isdigit():  # likely a URL
            status.update("Getting external IP...")
            # We use httpx.get so that we don't leak client credentials.
            if verbose:
                console.log(f"GET {ip}")
            response = httpx.get(ip)
            if verbose:
                console.print(response.text)
            ip = response.text
            console.log("External IP appears to be: [link=http://{0}/]{0}".format(ip))

        if unless_a_record_is in ["NEW_IP", "CURRENT_IP"]:
            unless_a_record_is = ip

        status.update("Loading zone records")
        if verbose:
            console.log("GET /zones/%s/dns_records" % zone)
        response = client.get("/zones/" + zone + "/dns_records", params={"per_page": 5000})
        if verbose:
            console.print_json(response.text)
        if response.status_code != 200 or response.json().get("success", False) is False:
            console.log("Invalid response code for zone DNS records: %d" % response.status_code)
            console.log("Aborted.")
            return

        status.update("Processing zone records")
        data = [ZoneRecord(**x) for x in response.json()["result"]]
        to_edit = []
        status.update("Filtering zone records")
        for record in data:
            if old_ip and record.content == old_ip:
                to_edit.append(record.id)
                console.log("Added record '{0.type} {0.name}->{0.content}' ({0.content} == {1})".format(record, old_ip))
            elif record.name.lower() in names:
                to_edit.append(record.id)
                console.log("Added record '{0.type} {0.name}->{0.content}' ({0.name} in names)".format(record))
            elif record.type == "A" and unless_a_record_is is not None and record.content != unless_a_record_is:
                to_edit.append(record.id)
                console.log(
                    "Added record '{0.type} {0.name}->{0.content}' ({0.content} != {1})".format(
                        record, unless_a_record_is
                    )
                )

    if yes is False:
        if (
            Confirm.ask(f"Would you like to change {len(to_edit)} records' contents to {ip!r}?", console=console)
            is False
        ):
            return

    for record_id in track(to_edit, console=console, description="Editing zone records"):
        if verbose:
            console.log("PATCH /zones/{}/dns_records/{} | DATA=%s".format(zone, record_id) % ip)
        response = client.patch("/zones/{}/dns_records/{}".format(zone, record_id), json={"content": ip})
        if verbose:
            console.print_json(response.text)
        console.log(
            "[{}]{} ({})".format(
                "green" if response.status_code in [200, 304] else "red", record_id, response.status_code
            )
        )


@main.command()
def config():
    """Interactive setup of configuration"""
    console = get_console()
    file = config_dir() / "cf-ddns.json"
    if not file.exists():
        console.log("[yellow]:warning: Failed to find configuration file at %s. Using default config.[/]" % file)
        cfg = {
            "token": None,
            "zone": None,
            "ip": "https://api.ipify.org",
            "unless_a_record_is": "CURRENT_IP",
            "timeout": 30,
        }
    else:
        cfg = json.loads(file.read_text())

    while True:
        console.print(render_as_table(list(cfg.keys()), [list(cfg.values())]))
        key = console.input("Which key would you like to edit? ")
        if key.isdigit():
            key = list(cfg.keys())[int(key) - 1]

        if key == "names":
            cfg[key] = console.input("Enter a comma-separated list of names to update: ").strip().split(",")
        elif key == "timeout":
            cfg[key] = IntPrompt.ask("Enter a timeout in seconds")
        elif key == "unless_a_record_is":
            cfg[key] = console.input("Enter a value to ignore A records that are not equal to it: ").strip()
        elif key == "token":
            cfg[key] = console.input("Enter your API token: ").strip()
        elif key == "zone":
            cfg[key] = console.input("Enter your zone ID: ").strip()
        elif key == "ip":
            value = console.input("Enter a URL to get your external IP from, or a static IP: ")
            if not re.match(r"\d+\.\d+\.\d+\.\d+", value):
                parsed = urlparse(value)
                constructed = list(parsed)
                constructed[0] = (parsed.scheme or "https") + "://"
                constructed[1] = parsed.netloc or "api.ipify.org"
                if constructed[2]:
                    constructed[2] = ("/" + constructed[2]).lstrip("/")
                value = (urlparse("".join(constructed))).geturl()
                console.log("[i]remapped input to %s[/]" % value)
            cfg[key] = value
        elif key in ["quit", "exit", "save", "done", "q", "e", "s", "d"]:
            break
        else:
            console.log("Invalid key: %s. If you're done, say `quit`." % key)

    if Confirm.ask("Would you like to save these changes?", console=console) is False:
        return
    with file.open("w") as f:
        f.write(json.dumps(cfg, indent=4))
    console.log("Saved configuration to %s" % file)


if __name__ == "__main__":
    main()
