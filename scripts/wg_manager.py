#!/usr/bin/env python3
"""
Having wg-quick was way too difficult (actually having to type more than 3 words, ew), so I made a CLI that looks
pretty!
"""
import os
from io import StringIO
from pathlib import Path
from tempfile import mkstemp, NamedTemporaryFile

import click
import configparser
import subprocess
import rich
import httpx
from ipaddress import ip_address, ip_network
from rich.tree import Tree
from rich.table import Table
from rich.syntax import Syntax

from elevate import elevate

from .utils.wg_man import get_interface_stats, generate_tree, generate_private_key, generate_public_key, generate_psk

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

    # for config in configs:
    #     # noinspection PyTypeChecker
    #     config = dict(config)
    #     config.setdefault("Interface", {})
    #     config.setdefault("Peer", {})
    #     interface = config["Interface"].get("Address", "unknown")
    #     public_key = config["Peer"].get("PublicKey", "unknown")
    #     ip_address = config["Peer"].get("AllowedIPs", "unknown")
    #     endpoint = config["Peer"].get("Endpoint", "unknown")
    #     connected = ping_target_is_online(ip_address.split("/")[0])
    #
    #     _ips = ip_address.split(",")
    #     if len(_ips) > 1:
    #         ip_address = f"{_ips[0]} (+{len(_ips) - 1} more)"
    #     table.add_row(
    #         interface, public_key, ip_address, endpoint, {True: ":heavy_check_mark:", False: ":x:"}[connected]
    #     )

    console.print(table)


@peers.command()
@click.option("--dry-run", "-d", is_flag=True, help="Prints what commands would be run instead of running them.")
@click.option("--keepalive/--no-keepalive", default=False, help="Controls if keepalive should be used.")
@click.option("--psk/--no-psk", default=False, help="Controls if a PSK should be used.")
@click.argument("interface")
@click.argument("ip_addr")
def add(dry_run: bool, keepalive: bool, psk: bool, interface: str, ip_addr: str):
    """Adds a peer to an interface"""
    if not os.access("/etc/wireguard", os.W_OK):
        elevate()
        if not os.access("/etc/wireguard", os.W_OK):
            console.print("[red]:x: You do not have permissions to write to /etc/wireguard")
            return

    file = Path("/etc/wireguard") / f"{interface}.conf"
    if not file.exists():
        console.print(f"[red]:x: Interface {interface} does not exist")
        return

    # Parse config
    config = configparser.ConfigParser(strict=False)
    config.read(file)
    config_text = file.read_text()
    if not config.has_section("Interface"):
        console.print(f"[red]:x: Interface {interface} does not have an [Interface] section")
        return

    # get interface's IP range
    ip_range = config["Interface"].get("Address")
    ip_nets = []
    if ip_range is None:
        console.print(f"[red]:x: Interface {interface} does not have an Address")
        return
    for ip in ip_range.split(","):
        try:
            ip_nets.append(ip_network(ip, strict=False))
        except ValueError:
            console.print(f"[red]:x: Interface {interface} has an invalid Address: {ip}")
            return

    # check if IP is in range
    ip = ip_address(ip_addr)
    if not any(ip in ip_net for ip_net in ip_nets):
        console.print(f"[red]:x: IP {ip_addr} is not in range {ip_range}")
        return

    # check if peer already exists
    if ip_addr in config_text:
        console.print(f"[red]:x: Peer already exists with IP {ip_addr}")
        return

    with console.status("Generating peer"):
        private = generate_private_key()
        public = generate_public_key(private)
        psk = generate_psk() if psk else None

        command_args = [
            getattr(main, "sudo", "/usr/bin/sudo"),
            "wg",
            "set",
            interface,
            "peer",
            public,
            "allowed-ips",
            ip_addr,
        ]

        if keepalive:
            command_args.extend(["persistent-keepalive", "25"])

        with NamedTemporaryFile() as t_file:
            if psk:
                t_file.write(psk.encode())
                t_file.flush()
                command_args.extend(["preshared-key", t_file.name])

            if not dry_run:
                result = subprocess.run(command_args)
            else:
                result = subprocess.run(["echo", 'would be running:', *command_args])
        if result.returncode != 0:
            console.print("[dim i]Command failed: " + " ".join(command_args))
            console.print(f"[red]:x: Failed to add peer to {interface}")
            return
        else:
            try:
                external_ip = httpx.get("https://httpbin.org/ip").json()["origin"]
            except httpx.HTTPError:
                external_ip = "example.com"
            console.print(f"[green]:heavy_check_mark: Successfully added peer to {interface}")
            # Create a sample client config
            _client_config = configparser.ConfigParser(strict=False)
            _client_config["Interface"] = {
                "Address": ip_addr + "/24",
                "PrivateKey": private,
                "DNS": "94.140.14.14, 94.140.15.15"
            }
            _client_config["Peer"] = {
                "PublicKey": public,
                "AllowedIPs": "0.0.0.0/0, ::/0",
                "Endpoint": external_ip + ":" + config["Interface"].get("ListenPort", "51820")
            }
            if psk:
                _client_config["Peer"]["PresharedKey"] = psk

            console.print(f"[green]:heavy_check_mark: Sample client config:")
            _io = StringIO()
            _client_config.write(_io)
            _io.seek(0)
            data = _io.read().strip()
            syntax = Syntax(data, "ini", theme="monokai")
            console.print(syntax)
            fn = mkstemp(suffix=".conf")
            with open(fn[1], "w") as f:
                f.write(data)
            os.chmod(fn[1], 0o600)
            console.print(f"[green]:heavy_check_mark: Saved sample client config to {fn[1]}.")


@peers.command()
@click.option("--dry-run", "-d", is_flag=True, help="Prints what commands would be run instead of running them.")
@click.argument("interface")
@click.argument("public_key")
def remove(dry_run: bool, interface: str, public_key: str):
    """Removes a peer from an interface"""
    if not os.access("/etc/wireguard", os.W_OK):
        elevate()
        if not os.access("/etc/wireguard", os.W_OK):
            console.print("[red]:x: You do not have permissions to write to /etc/wireguard")
            return

    with console.status("Removing peer"):
        command_args = [
            getattr(main, "sudo", "/usr/bin/sudo"),
            "wg",
            "set",
            interface,
            "peer",
            public_key,
            "remove",
        ]

        if not dry_run:
            result = subprocess.run(command_args)
        else:
            result = subprocess.run(["echo", 'would be running:', *command_args])
    if result.returncode != 0:
        console.print("[dim i]Command failed: " + " ".join(command_args))
        console.print(f"[red]:x: Failed to remove peer from {interface}")
        return
    else:
        console.print(f"[green]:heavy_check_mark: Successfully removed peer from {interface}")


if __name__ == "__main__":
    main()
