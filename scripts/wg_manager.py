#!/usr/bin/env python3
"""
Having wg-quick was way too difficult (actually having to type more than 3 words, ew), so I made a CLI that looks
pretty!
"""

import click
import subprocess
import rich
from rich.table import Table
from rich.tree import Tree
import datetime
import humanize
try:
    from utils.wg_man import get_interface_stats
except ImportError:
    from scripts.utils.wg_man import get_interface_stats
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
    sudo = getattr(main, "sudo")  # getattr because linting complains about it being an attribute

    if interface is None:
        interfaces_proc = subprocess.run((sudo, "wg", "show", "interfaces"), capture_output=True, encoding="utf-8")
        interfaces = interfaces_proc.stdout.strip().split()
        console.print(interfaces)
        raise NotImplementedError("Not implemented yet. Please specify an interface name.")
    else:
        details = get_interface_stats(sudo, interface)
        console.print(details)
        tree = Tree(f"[bold red]{interface}[/]")
        tree.add(f"[bold]Public Key:[/bold] [code]{details['public_key']}[/]")
        if not censor:
            tree.add(f"[bold]Private Key:[/bold] [code]{details['private_key']}[/]")
        tree.add(f"[bold]Listen Port:[/bold] {details['listen_port']}")

        peers_tree = tree.add(f"[bold]Peers:[/bold]")
        for peer_pubkey in details["peers"]:
            peer_tree = peers_tree.add(f"[bold yellow]Public Key:[/] [code]{peer_pubkey}[/]")
            if not censor:
                peer_tree.add(f"[bold]PSK:[/bold] [code]{details['preshared-keys'].get(peer_pubkey, '?')}[/]")
            peer_tree.add(f"[bold]Endpoint:[/bold] {details['endpoints'].get(peer_pubkey, '?')}")

            allowed_ips = [
                str(x) for x in details["allowed-ips"].get(peer_pubkey, [])
            ]
            peer_tree.add(f"[bold]Allowed IPs:[/bold] {', '.join(allowed_ips)}")

            keep_alive = details['persistent-keepalive'].get(peer_pubkey, '?')
            if keep_alive == "0":
                keep_alive = "off"
            peer_tree.add(f"[bold]Persistent Keepalive:[/bold] {keep_alive}")

            last_handshake = details['latest-handshakes'].get(peer_pubkey, '?')
            last_handshake_ago = "?"
            if last_handshake != "?":
                if last_handshake is not None:
                    last_handshake_ago = humanize.naturaltime(datetime.datetime.now() - last_handshake)
                last_handshake = last_handshake.strftime("%x at %X")
            else:
                last_handshake_ago = "?"
            peer_tree.add(f"[bold]Last Handshake:[/bold] {last_handshake} ({last_handshake_ago})")

            transfer = details['transfer'].get(peer_pubkey, {"upload": 0, "download": 0})
            transfer_tree = peer_tree.add(f"[bold]Transfer:[/bold]")
            transfer_tree.add(f"[bold]Uploaded:[/bold] {humanize.naturalsize(transfer['upload'], gnu=True, format='%.2f')}")
            transfer_tree.add(f"[bold]Downloaded:[/bold] {humanize.naturalsize(transfer['download'], gnu=True, format='%.2f')}")

        console.print(tree)


if __name__ == "__main__":
    main()
