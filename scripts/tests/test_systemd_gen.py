def test_import():
    from .. import systemd_gen

    assert systemd_gen.__file__.endswith(".py")
