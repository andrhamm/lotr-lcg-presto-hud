"""The tablet client's pure modules, driven under node the way
test_twin_parity.py drives the model. Render functions return strings and
never touch `document`, which is what makes this possible."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _stage(tmp):
    """Copy docs/js and docs/tablet/js so ../../js imports resolve."""
    for sub in ("js", os.path.join("tablet", "js")):
        src = os.path.join(ROOT, "docs", sub)
        dst = os.path.join(tmp, sub)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if f.endswith(".js"):
                shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    with open(os.path.join(tmp, "package.json"), "w") as f:
        f.write('{"type":"module"}')


def node(probe):
    """Run `probe` (an ES module body) from tablet/js/ and return its JSON."""
    exe = shutil.which("node")
    if exe is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        _stage(tmp)
        path = os.path.join(tmp, "tablet", "js", "probe.mjs")
        with open(path, "w") as f:
            f.write(probe)
        r = subprocess.run([exe, path], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, "tablet module failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


def test_h_escapes_interpolations_but_not_raw():
    js = node("""
import { h, raw } from "./dom.js";
console.log(JSON.stringify({
  esc: h`<b>${"<i>&"}</b>`,
  raw: h`<b>${raw("<i>x</i>")}</b>`,
  list: h`<ul>${["a", raw("<li>b</li>")]}</ul>`,
}));
""")
    assert js["esc"] == "<b>&lt;i&gt;&amp;</b>"
    assert js["raw"] == "<b><i>x</i></b>"
    assert js["list"] == "<ul>a<li>b</li></ul>"


def test_primitives_are_buttons_with_actions():
    js = node("""
import { chip, cta, counter, band } from "./primitives.js";
console.log(JSON.stringify({
  chip: chip({ act: "open_log", label: "Open" }),
  cta: cta({ act: "advance", label: "Next: Travel" }),
  counter: counter({ label: "Staging area", icon: "", value: 4, act: "stg" }),
  band: band({ kind: "window", text: "Responses.", sub: "Last window." }),
}));
""")
    assert 'data-act="open_log"' in js["chip"] and js["chip"].startswith("<button")
    assert 'data-act="advance"' in js["cta"] and "Next: Travel" in js["cta"]
    assert 'data-act="stg-"' in js["counter"] and 'data-act="stg+"' in js["counter"]
    assert ">4<" in js["counter"]
    assert 'class="band band-window"' in js["band"] and "Last window." in js["band"]


def test_stat_icons_are_generated_from_the_masks():
    js = node("""
import { ICONS, icon } from "../../js/icons_svg.js";
console.log(JSON.stringify({ names: Object.keys(ICONS).sort().slice(0, 4),
  threat: icon("THREAT", 28, "#f7653e", "#070503") }));
""")
    assert "THREAT" in js["names"] or "ARCHERY" in js["names"]
    assert js["threat"].startswith("<svg") and 'viewBox="0 0 20 20"' in js["threat"]
    assert js["threat"].count("<path") == 2      # shadow first, then the fill


_WALK = """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, setBoardTracking } from "../../js/gamestate.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS); setBoardTracking(true);
const g = new GameState(4, 25);
g.advanceView();                       // setup -> round 1 (no catalog: a bare game)
[3, 4, 2, 2].forEach((c, i) => g.setCommit(i, c));
g.quest.points = 20;                   // room enough that the walk never clears the stage
const ui = newUi();
const taps = [];
const tap = (act, arg) => { taps.push(act); return dispatch(g, ui, act, arg ?? ""); };
tap("advance");                        // resource -> planning
tap("advance");                        // planning -> quest_commit
tap("wp-");                            // 11 -> 10, detached total
tap("advance");                        // -> quest_staging
tap("stg+"); tap("stg+"); tap("stg+");
tap("resolve");                        // -> quest_resolution, resolved
const budget = g.pending_budget;
tap("apply_alloc");
const placed = g.quest.progress;
tap("advance");                        // -> travel
tap("advance");                        // -> enc_optional
tap("advance");                        // -> enc_checks
tap("advance");                        // -> combat_shadow
tap("advance");                        // -> combat_enemy
tap("advance");                        // -> combat_player
tap("advance");                        // -> refresh
tap("advance");                        // -> round_end
"""
# _WALK prints nothing; each test appends the one console.log it wants.


def test_the_m2_walk_reaches_round_end_in_17_taps():
    """The HUD's tap-budget walk minus the shadow-effect threat edits (those
    need the players sheet, milestone 3). 31 taps on the HUD for the whole
    walk; 17 here for this part of it, and the count is the gate."""
    js = node(_WALK + """
console.log(JSON.stringify({ taps: taps.length, view: g.view, round: g.round,
  willpower: g.willpower, staging: g.staging, budget, placed,
  unknown: dispatch(g, ui, "nope", ""), first: g.first_player }));
""")
    assert js["view"] == "round_end"
    assert js["round"] == 1
    assert js["taps"] <= 17
    assert js["willpower"] == 10 and js["staging"] == 3
    assert js["budget"] == 7 and js["placed"] == 7
    assert js["first"] == 1              # the token passed on arrival at refresh
    assert js["unknown"] is False


def test_endround_starts_the_next_round():
    js = node(_WALK + """
const changed = dispatch(g, ui, "endround", "");
console.log(JSON.stringify({ changed, view: g.view, round: g.round }));
""")
    assert js == {"changed": True, "view": "resource", "round": 2}


def test_a_stepper_at_its_floor_reports_no_change():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
console.log(JSON.stringify({ stgFloor: dispatch(g, ui, "stg-", ""), stgUp: dispatch(g, ui, "stg+", ""),
  engFloor: dispatch(g, ui, "eng-", "1"), engUp: dispatch(g, ui, "eng+", "1"),
  wpFloor: dispatch(g, ui, "wp-", ""), wpUp: dispatch(g, ui, "wp+", ""),
  stgenFloor: dispatch(g, ui, "stgen-", ""), stgenUp: dispatch(g, ui, "stgen+", ""),
  stglocFloor: dispatch(g, ui, "stgloc-", ""), stglocUp: dispatch(g, ui, "stgloc+", "") }));
""")
    assert js == {"stgFloor": False, "stgUp": True, "engFloor": False, "engUp": True,
                  "wpFloor": False, "wpUp": True, "stgenFloor": False, "stgenUp": True,
                  "stglocFloor": False, "stglocUp": True}


def test_strip_has_a_segment_per_phase_and_a_playhead_on_the_current_view():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
const html = renderStrip(g, newUi());
console.log(JSON.stringify({ segs: (html.match(/class="seg/g) || []).length,
  current: (html.match(/is-current/g) || []).length,
  currentView: /data-view="quest_staging"[^>]*is-current|is-current[^>]*data-view="quest_staging"/.test(html),
  windows: (html.match(/tick-window/g) || []).length, aw: html.includes("aw_"),
  planningWindow: /data-view="planning"[^>]*tick-window|tick-window[^>]*data-view="planning"/.test(html),
  round: html.includes(">1<") }));
""")
    assert js["segs"] == 8
    assert js["current"] == 1 and js["currentView"]
    assert js["windows"] == 11         # 8 aw_ windows + planning + the two combat windows
    assert js["aw"] is False           # window views are ticks, never named
    assert js["planningWindow"]        # Planning's own tick IS the round's window tick
    assert js["round"]


def test_strip_marks_the_combat_segment_skippable_when_the_offer_is_promoted():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("enc_checks");
const a = renderStrip(g, newUi());
g.setEngaged(0, 1);
const b = renderStrip(g, newUi());
console.log(JSON.stringify({ promoted: /data-phase="Combat"[^>]*is-skippable/.test(a),
  demoted: /data-phase="Combat"[^>]*is-skippable/.test(b), landing: a.includes("6.P") }));
""")
    assert js["promoted"] and js["landing"]
    assert js["demoted"] is False


def test_strip_skip_landing_off_flow_still_finds_its_segment():
    """lastWindowBefore walks the raw VIEW_ORDER, so under "bands" it can
    return an aw_ view flowViews() has filtered out - not reachable via the
    one shipped skip (its landing is combat_player, on-flow), so this pushes
    a second skip onto SKIPS (an exported mutable array; this probe runs in
    its own node process, so nothing leaks) whose landing lands off-flow, on
    aw_enc_checks -> phase view enc_checks, step 5.3 - the last view of the
    Encounter segment, so the fix (mapping through phaseViewOf instead of
    indexOf'ing the raw aw_ id) is what lets that whole segment - not just
    the landing tick - light up is-skippable. Before the fix, indexOf(-1)
    on the un-mapped aw_ id sinks the range check and NOTHING lights up."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, SKIPS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
SKIPS.push({ id: "t", from: ["travel"], to: "combat_shadow", label: "x", claim: "y" });
const g = new GameState(2, 25); g.advanceView(); g.enterView("travel");
const html = renderStrip(g, newUi());
console.log(JSON.stringify({
  encounterSkippable: /data-phase="Encounter"[^>]*is-skippable/.test(html),
  combatSkippable: /data-phase="Combat"[^>]*is-skippable/.test(html),
  landing53: html.includes(">5.3<"),
}));
""")
    assert js["encounterSkippable"]
    assert js["landing53"]
    assert js["combatSkippable"] is False


def test_rail_shows_every_player_and_the_three_zones():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderRail } from "./rail.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(3, 25); g.advanceView();
g.adjustThreat(2, 16); g.setEngaged(2, 1); g.setStagingEnemies(2); g.setStaging(5);
g.logEvent("P1 threat 25 -> 26");
const html = renderRail(g, newUi());
console.log(JSON.stringify({ zones: (html.match(/class="zone /g) || []).length,
  cells: (html.match(/player-cell/g) || []).length, danger: html.includes("bar-danger"),
  buttons: html.includes("<button"), log: html.includes("P1 threat 25 -&gt; 26"),
  prompt: html.includes("Resource"), staging: />5</.test(html) && />2</.test(html),
  captions: html.includes("Enemies") && html.includes("Locations") }));
""")
    assert js["zones"] == 3 and js["cells"] == 3
    assert js["danger"]                # P3 at 41 is within 10 of elimination
    assert js["buttons"] is False      # status, not controls, in this milestone
    assert js["log"] and js["prompt"] and js["staging"]
    assert js["captions"]


_ALL_VIEWS = """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, flowViews } from "../../js/gamestate.js";
import { layout } from "./layout.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const out = {};
for (const v of flowViews()) {
  const g = new GameState(4, 25); g.advanceView(); g.enterView(v);
  if (v === "quest_resolution") { g.setWillpower(9); g.setStaging(2); g.resolveQuest(9, 2); g.pending_budget = 7; }
  const html = layout(g, newUi());
  out[v] = { len: html.length, next: html.includes('data-act="advance"') || html.includes('data-act="endround"'),
             bad: /undefined|NaN|\\[object Object\\]/.test(html), title: html.includes('class="display"') };
}
console.log(JSON.stringify(out));
"""


def test_every_flow_view_renders_a_pane_with_a_way_forward():
    js = node(_ALL_VIEWS)
    for v, r in js.items():
        assert r["len"] > 2000, v
        assert r["title"], v
        assert not r["bad"], v
        assert r["next"] or v == "quest_resolution", v


def test_resolution_pane_offers_the_allocator_then_the_window():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
g.setWillpower(9); g.setStaging(2); g.quest.points = 20;
const ui = newUi();
dispatch(g, ui, "resolve", "");
const before = renderPane(g, ui);
dispatch(g, ui, "apply_alloc", "");
const after = renderPane(g, ui);
console.log(JSON.stringify({ allocator: before.includes('data-act="apply_alloc"'),
  placed: after.includes('data-act="advance"') && !after.includes('data-act="apply_alloc"'),
  progress: g.quest.progress }));
""")
    assert js["allocator"] and js["placed"] and js["progress"] == 7


def test_enc_checks_pane_carries_the_skip_cta_promoted_or_demoted():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("enc_checks");
const a = renderPane(g, newUi()); g.setEngaged(1, 2); const b = renderPane(g, newUi());
console.log(JSON.stringify({ a: /data-act="skip"[^>]*/.exec(a)?.[0] ?? "", b: /class="cta cta-(\\w+)[^>]*data-act="skip"/.exec(b)?.[1] ?? "",
  aTone: /class="cta cta-(\\w+)[^>]*data-act="skip"/.exec(a)?.[1] ?? "", counts: b.includes("2 engaged") }));
""")
    assert 'data-arg="combat_empty"' in js["a"]
    assert js["aTone"] == "skip" and js["b"] == "plain" and js["counts"]


def test_new_game_screen_lists_scenarios_and_players():
    """renderNewGame(ui) is a pure string builder (Task 6): player-count
    chips, a starting-threat counter per player, and the official quest
    catalog (kind=="quest" only - "n" here is kind "nightmare" and must not
    surface), plus a resume chip whenever the caller says there is a save."""
    js = node("""
import { renderNewGame } from "./newgame.js";
const html = renderNewGame({ picker: { index: { scenarios: [
  { slug: "a", name: "A", pack: "P", cycle: "C", kind: "quest", order: 1, source: "official" },
  { slug: "n", name: "N", pack: "P", cycle: "C", kind: "nightmare", order: 2, source: "official" },
] }, players: 3, threats: [25, 25, 30], hasSave: true } });
console.log(JSON.stringify({
  counters: (html.match(/class="counter"/g) || []).length,
  hasA: html.includes(">A<"),
  hasN: html.includes(">N<"),
  resume: html.includes('data-act="resume"'),
}));
""")
    assert js["counters"] == 3
    assert js["hasA"] and not js["hasN"]
    assert js["resume"]
