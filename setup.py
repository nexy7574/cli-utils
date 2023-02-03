import glob

from setuptools import setup
from subprocess import run

__VERSION__ = (
    "0.1.0+g"
    + run(("git", "rev-parse", "--short", "HEAD"), capture_output=True, encoding="utf-8", check=True).stdout.strip()
)

with open("./requirements.txt") as file:
    requirements = file.read().splitlines()

setup(
    name="cli-utils",
    version=__VERSION__,
    packages=["scripts", "scripts.utils"],
    url="https://github.com/EEKIM10/cli-utils",
    license="GNU General Public License v3.0",
    author="nex",
    author_email="",
    description="A set of CLI tools that I use.",
    install_requires=requirements,
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "ensure-upnp = scripts.ensure_upnp:main",
            "systemd-gen = scripts.systemd_gen:main",
            "upnp-revoker = scripts.upnp_revoker:main",
            "revoke-upnp = scripts.upnp_revoker:main",
            "visual-rm = scripts.visual_rm:main",
            "vrm = scripts.visual_rm:main",
            "hashgen = scripts.hashgen:main",
            "ruin = scripts.ruin:main",
            "arriva = scripts.arriva:main",
            "wg-manager = scripts.wg_manager:main",
            "afan = scripts.asus_fx504_fan_control:main",
            "cli-utils-install-extra = scripts.install_bash_scripts:main",
            "cf-ddns = scripts.cf_ddns:main",
            "file-gen = scripts.filegen:main",
            "filegen = scripts.filegen:main",
        ]
    },
)
