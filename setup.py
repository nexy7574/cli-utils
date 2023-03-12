from os import getenv
from setuptools import setup
from subprocess import run

base_version = getenv("UTILS_BUILD_VERSION", "0.2.0a1")
if getenv("UTILS_RELEASE", "0") == "1":
    version = base_version
else:
    _commit = run(("git", "rev-list", "--count", "HEAD"), capture_output=True, encoding="utf-8").stdout
    _commit = _commit.strip()
    version = f"{base_version}.dev{_commit}"

with open("./requirements.txt") as file:
    requirements = file.read().splitlines()

setup(
    name="cli-utils",
    version=version,
    packages=["scripts", "scripts.utils"],
    url="https://github.com/EEKIM10/cli-utils",
    license="GNU General Public License v3.0",
    author="nex",
    author_email="packages+cli-utils@nexy7574.co.uk",
    description="A set of CLI tools that I use.",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pycodestyle>=2.10.0",
            "black>=22.10.0",
        ],
        "gui": [
            "PyQt6>=6.2.0",
        ],
    },
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
