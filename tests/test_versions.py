import pytest


@pytest.mark.parametrize("module", ["ensure_upnp", "hashgen", "systemd_gen", "upnp_revoker", "visual_rm"])
def test_import(module: str):
    try:
        __import__("scripts." + module)
    except ImportError as e:
        assert False, e
