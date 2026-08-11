"""Executed twin parity: the web twin's classes must still have their methods.

The iron rule says the two implementations stay in lockstep, and every check
for that until now compared *behaviour* at points a test thought to look at.
Nothing asserted the JS classes were structurally intact, so an edit that
deleted a span of screen_play.js took `draw`, `_totalsRow` and
`_drawQuestSetup` with it and the suite stayed green - the firmware was fine,
the twin had no `draw`, and the app froze on the first tap that routed to the
play screen.

Reading the file would not have caught it either: the class still parsed, the
module still imported, and the missing methods were only visible by asking the
prototype what it had. So this asks.
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


def _camel(name):
    """ui/screen_play.py's `_draw_quest_setup` is screen_play.js's
    `_drawQuestSetup`. Leading underscores are kept."""
    lead = len(name) - len(name.lstrip("_"))
    head, *rest = name.lstrip("_").split("_")
    return "_" * lead + head + "".join(p.title() for p in rest)


_PROBE = """\
const out = {};
for (const [mod, names] of Object.entries(%s)) {
  const m = await import(mod);
  for (const n of names) {
    const C = m[n];
    if (typeof C !== "function") { out[n] = null; continue; }
    // Walk the prototype chain so an inherited method still counts.
    const seen = new Set();
    for (let p = C.prototype; p && p !== Object.prototype; p = Object.getPrototypeOf(p)) {
      for (const k of Object.getOwnPropertyNames(p)) seen.add(k);
    }
    out[n] = [...seen];
  }
}
console.log(JSON.stringify(out));
"""


def _js_methods(targets):
    """{className: [method, ...]} from the real modules, under node."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        # docs/js has no package.json, so node reads its .js as CommonJS.
        # Copying beside a type:module marker is the least invasive fix - the
        # alternative puts a package.json into the deployed Pages site.
        for f in os.listdir(os.path.join(ROOT, "docs", "js")):
            if f.endswith(".js"):
                shutil.copy(os.path.join(ROOT, "docs", "js", f),
                            os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write(_PROBE % json.dumps(targets))
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, "web twin failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


# Every class the router constructs and then calls .draw()/.onButton() on.
_ROUTED = {
    "./screen_play.js": ["ScreenPlay"],
    "./screens.js": ["CounterModal", "PlayerSettingsModal", "SideQuestsModal",
                     "LocationPickModal", "PlayersDetailModal",
                     "EliminationModal",
                     "QuestingProgressModal", "SailingModal",
                     "ResolutionModal",
                     "QuestConfigModal", "QuestCardModal",
                     "SideQuestPickModal"],
    "./screens_other.js": ["ScreenPhases", "ScreenLog", "LedModal",
                           "ScreenSettings", "GameOverScreen", "ScreenAbout",
                           "BootScreen", "SetupScreen",
                           "ScenarioSourceScreen", "PickCycleScreen",
                           "ChooseScenarioScreen", "ScenarioOptionsScreen",
                           "CatalogUnavailableScreen",
                           "OptionListModal", "LegendScreen",
                           "FirstRunScreen"],
}


def test_every_routed_web_class_can_be_drawn_and_tapped():
    """`screens[active].draw(...)` is the main loop's whole job; a class that
    has lost it takes the app down on the tap that routes there."""
    found = _js_methods(_ROUTED)
    broken = []
    for name, methods in found.items():
        if methods is None:
            broken.append("%s: not exported" % name)
            continue
        if "draw" not in methods:
            broken.append("%s: no draw()" % name)
        if "onButton" not in methods:
            broken.append("%s: no onButton()" % name)
    assert not broken, "web twin classes are not usable:\n  %s" % "\n  ".join(broken)


def test_screen_play_twins_expose_the_same_methods():
    """ScreenPlay is the biggest class in the app and the one both twins edit
    most, so it gets the stricter check: every method the firmware has must
    exist on the twin. Extra JS-only helpers are fine - a missing one is not.
    """
    # Long-standing structural divergence, checked to be functional parity
    # rather than missing behaviour: the twin inlines these into draw()'s
    # branches instead of factoring them out. They predate this gate.
    inlined_in_js = {"_draw_sailing", "_draw_staging"}
    from ui.screen_play import ScreenPlay
    py = {m for m, v in vars(ScreenPlay).items()
          if callable(v) and not m.startswith("__")} - inlined_in_js
    js = set(_js_methods({"./screen_play.js": ["ScreenPlay"]})["ScreenPlay"])
    missing = sorted(m for m in py if _camel(m) not in js)
    assert not missing, (
        "the web twin's ScreenPlay is missing: %s"
        % [(m, _camel(m)) for m in missing])


_SKIP_PROBE = """\
import { skipsFrom, lastWindowBefore, isActionWindow, VIEW_ORDER, SKIPS,
         GameState } from "./gamestate.js";
const g = new GameState();
g.enterView("aw_enc_checks");
const landed = g.skipTo("combat_empty");
console.log(JSON.stringify({
  offeredOn: VIEW_ORDER.filter(v => skipsFrom(v).length).sort(),
  landing: lastWindowBefore("refresh"),
  landingIsWindow: isActionWindow(lastWindowBefore("refresh")),
  skipIds: SKIPS.map(s => s.id).sort(),
  landedOn: landed,
  view: g.view,
  step: g.step,
  logMentionsSkip: g.log.some(e => String(e.text || "").includes("Skipped")),
}));
"""


def _js_skip_facts():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(os.path.join(ROOT, "docs", "js")):
            if f.endswith(".js"):
                shutil.copy(os.path.join(ROOT, "docs", "js", f),
                            os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write(_SKIP_PROBE)
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True,
                           text=True)
        assert r.returncode == 0, "web twin failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


def test_phase_skip_behaves_identically_in_both_twins():
    """The skip's safety rule has to hold on the web too.

    Landing on the last action window before the destination is what keeps a
    skip from silently eating a phase-locked opportunity (34 distinct cards
    print "Combat Action:"). A twin that landed somewhere else would be a
    different game, so this compares the actual values rather than trusting
    that the port looked right.
    """
    from gamestate import (GameState, VIEW_ORDER, SKIPS, is_action_window,
                           last_window_before, skips_from)

    js = _js_skip_facts()

    assert js["offeredOn"] == sorted(v for v in VIEW_ORDER if skips_from(v))
    assert js["skipIds"] == sorted(s["id"] for s in SKIPS)
    assert js["landing"] == last_window_before("refresh")
    assert js["landingIsWindow"] is is_action_window(last_window_before("refresh"))

    g = GameState()
    g.enter_view("aw_enc_checks")
    landed = g.skip_to("combat_empty")
    assert js["landedOn"] == landed
    assert js["view"] == g.view
    assert js["step"] == g.step
    assert js["logMentionsSkip"] is True
