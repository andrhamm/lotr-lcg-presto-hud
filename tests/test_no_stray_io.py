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
import re
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
    """Same rule, same reason - the twin had three keys spread across main.js.
    The tablet client (docs/tablet/) is under the same rule from its first
    file; the directory may not exist yet."""
    offenders = []
    for sub in ("js", "tablet"):
        top = os.path.join(ROOT, "docs", sub)
        if not os.path.isdir(top):
            continue
        for dirpath, _dirs, files in os.walk(top):
            for fn in sorted(files):
                if not fn.endswith(".js"):
                    continue
                path = os.path.join(dirpath, fn)
                # Only docs/js/db.js is the exempt client - not any file
                # named db.js at any depth (a future docs/tablet/db.js would
                # need its own exemption, and localStorage anywhere else
                # under either directory is still a violation).
                if os.path.relpath(path, ROOT) == os.path.join("docs", "js", "db.js"):
                    continue
                with open(path) as f:
                    for i, line in enumerate(f, 1):
                        if "localStorage" in line and not line.strip().startswith("//"):
                            offenders.append("%s:%d" % (os.path.relpath(path, ROOT), i))
    assert not offenders, (
        "localStorage outside docs/js/db.js at %s - route it through the client"
        % offenders)


# The browser twins' version of the `open` rule above: `fetch` is how a page
# reads, so every read has to go through the client for the same reason - one
# home for caching, formats and durability. Two files are exempt, each for the
# same reason its Python counterpart is.
FETCH_OWNERS = {
    # The catalog READER db.js delegates to - the exact JS twin of the
    # quest_catalog.py exception in STORAGE_OWNERS above.
    os.path.join("docs", "js", "quest_catalog.js"),
    # The service worker IS the network (Task 6; moved to the site root in
    # the hosting-plan Task 1 so its scope covers both clients): its whole
    # contract is to intercept requests and re-issue them, and the client's
    # own reads are among the requests passing through it. It also runs in a
    # worker global with no module graph at all, so it could not import the
    # client even if the layering allowed it.
    os.path.join("docs", "sw.js"),
}

# `fetch(` in code, not in prose - several comments in docs/js discuss "a
# catalog fetch (...)", so the comment filter below is load-bearing. \b keeps
# `prefetch(` out of it.
FETCH_CALL = re.compile(r"\bfetch\s*\(")


def test_the_browser_twins_keep_fetch_in_the_catalog_reader_and_the_worker():
    """Same rule as the localStorage one above, for reads instead of writes.
    A stray fetch is how a screen grows its own cache: the location picker
    used to re-read its gather-list union on every open, and the tablet's
    picker would have every reason to do it again for card art if this were
    not enforced."""
    offenders = []
    for sub in ("js", "tablet"):
        top = os.path.join(ROOT, "docs", sub)
        if not os.path.isdir(top):
            continue
        for dirpath, _dirs, files in os.walk(top):
            for fn in sorted(files):
                if not fn.endswith(".js"):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, ROOT)
                if rel in FETCH_OWNERS:
                    continue
                with open(path) as f:
                    for i, line in enumerate(f, 1):
                        if line.strip().startswith("//"):
                            continue
                        if FETCH_CALL.search(line):
                            offenders.append("%s:%d" % (rel, i))
    # sw.js now lives at the site root (Task 1 of the hosting plan moved it
    # out from under docs/tablet/, so its scope could cover both clients) -
    # scanned directly rather than widening the walk above into every
    # unrelated docs/ subtree (data/, screenshots/, presto/'s markup, ...).
    docs_root = os.path.join(ROOT, "docs")
    for fn in sorted(os.listdir(docs_root)):
        path = os.path.join(docs_root, fn)
        if not (fn.endswith(".js") and os.path.isfile(path)):
            continue
        rel = os.path.relpath(path, ROOT)
        if rel in FETCH_OWNERS:
            continue
        with open(path) as f:
            for i, line in enumerate(f, 1):
                if line.strip().startswith("//"):
                    continue
                if FETCH_CALL.search(line):
                    offenders.append("%s:%d" % (rel, i))
    assert not offenders, (
        "fetch outside %s at %s - route it through the client"
        % (sorted(FETCH_OWNERS), offenders))


def test_the_fetch_owners_are_the_ones_that_actually_fetch():
    """Guards the inverse: an allow-list entry that stopped fetching would
    make the test above pass vacuously (and would mean the exemption is stale
    and should be deleted)."""
    for rel in sorted(FETCH_OWNERS):
        with open(os.path.join(ROOT, rel)) as f:
            code = [ln for ln in f if not ln.strip().startswith("//")]
        assert any(FETCH_CALL.search(ln) for ln in code), \
            "%s is allow-listed for fetch but never calls it" % rel


def test_the_fetch_regex_ignores_prose_and_prefetch():
    assert FETCH_CALL.search("return fetch(url)")
    assert FETCH_CALL.search("await fetch (url)")
    assert not FETCH_CALL.search("prefetch(urls)")
    assert not FETCH_CALL.search("a catalog fetch, once")


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
                       ("tips", "tips"), ("rules_text", "rulesText")]:
        assert hasattr(db.DataClient, py), "db.py DataClient lacks %s" % py
        assert jsname + "(" in js, "db.js DataClient lacks %s" % jsname
