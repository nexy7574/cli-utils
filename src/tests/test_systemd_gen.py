import pathlib

import pytest

from src.nex_utils.systemd_gen import find_executable

# ASSETS = pathlib.Path(__file__).parent / "assets"
# NO_EXEC_NO_SHEBANG = ASSETS / 'no_exec_no_shebang.sh'
# NO_EXEC_SHEBANG = ASSETS / 'no_exec_shebang.sh'
# EXEC_SHEBANG = ASSETS / 'no_exec_shebang.sh'
# EXEC_NO_SHEBANG = ASSETS / 'exec_no_shebang.sh'
# if not all(x.exists() for x in (NO_EXEC_NO_SHEBANG, NO_EXEC_SHEBANG, EXEC_SHEBANG, EXEC_NO_SHEBANG)):
#     raise RuntimeError("Missing assets")


@pytest.mark.parametrize(
    "pth,direct,is_none",
    [
        ("/bin/bash", False, False),
        ("/bin/bash", True, False),
        ("/bin/.this-should-not.exist-nexutils", False, True),
        ("bash", False, False),
        ("python3", False, False),
        ("/bin/systemctl", False, False),
    ],
)
def test_exec_finder(pth: str, direct: bool, is_none: bool):
    r = find_executable(pth, direct)
    if is_none:
        assert r is None, f"{pth} ({direct}) -> {r} != None"
    else:
        assert r is not None, f"{pth} ({direct}) -> {r} != !None"
