"""DataClient.rulesText()/rules_text() (tablet M5 Task 2) - the client reads
tools/build_rules_text.py's docs/data/rules_text.json artifact.

Mirrors tips()/loadTips()'s contract exactly, except the miss value: tips()
degrades to {} (a lookup table that should just miss), rules_text() degrades
to None (there is nothing sensible to merge a lookup into - the tablet boot
seats it straight into ui.rules and treats None as "unavailable").

Python side is exercised directly against quest_catalog.load_rules_text() and
db.DataClient.rules_text() (path swapped via monkeypatch - there is no /data/
on the host). JS side is a node probe with globalThis.fetch stubbed, the same
staging test_db_prefix.py uses.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db
import quest_catalog

RULES_FIXTURE = {
    "book": "Rules Reference",
    "sections": {
        "1.1": {"ids": ["1.1"], "title": "t", "text": "x", "see_also": []},
    },
    "glossary": {},
    "faq": [],
}


# --- Python: quest_catalog.load_rules_text() -------------------------------

def test_load_rules_text_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(quest_catalog, "RULES_TEXT_PATH",
                         str(tmp_path / "no-such-file.json"))
    assert quest_catalog.load_rules_text() is None


def test_load_rules_text_returns_none_on_corrupt_json(tmp_path, monkeypatch):
    path = tmp_path / "rules_text.json"
    path.write_text("{not json")
    monkeypatch.setattr(quest_catalog, "RULES_TEXT_PATH", str(path))
    assert quest_catalog.load_rules_text() is None


def test_load_rules_text_returns_dict_when_present(tmp_path, monkeypatch):
    path = tmp_path / "rules_text.json"
    path.write_text(json.dumps(RULES_FIXTURE))
    monkeypatch.setattr(quest_catalog, "RULES_TEXT_PATH", str(path))
    assert quest_catalog.load_rules_text() == RULES_FIXTURE


# --- Python: db.DataClient.rules_text() (pinned cache) ----------------------

def test_data_client_rules_text_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(quest_catalog, "RULES_TEXT_PATH",
                         str(tmp_path / "missing.json"))
    client = db.DataClient()
    assert client.rules_text() is None


def test_data_client_rules_text_caches_miss_on_absent(tmp_path, monkeypatch):
    """Calling twice with missing file should cache the miss, not re-read."""
    monkeypatch.setattr(quest_catalog, "RULES_TEXT_PATH",
                         str(tmp_path / "missing.json"))
    calls = []
    real_load = quest_catalog.load_rules_text()

    def counting_load():
        calls.append(1)
        return real_load
    monkeypatch.setattr(quest_catalog, "load_rules_text", counting_load)

    client = db.DataClient()
    first = client.rules_text()
    second = client.rules_text()
    assert first is None
    assert second is None
    assert len(calls) == 1        # second call hit the pinned cache


def test_data_client_rules_text_caches_after_first_call(tmp_path, monkeypatch):
    path = tmp_path / "rules_text.json"
    path.write_text(json.dumps(RULES_FIXTURE))
    monkeypatch.setattr(quest_catalog, "RULES_TEXT_PATH", str(path))
    calls = []
    real_load = quest_catalog.load_rules_text()

    def counting_load():
        calls.append(1)
        return real_load
    monkeypatch.setattr(quest_catalog, "load_rules_text", counting_load)

    client = db.DataClient()
    first = client.rules_text()
    second = client.rules_text()
    assert first == RULES_FIXTURE
    assert second == RULES_FIXTURE
    assert len(calls) == 1        # second call hit the pinned cache


# --- JS: DataClient.rulesText() under node, fetch stubbed -------------------

_PROBE = """\
let mode = "404";
let rulesFetchCount = 0;
globalThis.fetch = async (url) => {
  if (String(url).includes("rules_text.json")) {
    rulesFetchCount++;
    if (mode === "404") return { ok: false };
    return { ok: true, json: async () => (%s) };
  }
  return { ok: false };
};
const { DataClient } = await import("./db.js");

// Test 1: Two calls on same client with missing file - should cache miss
const clientMiss = new DataClient();
const missFirst = await clientMiss.rulesText();
const countAfterFirstMiss = rulesFetchCount;
const missSecond = await clientMiss.rulesText();
const countAfterSecondMiss = rulesFetchCount;

rulesFetchCount = 0;
mode = "ok";
// Test 2: Two calls on same client with present file - should cache hit
const clientHit = new DataClient();
const first = await clientHit.rulesText();
const second = await clientHit.rulesText();

console.log(JSON.stringify({
  missFirst, missSecond, countAfterFirstMiss, countAfterSecondMiss,
  first, second, countAfterTwoCalls: rulesFetchCount,
}));
""" % json.dumps(RULES_FIXTURE)


def _run_js_probe():
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
    return _run_js_probe()


def test_js_rules_text_caches_miss_on_404(js):
    assert js["missFirst"] is None
    assert js["countAfterFirstMiss"] == 1
    assert js["missSecond"] is None
    # Two calls to rulesText() with 404, one fetch - the second hit the pinned cache.
    assert js["countAfterSecondMiss"] == 1


def test_js_rules_text_returns_parsed_body_and_caches(js):
    assert js["first"] == RULES_FIXTURE
    assert js["second"] == RULES_FIXTURE
    # Two calls to rulesText(), one fetch - the second hit the pinned cache.
    assert js["countAfterTwoCalls"] == 1
