import datetime
import json
import logging
import sys

import click
import httpx
import typing as t
import json
from pathlib import Path

from rich import get_console
from rich.table import Table
from rich.logging import RichHandler
from rich.syntax import Syntax
from configparser import ConfigParser

from .utils.generic__shell import config_dir, cache_dir
from .utils.generic__size import humanise_time

DEFAULT_CONFIG_PATH = config_dir() / "cli-tools.ini"
IP4_GETTERS = [
    "https://api.ipify.org",
    "https://icanhazip.com",
    "https://ifconfig.me/ip",
    "https://ipinfo.io/ip",
]
IP6_GETTERS = [
    # "https://api64.ipify.org",  # Sometimes returns IPv4 in the event there's no IPv6.
    "https://icanhazip.com",
    "https://ifconfig.me/ip",
    # "https://ipinfo.io/ip",  # Only seems to return IPv4.
]
console = get_console()


def find_ip(ip_version: t.Literal["4", "6"], suppress: bool = False) -> str:
    if ip_version == "6":
        with console.status("Determining if the network supports IPv6"):
            try:
                httpx.get("https://ipv6.google.com", timeout=5)
            except httpx.HTTPError:
                if not suppress:
                    console.log("[red]Network does not support IPv6.")
                return ""
    getters = IP4_GETTERS if ip_version == "4" else IP6_GETTERS
    with console.status("Fetching public IPv%s address" % ip_version) as status:
        for url in getters:
            try:
                status.update("Fetching public IPv%s address (through %s)" % (ip_version, url))
                response = httpx.get(url, headers={"accept": "text/plain"})
                response.raise_for_status()
                return response.text.strip()
            except httpx.HTTPError:
                console.log(f"[red]Failed to query {url}. Trying next getter.")
                continue
        else:
            console.log("[red]Failed to find public IP address.")
            raise RuntimeError("Failed to find public IP address.")


def update_cache(zone_id: str, data: t.Dict[str, t.Any]):
    now = datetime.datetime.now()
    file = cache_dir() / "cf-dns.cache.json"
    if not file.exists():
        file.write_text("{}")
    cache = json.loads(file.read_text())
    cache[zone_id] = {
        "data": data,
        "last_updated": now.isoformat(),
    }
    file.write_text(json.dumps(cache, indent=2))


def read_cache(zone_id: str = None) -> t.Optional[t.Dict[str, t.Any] | list[t.Dict[str, t.Any]]]:
    def expired(ts: str):
        last_modified = datetime.datetime.fromisoformat(ts)
        # If it's older than a day, return True.
        if (datetime.datetime.now() - last_modified).days > 1:
            return True
        return False

    file = cache_dir() / "cf-dns.cache.json"
    if not file.exists():
        return
    cache = json.loads(file.read_text())
    if zone_id:
        if zone_id not in cache:
            return
    else:
        logging.debug("Returning cache for CACHE/ZONE/ALL")
        return_value = {_id: cache[_id]["data"] for _id in cache.keys() if not expired(cache[_id]["last_updated"])}
        logging.debug("%r -> %r", zone_id, return_value)
        return list(return_value.values())

    if expired(cache[zone_id]["last_updated"]):
        return
    logging.debug("Returning cache for CACHE/ZONE/%s", zone_id)
    logging.debug("%r -> %r", zone_id, cache[zone_id]["data"])
    return cache[zone_id]["data"]


def get_zones(ctx: click.Context) -> t.List[dict]:
    """
    Fetches all zones that the API token can access.

    :param ctx:
    :return:
    """
    cache = read_cache()
    if cache:
        return cache
    response = ctx.obj["session"].get("/zones")
    response.raise_for_status()
    result = response.json()["result"]
    for zone in result:
        update_cache(zone["id"], zone)
    return result


def get_records(
        ctx: click.Context,
        zone_identifier: str,
        types: list[str] = None,
):
    """
    Fetches all records in a zone.

    :param ctx:
    :param zone_identifier:
    :param types:
    :return:
    """
    # Check if its in cache first
    cache = read_cache(zone_identifier)
    if cache:
        records = cache.get("records")
        if records:
            if types:
                records = [record for record in records if record["type"] in types]
            console.log("[dim i]Returning cache for RECORDS/" + zone_identifier)
            return records
    response = ctx.obj["session"].get(f"/zones/{zone_identifier}/dns_records")
    response.raise_for_status()
    records = response.json()["result"]
    # Update the cache
    _zone_cache = read_cache(zone_identifier) or {}
    _zone_cache["records"] = records
    update_cache(zone_identifier, _zone_cache)
    if types:
        records = [record for record in records if record["type"] in types]
    return records


def get_zone_by(
        ctx: click.Context,
        name: str = None,
        zone_id: str = None,
        zones: list[dict] = None
) -> t.Optional[dict]:
    """
    Prompts the user to select a zone by name. Returns None if the user cancels.

    :param ctx:
    :param name:
    :param zone_id:
    :param zones:
    :return:
    """
    name = name or ""
    zone_id = zone_id.casefold() if zone_id else ""
    if not any((name, zone_id)):
        raise ValueError("You must specify either a zone name or zone ID.")
    zones = zones or get_zones(ctx)
    found = []
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        if zone["name"].casefold() == name.casefold():
            found.append(zone)
        elif zone["id"] == zone_id:
            found.append(zone)
    if len(found) == 1:
        return found[0]
    elif len(found) == 0:
        return None
    else:
        raise ValueError("More than one zone with the same name/ID.")


def get_record_by(
        ctx: click.Context,
        zone_identifier: str,
        name: str = None,
        record_id: str = None,
        records: list[dict] = None
) -> t.Optional[dict]:
    """
    Prompts the user to select a record by name. Returns None if the user cancels.

    :param ctx:
    :param zone_identifier:
    :param name:
    :param record_id:
    :param records:
    :return:
    """
    if not any((name, record_id)):
        raise ValueError("You must specify either a record name or record ID.")
    name = name or ""
    record_id = record_id.casefold() if record_id else ""
    records = records or get_records(ctx, zone_identifier)
    found = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record["name"].casefold() == name.casefold():
            found.append(record)
        elif record["id"] == record_id:
            found.append(record)
    if len(found) == 1:
        return found[0]
    elif len(found) == 0:
        return None
    else:
        raise ValueError("More than one record with the same name.")


@click.group()
@click.option(
    "--token",
    "-T",
    default=None,
    help="The CloudFlare API token to use. Defaults to the value in the configuration file."
)
@click.option(
    "--config",
    "-C",
    "config_file",
    default=str(DEFAULT_CONFIG_PATH),
    help="The path to the configuration file to use",
    show_default=str(DEFAULT_CONFIG_PATH)
)
@click.option(
    "--api-version",
    "-A",
    default="v4",
    help="The CloudFlare API version to use. Defaults to v4."
)
@click.option(
    "--log-level",
    "-L",
    default="INFO",
    help="The log level to use. Defaults to INFO.",
    type=click.Choice(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
)
@click.pass_context
def main(ctx: click.Context, api_version: str, log_level: str, token: t.Optional[str], config_file: t.Optional[str]):
    """
    Manage CloudFlare DNS records right from your command line!
    """
    logging.basicConfig(
        format="%(message)s",
        datefmt="[%X]",
        level=getattr(logging, log_level),
        handlers=[RichHandler()]
    )
    if "--help" in map(str.casefold, sys.argv):
        return
    ctx.obj = {}
    parser = ConfigParser()
    if "cf-dns" not in parser:
        parser["cf-dns"] = {}
    if "token" not in parser["cf-dns"]:
        parser["cf-dns"]["token"] = str(token or "")

    if config_file:
        config_file = Path(config_file).expanduser().resolve()
        if config_file.exists():
            parser.read_string(config_file.read_text())
    config = parser
    ctx.obj["config"] = config
    ctx.obj["config.path"] = Path(config_file) or DEFAULT_CONFIG_PATH
    with ctx.obj["config.path"].open("w") as file_handle:
        parser.write(file_handle, space_around_delimiters=True)

    ctx.obj["session"] = httpx.Client(
        base_url="https://api.cloudflare.com/client/" + api_version,
        headers={
            "Authorization": f"Bearer {parser['cf-dns']['token']}",
            "Accept": "application/json",
        }
    )

    if not ctx.obj["config"]["cf-dns"]["token"]:
        console.log(f"[red]No API token provided. Please edit {config_file}.")
        raise click.Abort

    if ctx.obj["config"]["cf-dns"].get("skip-auth-check") != "true":
        # if not read_cache(ctx.obj["config"]["cf-dns"]["token"]):
        with console.status("Checking API token"):
            try:
                response = ctx.obj["session"].get("/user/tokens/verify")
                response.raise_for_status()
            except httpx.HTTPError:
                console.log(f"[red]Invalid API token provided. Please edit {config_file}.")
                raise click.Abort
            else:
                console.log(
                    f"[green]Successfully authenticated as [bold]{response.json()['result']['id']}[/bold]"
                )
    ctx.obj["ip"] = {"4": "", "6": ""}
    if ctx.obj["config"]["cf-dns"].get("skip-ip-fetch") != "true":
        for ip_version in ctx.obj["ip"].keys():
            ctx.obj["ip"][ip_version] = find_ip(ip_version, True)
    ctx.obj["token"] = ctx.obj["config"]["cf-dns"]["token"]


@main.command()
def info():
    """Collects current information."""
    console.log("[i dim]Re-calculating information, this may take a moment.[/]")
    console.log(f"[bold]IPv4:[/bold] {find_ip('4')}")
    console.log(f"[bold]IPv6:[/bold] {find_ip('6')}")
    console.log(f"[bold]Configuration file:[/bold] {DEFAULT_CONFIG_PATH}")
    console.log(f"[bold]Cache file:[/] {cache_dir() / 'cf-dns.cache.json'}")


@main.group(name="list")
def _list():
    """List either zones or records."""


@_list.command(name="zones")
@click.pass_context
def _list_zones(ctx: click.Context):
    """Lists all zones that this API token can access."""
    with console.status("Fetching zones"):
        try:
            zones = get_zones(ctx)
        except httpx.HTTPError:
            console.log(f"[red]Failed to fetch zones.")
            console.print_exception()
            raise click.Abort
        else:
            console.log(f"[green]Successfully fetched zones.")
            for n, zone in enumerate(zones, start=1):
                if not isinstance(zone, dict):
                    continue
                console.print(f"{n:,}. [bold]{zone['name']}[/bold] ({zone['id']})")


@_list.command(name="records")
@click.option(
    "--type",
    "--types",
    "-T",
    "types",
    default=None,
    help="The types of records to list. Comma separated."
)
@click.argument("zone_identifier")
@click.pass_context
def _list_records(ctx: click.Context, types: str, zone_identifier: str):
    """Lists all records in a zone."""
    if types:
        types = types.split(",")
    else:
        types = []
    table = Table(title="Records for zone " + zone_identifier)
    table.add_column("Type", justify="center")
    table.add_column("Name", justify="left")
    table.add_column("Content", justify="left")
    table.add_column("TTL", justify="center")
    table.add_column("Proxied", justify="center")
    table.add_column("Record ID", justify="center")

    with console.status("Fetching records"):
        try:
            zone = get_zone_by(ctx, zone_id=zone_identifier, name=zone_identifier)
            if zone is None:
                console.log("[yellow]:warning: Unable to locally resolve zone name. Fetching from API.")
                zone = {"id": zone_identifier}
            records = get_records(ctx, zone["id"], types=types)
        except httpx.HTTPError:
            console.log(f"[red]Failed to fetch records.")
            console.print_exception()
            raise click.Abort
        else:
            console.log(f"[green]Successfully fetched records.")
            for record in records:
                if types:
                    if record["type"] not in types:
                        continue
                _type = record["type"]
                name = record["name"]
                content = record["content"]
                ttl = record["ttl"]
                if ttl == 1:
                    ttl = "auto"
                else:
                    human_ttl = humanise_time(ttl)
                    if human_ttl != f"{human_ttl} seconds":
                        ttl = f"{human_ttl} ({ttl} seconds)"
                    else:
                        ttl = human_ttl
                proxied = {True: "[#F6821F]Yes[/]", False: "[#92979B]No[/]"}[record["proxied"]]
                if record["proxiable"] is False:
                    proxied = "[#92979B i]N/A[/]"
                table.add_row(_type, name, content, ttl, proxied, record["id"])
    console.print(table)


@main.command()
@click.option(
    "--type",
    "-T",
    "record_type",
    default="A",
    help="The type of record to create. Defaults to A.",
    type=click.Choice(
        ("A", "AAAA", "CNAME", "NS", "PTR", "TXT")
    )
)
@click.option(
    "--name",
    "-N",
    "record_name",
    help="The name of the record to create.",
    prompt=True
)
@click.option(
    "--ttl",
    "-L",
    "ttl",
    default=1,
    help="The TTL of the record to create. Defaults to 1 (auto). Must be 60-86400 otherwise.",
    type=click.IntRange(1, 86400)
)
@click.option(
    "--comment",
    "-C",
    "comment",
    default=None,
    help="The comment of the record to create."
)
@click.option(
    "--proxied",
    "-P",
    "proxied",
    default=False,
    help="Whether the record should be proxied. Defaults to False.",
    type=click.BOOL
)
@click.option(
    "--dry",
    "dry_run",
    is_flag=True,
    help="Only display the changes to make, don't actually make any."
)
@click.argument("zone_identifier", type=str)
@click.argument("content", type=str)
@click.pass_context
def new(
        ctx: click.Context,
        zone_identifier: str,
        record_type: str,
        record_name: str,
        ttl: int,
        comment: t.Optional[str],
        proxied: bool,
        content: str,
        dry_run: bool
):
    """
    Creates a new DNS record.

    ZONE_IDENTIFIER is the ID of the zone to create the record in.

    CONTENT is the content of the record to create. If you want it to be the current IPv4, use `{ipv4}`.
    To instead substitute it for the current IPv6, use `{ipv6}`.
    """

    if ttl != 1 and ttl < 60:
        console.print("TTL must be between 60 and 86,400 seconds, or 1 for auto.")
        raise click.Abort
    if len(record_name) > 255:
        console.print("Record name must be less than 255 characters.")
        raise click.Abort
    content = content.format(
        ipv4=ctx.obj["ip"]["4"],
        ipv6=ctx.obj["ip"]["6"]
    )
    with console.status("Creating DNS record"):
        body = {
            "type": record_type,
            "name": record_name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied,
            "comment": comment,
        }
        if dry_run:
            cts = Syntax(content, "txt", theme="monokai")
            bds = Syntax(json.dumps(body, indent=2), "json", theme="monokai", line_numbers=True)
            console.print(f"Content:")
            console.print(cts)
            console.print()
            console.print(f"JSON POST (to [code]/zones/{zone_identifier}/dns_records[/]):")
            console.print(bds)
            raise click.Abort
        try:
            response = ctx.obj["session"].post(
                f"/zones/{zone_identifier}/dns_records",
                json=body
            )
            response.raise_for_status()
        except httpx.HTTPError:
            console.log(f"[red]Failed to create DNS record.")
            console.print_exception()
            raise click.Abort
        else:
            console.log(f"[green]Successfully created DNS record.")


@main.command()
@click.argument("zone_identifier")
@click.argument("record_identifier")
@click.pass_context
def show(
        ctx: click.Context,
        zone_identifier: str,
        record_identifier: str
):
    """
    Shows information about a DNS record.

    ZONE_IDENTIFIER is the ID of the zone to show the record from.

    RECORD_IDENTIFIER is the ID of the record to show.
    """
    with console.status("Fetching DNS record"):
        try:
            zone = get_zone_by(ctx, zone_id=zone_identifier, name=zone_identifier)
            if zone is None:
                console.log("[yellow]:warning: Unable to locally resolve zone name. Fetching from API.")
                zone = zone_identifier
            record = get_record_by(ctx, zone["zone_id"], record_id=record_identifier)
            if record is None:
                console.log(f"[red]Failed to find DNS record (404).")
                raise click.Abort
        except httpx.HTTPError:
            console.log(f"[red]Failed to fetch DNS record.")
            console.print_exception()
            raise click.Abort
        else:
            table = Table(title="Record " + record["id"])
            table.add_column("Key", justify="right")
            table.add_column("Value", justify="left")
            for key, value in record.items():
                # if key in ("zone_id", "id", "created_on", "modified_on"):
                #     continue
                if key == "proxiable":
                    value = {True: "[#F6821F]Yes[/]", False: "[#92979B]No[/]"}[value]
                table.add_row(key, str(value))
            console.print(table)


@main.command()
@click.option(
    "--type",
    "-T",
    "record_type",
    default=None,
    help="The type to change the record to. Defaults to <existing>",
    type=click.Choice(
        ("A", "AAAA", "CNAME", "NS", "PTR", "TXT")
    )
)
@click.option(
    "--name",
    "-N",
    "record_name",
    help="The name to change the record to.",
    default=None
)
@click.option(
    "--ttl",
    "-L",
    "ttl",
    default=None,
    help="The TTL of the record to create. Defaults to <existing>. Must be 60-86400 otherwise.",
    type=click.IntRange(1, 86400)
)
@click.option(
    "--proxied/--unproxied",
    "-P",
    "proxied",
    default=None,
    help="Whether the record should be proxied. Defaults to <existing>.",
)
@click.option(
    "--dry",
    "dry_run",
    is_flag=True,
    help="Only display the changes to make, don't actually make any."
)
@click.argument("zone_identifier", type=str, required=True)
@click.argument("record_identifier", type=str, required=True)
@click.argument("content", type=str, nargs=1, required=False)
@click.pass_context
def edit(
        ctx: click.Context,
        zone_identifier: str,
        record_type: str | None,
        record_name: str | None,
        ttl: int | None,
        proxied: bool | None,
        content: str | None,
        dry_run: bool,
        record_identifier: str
):
    """
    Edits an existing DNS record. This will fully replace it.

    ZONE_IDENTIFIER is the ID of the zone to create the record in.

    CONTENT is the content of the record to create. If you want it to be the current IPv4, use `{ipv4}`.
    To instead substitute it for the current IPv6, use `{ipv6}`.
    """
    content = content.format(
        ipv4=ctx.obj["ip"]["4"],
        ipv6=ctx.obj["ip"]["6"]
    )
    with console.status("Fetching DNS record") as status:
        record = get_record_by(ctx, zone_identifier, name=record_identifier, record_id=record_identifier)
        if record is None:
            console.log(f"[red]Failed to find DNS record (404).")
            raise click.Abort
        body = {
            "type": record_type,
            "name": record_name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied,
        }
        for key, value in body.items():
            if value is None:
                body[key] = record[key]
        if dry_run:
            cts = Syntax(content, "txt", theme="monokai")
            bds = Syntax(json.dumps(body, indent=2), "json", theme="monokai", line_numbers=True)
            console.print(f"Content:")
            console.print(cts)
            console.print()
            console.print(f"JSON POST (to [code]/zones/{zone_identifier}/dns_records[/]):")
            console.print(bds)
            raise click.Abort
        try:
            status.update("Editing DNS record")
            response = ctx.obj["session"].put(
                f"/zones/{zone_identifier}/dns_records",
                json=body
            )
            response.raise_for_status()
        except httpx.HTTPError:
            console.log(f"[red]Failed to create DNS record.")
            console.print_exception()
            raise click.Abort
        else:
            console.log(f"[green]Successfully created DNS record.")


@main.command()
@click.argument("zone_identifier")
@click.argument("record_identifier")
@click.pass_context
def delete(ctx: click.Context, zone_identifier: str, record_identifier: str):
    """
    Deletes a DNS record.

    ZONE_IDENTIFIER is the ID of the zone to delete the record from.

    RECORD_IDENTIFIER is the ID of the record to delete.
    """
    with console.status("Deleting DNS record"):
        try:
            response = ctx.obj["session"].delete(
                f"/zones/{zone_identifier}/dns_records/{record_identifier}"
            )
            response.raise_for_status()
        except httpx.HTTPError:
            console.log(f"[red]Failed to delete DNS record.")
            console.print_exception()
            raise click.Abort
        else:
            console.log(f"[green]Successfully deleted DNS record.")


if __name__ == "__main__":
    main(
        auto_envvar_prefix="CF"
    )
