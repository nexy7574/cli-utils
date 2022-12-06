import subprocess
import ipaddress
import datetime
import sys


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

    cmd = ["sudo", "wg", "show", interface_name]
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
                data["preshared-keys"] = {
                    peer: key for peer, key in [y.split("\t") for y in x]
                }
            case "endpoints":
                x = stdout.strip().split("\n")
                data["endpoints"] = {
                    peer: endpoint for peer, endpoint in [y.split("\t") for y in x]
                }
            case "allowed-ips":
                x = stdout.strip().split("\n")
                data["allowed-ips"] = {
                    peer: [ipaddress.ip_network(ip) for ip in ips.split(" ")] for peer, ips in [y.split("\t") for y in x]
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
