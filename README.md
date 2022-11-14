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

<detail>
<summary>If you don't have pipx:</summary>

```bash
$ pip install pipx
$ python3 -m pipx ensurepath
```
</detail>

> Note: In order to install scripts properly, pip(x) requires that you have python 3.9 or newer.

## What each tool is

|                file               |             command            |                            description                              |
| --------------------------------- | ------------------------------ | ------------------------------------------------------------------- |
| [systemd_gen.py](/scripts/systemd_gen.py) | runs on it's own, or `python3` | Generates systemd services. Decent customisable, and very fast.     |
| [test_script.sh](/test_script.sh) | literally a shell script       | Mostly used internally for testing scripts that call other scripts. |
| [README.md](/README.md)           | `cat README.md`                | Hm. I'm not sure what this is for. I think it shows text.           |
| [.gitignore](/.gitignore)         | `ed .gitignore`                | Tells git "HEY DON'T UPLOAD ./VENV SINCE IT CONTAINS THE ENTIRE PYTHON LIBRARY" |
| [venv](https://youtu.be/dQw4w9WgXcQ) | `rm -rf venv`                  | If you got this directory while cloning, the gitignore broke.       |
| [requirements.txt](/requirements.txt) | `pip install -r requirements.txt` | Just a list of dependencies for the project.                 |
| [upnp_revoker.py](/scripts/upnp_revoker.py) | Same as systemd-gen           | Allows for bulk-deletion of upnp forwards, wrapping with the upnpc package. |
| [mass-git-updater](/scripts/mass-git-updater/main.py) | `python3 scripts/mass-git-updater` | Recursively searches the provided file path and basically runs `git pull` on all known repos. |

## Contributing
Not sure why you would be, but basically just make sure it works, and that it's a modification to a current script.
I'll only add new scripts if they look really really really useful.
