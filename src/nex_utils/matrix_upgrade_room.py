"""
Upgrades a matrix room and handles a graceful transfer.
"""
import pprint
import traceback

import httpx
import click
from urllib.parse import quote

STATE_TO_COPY = (
    "m.room.avatar",
    "m.room.server_acl",
    "m.space.parent",
    "m.space.child",
    "im.ponies.room_emotes",
    "org.matrix.room.preview_urls",
    "m.room.history_visibility",
    "m.room.encryption",
    "m.room.join_rules",
    "m.room.guest_access",
    "🐟"
)


def get_state(client: httpx.Client, room_id: str) -> list[dict]:
    """Get the state of a room."""
    response = client.get(f"/_matrix/client/v3/rooms/{quote(room_id, '')}/state")
    response.raise_for_status()
    return response.json()


def set_state(client: httpx.Client, room_id: str, event_type: str, state_key: str, content: dict) -> str:
    """Set the state of a room."""
    uri = f"/_matrix/client/v3/rooms/{quote(room_id, '')}/state/{event_type}"
    if state_key:
        uri += f"/{quote(state_key, '')}"
    response = client.put(
        uri,
        json=content
    )
    response.raise_for_status()
    data = response.json()
    return data["event_id"]


def disable_further_messages(client: httpx.Client, room_id: str, current_powerlevels: dict) -> str:
    """Disables further messages in a room."""
    pls = current_powerlevels.copy()
    pls.setdefault("events", {})
    upgrade_pl = pls.get("events", {}).get(
        "m.room.tombstone", pls.get("state_default", 50)
    )
    if pls.get("users_default", 0) >= upgrade_pl:
        pls["users_default"] = upgrade_pl - 1
    if pls.get("events_default", 0) >= upgrade_pl:
        pls["events_default"] = upgrade_pl - 1
    pls["events"]["m.room.message"] = upgrade_pl
    pls["events"]["m.reaction"] = upgrade_pl
    return set_state(client, room_id, "m.room.power_levels", "", pls)

def send_tombstone(client: httpx.Client, room_id: str, new_room_id: str | None, reason: str | None) -> str:
    """Send a tombstone event to a room."""
    content = {
        "replacement_room": new_room_id,
    }
    if reason:
        content["body"] = reason
    return set_state(
        client,
        room_id,
        "m.room.tombstone",
        "",
        content
    )


def get_aliases(client: httpx.Client, room_id: str) -> list[str]:
    """Get the aliases of a room."""
    response = client.get(f"/_matrix/client/v3/rooms/{quote(room_id, '')}/aliases")
    response.raise_for_status()
    return response.json().get("aliases", [])


def delete_aliases(client: httpx.Client, aliases: list[str]) -> None:
    """Delete the aliases of a room."""
    for alias in aliases:
        response = client.delete(f"/_matrix/client/v3/directory/room/{quote(alias, '')}")
        response.raise_for_status()


def create_alias(client: httpx.Client, room_id: str, alias: str) -> None:
    """Create an alias for a room."""
    response = client.put(f"/_matrix/client/v3/directory/room/{quote(alias, '')}", json={"room_id": room_id})
    response.raise_for_status()


def get_member_ids(client: httpx.Client, room_id: str) -> list[str]:
    """Get the member IDs of a room. Only joined members."""
    response = client.get(f"/_matrix/client/v3/rooms/{quote(room_id, '')}/joined_members")
    response.raise_for_status()
    return list(response.json().get("joined", {}).keys())


def get_state_event(state: list[dict], event_type: str, state_key: str = "") -> dict | None:
    """Get a state event from a state list."""
    for evt in state:
        if evt["type"] == event_type and evt.get("state_key") == state_key:
            return evt["content"]
    return None


@click.command()
@click.argument("homeserver", type=str, required=False)
@click.argument("access_token", type=str, required=False)
@click.argument("room_id", type=str, required=False)
def main(homeserver: str, access_token: str, room_id: str) -> None:
    """Upgrades a matrix room. Entirely interactive."""
    homeserver = homeserver or click.prompt("Homeserver URL", type=str)
    access_token = access_token or click.prompt("Access Token", type=str)
    room_id = room_id or click.prompt("Room ID to upgrade", type=str)
    new_room_version = click.prompt("New room version", type=str, default="11", show_default=True)
    custom_room_id = click.prompt("New room ID (empty for auto)", type=str, default="", show_default=True)
    if custom_room_id and not custom_room_id.startswith("!"):
        raise click.UsageError("Custom room ID must be fully qualified.")

    client = httpx.Client(base_url=homeserver, headers={"Authorization": f"Bearer {access_token}"}, timeout=None)
    state = get_state(client, room_id)
    current_powerlevels = get_state_event(state, "m.room.power_levels")
    if not current_powerlevels:
        raise click.ClickException("Room is missing power levels!")
    current_joinrules = get_state_event(state, "m.room.join_rules")
    if not current_joinrules:
        raise click.ClickException("Room is missing join rules!")
    if current_joinrules["join_rule"] == "public":
        preset = "public"
    else:
        preset = "private"
    original_powerlevels = current_powerlevels.copy()

    aliases = get_aliases(client, room_id)
    name = (get_state_event(state, "m.room.name") or {}).get("name")
    if not name:
        click.echo("No room name found.")
    name = click.prompt("New room name", type=str, default=name, show_default=True)
    canonical_alias = get_state_event(state, "m.room.canonical_alias") or {}
    if a := canonical_alias.get("alias"):
        _default = a.split(":")[0][1:]
        alias_local = click.prompt("New canonical alias", type=str, default=_default, show_default=True)
    else:
        alias_local = click.prompt("New canonical alias", type=str, default="")

    room_topic = (get_state_event(state, "m.room.topic") or {}).get("topic", None)
    members = get_member_ids(client, room_id)
    user_pls = current_powerlevels.get("users", {})
    current_powerlevels["users"] = {}
    for user_id, level in user_pls.items():
        try:
            new_pl = click.prompt(f"New power level for {user_id} (^C to omit)", type=int, default=level, show_default=True)
        except KeyboardInterrupt:
            continue
        current_powerlevels["users"][user_id] = new_pl
    if click.confirm("Would you like to add more users to the power levels on creation?"):
        while True:
            user_id = click.prompt("User ID", type=str)
            if user_id not in members:
                if not click.confirm("User is not in the room, add anyway?"):
                    continue
            pl = click.prompt("Power Level", type=int)
            current_powerlevels["users"][user_id] = pl
            if not click.confirm("Add another user?"):
                break

    invite_targets = list(current_powerlevels["users"].keys())
    click.echo("The following members are in the current room: " + ", ".join(members))
    if click.confirm("Would you like to invite everyone from the current room to the new one?", default=True):
        for member in members:
            if member not in invite_targets:
                invite_targets.append(member)
    if click.confirm("Would you like to add more users to the invite list?"):
        while True:
            user_id = click.prompt("User ID (empty to finish)", type=str)
            if not user_id:
                break
            invite_targets.append(user_id)
            if not click.confirm("Add another user?"):
                break

    click.echo("Will invite: " + ", ".join(invite_targets))

    request: dict = {
        "invite": invite_targets,
        "creation_content": {
            "predecessor": {
                "room_id": room_id,
            }
        },
        "power_level_content_override": current_powerlevels,
        "version": new_room_version,
        "initial_state": [],
        "preset": preset
    }
    if name:
        request["name"] = name
    if room_topic:
        request["topic"] = room_topic
    if alias_local:
        if alias_local.startswith("#"):
            alias_local, _ = alias_local.split(":", 1)
            alias_local = alias_local[1:]
        request["room_alias_name"] = alias_local
    if click.confirm("Do you want to publish this room to the directory on creation?"):
        request["visibility"] = "public"

    for evt in state:
        if evt["type"] in STATE_TO_COPY:
            request["initial_state"].append(evt)

    if custom_room_id:
        request["room_id"] = custom_room_id.split(":", 1)[0][1:]
        request["fi.mau.room_id"] = custom_room_id

    reason = click.prompt("Why are you upgrading this room?", type=str)

    done = {
        "aliases": False,
        "canonical_alias": False,
        "lock": False,
        "new_room": False,
        "tombstone": False,
    }

    if not click.confirm("Are you sure you want to proceed?"):
        return
    new_room_id = None
    try:
        click.echo("Removing aliases from previous room")
        delete_aliases(client, aliases)
        done["aliases"] = True
        click.echo("Sending empty canonical alias event")
        set_state(client, room_id, "m.room.canonical_alias", "", {})
        done["canonical_alias"] = True
        click.echo("Locking previous room. Actions past this point are un-reversible.")
        set_state(client, room_id, "m.room.join_rules", "", {"join_rule": "invite"})
        evt_id = disable_further_messages(client, room_id, current_powerlevels)
        request["creation_content"]["predecessor"] = {
            "room_id": room_id,
            "event_id": evt_id
        }
        done["lock"] = True
        click.secho("Creating new room")
        response = client.post("/_matrix/client/v3/createRoom", json=request)
        response.raise_for_status()
        new_room_id = response.json()["room_id"]
        done["new_room"] = True
        click.echo("Sending tombstone event")
        send_tombstone(client, room_id, new_room_id, reason or None)
        done["tombstone"] = True
    except Exception:
        traceback.print_exc()
        click.secho("Upgrade failed! Rolling back as much as possible.", fg="red")
        for key in reversed(done.keys()):
            if not done[key]:
                continue
            click.secho("Reverting %r" % key, fg="yellow")
            match key:
                case "tombstone":
                    click.secho("Tombstone was sent, unable to revert it!", fg="red")
                case "new_room":
                    click.secho("New room was created! Cannot safely revert.", fg="red")
                case "lock":
                    click.echo("Unlocking previous room")
                    set_state(client, room_id, "m.room.power_levels", "", original_powerlevels)
                    set_state(client, room_id, "m.room.join_rules", "", current_joinrules)
                case "canonical_alias":
                    click.echo("Setting back the canonical alias")
                    set_state(client, room_id, "m.room.canonical_alias", "", canonical_alias)
                case "aliases":
                    click.echo("Re-adding aliases to previous room")
                    delete_aliases(client, aliases)
                    for alias in aliases:
                        try:
                            create_alias(client, room_id, alias)
                        except Exception:
                            click.secho("Failed to re-add alias %r" % alias, fg="red")
                case _:
                    break
        click.secho("Reverted as much as possible.", fg="yellow")
        raise click.ClickException("Upgrade failed! Please check the logs for more information.")
    else:
        click.echo("Transferring aliases to new room")
        delete_aliases(client, aliases)
        for alias in aliases:
            try:
                create_alias(client, new_room_id, alias)
            except Exception:
                click.secho("Failed to transfer alias %r" % alias, fg="red")
        done["new_aliases"] = True
        click.secho("All done!", fg="green")


if __name__ == "__main__":
    main()
