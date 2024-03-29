# cli-utils

This package contains a bunch of shell scripts that I use to make my life easier when working in a command line.
A lot of these scripts are mainly just wrappers around other tools, but with more ✨sparkle✨.
A lot of the modifications include adding colours, progress bars, etc, as well as making logging more verbose,
and generally just looking pretty.

The only benefit to these tools is they look good - I am almost certain you can find an officially maintained 
package that includes very similar scripts that do the exact same thing as mine, just with better efficiency.

Still though, if you're a sucker for moving bars and colours, then this is the package for you.

## Installing (the right way)

Previously, it was recommended to just add [scripts](/scripts) to your PATH.
This is no longer the case.

You can now install these scripts using `pipx`:

```bash
$ pipx install git+https://github.com/EEKIM10/cli-utils
```

<details markdown="1">
<summary>If you don't have pipx:</summary>

```bash
$ pip install pipx
$ python3 -m pipx ensurepath
```

</details>

> Note: In order to install scripts properly, pip(x) requires that you have python 3.10 or newer.

## Running
Once you've installed via `pipx`, you'll want to ensure that the scripts are on your PATH.
By default, `pipx` installs the scripts into `~/.local/bin`, so you'll want to add that to your PATH.
Pipx has a useful command for this: `pipx ensurepath`. It may take a few seconds, but it will ensure that all shells
have the correct PATH.

### Elevated privileges
By default, scripts are added to ~/.local/bin, meaning if you want to run them with elevated privileges, you'll need to
either add `/home/<user>/.local/bin` to `/root/.profile`, or specify the full path
(like `sudo ~/.local/bin/vrm`).

Scripts now attempt to automatically elevate their privileges if they need it - note that this may require a password
prompt, which *may* break the output.
Bear in mind that, if you do not add the scripts to root's PATH, the automatic elevation will fail
(since [elevate](https://pypi.org/projects/elevate) spawns the command again in a fresh shell)

## What each tool is

| file                                                            | command                       | version      | description                                                                                                                                                                                           |
|-----------------------------------------------------------------|-------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [ensure_upnp.py](/scripts/ensure_upnp.py)                       | `ensure-upnp`                 | python 3.10+ | Simple script designed to be run by a crontab to mass-forward upnp ports                                                                                                                              |
| [hashgen.py](/scripts/hashgen.py)                               | `hashgen`                     | python 3.10+ | A custom tool to generate file hashes. Shows progress for large files & supports simultaneous hashing                                                                                                 |
| [systemd_gen.py](/scripts/systemd_gen.py)                       | `systemd-gen`                 | python 3.10+ | Program to create systemd unit files.                                                                                                                                                                 |
| [upnp_revoker.py](/scripts/upnp_revoker.py)                     | `revoke-upnp`, `upnp-revoker` | python 3.10+ | The reverse of ensure_upnp - lists all forwarded upnp ports in a nice little table with bulk-unforwarding                                                                                             |
| [visual_rm.py](/scripts/visual_rm.py)                           | `vrm`, `visual-rm`            | python 3.10+ | Used for mass-deleting files by recursively removing their directories. Provides a nice progress display with an ETA.                                                                                 |
| [ruin.py](/scripts/ruin.py)                                     | `ruin`                        | python 3.10+ | A tool to corrupt files in fun ways. Has some amazing effects on MP4/MOVs, and is very useful for "accidentally corrupting" school work :^)                                                           |
| [arriva](/scripts/arriva.py)                                    | `arriva`                      | python 3.11+ | This is a tool I use to automatically connect to my bus operator's free wifi without the hassle of a web-browser captive portal. **This is a very personal script and likely will not work for you!** |
| [wg_manager.py](/scripts/wg_manager.py)                         | `wg-manager`                  | python 3.10+ | A tool to manage wireguard VPN connections. (WIP)                                                                                                                                                     |
| [asus_fx504_fan_control.py](/scripts/asus_fx504_fan_control.py) | `afan`                        | python 3.10+ | A tool to control the fan boost mode on my laptop (ASUS FX504GD). Probably not universally useful                                                                                                     |
| [filegen.py](/scripts/filegen.py)                               | `filegen`                     | python 3.10+ | A tool to generate files of a given size.                                                                                                                                                             |
| [flash.py](/scripts/flash.py)                                   | `flash`                       | python 3.12+ | A tool to flash a file to a device.                                                                                                                                                                   |

### "Version"
In the above table, "Version" refers to the python version that the script was written in.
If a script requires a newer python version, such will be stated.

If a script does not work with your python version (e.g. a SyntaxError is raised at runtime), please upgrade your python version.
You can also open an issue to ask me to update the minimum python version, or open a PR to do it yourself.

## Configuration

All configuration files are stored in `$HOME/.config/cli-utils`, even on Windows.

You should not need to edit these files as usually they're controlled by scripts.

## Cache?

Any caches are stored in `$HOME/.cache/cli-utils`, though caches aren't frequently used.
More-often than not, any "cache" files are stored in /tmp (or an equivalent temporary directory).

## Contributing

Not sure why you would be, but basically just make sure it works, and that it's a modification to a current script.
I'll only add new scripts if they look really really really useful.
