"""Two clients share one origin (docs/ and docs/tablet/ on the same Pages
site), so they must not share localStorage keys - a tablet save would
otherwise clobber the web twin's. The prefix is the only thing that keeps
them apart, so it is tested under node with a localStorage shim."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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
console.log(JSON.stringify({
  keys: [...store.keys()].sort(),
  hudPlayers: hud.loadState().state.players.length,
  tabPlayers: tab.loadState().state.players.length,
  hudExists: hud.exists(), tabExists: tab.exists(),
  defaults: storageKeys(),
  legacyState: STATE_KEY,
  prefs: client.loadPrefs().brightness,
  cleared: (() => { tab.clear(); return [...store.keys()].sort(); })(),
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


def test_two_prefixes_keep_two_games_apart():
    js = _run()
    assert "lotr-hud-state" in js["keys"]
    assert "lotr-tablet-state" in js["keys"]
    assert js["hudPlayers"] == 2
    assert js["tabPlayers"] == 3
    assert js["hudExists"] and js["tabExists"]


def test_the_default_prefix_is_the_web_twins_existing_keys():
    js = _run()
    assert js["defaults"]["state"] == "lotr-hud-state"
    assert js["defaults"]["replayJournal"] == "lotr-hud-replay-journal"
    assert js["defaults"]["rollup"] == "lotr-hud-stats"
    assert js["legacyState"] == "lotr-hud-state"


def test_history_and_prefs_take_the_prefix_too():
    js = _run()
    assert "lotr-tablet-history" in js["keys"]
    assert "lotr-tablet-stats" in js["keys"]
    assert "lotr-tablet-prefs" in js["keys"]
    assert js["prefs"] == 50


def test_clearing_one_client_leaves_the_other():
    js = _run()
    assert "lotr-hud-state" in js["cleared"]
    assert "lotr-tablet-state" not in js["cleared"]
    assert "lotr-tablet-log" not in js["cleared"]
