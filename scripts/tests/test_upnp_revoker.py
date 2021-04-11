def test_import():
    from .. import upnp_revoker

    assert upnp_revoker.__file__.endswith(".py"), "the hell"
    assert hasattr(upnp_revoker, "printPorts"), "No function thingy"


def test_function_printPorts():
    # TODO: Fix this function
    pass
    # from ..upnp_revoker import printPorts
    # from contextlib import redirect_stdout  # has to be done to redirect where printPorts
    # # outputs to
    #
    # from io import StringIO
    #
    # stdout = StringIO()
    # with redirect_stdout(stdout):
    #     printed = printPorts([(1, "TCP")])
    #     assert printed is None
    #
    # assert "0: port=1, connection_type=TCP" in stdout.read()
    # # We'll loosely check if it's in there, since whitespace and whatnot don't really matter much
