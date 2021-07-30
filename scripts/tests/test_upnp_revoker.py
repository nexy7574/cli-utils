def test_import():
    try:
        from .. import upnp_revoker
    except ImportError:
        return False

    assert upnp_revoker.__file__.endswith(".py"), "the hell"
    assert hasattr(upnp_revoker, "print_ports"), "No function thingy"
