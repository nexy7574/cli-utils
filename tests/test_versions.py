import pytest
import importlib


@pytest.mark.parametrize("module", ["ensure_upnp", "hashgen", "systemd_gen", "upnp_revoker", "visual_rm"])
def test_import(module: str):
    try:
        importlib.import_module("scripts." + module, "scripts")
    except ImportError as e:
        assert False, e
