"""All data access goes through the client - enforced, not aspirational.

`db.py` exists so that caching, formats and durability are decisions with ONE
home. That only holds if nothing else opens a file. Before this test the
firmware's I/O was split across `main.py` and `quest_catalog.py` with four
ad-hoc closure caches, and one of them (`load_player_side_quests`) was re-read
on every single "+ Side quest" tap because no one place owned the question.

`quest_catalog.py` is the one allowed exception: it is the catalog READER the
client delegates to, and its pure functions are separately host-tested.
"""
import ast
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The client, and the catalog reader it delegates to.
STORAGE_OWNERS = {"db.py", "quest_catalog.py"}

FIRMWARE = (
    ["gamestate.py", "main.py", "phases.py", "leds.py", "hardware.py",
     "viewcopy.py", "xtargets.py"]
    + [os.path.join("ui", f)
       for f in sorted(os.listdir(os.path.join(ROOT, "ui"))) if f.endswith(".py")]
)

IO_CALLS = {"open"}
IO_ATTRS = {("json", "load"), ("json", "dump"),
            ("os", "remove"), ("os", "rename"), ("os", "stat"),
            ("os", "listdir"), ("os", "mkdir")}


def _io_sites(path):
    with open(os.path.join(ROOT, path)) as f:
        tree = ast.parse(f.read())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in IO_CALLS:
            out.append((node.lineno, fn.id))
        elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
            if (fn.value.id, fn.attr) in IO_ATTRS:
                out.append((node.lineno, "%s.%s" % (fn.value.id, fn.attr)))
    return out


@pytest.mark.parametrize("path", FIRMWARE)
def test_firmware_module_does_no_storage_io(path):
    assert os.path.basename(path) not in STORAGE_OWNERS, "fixture drift"
    sites = _io_sites(path)
    assert not sites, (
        "%s touches storage directly at %s - route it through db.py so caching, "
        "formats and durability stay in one place" % (path, sites))


def test_the_client_is_the_one_that_does():
    """Guards the inverse: if db.py stopped doing I/O the test above would
    pass vacuously and mean nothing."""
    assert _io_sites("db.py"), "db.py should be the module that touches storage"


def test_main_does_not_import_storage_primitives():
    """main.py used to own the framing and the paths; db.py does now."""
    with open(os.path.join(ROOT, "main.py")) as f:
        tree = ast.parse(f.read())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert "struct" not in roots, "framing belongs to db.py"
    assert "db" in roots, "main.py must go through the client"


@pytest.mark.parametrize("name", ["STATE_PATH", "LOG_PATH", "REPLAY_JOURNAL",
                                  "HISTORY_PATH", "PREFS_PATH"])
def test_every_store_path_is_declared_in_one_place(name):
    import db
    assert isinstance(getattr(db, name), str)


def test_the_web_twin_keeps_localstorage_in_its_client_too():
    """Same rule, same reason - the twin had three keys spread across main.js."""
    js = os.path.join(ROOT, "docs", "js")
    offenders = []
    for fn in sorted(os.listdir(js)):
        if not fn.endswith(".js") or fn == "db.js":
            continue
        with open(os.path.join(js, fn)) as f:
            for i, line in enumerate(f, 1):
                if "localStorage" in line and not line.strip().startswith("//"):
                    offenders.append("%s:%d" % (fn, i))
    assert not offenders, (
        "localStorage outside docs/js/db.js at %s - route it through the client"
        % offenders)


def test_the_twins_expose_the_same_client_surface():
    """db.py <-> db.js, since quest_catalog's pair has no parity test and drifted."""
    import db
    with open(os.path.join(ROOT, "docs", "js", "db.js")) as f:
        js = f.read()
    for py, jsname in [("save_state", "saveState"), ("save_log", "saveLog"),
                       ("save_replay", "saveReplay"), ("commit", "commit"),
                       ("load_state", "loadState"), ("load_log", "loadLog"),
                       ("load_replay", "loadReplay"), ("exists", "exists"),
                       ("clear", "clear")]:
        assert hasattr(db.Session, py), "db.py Session lacks %s" % py
        assert jsname + "(" in js, "db.js Session lacks %s" % jsname
    for py, jsname in [("append", "append"), ("scan", "scan"),
                       ("rollup", "rollup")]:
        assert hasattr(db.History, py)
        assert jsname + "(" in js, "db.js History lacks %s" % jsname
    for py, jsname in [("index", "index"), ("scenario", "scenario"),
                       ("bundle", "bundle"), ("locations", "locations"),
                       ("side_quests", "sideQuests"), ("icons", "icons"),
                       ("tips", "tips")]:
        assert hasattr(db.DataClient, py), "db.py DataClient lacks %s" % py
        assert jsname + "(" in js, "db.js DataClient lacks %s" % jsname
