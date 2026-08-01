"""Guards against host-only Python reaching the device.

The host runs CPython; the Presto runs MicroPython, whose stdlib is much
smaller. Nothing in the firmware may import a module the device does not have.

This file exists because `preload_scenario` shipped with `import copy` and
sat broken on the device for an entire milestone. It was never caught because
the host has `copy`, and the device never had the quest-picker screens
deployed - so the code path was unreachable there. The moment the firmware was
brought current, tapping "Begin Setup" raised
`ImportError: no module named 'copy'` out of an unguarded dispatch loop and
froze the panel.

Verified against the device (`mpremote ... exec "import copy"`): of everything
the firmware imports, `copy` was the only absent module.
"""
import ast
import builtins
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules the Presto's MicroPython build actually provides, confirmed on the
# device. Anything else in a firmware file is a deploy-time crash.
DEVICE_MODULES = {
    "json", "math", "os", "random", "re", "time", "sys", "gc",
    "pngdec", "presto", "micropython", "machine", "rp2", "array", "struct",
}
# Our own modules, which are deployed alongside.
LOCAL_MODULES = {
    "gamestate", "phases", "leds", "hardware", "quest_catalog", "ui",
    "viewcopy", "xtargets",
    # The data client - the only module that touches storage (see
    # tests/test_no_stray_io.py).
    "db",
}

FIRMWARE_FILES = (
    ["gamestate.py", "main.py", "db.py", "phases.py", "leds.py", "hardware.py",
     "quest_catalog.py", "viewcopy.py", "xtargets.py"]
    + [os.path.join("ui", f) for f in sorted(os.listdir(os.path.join(ROOT, "ui")))
       if f.endswith(".py")]
)


def _imported_roots(path):
    """Every top-level module name imported by a file, including inside
    functions - `import copy` was function-local, which is exactly why a
    module-level scan would have missed it."""
    with open(os.path.join(ROOT, path)) as f:
        tree = ast.parse(f.read())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", FIRMWARE_FILES)
def test_firmware_only_imports_modules_the_device_has(path):
    allowed = DEVICE_MODULES | LOCAL_MODULES
    used = _imported_roots(path)
    missing = sorted(used - allowed)
    assert not missing, (
        "%s imports %s, which MicroPython does not provide. This will raise "
        "ImportError on the Presto - and an unguarded one freezes the panel."
        % (path, missing))


def test_preload_scenario_works_without_the_copy_module():
    """The specific regression: simulate the device by making `copy`
    unimportable, then run the path 'Begin Setup' takes."""
    from gamestate import GameState

    real_import = builtins.__import__

    def no_copy(name, *args, **kwargs):
        if name == "copy":
            raise ImportError("no module named 'copy'")
        return real_import(name, *args, **kwargs)

    stages = [{"stage": 1, "cards": [{"questPoints": 8, "sailing": False,
                                      "faces": [{"side": "A", "name": "X"}]}]}]
    builtins.__import__ = no_copy
    sys.modules.pop("copy", None)
    try:
        g = GameState(2, 25)
        g.preload_scenario({"slug": "s", "name": "n"}, stages)
    finally:
        builtins.__import__ = real_import

    assert g.stages[0]["stage"] == 1
    assert g.quest["stage_n"] == 1 and g.quest["side"] == "A"


def test_preload_scenario_deep_copies_so_the_catalog_is_not_mutated():
    """It must stay a DEEP copy - the caller passes the cached catalog dict,
    and play mutates game.stages."""
    from gamestate import GameState
    stages = [{"stage": 1, "cards": [{"questPoints": 8, "sailing": False,
                                      "faces": [{"side": "A", "name": "X"}]}]}]
    g = GameState(2, 25)
    g.preload_scenario({"slug": "s"}, stages)
    g.stages[0]["cards"][0]["faces"][0]["name"] = "MUTATED"
    g.stages[0]["cards"][0]["questPoints"] = 999
    assert stages[0]["cards"][0]["faces"][0]["name"] == "X"
    assert stages[0]["cards"][0]["questPoints"] == 8
