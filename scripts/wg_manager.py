#!/usr/bin/env python3
"""
Having wg-quick was way too difficult (actually having to type more than 3 words, ew), so I made a CLI that looks
pretty!
"""
import os
from pathlib import Path

import click
import configparser
import subprocess
import rich
from rich.tree import Tree
from rich.table import Table
from elevate import elevate

from .utils.wg_man import get_interface_stats, generate_tree, ping_target_is_online

    # dev vs prod

console = rich.get_console()


@click.group()
@click.option("--sudo", default="/usr/bin/sudo", help="Path to sudo or alternative program")
@click.option("--no-colour", "--no-color", is_flag=True, help="Disable colour output")
def main(sudo: str, no_colour: bool):
    """
    Very nice and pretty looking wireguard manager
    :return:
    """
    if no_colour:
        console.no_color = True
    try:
        subprocess.run(("wg-quick",), capture_output=True)
        subprocess.run(("wg",), capture_output=True)
    except FileNotFoundError:
        console.log("[red]:x: Wireguard is not installed. See: https://www.wireguard.com/install/")
        return

    main.sudo = sudo


@main.command()
@click.option("--censor", "-C", "--safe", "-S", is_flag=True, help="Censor private keys")
@click.argument("interface", required=False)
def status(censor: bool, interface: str | None):
    """Views the status of an interface. If no interface is specified, all interfaces are shown"""
    sudo = getattr(main, "sudo", "/usr/bin/sudo")  # getattr because linting complains about it being an attribute
    interfaces_proc = subprocess.run((sudo, "wg", "show", "interfaces"), capture_output=True, encoding="utf-8")
    interfaces = interfaces_proc.stdout.strip().split()
    if not interfaces:
        console.log("[red]:x: No active tunnels found")
        return

    if interface is None:
        master_tree = Tree("Active Tunnels")
        for interface in interfaces:
            data = get_interface_stats(sudo, interface)
            tree = generate_tree(censor, data, interface)
            master_tree.add(tree)
        console.print(master_tree)
    else:
        details = get_interface_stats(sudo, interface)
        console.print(generate_tree(censor, details, interface))


@main.group()
def peers():
    """Commands for managing peers."""


@peers.command(name="list")
def _list():
    """Lists existing peers & interfaces"""
    _dir = Path("/etc/wireguard")
    if not _dir.exists():
        console.print("[red]:x: Wireguard directory does not exist")
        return

    files = list(_dir.glob("*.conf"))
    if not files:
        elevate()
        console.print("[red]:x: No configuration files found in /etc/wireguard")
        if os.getuid() != 0 and not os.access(_dir, os.R_OK):
            console.print("[red]:x: [i]Hint: You may not have permissions to list files in /etc/wireguard")
        return

    configs = []
    for file in files:
        config = configparser.ConfigParser(
            strict=False
        )
        config.read(file)
        configs.append(config)

    table = Table(
        title="Peers",
        leading=1
    )
    table.add_column("IP Address")
    table.add_column("Public Key")
    table.add_column("IP Range")
    table.add_column("Endpoint")
    table.add_column("Connected")

    for config in configs:
        # noinspection PyTypeChecker
        config = dict(config)
        config.setdefault("Interface", {})
        config.setdefault("Peer", {})
        interface = config["Interface"].get("Address", "unknown")
        public_key = config["Peer"].get("PublicKey", "unknown")
        ip_address = config["Peer"].get("AllowedIPs", "unknown")
        endpoint = config["Peer"].get("Endpoint", "unknown")
        connected = ping_target_is_online(ip_address.split("/")[0])

        _ips = ip_address.split(",")
        if len(_ips) > 1:
            ip_address = f"{_ips[0]} (+{len(_ips) - 1} more)"
        table.add_row(
            interface, public_key, ip_address, endpoint, {True: ":heavy_check_mark:", False: ":x:"}[connected]
        )

    console.print(table)


if __name__ == "__main__":
    main()
