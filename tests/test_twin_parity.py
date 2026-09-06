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
import { skipsFrom, lastWindowBefore, isActionWindow, SKIPS,
         GameState, setWindowPolicy, flowViews } from "./gamestate.js";
setWindowPolicy(%(policy)r);
const g = new GameState();
g.advanceView();
g.enterView(%(origin)r);
const landed = g.skipTo("combat_empty");
const walk = new GameState(); walk.advanceView();
const seen = [walk.view];
for (let n = 0; n < 20 && walk.view !== "round_end"; n++) { walk.advanceView(); seen.push(walk.view); }
console.log(JSON.stringify({
  offeredOn: flowViews().filter(v => skipsFrom(v).length).sort(),
  landing: lastWindowBefore("refresh"),
  landingIsWindow: isActionWindow(lastWindowBefore("refresh")),
  skipIds: SKIPS.map(s => s.id).sort(),
  landedOn: landed,
  view: g.view,
  step: g.step,
  skipText: g.log.filter(e => String(e.text || "").includes("Skipped")).map(e => e.text),
  offer: (() => { const o = g.skipOffer(); return o && { id: o.skip.id, promoted: o.promoted, engaged: o.engaged, staging_enemies: o.staging_enemies }; })(),
  offerBeforeSkip: (() => { const h = new GameState(); h.advanceView(); h.enterView(%(origin)r); h.setEngaged(0, 1); h.setStagingEnemies(1); const o = h.skipOffer(); return o && { promoted: o.promoted, engaged: o.engaged, staging_enemies: o.staging_enemies }; })(),
  walk: seen,
  offFlow: (() => { const h = new GameState(); h.advanceView(); h.enterView("aw_quest_resolution"); return [h.nextView(), h.prevView()]; })(),
  unknownView: (() => { const h = new GameState(); h.advanceView(); h.view = "some_legacy_view"; return { nextPhase: h.nextPhaseView() }; })(),
}));
"""


@pytest.mark.parametrize("policy,origin", [("views", "aw_enc_checks"),
                                           ("bands", "enc_checks")])
def test_phase_skip_behaves_identically_in_both_twins(policy, origin):
    """The skip's safety rule has to hold on the web too, under both window
    policies.

    Landing on the last action window before the destination is what keeps a
    skip from silently eating a phase-locked opportunity (34 distinct cards
    print "Combat Action:"). A twin that landed somewhere else would be a
    different game, so this compares the actual values rather than trusting
    that the port looked right - and it does so under "views" (the Presto)
    and "bands" (the tablet) alike, since the policy is client-selected state
    and the skip's safety rule must hold under both.
    """
    import gamestate
    from gamestate import (GameState, SKIPS, flow_views, is_action_window,
                           last_window_before, skips_from)

    js = _js_facts(_SKIP_PROBE % {"policy": policy, "origin": origin})
    gamestate.set_window_policy(policy)

    assert js["offeredOn"] == sorted(v for v in flow_views() if skips_from(v))
    assert js["skipIds"] == sorted(s["id"] for s in SKIPS)
    assert js["landing"] == last_window_before("refresh")
    assert js["landingIsWindow"] is is_action_window(last_window_before("refresh"))

    g = GameState()
    g.advance_view()
    g.enter_view(origin)
    landed = g.skip_to("combat_empty")
    assert js["landedOn"] == landed
    assert js["view"] == g.view
    assert js["step"] == g.step
    assert js["skipText"] == [e["text"] for e in g.log if "Skipped" in str(e.get("text", ""))]
    assert js["offer"] == g.skip_offer()        # the skip was already taken - None on both
    h = GameState()
    h.advance_view()
    h.enter_view(origin)
    h.set_engaged(0, 1)
    h.set_staging_enemies(1)
    o = h.skip_offer()
    assert js["offerBeforeSkip"] == {"promoted": o["promoted"], "engaged": o["engaged"],
                                     "staging_enemies": o["staging_enemies"]}

    walk = GameState()
    walk.advance_view()
    seen = [walk.view]
    for _ in range(20):
        if walk.view == "round_end":
            break
        walk.advance_view()
        seen.append(walk.view)
    assert js["walk"] == seen

    # The allocation path enters aw_quest_resolution directly (see
    # screen_play's apply_alloc) - an off-flow view under "bands". Navigation
    # from there must be total in both twins, not just in Python.
    h = GameState()
    h.advance_view()
    h.enter_view("aw_quest_resolution")
    assert js["offFlow"] == [h.next_view(), h.prev_view()]

    # An unrecognised view id has no next phase either - the same total-
    # navigation guarantee next_view()/prev_view() give above, extended to
    # the CTA-label helper.
    h = GameState()
    h.advance_view()
    h.view = "some_legacy_view"
    assert js["unknownView"]["nextPhase"] == h.next_phase_view()


_TRACK_PROBE = """\
import { GameState, setBoardTracking } from "./gamestate.js";
const g = new GameState(2, 25);
g.advanceView();
const n0 = g.log.length;
g.setEngaged(0, 1); g.setEngaged(0, 2); g.setEngaged(0, 3);
g.setStagingEnemies(2);
g.setStagingLocations(1);
const clamp = g.setEngaged(1, -4);
const saved = GameState.fromDict(g.toDict());
const snap = g.snapshot();
const before = g.beginAction();
g.setEngaged(1, 5);
g.addDelta(before);
g.undo();
const xctxOff = Object.keys(g.xContext()).sort();
setBoardTracking(true);
const xctxOn = g.xContext();
console.log(JSON.stringify({
  engaged: g.players.map(p => p.engaged),
  rowsAdded: g.log.length - n0,
  lastTexts: g.log.slice(-3).map(e => e.text),
  clamp,
  savedEngaged: saved.players.map(p => p.engaged),
  savedStaging: [saved.staging_enemies, saved.staging_locations],
  snapEngaged: snap.players["0"].engaged,
  snapStaging: [snap.staging_enemies, snap.staging_locations],
  totals: [g.engagedTotal(), g.enemiesInPlay()],
  undone: g.players[1].engaged,
  xctxOff,
  xctxOn,
}));
"""

# gamestate.py's x_context() keys, in gamestate.js's xContext() spelling.
_XCTX_JS_KEY = {"players": "players", "stage": "stage",
                "highest_threat": "highestThreat", "enemies": "enemies",
                "staging_locations": "stagingLocations"}


def _js_facts(probe):
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
        path = os.path.join(tmp, "probe.mjs")
        with open(path, "w") as f:
            f.write(probe)
        r = subprocess.run([node, path], cwd=tmp, capture_output=True,
                           text=True)
        assert r.returncode == 0, "web twin failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


def test_tracked_counts_behave_identically_in_both_twins():
    import gamestate
    from gamestate import GameState

    js = _js_facts(_TRACK_PROBE)

    g = GameState(2, 25)
    g.advance_view()
    n0 = len(g.log)
    g.set_engaged(0, 1); g.set_engaged(0, 2); g.set_engaged(0, 3)
    g.set_staging_enemies(2)
    g.set_staging_locations(1)
    clamp = g.set_engaged(1, -4)
    saved = GameState.from_dict(g.to_dict())
    snap = g.snapshot()
    before = g.begin_action()
    g.set_engaged(1, 5)
    g.add_delta(before)
    g.undo()

    assert js["engaged"] == [p.engaged for p in g.players]
    assert js["rowsAdded"] == len(g.log) - n0
    assert js["lastTexts"] == [e["text"] for e in g.log[-3:]]
    assert js["clamp"] == clamp
    assert js["savedEngaged"] == [p.engaged for p in saved.players]
    assert js["savedStaging"] == [saved.staging_enemies, saved.staging_locations]
    assert js["snapEngaged"] == snap["players"]["0"]["engaged"]
    assert js["snapStaging"] == [snap["staging_enemies"], snap["staging_locations"]]
    assert js["totals"] == [g.engaged_total(), g.enemies_in_play()]
    assert js["undone"] == g.players[1].engaged

    # x_context()/xContext() omit the tracker-only keys until the client says
    # it tracks the board, and carry the same values as the other once it does.
    assert js["xctxOff"] == sorted(_XCTX_JS_KEY[k] for k in g.x_context())
    gamestate.set_board_tracking(True)
    assert js["xctxOn"] == {_XCTX_JS_KEY[k]: v for k, v in g.x_context().items()}


# xtargets.resolve()'s Python kwarg names, in docs/js/xtargets.js resolve()'s
# option-object spelling.
_RESOLVE_JS_KEY = {"count": "count", "players": "players", "stage": "stage",
                   "highest_threat": "highestThreat", "enemies": "enemies",
                   "staging_locations": "stagingLocations"}

# (description, spec, kwargs) - kwargs are xtargets.resolve()'s Python
# keyword names; unset ones take that function's own defaults on both twins.
_XRESOLVE_CASES = [
    ("players auto ignores a stale count",
     {"target": "players"}, {"count": 99, "players": 3}),
    ("stage auto ignores a stale count",
     {"target": "stage_number"}, {"count": 99, "stage": 4}),
    ("highest_threat auto ignores a stale count",
     {"target": "highest_threat"}, {"count": 99, "highest_threat": 37}),
    ("enemies auto, tracker present, ignores a stale count",
     {"target": "enemies_in_play"}, {"count": 99, "enemies": 6}),
    ("staging_locations auto, tracker present, ignores a stale count",
     {"target": "locations_in_staging"}, {"count": 99, "staging_locations": 2}),
    ("enemies tracker absent falls back to the count",
     {"target": "enemies_in_play"}, {"count": 8}),
    ("enemies tracker and count both absent resolves to nothing",
     {"target": "enemies_in_play"}, {}),
    ("staging_locations tracker absent falls back to the count",
     {"target": "locations_in_staging"}, {"count": 8}),
    ("staging_locations tracker and count both absent resolves to nothing",
     {"target": "locations_in_staging"}, {}),
    # The deferred "enemies == 0" gap: a tracked zero must resolve to 0, not
    # fall back to the stale count as if the tracker had nothing to say.
    ("enemies tracker present and zero resolves to zero, not the stale count",
     {"target": "enemies_in_play"}, {"count": 5, "enemies": 0}),
    ("staging_locations tracker present and zero resolves to zero, not the stale count",
     {"target": "locations_in_staging"}, {"count": 5, "staging_locations": 0}),
    ("a non-auto target with a count",
     {"target": "nazgul_in_play"}, {"count": 3}),
    ("a non-auto target without a count resolves to nothing",
     {"target": "nazgul_in_play"}, {}),
    ("mul/add arithmetic on the count path",
     {"target": "nazgul_in_play", "mul": 2, "add": 3}, {"count": 4}),
    ("mul/add arithmetic on an auto path",
     {"target": "players", "mul": 2, "add": 1}, {"players": 3}),
    ("value never goes below zero",
     {"target": "nazgul_in_play", "add": -100}, {"count": 1}),
    ("an empty spec resolves to nothing, same as a missing one",
     {}, {"count": 5}),
    ("a None/null spec resolves to nothing",
     None, {"count": 5}),
]

_XTARGETS_RESOLVE_PROBE = """\
import { resolve } from "./xtargets.js";
const cases = %s;
console.log(JSON.stringify(cases.map(([spec, opts]) => resolve(spec, opts))));
"""


def test_xtargets_resolve_behaves_identically_in_both_twins():
    """docs/js/xtargets.js's resolve() is hand-mirrored - tools/gen_web_data.py
    embeds it as a fixed string rather than deriving it from xtargets.py's
    source, so nothing but an executed probe catches the two disagreeing.
    One already did: an empty spec ({}) used to resolve through the JS twin
    instead of returning null, because `{}` is truthy in JS where an empty
    dict is falsy in Python - fixed alongside this probe.
    """
    import xtargets

    js_cases = [[spec, {_RESOLVE_JS_KEY[k]: v for k, v in kwargs.items()}]
               for _, spec, kwargs in _XRESOLVE_CASES]
    js = _js_facts(_XTARGETS_RESOLVE_PROBE % json.dumps(js_cases))

    expected = [xtargets.resolve(spec, **kwargs) for _, spec, kwargs in _XRESOLVE_CASES]
    mismatches = [(desc, py, got) for (desc, _, _), py, got
                 in zip(_XRESOLVE_CASES, expected, js) if py != got]
    assert not mismatches, mismatches
    assert js == expected


_ALL_THREAT_PROBE = """\
import { GameState } from "./gamestate.js";
const g = new GameState(3, 25);
g.advanceView();
g.players[2].threat = 49;
const threats = g.adjustAllThreat(2);
console.log(JSON.stringify({
  threats,
  text: g.log[g.log.length - 1].text,
  pendingElim: g.pending_elim,
  eliminated: g.players.map(p => p.eliminated),
}));
"""


def test_adjust_all_threat_matches_the_twin():
    """The tablet players sheet's "All -1/+1/+2" chips (milestone 3, Task 2):
    adjust_all_threat/adjustAllThreat must bump every LIVING player's threat
    and log one line naming every player's resulting value identically on
    both twins - including the case where the batch pushes exactly one
    player over their elimination level (pending_elim)."""
    from gamestate import GameState

    js = _js_facts(_ALL_THREAT_PROBE)

    g = GameState(3, 25)
    g.advance_view()
    g.players[2].threat = 49
    threats = g.adjust_all_threat(2)

    assert js["threats"] == threats == [27, 27, 51]
    assert js["text"] == g.log[-1]["text"]
    assert js["pendingElim"] == g.pending_elim == 2
    assert js["eliminated"] == [p.eliminated for p in g.players] == [False, False, True]


_METADATA_PROBE = """\
import { GameState, foldLog, setWindowPolicy, WINDOW_POLICY_BANDS } from "./gamestate.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2); g.view = "resource";
const tap = fn => { const s = g.beginAction(); fn(); return g.addDelta(s); };
tap(() => g.setStaging(1)); tap(() => g.advanceView()); tap(() => g.setStaging(2));
const views = g.deltas.map(d => d._delta_metadata.view);
const idx = [g.deltaIndexForView(g.round, "planning"), g.deltaIndexForView(g.round, "resource"), g.deltaIndexForView(g.round, "combat_shadow")];
let appends = g.takeLogAppends();
g.undo(); tap(() => g.setWillpower(3));
appends = appends.concat(g.takeLogAppends());
console.log(JSON.stringify({ views, idx,
  folded: foldLog(appends).map(e => e.text), live: g.log.map(e => e.text),
  ops: appends.filter(r => r.op === "lt").length }));
"""


def test_delta_metadata_and_log_truncation_match_the_twin():
    """A delta's _delta_metadata carries the view/round it landed on, and an
    edit after an undo truncates the log rows the discarded redo future
    produced, on both twins identically - deltaIndexForView, foldLog's "lt"
    tombstone, and the live g.log all agree."""
    import gamestate
    from gamestate import GameState, fold_log

    js = _js_facts(_METADATA_PROBE)

    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2); g.view = "resource"
    def tap(fn):
        s = g.begin_action(); fn(); return g.add_delta(s)
    tap(lambda: g.set_staging(1)); tap(lambda: g.advance_view()); tap(lambda: g.set_staging(2))
    assert js["views"] == [d["_delta_metadata"]["view"] for d in g.deltas]
    assert js["idx"] == [g.delta_index_for_view(g.round, v) for v in ("planning", "resource", "combat_shadow")]
    appends = list(g.take_log_appends()); g.undo(); tap(lambda: g.set_willpower(3))
    appends += g.take_log_appends()
    assert js["live"] == [e["text"] for e in g.log]
    assert js["folded"] == js["live"] == [e["text"] for e in fold_log(appends)]
    assert js["ops"] == 1


_ORPHAN_COALESCE_PROBE = """\
import { GameState, foldLog, setWindowPolicy, WINDOW_POLICY_BANDS } from "./gamestate.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2);
const tap = fn => { const s = g.beginAction(); fn(); return g.addDelta(s); };
let appends = [];
tap(() => g.setStaging(1));                  // delta 0, row A (key stg)
appends = appends.concat(g.takeLogAppends());
tap(() => g.setWillpower(5));                // delta 1, row B
appends = appends.concat(g.takeLogAppends());
tap(() => g.setStaging(2));                  // delta 2, row C (key stg)
appends = appends.concat(g.takeLogAppends());
const rowBSeq = g.log.find(e => e.text === "Players committed 5 willpower to the quest").seq;
const rowCSeq = g.log.find(e => e.text === "Staging area threat 2").seq;
g.undo(); g.undo();                          // replay_step -> 0
appends = appends.concat(g.takeLogAppends());
tap(() => g.setStaging(9));                  // fresh tally after undo
const newAppends = g.takeLogAppends();
appends = appends.concat(newAppends);
const newRow = newAppends.find(r => r.op !== "lt");
const tombstones = newAppends.filter(r => r.op === "lt");
console.log(JSON.stringify({
  live: g.log.map(e => e.text),
  folded: foldLog(appends).map(e => e.text),
  newRowDeltaI: newRow.delta_i,
  tombstoneCount: tombstones.length,
  tombstoneLo: tombstones.length ? tombstones[0].lo : null,
  tombstoneHi: tombstones.length ? tombstones[0].hi : null,
  rowBSeq, rowCSeq,
}));
"""


def test_a_fresh_tally_after_undo_never_coalesces_onto_an_orphaned_row_in_either_twin():
    """The same walk as test_a_fresh_tally_after_undo_never_coalesces_onto_an_
    orphaned_row in test_replay_metadata.py, run under node and under Python,
    asserting the two logs agree: a tally coalesced onto a row that an undo
    just orphaned used to vanish entirely when the redo future was truncated
    (logEvent/log_event rewrote the orphan in place, then _truncateLog/
    _truncate_log dropped it). Both twins now refuse to coalesce onto an
    orphaned row and start a fresh one instead."""
    import gamestate
    from gamestate import GameState, fold_log

    js = _js_facts(_ORPHAN_COALESCE_PROBE)

    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    def tap(fn):
        s = g.begin_action(); fn(); return g.add_delta(s)
    appends = []
    tap(lambda: g.set_staging(1))
    appends += g.take_log_appends()
    tap(lambda: g.set_willpower(5))
    appends += g.take_log_appends()
    tap(lambda: g.set_staging(2))
    appends += g.take_log_appends()
    row_b_seq = next(e["seq"] for e in g.log
                      if e["text"] == "Players committed 5 willpower to the quest")
    row_c_seq = next(e["seq"] for e in g.log if e["text"] == "Staging area threat 2")
    assert g.undo() and g.undo()
    appends += g.take_log_appends()
    tap(lambda: g.set_staging(9))
    new_appends = g.take_log_appends()
    appends += new_appends

    py_live = [e["text"] for e in g.log]
    py_folded = [e["text"] for e in fold_log(appends)]
    new_row = next(r for r in new_appends if r.get("op") != "lt")
    tombstones = [r for r in new_appends if r.get("op") == "lt"]

    assert js["rowBSeq"] == row_b_seq and js["rowCSeq"] == row_c_seq
    assert js["live"] == py_live == ["Staging area threat 1", "Staging area threat 9"]
    assert js["folded"] == py_folded == py_live
    assert js["newRowDeltaI"] == new_row["delta_i"] == 1
    assert js["tombstoneCount"] == len(tombstones) == 1
    assert js["tombstoneLo"] == tombstones[0]["lo"] == row_b_seq
    assert js["tombstoneHi"] == tombstones[0]["hi"] == row_c_seq


_TALLY_RESTAMP_PROBE = """\
import { GameState, foldLog, setWindowPolicy, WINDOW_POLICY_BANDS } from "./gamestate.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const tap = (g, fn) => { const s = g.beginAction(); fn(); return g.addDelta(s); };
// db.js serializes each record as it leaves takeLogAppends(); the live rows
// keep being edited afterwards, so freeze here the same way it does.
const drain = g => g.takeLogAppends().map(r => JSON.parse(JSON.stringify(r)));
function tallyGame(n) {
  const g = new GameState(2);
  let appends = [];
  for (let v = 1; v <= n; v++) { tap(g, () => g.setStaging(v)); appends = appends.concat(drain(g)); }
  return [g, appends];
}
const [g, _a] = tallyGame(5);
const row = g.log.find(e => e.key === "stg");
const rowDeltaI = row.delta_i;
g.undo(); g.undo(); g.undo();
const undone = row.delta_i > g.replay_step;
const stepAfterUndos = g.replay_step, stagingAfterUndos = g.staging;
g.stepThrough({ size: "index", index: row.delta_i });
const stagingAfterRewind = g.staging;

const folds = [];
{ const [h, ap0] = tallyGame(3); let ap = ap0;
  h.undo(); ap = ap.concat(drain(h));
  tap(h, () => h.setWillpower(3)); ap = ap.concat(drain(h));
  h.undo(); ap = ap.concat(drain(h));
  tap(h, () => h.setStaging(8)); ap = ap.concat(drain(h));
  folds.push([h.log.map(e => e.text), foldLog(ap).map(e => e.text)]); }
{ const [h, ap0] = tallyGame(3); let ap = ap0;
  h.undo(); h.undo(); ap = ap.concat(drain(h));
  tap(h, () => h.setStaging(9)); ap = ap.concat(drain(h));
  folds.push([h.log.map(e => e.text), foldLog(ap).map(e => e.text)]); }
{ const [h, ap0] = tallyGame(5); let ap = ap0;
  tap(h, () => h.setWillpower(2)); ap = ap.concat(drain(h));
  h.undo(); h.undo(); ap = ap.concat(drain(h));
  tap(h, () => h.setStaging(7)); ap = ap.concat(drain(h));
  folds.push([h.log.map(e => e.text), foldLog(ap).map(e => e.text)]); }
{ const [h, ap0] = tallyGame(3); let ap = ap0;
  while (h.undo()) {}
  ap = ap.concat(drain(h));
  tap(h, () => h.setStaging(6)); ap = ap.concat(drain(h));
  folds.push([h.replay_step, h.log.map(e => e.text), foldLog(ap).map(e => e.text)]); }

// The MAX_SAVED_DELTAS front trim, driven at full size: the constant is a
// `const` export, so there is nothing to lower from a probe - and 501 taps
// under node cost milliseconds.
const t = new GameState(2);
let tAppends = [];
for (let i = 0; i <= 500; i++) {
  tap(t, () => (i % 2 ? t.setStaging(i % 9 + 1) : t.setWillpower(i % 9 + 1)));
  tAppends = tAppends.concat(drain(t));
}
const trims = tAppends.filter(r => r.op === "lx");
const stamped = t.log.filter(e => "delta_i" in e).map(e => e.delta_i);
console.log(JSON.stringify({
  rowText: row.text, rowDeltaI, undone, stepAfterUndos, stagingAfterUndos,
  stagingAfterRewind, folds,
  trimCount: trims.length, trimN: trims.length ? trims[0].n : null,
  nDeltas: t.deltas.length, trimStep: t.replay_step,
  firstStamped: stamped[0], lastStamped: stamped[stamped.length - 1],
  trimFolded: JSON.stringify(foldLog(tAppends)) === JSON.stringify(t.log),
}));
"""


def test_a_coalesced_tally_row_is_restamped_and_the_trim_is_journalled_in_both_twins():
    """F1 + F3 of the milestone-4 fix wave, run under node and under Python.

    F1: a run of taps on one stepper is ONE log row, and that row belongs to
    the LAST tap - the coalesce path rewrites it in place, so it has to join
    _action_entries or add_delta's stamp loop leaves it carrying the first
    tap's delta index (greying under-fires; a rewind to the row lands on the
    wrong tap).

    F3: the MAX_SAVED_DELTAS front trim renumbers delta_i in RAM, and the log
    store hears about it as {"op":"lx","n":drop} - both folds apply it.
    """
    import json as _json
    import gamestate
    from gamestate import GameState, fold_log

    js = _js_facts(_TALLY_RESTAMP_PROBE)

    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)

    def tap(g, fn):
        s = g.begin_action(); fn(); return g.add_delta(s)

    def drain(g):
        return [_json.loads(_json.dumps(r)) for r in g.take_log_appends()]

    def tally_game(n):
        g = GameState(2)
        appends = []
        for v in range(1, n + 1):
            tap(g, lambda v=v: g.set_staging(v))
            appends += drain(g)
        return g, appends

    g, _ = tally_game(5)
    row = next(e for e in g.log if e.get("key") == "stg")
    assert js["rowText"] == row["text"] == "Staging area threat 5"
    assert js["rowDeltaI"] == row["delta_i"] == 4
    g.undo(); g.undo(); g.undo()
    assert js["undone"] is (row["delta_i"] > g.replay_step) is True
    assert js["stepAfterUndos"] == g.replay_step == 1
    assert js["stagingAfterUndos"] == g.staging == 2
    g.step_through({"size": "index", "index": row["delta_i"]})
    assert js["stagingAfterRewind"] == g.staging == 5

    folds = []
    h, ap = tally_game(3)
    h.undo(); ap += drain(h)
    tap(h, lambda: h.set_willpower(3)); ap += drain(h)
    h.undo(); ap += drain(h)
    tap(h, lambda: h.set_staging(8)); ap += drain(h)
    folds.append([[e["text"] for e in h.log], [e["text"] for e in fold_log(ap)]])
    assert fold_log(ap) == h.log

    h, ap = tally_game(3)
    h.undo(); h.undo(); ap += drain(h)
    tap(h, lambda: h.set_staging(9)); ap += drain(h)
    folds.append([[e["text"] for e in h.log], [e["text"] for e in fold_log(ap)]])
    assert fold_log(ap) == h.log

    h, ap = tally_game(5)
    tap(h, lambda: h.set_willpower(2)); ap += drain(h)
    h.undo(); h.undo(); ap += drain(h)
    tap(h, lambda: h.set_staging(7)); ap += drain(h)
    folds.append([[e["text"] for e in h.log], [e["text"] for e in fold_log(ap)]])
    assert fold_log(ap) == h.log

    h, ap = tally_game(3)
    while h.undo():
        pass
    ap += drain(h)
    tap(h, lambda: h.set_staging(6)); ap += drain(h)
    folds.append([h.replay_step, [e["text"] for e in h.log],
                  [e["text"] for e in fold_log(ap)]])
    assert fold_log(ap) == h.log

    assert js["folds"] == folds
    for f in folds[:3]:
        assert f[0] == f[1]

    t = GameState(2)
    t_appends = []
    for i in range(gamestate.MAX_SAVED_DELTAS + 1):
        tap(t, (lambda i=i: t.set_staging(i % 9 + 1)) if i % 2
               else (lambda i=i: t.set_willpower(i % 9 + 1)))
        t_appends += drain(t)
    trims = [r for r in t_appends if r.get("op") == "lx"]
    stamped = [e["delta_i"] for e in t.log if "delta_i" in e]
    assert js["trimCount"] == len(trims) == 1
    assert js["trimN"] == trims[0]["n"] == 1
    assert js["nDeltas"] == len(t.deltas) == gamestate.MAX_SAVED_DELTAS
    assert js["trimStep"] == t.replay_step == gamestate.MAX_SAVED_DELTAS - 1
    assert js["firstStamped"] == stamped[0] == -1
    assert js["lastStamped"] == stamped[-1] == gamestate.MAX_SAVED_DELTAS - 1
    assert js["trimFolded"] is True and fold_log(t_appends) == t.log


_FROZEN_ROW_PROBE = """\
import { GameState, foldLog, setWindowPolicy, WINDOW_POLICY_BANDS, MAX_SAVED_DELTAS } from "./gamestate.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const tap = (g, fn) => { const s = g.beginAction(); fn(); return g.addDelta(s); };

// (a) a row handed out by takeLogAppends() must not change when the live row
// is mutated afterwards - directly, or via a re-tally's coalesce.
const f = new GameState(2);
tap(f, () => f.setStaging(1));
const taken = f.takeLogAppends();
const takenTextBefore = taken[0].text;
f.log[f.log.length - 1].text = "changed";
const takenTextAfterDirectMutate = taken[0].text;
tap(f, () => f.setStaging(2));
f.takeLogAppends();
const takenTextAfterRetally = taken[0].text;

// (b) a row extracted every tap but never folded/consumed (a stand-in for
// db.js's Session._queue sitting undrained) must not be shifted twice when
// the MAX_SAVED_DELTAS front trim lands on a later tap.
const t = new GameState(2);
let queued = [];
for (let i = 0; i <= MAX_SAVED_DELTAS; i++) {
  tap(t, () => (i % 2 ? t.setStaging(i % 9 + 1) : t.setWillpower(i % 9 + 1)));
  queued = queued.concat(t.takeLogAppends());
}
const hasTrim = queued.some(r => r.op === "lx");
const liveFoldedMatch = JSON.stringify(foldLog(queued)) === JSON.stringify(t.log);

console.log(JSON.stringify({
  takenTextBefore, takenTextAfterDirectMutate, takenTextAfterRetally,
  hasTrim, liveFoldedMatch,
}));
"""


def test_take_log_appends_hands_out_frozen_rows_in_both_twins():
    """Node mirror of test_take_log_appends_hands_out_frozen_rows and
    test_front_trim_never_shifts_a_queued_row_twice in test_replay_metadata.py.

    takeLogAppends()/take_log_appends() must hand out copies, never the live
    row objects - db.js's/db.py's Session queues whatever they return and
    only serializes it later, in tick(). Two things mutate a row in place
    after it has already been handed out: a re-tally's coalesce (log_event/
    logEvent rewrites the same dict), and the MAX_SAVED_DELTAS front trim
    (decrements delta_i on every row still live). Either would leak into an
    already-queued record if takeLogAppends()/take_log_appends() returned a
    reference instead of a copy."""
    import gamestate
    from gamestate import GameState, fold_log

    js = _js_facts(_FROZEN_ROW_PROBE)

    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)

    def tap(g, fn):
        s = g.begin_action(); fn(); return g.add_delta(s)

    f = GameState(2)
    tap(f, lambda: f.set_staging(1))
    taken = f.take_log_appends()
    taken_text_before = taken[0]["text"]
    f.log[-1]["text"] = "changed"
    taken_text_after_direct_mutate = taken[0]["text"]
    tap(f, lambda: f.set_staging(2))
    f.take_log_appends()
    taken_text_after_retally = taken[0]["text"]

    assert js["takenTextBefore"] == taken_text_before == "Staging area threat 1"
    assert js["takenTextAfterDirectMutate"] == taken_text_after_direct_mutate == "Staging area threat 1"
    assert js["takenTextAfterRetally"] == taken_text_after_retally == "Staging area threat 1"

    t = GameState(2)
    queued = []
    for i in range(gamestate.MAX_SAVED_DELTAS + 1):
        tap(t, (lambda i=i: t.set_staging(i % 9 + 1)) if i % 2
               else (lambda i=i: t.set_willpower(i % 9 + 1)))
        queued += t.take_log_appends()

    assert js["hasTrim"] is True and any(r.get("op") == "lx" for r in queued)
    assert js["liveFoldedMatch"] is True and fold_log(queued) == t.log


_IMAGE_PREFIX_PROBE = """\
import { imagePrefix } from "./quest_catalog.js";
console.log(JSON.stringify({
  withPrefix: imagePrefix({imagePrefix: "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/"}),
  withoutPrefix: imagePrefix({generated: "2026-09-05", source: "fixture"}),
  emptyObject: imagePrefix({}),
}));
"""


def test_image_prefix_reads_the_same_pinned_key_in_both_twins():
    """quest_catalog.py's image_prefix() and quest_catalog.js's imagePrefix()
    are both trivial readers over index.json's `imagePrefix` (build_card_
    data.py Task 6/R5: the card-image URL prefix is pinned beside the card
    TSV and copied into the compiled index, top-level beside source/
    generated). Both must read the identical key and agree on the fallback
    for an index that predates the field."""
    import quest_catalog as qc

    js = _js_facts(_IMAGE_PREFIX_PROBE)

    prefix = "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/"
    assert js["withPrefix"] == qc.image_prefix({"imagePrefix": prefix}) == prefix
    assert js["withoutPrefix"] is None
    assert qc.image_prefix({"generated": "2026-09-05", "source": "fixture"}) is None
    assert js["emptyObject"] is None and qc.image_prefix({}) is None
