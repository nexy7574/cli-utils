#!/usr/bin/env python3
"""
Having wg-quick was way too difficult (actually having to type more than 3 words, ew), so I made a CLI that looks
pretty!
"""

import click
import subprocess
import rich
from rich.tree import Tree

try:
    from utils.wg_man import get_interface_stats, generate_tree
except ImportError:
    from scripts.utils.wg_man import get_interface_stats, generate_tree

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


if __name__ == "__main__":
    main()