import subprocess
import ipaddress
import datetime
import humanize
from rich.tree import Tree


__all__ = (
    "get_interface_stats",
    "generate_tree"
)


def get_interface_stats(sudo: str, interface_name: str) -> dict:
    """Gets an interface details as JSON"""
    data = {
        "public_key": None,
        "private_key": None,
        "listen_port": None,
        "peers": [],
        "preshared-keys": {},
        "endpoints": {},
        "allowed-ips": {},
        "latest-handshakes": {},
        "transfer": {},
        "persistent-keepalive": {},
    }

    cmd = [sudo, "wg", "show", interface_name]
    for key in data.keys():
        command = cmd[:] + [key.replace("_", "-")]
        proc = subprocess.run(command, capture_output=True, encoding="utf-8")
        # print(proc.stdout.encode(), flush=True)
        # print(proc.stderr.encode(), file=sys.stderr, flush=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Command {command} failed with return code {proc.returncode}")
        stdout = proc.stdout.strip()
        match key:
            case "public_key":
                data["public_key"] = stdout.strip()
            case "private_key":
                data["private_key"] = stdout.strip()
            case "listen_port":
                data["listen_port"] = int(stdout.strip())
            case "peers":
                data["peers"] = stdout.strip().split()
            case "preshared-keys":
                x = stdout.strip().split("\n")
                data["preshared-keys"] = {peer: key for peer, key in [y.split("\t") for y in x]}
            case "endpoints":
                x = stdout.strip().split("\n")
                data["endpoints"] = {peer: endpoint for peer, endpoint in [y.split("\t") for y in x]}
            case "allowed-ips":
                x = stdout.strip().split("\n")
                data["allowed-ips"] = {
                    peer: [ipaddress.ip_network(ip) for ip in ips.split(" ")]
                    for peer, ips in [y.split("\t") for y in x]
                }
            case "latest-handshakes":
                x = stdout.strip().split("\n")
                _d = {}
                for peer, timestamp in [y.split("\t") for y in x]:
                    if timestamp == "0":
                        _d[peer] = None
                    else:
                        _d[peer] = datetime.datetime.fromtimestamp(int(timestamp))
                data["latest-handshakes"] = _d
            case "transfer":
                x = stdout.strip().split("\n")
                data["transfer"] = {
                    peer: {
                        "download": int(received),
                        "upload": int(sent),
                    }
                    for peer, received, sent in [y.split("\t") for y in x]
                }
            case "persistent-keepalive":
                x = stdout.strip().split("\n")
                data["persistent-keepalive"] = {
                    peer: int(interval) if interval.isdigit() else 0 for peer, interval in [y.split("\t") for y in x]
                }
            case _:
                data[key] = stdout or None
    return data


def generate_tree(censor: bool, details: dict, interface: str) -> Tree:
    tree = Tree(f"[bold red]{interface}[/]")
    tree.add(f"[bold]Public Key:[/bold] [black on white]{details['public_key']}[/]")
    if not censor:
        tree.add(f"[bold]Private Key:[/bold] [black on white]{details['private_key']}[/]")
    tree.add(f"[bold]Listen Port:[/bold] {details['listen_port']}")

    peers_tree = tree.add(f"[bold]Peers:[/bold]")
    for peer_pubkey in details["peers"]:
        peer_tree = peers_tree.add(f"[bold yellow]Public Key:[/] [black on white]{peer_pubkey}[/]")
        if not censor:
            peer_tree.add(f"[bold]PSK:[/bold] [black on white]{details['preshared-keys'].get(peer_pubkey, '?')}[/]")
        peer_tree.add(f"[bold]Endpoint:[/bold] {details['endpoints'].get(peer_pubkey, '?')}")

        allowed_ips = [str(x) for x in details["allowed-ips"].get(peer_pubkey, [])]
        peer_tree.add(f"[bold]Allowed IPs:[/bold] {', '.join(allowed_ips)}")

        keep_alive = details["persistent-keepalive"].get(peer_pubkey, "?")
        if keep_alive == "0":
            keep_alive = "off"
        peer_tree.add(f"[bold]Persistent Keepalive:[/bold] {keep_alive}")

        last_handshake = details["latest-handshakes"].get(peer_pubkey, "?")
        if last_handshake != "?":
            if last_handshake is not None:
                last_handshake_ago = humanize.naturaltime(datetime.datetime.now() - last_handshake)
                last_handshake = last_handshake.strftime("%x at %X")
            else:
                last_handshake = last_handshake_ago = "N/A"
        else:
            last_handshake_ago = "?"
        peer_tree.add(f"[bold]Last Handshake:[/bold] {last_handshake} ({last_handshake_ago})")

        transfer = details["transfer"].get(peer_pubkey, {"upload": 0, "download": 0})
        transfer_tree = peer_tree.add(f"[bold]Transfer:[/bold]")
        transfer_tree.add(f"[bold]Uploaded:[/bold] {humanize.naturalsize(transfer['upload'], gnu=True, format='%.2f')}")
        transfer_tree.add(
            f"[bold]Downloaded:[/bold] {humanize.naturalsize(transfer['download'], gnu=True, format='%.2f')}"
        )
    return tree
