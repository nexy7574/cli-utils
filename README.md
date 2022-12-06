# cli-utils

I use these.

I also wrote these.

You can use them if you wanna, however I'm not sure how well they'll work cross-platform

I know they work on my linux install, and most likely work on my raspberry pi too,
but that doesn't mean it'll work globally.

## Running

If you want to run any of these, you need at least python3.6 for most of these,
however python3.8+ is recommended (since these are written in 3.9)

If you're suddenly getting `SyntaxError`, just upgrade.

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

> Note: In order to install scripts properly, pip(x) requires that you have python 3.9 or newer.

## What each tool is

| file                                        | command                       | version      | description                                                                                                                                                                                           |
|---------------------------------------------|-------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [ensure_upnp.py](/scripts/ensure_upnp.py)   | `ensure-upnp`                 | python 3.9+  | Simple script designed to be run by a crontab to mass-forward upnp ports                                                                                                                              |
| [hashgen.py](/scripts/hashgen.py)           | `hashgen`                     | python 3.9+  | A custom tool to generate file hashes. Shows progress for large files & supports simultaneous hashing                                                                                                 |
| [systemd_gen.py](/scripts/systemd_gen.py)   | `systemd-gen`                 | python 3.9+  | Program to create systemd unit files.                                                                                                                                                                 |
| [upnp_revoker.py](/scripts/upnp_revoker.py) | `revoke-upnp`, `upnp-revoker` | python 3.9+  | The reverse of ensure_upnp - lists all forwarded upnp ports in a nice little table with bulk-unforwarding                                                                                             |
| [visual_rm.py](/scripts/visual_rm.py)       | `vrm`, `visual-rm`            | python 3.9+  | Used for mass-deleting files by recursively removing their directories. Provides a nice progress display with an ETA.                                                                                 |
| [ruin.py](/scripts/ruin.py)                 | `ruin`                        | python 3.9+  | A tool to corrupt files in fun ways. Has some amazing effects on MP4/MOVs, and is very useful for "accidentally corrupting" school work :^)                                                           |
| [arriva](/scripts/arriva.py)                | `arriva`                      | python 3.11+ | This is a tool I use to automatically connect to my bus operator's free wifi without the hassle of a web-browser captive portal. **This is a very personal script and likely will not work for you!** |

### "Version"
In the above table, "Version" refers to the python version that the script was written in.
If a script requires a newer python version, such will be stated.

If a script does not work with your python version (e.g. a SyntaxError is raised at runtime), please upgrade your python version.
You can also open an issue to ask me to update the minimum python version, or open a PR to do it yourself.

## Contributing

Not sure why you would be, but basically just make sure it works, and that it's a modification to a current script.
I'll only add new scripts if they look really really really useful.
