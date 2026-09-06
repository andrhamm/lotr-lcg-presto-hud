"""Two clients share one origin (docs/ and docs/tablet/ on the same Pages
site), so they must not share localStorage keys - a tablet save would
otherwise clobber the web twin's. The prefix is the only thing that keeps
them apart, so it is tested under node with a localStorage shim."""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PROBE = """\
const store = new Map();
globalThis.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => { store.set(k, String(v)); },
  removeItem: k => { store.delete(k); },
  key: i => [...store.keys()][i] ?? null,
  get length() { return store.size; },
};
const { Session, History, DataClient, storageKeys, STATE_KEY } = await import("./db.js");
const { GameState } = await import("./gamestate.js");
const hud = new Session();
const tab = new Session({ prefix: "lotr-tablet-" });
const g1 = new GameState(2, 25); g1.advanceView();
const g2 = new GameState(3, 30); g2.advanceView();
hud.saveState(g1);
tab.saveState(g2);
hud.saveLog(g1);
tab.saveLog(g2);
const hist = new History({ prefix: "lotr-tablet-" });
hist.append({ result: "victory", round: 9 });
const client = new DataClient({ prefix: "lotr-tablet-" });
client.savePrefs({ brightness: 50 });
// The route (where the player was looking) is its own collection, and its
// lifetime is the point: a new game clears the session, and where you are
// looking is not part of that.
client.route.save({ screen: "newgame", cycle: "The Haradrim", slug: "the-mumakil" });
const routeBeforeClear = client.route.load();
console.log(JSON.stringify({
  keys: [...store.keys()].sort(),
  hudPlayers: hud.loadState().state.players.length,
  tabPlayers: tab.loadState().state.players.length,
  hudExists: hud.exists(), tabExists: tab.exists(),
  defaults: storageKeys(),
  legacyState: STATE_KEY,
  prefs: client.loadPrefs().brightness,
  route: routeBeforeClear,
  cleared: (() => { tab.clear(); return [...store.keys()].sort(); })(),
  routeAfterSessionClear: client.route.load(),
  routeAfterOwnClear: (() => { client.route.clear(); return client.route.load(); })(),
}));
"""


def _run():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(os.path.join(ROOT, "docs", "js")):
            if f.endswith(".js"):
                shutil.copy(os.path.join(ROOT, "docs", "js", f), os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write(_PROBE)
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)


@pytest.fixture(scope="module")
def js():
    """The probe is one node process producing every fact these tests check;
    run it once per module rather than once per test."""
    return _run()


def test_two_prefixes_keep_two_games_apart(js):
    assert "lotr-hud-state" in js["keys"]
    assert "lotr-tablet-state" in js["keys"]
    assert js["hudPlayers"] == 2
    assert js["tabPlayers"] == 3
    assert js["hudExists"] and js["tabExists"]


def test_the_default_prefix_is_the_web_twins_existing_keys(js):
    assert js["defaults"]["state"] == "lotr-hud-state"
    assert js["defaults"]["replayJournal"] == "lotr-hud-replay-journal"
    assert js["defaults"]["rollup"] == "lotr-hud-stats"
    assert js["legacyState"] == "lotr-hud-state"


def test_history_and_prefs_take_the_prefix_too(js):
    assert "lotr-tablet-history" in js["keys"]
    assert "lotr-tablet-stats" in js["keys"]
    assert "lotr-tablet-prefs" in js["keys"]
    assert js["prefs"] == 50


def test_the_route_is_its_own_collection_and_outlives_a_new_game(js):
    """Where the player was looking is not part of the save: db.session.clear()
    (what "New game" does) must leave it alone, or a reload during setup would
    be sent back to the landing screen by the very act of starting a game.
    It takes the prefix like everything else, and it has its own clear()."""
    assert "lotr-tablet-route" in js["keys"]
    assert js["route"] == {"screen": "newgame", "cycle": "The Haradrim",
                           "slug": "the-mumakil"}
    assert js["routeAfterSessionClear"] == js["route"]
    assert js["routeAfterOwnClear"] is None


def test_clearing_one_client_leaves_the_other(js):
    assert "lotr-hud-state" in js["cleared"]
    assert "lotr-tablet-state" not in js["cleared"]
    assert "lotr-tablet-log" not in js["cleared"]
