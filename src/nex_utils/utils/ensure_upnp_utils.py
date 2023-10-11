import textwrap

from rich.table import Table

__all__ = ("resolve_name", "is_sane_port_number", "render_mapping_table", "generate_rule_info")


def resolve_name(entry: dict) -> str:
    """Resolves a configuration name to something that is human-readable"""
    name = entry.get("name")
    if not name:
        internal = entry["internal_port"]
        external = entry["external_port"]
        protocol = entry["protocol"].upper()
        if internal == external:
            return "{} ({})".format(internal, protocol)
        else:
            return "{}<=>{} ({})".format(internal, external, protocol)
    return name


def is_sane_port_number(port: int) -> bool:
    """Checks if a port is a sane one."""
    return port in range(1, 2**16 + 1)


def _generate_table(plural: bool = True) -> Table:
    table = Table(title="Persistent UPnP Port Mapping" + ("s" if plural else ""))

    if plural:
        table.add_column("Index", justify="left")
    table.add_column("Name", justify="left")
    table.add_column("Internal Port", justify="center")
    table.add_column("External Port", justify="center")
    table.add_column("Protocol", justify="center")
    table.add_column("Lease time (s)", justify="center")
    return table


def _add_entry_to_table(table: Table, entry: dict, *, index: int = None):
    name = textwrap.shorten(resolve_name(entry), width=32, placeholder="...")
    internal = entry["internal_port"]
    external = entry["external_port"]
    protocol = entry["protocol"].upper()
    lease_time = entry.get("lease_time") or "unlimited"
    if index is None:
        table.add_row(str(name), str(internal), str(external), str(protocol), str(lease_time))
    else:
        table.add_row(str(index), str(name), str(internal), str(external), str(protocol), str(lease_time))


def render_mapping_table(config: list) -> Table:
    table = _generate_table(True)

    for n, entry in enumerate(config):
        _add_entry_to_table(table, entry, index=n)

    return table


def generate_rule_info(entry: dict) -> Table:
    table = _generate_table(False)
    _add_entry_to_table(table, entry)
    return table
