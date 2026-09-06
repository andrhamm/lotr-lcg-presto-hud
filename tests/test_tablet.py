"""The tablet client's pure modules, driven under node the way
test_twin_parity.py drives the model. Render functions return strings and
never touch `document`, which is what makes this possible."""
import json
import os
import re
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


# A nested h`` call interpolated into an outer h`` template returns an
# already-escaped plain string - dom.js's one() only trusts a Raw instance
# (raw()'s wrapper), so the outer template escapes that string a second time
# and the fragment renders as literal markup text instead of markup. This
# regex is a conservative static scan for the shape, not a parser: it flags
# any `${...h`` interpolation that doesn't also contain `raw(` before the
# nested call. It caught sheet_locpick.js's set-group header
# (39f0cb2, `${set ? h\`<div class="label">${set}</div>\` : ""}`) - see
# test_location_picker_travel_then_manual_entry_appends_a_second_seat's own
# regression assertion on the rendered HTML for the runtime side of the fix.
NESTED_H_WITHOUT_RAW_RE = re.compile(r"\$\{([^}]*?)h`")


def test_no_nested_h_without_raw():
    tablet_js_dir = os.path.join(ROOT, "docs", "tablet", "js")
    violations = []
    for name in sorted(os.listdir(tablet_js_dir)):
        if not name.endswith(".js"):
            continue
        with open(os.path.join(tablet_js_dir, name)) as f:
            for lineno, line in enumerate(f, 1):
                for m in NESTED_H_WITHOUT_RAW_RE.finditer(line):
                    if "raw(" not in m.group(1):
                        violations.append("%s:%d: %s" % (name, lineno, line.strip()))
    assert not violations, (
        "nested h`` inside an interpolation must be wrapped in raw(...), "
        "or the outer template double-escapes it:\n" + "\n".join(violations)
    )


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
const threatsBefore = g.players.map(p => p.threat);
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
tap("open_players");
tap("all_thr", "1");
tap("sheet_close");
tap("advance");                        // -> combat_enemy
tap("advance");                        // -> combat_player
tap("advance");                        // -> refresh
tap("advance");                        // -> round_end
const threatsAfter = g.players.map(p => p.threat);
"""
# _WALK prints nothing; each test appends the one console.log it wants.


def test_the_common_round_costs_at_most_20_taps():
    """The spec's full common round walk: includes the players sheet threat
    edits after combat_shadow. 20 taps total. Threat must rise by EXACTLY 2
    per player over the walk: the walk's own "all_thr 1" tap (players sheet)
    plus applyRefresh()'s own +1 (7.3, threat_per_round defaults to 1) - not
    merely "at least one", which would still pass if either bump silently
    dropped or one ran twice."""
    js = node(_WALK + """
const unknown = dispatch(g, ui, "nope", "");
console.log(JSON.stringify({ taps: taps.length, view: g.view, round: g.round,
  willpower: g.willpower, staging: g.staging, budget, placed,
  unknown, first: g.first_player, threatsBefore, threatsAfter }));
""")
    assert js["view"] == "round_end"
    assert js["round"] == 1
    assert js["taps"] <= 20
    assert js["willpower"] == 10 and js["staging"] == 3
    assert js["budget"] == 7 and js["placed"] == 7
    assert js["first"] == 1              # the token passed on arrival at refresh
    assert js["unknown"] is False
    before, after = js["threatsBefore"], js["threatsAfter"]
    assert len(before) == len(after) == 4
    # all_thr 1 + the refresh phase's own +1, exactly, for every player.
    assert all(after[i] - before[i] == 2 for i in range(len(before))), (before, after)


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


def test_alloc_steppers_report_whether_they_changed_anything():
    """alloc+/alloc-/alloc_reset used to return true unconditionally (every
    branch either mutated ui.alloc or fell through to a bare `return true`),
    so a budget-spent "+" or a zeroed "-"/"reset" recorded a no-op delta and
    still re-rendered. budget=2, quest room=20, no active locations - resolve
    seeds ui.alloc via autoSplit, which (being the only sink) immediately
    places the whole budget on the quest, so alloc_reset's own change-
    reporting is exercised first to get back to a clean zero: two "+" taps
    then refill it, a third has nowhere to go (budget spent), and a second
    reset/a "-" at zero both report no change."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
g.setWillpower(2); g.setStaging(0); g.quest.points = 20;
const ui = newUi();
dispatch(g, ui, "resolve", "");                           // autoSplit: quest = 2 already
const resetChanged1 = dispatch(g, ui, "alloc_reset", "");  // 2 -> 0
const plus1 = dispatch(g, ui, "alloc+", "quest");          // 0 -> 1
const plus2 = dispatch(g, ui, "alloc+", "quest");          // 1 -> 2
const plus3 = dispatch(g, ui, "alloc+", "quest");          // budget spent
const resetChanged2 = dispatch(g, ui, "alloc_reset", "");  // 2 -> 0
const resetNoop = dispatch(g, ui, "alloc_reset", "");      // already 0
const minusAtZero = dispatch(g, ui, "alloc-", "quest");    // already 0
console.log(JSON.stringify({ budget: g.pending_budget, resetChanged1, plus1, plus2, plus3,
  resetChanged2, resetNoop, minusAtZero }));
""")
    assert js["budget"] == 2
    assert js["resetChanged1"]
    assert js["plus1"] and js["plus2"]
    assert js["plus3"] is False           # budget spent
    assert js["resetChanged2"]            # 2 -> 0
    assert js["resetNoop"] is False       # already 0
    assert js["minusAtZero"] is False


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


def test_strip_marks_the_current_phase_when_the_view_is_off_flow():
    """quest_sailing and quest_setup sit off VIEW_ORDER entirely (they are
    bands, not flow views, under WINDOW_POLICY_BANDS), so
    flowViews().indexOf(game.view) is always -1 for them and every tick used
    to render is-future - no playhead anywhere. renderStrip now resolves the
    view's PHASE (step(VIEW_STEP[game.view]).phase) and marks THAT segment
    current instead: quest_sailing is step 3.1, phase Quest, so the Quest
    segment's first tick (quest_commit) should carry the sole is-current and
    its playhead. quest_setup is phase Beginning, which has no segment at
    all (round 1 hasn't started) - nothing should light up there."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView();
g.sailing = true;
g.enterView("quest_sailing");
const html = renderStrip(g, newUi());
const start = html.indexOf('data-phase="Quest"');
const next = html.indexOf('data-phase="', start + 1);
const questSeg = next === -1 ? html.slice(start) : html.slice(start, next);
const setupHtml = renderStrip(new GameState(2, 25), newUi());   // fresh: view is quest_setup
console.log(JSON.stringify({
  totalCurrent: (html.match(/is-current/g) || []).length,
  questCurrent: (questSeg.match(/is-current/g) || []).length,
  questPlayhead: questSeg.includes('class="playhead"'),
  setupCurrent: (setupHtml.match(/is-current/g) || []).length,
}));
""")
    assert js["totalCurrent"] == 1
    assert js["questCurrent"] == 1
    assert js["questPlayhead"]
    assert js["setupCurrent"] == 0


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
  buttons: (html.match(/<button/g) || []).length, log: html.includes("P1 threat 25 -&gt; 26"),
  openLog: html.slice(html.indexOf("log-head-row")),
  prompt: html.includes("Resource"), staging: />5</.test(html) && />2</.test(html),
  captions: html.includes("Enemies") && html.includes("Locations"),
  grid: html.includes("staging-grid") }));
""")
    assert js["zones"] == 3 and js["cells"] == 3
    assert js["danger"]                # P3 at 41 is within 10 of elimination
    # The rail's only controls are the three zones' own "Edit ›" chips
    # (milestone 3) plus the log block's "Open ›" (milestone 4, Task 3) - the
    # player cells/pills underneath stay pure status.
    assert js["buttons"] == 4
    assert 'data-act="open_log"' in js["openLog"]
    assert js["log"] and js["prompt"] and js["staging"]
    assert js["captions"]
    assert js["grid"]                  # the three staging pills are a grid, not a row


def test_quest_setup_reads_the_a_face_of_a_catalog_card():
    """The compiled catalog's stage cards are `{ faces: [...] }`, not
    `{ name, text }` at the top level - pane.js's quest_setup branch and
    rail.js's stage pill both used to read the top-level fields directly and
    so always fell to the "no card"/nameless branch, even for a card (like
    Passage Through Mirkwood's 1A) that prints real Setup text. cards.js's
    frontFace()/faceOf() fix that; this drives both renderPane (before the
    flip, side A) and renderRail (after it, side B) off one preloaded card."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { renderRail } from "./rail.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25);
g.preloadScenario({ slug: "x", name: "X" }, [{ stage: 1, cards: [{
  faces: [
    { name: "Flies and Spiders", side: "A", text: "Setup: search the encounter deck." },
    { name: "Flies and Spiders", side: "B", text: "" },
  ],
  questPoints: 8,
}] }]);
g.view = "quest_setup";
const ui = newUi();
const before = renderPane(g, ui);
const changed = dispatch(g, ui, "flip_to_b", "");
const after = renderRail(g, ui);
console.log(JSON.stringify({
  beforeName: before.includes("Flies and Spiders"),
  beforeText: before.includes("Setup: search the encounter deck."),
  beforeCta: before.includes('data-act="flip_to_b"'),
  changed,
  afterName: after.includes("Flies and Spiders"),
  afterProgress: />0<[/]span><span class="pill-sep">[/]<[/]span><span class="num num-26">8</.test(after),
}));
""")
    assert js["beforeName"]
    assert js["beforeText"]
    assert js["beforeCta"]
    assert js["changed"]
    assert js["afterName"]
    assert js["afterProgress"]         # 0 / 8, the stage pill's progress-over-points


_ALL_VIEWS = """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, flowViews } from "../../js/gamestate.js";
import { layout } from "./layout.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const out = {};
// quest_sailing is off flowViews() entirely (a band, not a flow view - see
// strip.js's off-flow handling), so it is appended by hand alongside the
// gate that reaches it (g.sailing = true) rather than turning up on its own.
for (const v of [...flowViews(), "quest_sailing"]) {
  const g = new GameState(4, 25); g.advanceView();
  if (v === "quest_sailing") g.sailing = true;
  g.enterView(v);
  if (v === "quest_resolution") { g.setWillpower(9); g.setStaging(2); g.resolveQuest(9, 2); g.pending_budget = 7; }
  const html = layout(g, newUi());
  out[v] = { len: html.length, next: html.includes('data-act="advance"') || html.includes('data-act="endround"')
               || html.includes('data-act="resolve"'),
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


def test_gameover_layout_shows_the_result_round_and_new_game_cta():
    """layout()'s gameover branch (layout.js's renderGameOver): victory
    shows the frozen duration setGameOver() captured, a defeat with no clock
    wired up (duration: null, and gameDuration() also returns null with no
    log/clock) falls back to just the round - either way the title, the
    round and the new_game CTA must be there."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { layout } from "./layout.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const gv = new GameState(2, 25);
gv.game_over = { result: "victory", round: 3, duration: "12m34s" };
const ui1 = newUi(); ui1.screen = "gameover";
const victoryHtml = layout(gv, ui1);
const gd = new GameState(2, 25);
gd.game_over = { result: "defeat", round: 5, duration: null };
const ui2 = newUi(); ui2.screen = "gameover";
const defeatHtml = layout(gd, ui2);
console.log(JSON.stringify({
  victoryTitle: victoryHtml.includes(">Victory!<"),
  victoryRound: victoryHtml.includes("Round 3"),
  victoryDuration: victoryHtml.includes("12m34s"),
  victoryCta: victoryHtml.includes('data-act="new_game"'),
  defeatTitle: defeatHtml.includes(">Defeat<"),
  defeatRound: defeatHtml.includes("Round 5"),
  defeatCta: defeatHtml.includes('data-act="new_game"'),
}));
""")
    assert js["victoryTitle"] and js["victoryRound"] and js["victoryDuration"] and js["victoryCta"]
    assert js["defeatTitle"] and js["defeatRound"] and js["defeatCta"]


def test_resolution_pane_offers_the_allocator_then_the_window():
    """Also the allocator minus stepper's own regression (review finding 7):
    allocStep interpolated "&minus;" through h``, which escapes the "&" a
    second time into literal "&amp;minus;" text on screen instead of the
    glyph. resolve seeds the whole budget onto the quest row via autoSplit,
    so its minus button is live (used > 0) in `before`."""
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
  progress: g.quest.progress,
  noEscapedMinus: before.includes("&amp;minus;"),
  minusGlyph: before.includes("−"),
}));
""")
    assert js["allocator"] and js["placed"] and js["progress"] == 7
    assert not js["noEscapedMinus"], "the minus stepper must never render as literal &amp;minus; text"
    assert js["minusGlyph"], "the minus stepper renders the U+2212 character"


def test_resolution_pane_reports_how_much_threat_rose_on_a_fail():
    """A failed resolve never places progress (no allocator), and the
    outcome line must say how much threat rose - not just that the quest
    failed. setWillpower(2)/setStaging(5) -> resolveQuest's shortfall is 3,
    so "rose by 3." (OUTCOME.fail_line2_pre + the icon + fail_line2_post)
    must be in the pane."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
g.setWillpower(2); g.setStaging(5);
const ui = newUi();
dispatch(g, ui, "resolve", "");
const html = renderPane(g, ui);
console.log(JSON.stringify({
  roseByThree: html.includes("rose by 3."),
  noAlloc: !html.includes('data-act="apply_alloc"'),
}));
""")
    assert js["roseByThree"]
    assert js["noAlloc"]


def test_resolution_pane_names_a_tie_by_its_own_copy():
    """A 4-4 tie must show OUTCOME.tie_line2's own text (not just
    OUTCOME.card_tie), the same two-part composition the twin uses."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { dispatch, newUi } from "./actions.js";
import { OUTCOME } from "../../js/viewcopy.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
g.setWillpower(4); g.setStaging(4);
const ui = newUi();
dispatch(g, ui, "resolve", "");
const html = renderPane(g, ui);
console.log(JSON.stringify({ tieLine: html.includes(OUTCOME.tie_line2) }));
""")
    assert js["tieLine"]


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
    surface, and a "quest"-kind row named "<Scenario> - Nightmare" - a
    Nightmare deck's replacement quest card - must not surface either).
    No resume chip: review finding M11 deleted it (no handler ever answered
    its tap, and app.js never actually set the hasSave flag it read)."""
    js = node("""
import { renderNewGame } from "./newgame.js";
const html = renderNewGame({ picker: { index: { scenarios: [
  { slug: "a", name: "A", pack: "P", cycle: "C", kind: "quest", order: 1, source: "official" },
  { slug: "n", name: "N", pack: "P", cycle: "C", kind: "nightmare", order: 2, source: "official" },
  { slug: "a-nm", name: "A - Nightmare", pack: "P", cycle: "C", kind: "quest", order: 3, source: "official" },
] }, players: 3, threats: [25, 25, 30] } });
console.log(JSON.stringify({
  counters: (html.match(/class="counter"/g) || []).length,
  hasA: html.includes(">A<"),
  hasN: html.includes(">N<"),
  hasANightmare: html.includes('data-arg="a-nm"'),
  noResume: !html.includes('data-act="resume"'),
}));
""")
    assert js["counters"] == 3
    assert js["hasA"] and not js["hasN"]
    assert not js["hasANightmare"]
    assert js["noResume"]


def test_catalog_paths_resolve_beside_the_module_not_the_page():
    js = node("""
import { dataUrl } from "../../js/quest_catalog.js";
console.log(JSON.stringify({ u: dataUrl("index.json"), s: dataUrl("scenarios/x.json") }));
""")
    assert js["u"].endswith("/js/../data/index.json") or js["u"].endswith("/data/index.json")
    assert "/tablet/" not in js["u"] and "/js/data/" not in js["u"]
    assert js["s"].endswith("/data/scenarios/x.json")


def test_perform_records_a_delta_per_changing_tap_so_undo_works():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
const before = g.deltas.length;
const a = perform(g, ui, "stg+", "");
const b = perform(g, ui, "stg-", "");
const c = perform(g, ui, "stg-", "");          // at the floor: no change, no delta
const n = g.deltas.length - before;
const canUndo = g.canUndo();
g.undo();
console.log(JSON.stringify({ a, b, c, n, canUndo, stagingAfterUndo: g.staging, replay: g.takeReplayAppends().length > 0 }));
""")
    assert js["a"] and js["b"] and js["c"] is False
    assert js["n"] == 2 and js["canUndo"]
    assert js["stagingAfterUndo"] == 1
    assert js["replay"]


def test_a_rewind_survives_the_journal_round_trip():
    """A cursor move via rw_undo writes a position op to the journal without
    recording a delta. Folding the journal ops via foldReplay should
    reconstruct [deltas, replay_step] matching the live game state."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, foldReplay } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
perform(g, ui, "stg+", "");
perform(g, ui, "advance", "");
perform(g, ui, "stg+", "");
perform(g, ui, "rw_undo", "");
const journal = g.takeReplayAppends();
const folded = foldReplay(journal);
const dict = g.replayToDict();
console.log(JSON.stringify({
  deltasLength: folded[0].length,
  foldedStep: folded[1],
  gameDeltas: g.deltas.length,
  gameStep: g.replay_step,
  dictStep: dict.replay_step,
  folded: [folded[0].length, folded[1]],
  game: [g.deltas.length, g.replay_step]
}));
""")
    assert js["deltasLength"] == 3
    assert js["foldedStep"] == 1
    assert js["gameDeltas"] == 3
    assert js["gameStep"] == 1
    assert js["dictStep"] == 1
    assert js["folded"] == js["game"]


def test_defeat_lands_inside_the_same_delta_so_undo_reverts_it():
    """app.js used to check allEliminated()/setGameOver() AFTER perform()
    had already closed its delta window (dispatch, then addDelta), so the
    game_over transition rode along on no delta at all and undo could never
    touch it - a rewound tap left the board un-eliminated but the screen
    still on gameover. perform() now runs the defeat check BETWEEN dispatch
    and addDelta, so it is part of the same snapshot diff as the tap that
    caused it."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
g.players.forEach(p => { p.elimination = 1; });
g.adjustThreat(0, 5); g.adjustThreat(1, 5);   // both at threat 5 >= elimination 1
const changed = perform(g, ui, "stg+", "");
const result = g.game_over?.result;
const deltaHasGameOver = "game_over" in g.deltas.at(-1);
g.undo();
console.log(JSON.stringify({ changed, result, deltaHasGameOver, gameOverAfterUndo: g.game_over }));
""")
    assert js["changed"]
    assert js["result"] == "defeat"
    assert js["deltaHasGameOver"]
    assert js["gameOverAfterUndo"] is None


def test_players_sheet_edits_every_player_and_logs_like_the_twin():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(3, 25); g.advanceView(); const ui = newUi();
perform(g, ui, "open_players", "");
const html = layout(g, ui);
perform(g, ui, "thr", "2:5"); perform(g, ui, "thr", "2:-1");
perform(g, ui, "commit", "0:1"); perform(g, ui, "commit", "0:1");
perform(g, ui, "eng+", "1");
perform(g, ui, "all_thr", "1");
const texts = g.log.slice(-6).map(e => e.text);
perform(g, ui, "sheet_close", "");
console.log(JSON.stringify({ sheet: html.includes('class="sheet sheet-players"'), rows: (html.match(/class="psheet-row/g) || []).length,
  threats: g.players.map(p => p.threat), commits: g.players.map(p => p.commit), eng: g.players[1].engaged,
  texts, closed: ui.sheet === null, deltas: g.deltas.length }));
""")
    assert js["sheet"] and js["rows"] == 3
    assert js["threats"] == [26, 26, 30]
    assert js["commits"] == [2, 0, 0] and js["eng"] == 1
    assert js["texts"][0] == "P3 threat 25 -> 30"
    assert js["texts"][1] == "P3 threat 30 -> 29"
    assert "P1 committed 2 willpower" in js["texts"]
    assert js["texts"][-1].startswith("All players threat +1 (P1 26, P2 26, P3 30)")
    assert js["closed"] and js["deltas"] == 6   # sheet open/close change ui only: no delta


def test_scrim_closes_and_the_sheet_body_does_not():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
perform(g, ui, "open_staging", "");
const html = layout(g, ui);
console.log(JSON.stringify({ scrim: /class="scrim"[^>]*data-act="sheet_close"/.test(html), stop: html.includes("data-stop"),
  rows: html.includes('data-act="stg5"') && html.includes('data-act="stgen+"') && html.includes('data-act="stgloc+"') }));
""")
    assert js["scrim"] and js["stop"] and js["rows"]


def test_elim_sheet_opens_on_threat_crossing_and_avert_reverts_it():
    """afterTap() is the auto-open app.js also calls after every perform() -
    this replicates that per-tap loop under node so the sheet's own opening
    is testable without a DOM. avertElimination()'s log line is the model's
    own (gamestate.js), asserted here byte-identical - see EliminationModal's
    "avert" case (docs/js/screens.js) for the twin's matching act."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
let opened = null;
for (let n = 0; n < 5; n++) {
  perform(g, ui, "thr", "1:5");
  afterTap(g, ui);
  if (ui.sheet && opened === null) opened = { kind: ui.sheet.kind, i: ui.sheet.i, level: ui.sheet.level, tapsSoFar: n + 1 };
}
perform(g, ui, "elim_avert", "");
console.log(JSON.stringify({ opened, threat: g.players[1].threat, pendingElim: g.pending_elim,
  sheet: ui.sheet, log: g.log.at(-1).text }));
""")
    assert js["opened"] == {"kind": "elim", "i": 1, "level": 50, "tapsSoFar": 5}
    assert js["threat"] == 45
    assert js["pendingElim"] is None
    assert js["sheet"] is None
    assert js["log"] == "P2 avoided elimination (card effect) - threat set to 45"


def test_elim_sheet_renders_and_confirm_lvl_setlvl_match_the_twin():
    """Covers the three acts test_elim_sheet_opens_... doesn't: elim_confirm
    (log line + pending_elim clear, player already eliminated so eliminated
    stays true), elim_lvl's clamp at both ends (20..99, per
    EliminationModal.onButton), and elim_setlvl's two branches - still
    eliminated at the recalibrated level (both log lines, matching the
    twin's "if (p.eliminated) {...}" branch) vs. no longer eliminated (one
    log line, matching its "else" branch)."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(3, 45); g.advanceView(); const ui = newUi();

perform(g, ui, "thr", "0:5"); afterTap(g, ui);            // P1: 45 -> 50, crosses
const opened = { kind: ui.sheet.kind, i: ui.sheet.i, level: ui.sheet.level };
const html = layout(g, ui);
perform(g, ui, "elim_confirm", "");
const confirmed = { pendingElim: g.pending_elim, sheet: ui.sheet, eliminated: g.players[0].eliminated,
  log: g.log.at(-1).text };

perform(g, ui, "thr", "1:5"); afterTap(g, ui);            // P2: 45 -> 50, crosses
perform(g, ui, "elim_lvl", "5");                          // 50 -> 55
perform(g, ui, "elim_lvl", "-100");                       // clamps down to 20
const clampedLow = ui.sheet.level;
perform(g, ui, "elim_lvl", "500");                        // clamps up to 99
const clampedHigh = ui.sheet.level;
const noopAtCeiling = perform(g, ui, "elim_lvl", "500");  // already 99: clamp is a no-op
perform(g, ui, "elim_lvl", "-49");                        // 99 -> 50, back where it crossed
perform(g, ui, "elim_setlvl", "");                        // still >= 50: stays eliminated
const stillElim = { level: g.players[1].elimination, eliminated: g.players[1].eliminated,
  pendingElim: g.pending_elim, sheet: ui.sheet, log: g.log.slice(-2).map(e => e.text) };

perform(g, ui, "thr", "2:5"); afterTap(g, ui);            // P3: 45 -> 50, crosses
perform(g, ui, "elim_lvl", "5"); perform(g, ui, "elim_lvl", "5");   // 50 -> 60, above the threat
perform(g, ui, "elim_setlvl", "");                        // no longer eliminated
const revived = { level: g.players[2].elimination, eliminated: g.players[2].eliminated,
  pendingElim: g.pending_elim, sheet: ui.sheet, log: g.log.at(-1).text };

console.log(JSON.stringify({ opened, sheet: html.includes('class="sheet sheet-elim"'),
  buttons: ["elim_confirm", "elim_avert", "elim_lvl", "elim_setlvl"].every(a => html.includes(`data-act="${a}"`)),
  title: html.includes("P1") && html.includes("50"),
  confirmed, clampedLow, clampedHigh, noopAtCeiling, stillElim, revived }));
""")
    assert js["opened"] == {"kind": "elim", "i": 0, "level": 50}
    assert js["sheet"] and js["buttons"] and js["title"]
    assert js["confirmed"] == {
        "pendingElim": None, "sheet": None, "eliminated": True,
        "log": "P1 eliminated (threat 50 >= level 50)",
    }
    assert js["clampedLow"] == 20
    assert js["clampedHigh"] == 99
    assert js["noopAtCeiling"] is False, "already at the 99 ceiling: elim_lvl must report no change"
    assert js["stillElim"] == {
        "level": 50, "eliminated": True, "pendingElim": None, "sheet": None,
        "log": ["P2 elimination level set to 50", "P2 eliminated (threat 50 >= level 50)"],
    }
    assert js["revived"] == {
        "level": 60, "eliminated": False, "pendingElim": None, "sheet": None,
        "log": "P3 elimination level set to 60",
    }


def test_elim_sheet_avert_preview_tracks_the_committed_level_not_the_draft():
    """Nudging the +/- stepper only edits ui.sheet.level (a draft, per
    elim_lvl above) - it does not touch p.elimination until elim_setlvl
    commits it. The title and the avert-button's preview text must read
    p.elimination throughout, exactly like EliminationModal.draw() reads it
    (docs/js/screens.js) for its own equivalent line, never the stepper's own
    draft number - otherwise nudging the stepper without tapping Set would
    make the preview lie about what tapping elim_avert is about to do."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 45); g.advanceView(); const ui = newUi();
perform(g, ui, "thr", "0:5"); afterTap(g, ui);   // P1: 45 -> 50, crosses (elimination 50)
perform(g, ui, "elim_lvl", "5");                 // draft only: ui.sheet.level -> 55
const html = layout(g, ui);
console.log(JSON.stringify({
  draftLevel: ui.sheet.level, committedLevel: g.players[0].elimination,
  title: html.includes("P1") && html.includes(" 50<") && !html.includes(" 55<"),
  avertBody: html.includes("Threat drops to 45,") && !html.includes("Threat drops to 50,"),
}));
""")
    assert js["draftLevel"] == 55 and js["committedLevel"] == 50
    assert js["title"], "title must still read the committed level, not the stepper's draft"
    assert js["avertBody"], "avert preview must still read Math.max(0, committed - 5), not the draft"


def test_quest_sheet_location_progress_steps_and_done_flags_resolution():
    """(a) from the task-4 brief: open the quest sheet on a bare game with one
    active location, step its progress up to its own quest points with lP+,
    then quest_done - mirroring the twin's close-time
    "if (g.needsResolution()) g.pending_resolution = 'auto'" (QuestingProgress-
    Modal.onButton's "close" case, docs/js/screens.js), left set for Task 7's
    own sheet to consume."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
g.active_locations.push({ points: 4, progress: 1, name: "Forest Gate", threat: 2 });
const ui = newUi();
perform(g, ui, "open_quest", "");
const html = layout(g, ui);
perform(g, ui, "lP+", "0"); perform(g, ui, "lP+", "0"); perform(g, ui, "lP+", "0");
const progress = g.active_locations[0].progress;
perform(g, ui, "quest_done", "");
console.log(JSON.stringify({
  sheet: html.includes('class="sheet sheet-quest"'), name: html.includes("Forest Gate"),
  stepper: html.includes('data-act="lP+"'), progress, closed: ui.sheet === null,
  pending: g.pending_resolution,
}));
""")
    assert js["sheet"] and js["name"] and js["stepper"]
    assert js["progress"] == 4
    assert js["closed"]
    assert js["pending"] == "auto"


def test_quest_sheet_printed_x_count_stepper_resolves_the_threat():
    """(b) from the task-4 brief: a location whose printed X is not one of
    the tracked auto targets (xtargets.autoFor returns null for
    "damaged_characters") gets a labelled count stepper (xtargets.labelFor)
    instead of a read-only value - lX+ steps the count, and the row's own
    displayed value re-resolves through xtargets.resolve (mul=1 default,
    add=1) exactly like LocationConfigModal's "count" branch."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
g.active_locations.push({ points: 3, progress: 0, name: "Sarn Ford",
  threatKind: "x", threatX: { target: "damaged_characters", add: 1 }, threatCount: null });
const ui = newUi();
perform(g, ui, "open_quest", "");
const before = layout(g, ui);
perform(g, ui, "lX+", "0"); perform(g, ui, "lX+", "0");
const after = layout(g, ui);
console.log(JSON.stringify({
  label: before.includes("Damaged characters"), stepper: before.includes('data-act="lX+"'),
  threat: g.active_locations[0].threat, count: g.active_locations[0].threatCount,
  shows3: after.includes(">3<"),
}));
""")
    assert js["label"]
    assert js["stepper"]
    assert js["threat"] == 3 and js["count"] == 2
    assert js["shows3"]


def test_quest_sheet_tracked_x_shows_the_value_with_no_stepper():
    """(c) from the task-4 brief: "enemies_in_play" is a tracker-backed auto
    target (xtargets.AUTO_ENEMIES) - under setBoardTracking(true) the sheet
    shows the resolved value read-only, with no lX+/lX- stepper at all,
    mirroring LocationConfigModal's threatShape === "auto" branch."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, setBoardTracking } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS); setBoardTracking(true);
const g = new GameState(1, 25); g.advanceView();
g.active_locations.push({ points: 3, progress: 0, name: "Goblin Camp",
  threatKind: "x", threatX: { target: "enemies_in_play" }, threatCount: null });
const ui = newUi();
perform(g, ui, "open_quest", "");
const html = layout(g, ui);
console.log(JSON.stringify({
  sheet: html.includes('class="sheet sheet-quest"'), name: html.includes("Goblin Camp"),
  hasStepper: html.includes('data-act="lX+"') || html.includes('data-act="lX-"'),
}));
""")
    assert js["sheet"]
    assert js["name"]
    assert not js["hasStepper"]


def test_quest_sheet_blank_printed_x_has_no_stepper_and_no_invented_zero():
    """Task-4 fix round 1, review finding 1 (important): a location with
    threatKind "x" but no coded threatX spec at all (21 of the catalog's
    locations) used to fall through to the ordinary editable stepper, which
    actions.js's lThr± then silently refused for every threatKind "x"
    location - a dead button, visible and tappable, doing nothing. Fixed:
    xshape.js's "blank" shape renders a read-only, blank value slot (never a
    0 the card never printed) plus the twin's own line for exactly this case
    (LocationConfigModal's threatBlank-with-no-threatX branch, docs/js/
    screens.js ~2052-2056)."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
g.active_locations.push({ points: 3, progress: 0, name: "Ranger Camp", threatKind: "x" });
const ui = newUi();
perform(g, ui, "open_quest", "");
const html = layout(g, ui);
console.log(JSON.stringify({
  name: html.includes("Ranger Camp"),
  noThrStepper: !html.includes('data-act="lThr+"') && !html.includes('data-act="lThr-"'),
  noXStepper: !html.includes('data-act="lX+"') && !html.includes('data-act="lX-"'),
  elsewhere: html.includes("the card prints X and defines it elsewhere"),
  blankValue: html.includes('<span class="num num-34"></span>'),
}));
""")
    assert js["name"]
    assert js["noThrStepper"], "threatKind x with no coded spec must not fall through to the ordinary stepper"
    assert js["noXStepper"], "no coded threatX means no count stepper either"
    assert js["elsewhere"]
    assert js["blankValue"], "the value slot must render blank, never an invented 0"


def test_quest_sheet_condition_stage_shows_both_advance_and_lose():
    """Task-4 fix round 1, review finding 2 (important): a condition stage
    only ever rendered how you WIN (game.quest.advance) - game.quest.lose was
    never shown. QuestingProgressModal's own "cond" row pairs them
    (docs/js/screens.js ~1069-1077: "showing only the win is showing half the
    rule"). Fixed: the lose sentence renders under the advance line as
    <p class="body no"> (var(--no-fg))."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
g.quest.mode = "condition";
g.quest.advance = "Heal Wilyador to advance.";
g.quest.lose = "If Wilyador is discarded, the players lose.";
const ui = newUi();
perform(g, ui, "open_quest", "");
const html = layout(g, ui);
console.log(JSON.stringify({
  advance: html.includes("Heal Wilyador to advance."),
  lose: html.includes("If Wilyador is discarded, the players lose."),
  loseClass: html.includes('class="body no"'),
}));
""")
    assert js["advance"]
    assert js["lose"]
    assert js["loseClass"]


def test_location_picker_travel_then_manual_entry_appends_a_second_seat():
    """From the task-5 brief: the Travel pane's own CTA opens the location
    picker in mode "new"/back "play" (pane.js); picking the one catalog row
    and confirming commits exactly like the twin's LocationPickModal._commit
    - GameState.travelTo with the catalog row's own points/threat/name, the
    "Traveled to ..." log line (arrival "travel" because back is "play"),
    and the staging reduction travelTo already applies - then the sheet
    closes (back "play" has no sheet to reopen). A second pass through the
    manual steppers (mode "new" again) APPENDS rather than replacing the
    first seat, and the manual seat's threat is pinned to the contribution
    stepper per LocationPickModal._commit's own rule."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView(); g.enterView("travel");
g.setStaging(4);
const ui = newUi();
ui.locations = [{ id: "a", name: "Old Forest Road", points: 3, threat: 1, set: "Passage Through Mirkwood" }];
const beforeHtml = layout(g, ui);
perform(g, ui, "open_locpick", "new::play");
const listHtml = layout(g, ui);
perform(g, ui, "locpick_row", "a");
perform(g, ui, "locpick_travel", "");
const seat0 = g.active_locations[0];
const afterTravel = {
  name: seat0.name, points: seat0.points, threat: seat0.threat,
  staging: g.staging, closed: ui.sheet === null,
  logged: g.log.some(e => e.text === "Traveled to Old Forest Road (3 quest points)"),
};
// A second seat, entered manually - reopening from the play pane again
// (mode "new" - it appends, it never replaces the seat travelTo just
// placed).
perform(g, ui, "open_locpick", "new::play");
perform(g, ui, "locpick_manual", "");
perform(g, ui, "locpick_pts", "1");
const manualPts = ui.sheet.manual.points;
const manualContrib = ui.sheet.manual.contrib;
perform(g, ui, "locpick_save", "");
console.log(JSON.stringify({
  travelChip: beforeHtml.includes('data-act="open_locpick"') && beforeHtml.includes('data-arg="new::play"'),
  rowRendered: listHtml.includes("Old Forest Road") && listHtml.includes('data-act="locpick_row"'),
  // Regression: the set-group header is a nested h`` fragment interpolated
  // into the outer h`` template (sheet_locpick.js's groupBySet loop) - it
  // must be wrapped in raw(...) there, or the outer template escapes the
  // inner one's own escaping and the header renders as literal markup text
  // instead of a heading (dom.js's one() only trusts a Raw instance).
  setHeaderHtml: listHtml,
  ...afterTravel,
  manualPts,
  seats: g.active_locations.length,
  secondThreat: g.active_locations[1].threat,
  manualContrib,
  manualClosed: ui.sheet === null,
}));
""")
    assert js["travelChip"], "the Travel pane must offer its own CTA when no location is active"
    assert js["rowRendered"]
    assert '<div class="label">Passage Through Mirkwood</div>' in js["setHeaderHtml"], \
        "the set header must render as markup, not escaped text"
    assert "&lt;div" not in js["setHeaderHtml"], \
        "a nested h`` fragment interpolated without raw(...) double-escapes into literal text"
    assert js["name"] == "Old Forest Road" and js["points"] == 3 and js["threat"] == 1
    assert js["staging"] == 3            # setStaging(4), then -1 (travelTo's own contribution)
    assert js["logged"]
    assert js["closed"], "back \"play\" has no sheet to reopen"
    assert js["manualPts"] == 4
    assert js["seats"] == 2, "mode \"new\" appends a second seat, it never replaces the first"
    assert js["secondThreat"] == js["manualContrib"]
    assert js["manualClosed"]


def test_side_quest_picker_pick_sphere_row_add_appends_and_reopens_quest():
    """Task-6 brief step 1. SideQuestPickModal's own two-step flow (pick a
    sphere, then a quest inside it) mirrored as a sheet - onButton "add"
    (docs/js/screens.js) pushes {points, progress:0, name} and logs the
    verbatim "Side quest added: ..." line, then _leave() reopens the
    progress modal (here, ui.sheet {kind:"quest"}). Two entries in two
    different spheres means picking "Neutral" only ever has one candidate
    row - acts_sqpick.js's own sqpick_sphere pre-selects it, and the
    explicit "row" tap below re-confirms the same id."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
const ui = newUi();
ui.sideQuests = [
  { id: "a", name: "Fortune or Fate", points: 3, sphere: "Neutral" },
  { id: "b", name: "A Test of Wills", points: 2, sphere: "Spirit" },
];
ui.sheet = { kind: "sqpick", sphere: null, selected: null, page: 0 };
perform(g, ui, "sqpick_sphere", "Neutral");
perform(g, ui, "sqpick_row", "a");
perform(g, ui, "sqpick_add", "");
console.log(JSON.stringify({
  count: g.side_quests.length,
  name: g.side_quests[0]?.name,
  points: g.side_quests[0]?.points,
  progress: g.side_quests[0]?.progress,
  logged: g.log.some(e => e.text === "Side quest added: Fortune or Fate (3 pts, progress view)"),
  sheetKind: ui.sheet?.kind,
}));
""")
    assert js["count"] == 1
    assert js["name"] == "Fortune or Fate"
    assert js["points"] == 3
    assert js["progress"] == 0
    assert js["logged"]
    assert js["sheetKind"] == "quest"


def test_side_quest_picker_manual_back_cancel_and_render_shape():
    """Manual entry skips the sphere/quest picker entirely (onButton
    "manual", verbatim log line) and, like every other exit, reopens the
    quest sheet - no stepper editor, unlike the location picker's manual
    mode: points/progress start at 0 for the quest sheet's own sPts± to fill
    in later. Back undoes a sphere pick without leaving the picker; Cancel
    leaves without adding anything. Also checks the render shape: an entry
    with no printed sphere buckets under "No sphere" (SideQuestPickModal's
    own NO_SPHERE), a side quest's own printed text renders as a second BODY
    secondary line under its name/points row, and the pager is absent when
    everything already fits on one page."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
const ui = newUi();
ui.sideQuests = [
  { id: "a", name: "Fortune or Fate", points: 3, sphere: "Neutral", text: "Draw the top card of the encounter deck." },
  { id: "b", name: "Unaligned Quest", points: 1 },
];
ui.sheet = { kind: "sqpick", sphere: null, selected: null, page: 0 };
const sphereHtml = layout(g, ui);
perform(g, ui, "sqpick_sphere", "Neutral");
const questHtml = layout(g, ui);
const autoSelected = ui.sheet.selected;
perform(g, ui, "sqpick_back", "");
const backSphere = ui.sheet.sphere;
perform(g, ui, "sqpick_cancel", "");
console.log(JSON.stringify({
  noSphereRow: sphereHtml.includes("No sphere") && sphereHtml.includes('data-act="sqpick_sphere"') && sphereHtml.includes('data-arg="No sphere"'),
  noPager: !sphereHtml.includes("sqpick-pager") && !sphereHtml.includes('data-act="sqpick_page"'),
  autoSelected,
  name: questHtml.includes("Fortune or Fate"),
  pts: questHtml.includes("3 pts"),
  text: questHtml.includes("Draw the top card of the encounter deck."),
  selectedClass: questHtml.includes("is-selected"),
  backSphere,
  cancelKind: ui.sheet?.kind,
  cancelCount: g.side_quests.length,
}));
""")
    assert js["noSphereRow"], "an entry with no printed sphere must bucket under \"No sphere\""
    assert js["noPager"], "two rows on one page must not draw a pager"
    assert js["autoSelected"] == "a", "a sphere with exactly one quest is pre-selected, ready for Add"
    assert js["name"] and js["pts"]
    assert js["text"], "the card's own printed text must render, not be dropped"
    assert js["selectedClass"]
    assert js["backSphere"] is None, "Back returns to the sphere step"
    assert js["cancelKind"] == "quest"
    assert js["cancelCount"] == 0, "Cancel must not add anything"


def test_side_quest_picker_manual_entry_pushes_zero_point_placeholder():
    """The Manual entry chip is offered even with no sphere picked (or no
    catalog at all) - it pushes {points:0, progress:0} straight away, with
    no manual stepper screen in between."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
const ui = newUi();
ui.sideQuests = [];
ui.sheet = { kind: "sqpick", sphere: null, selected: null, page: 0 };
perform(g, ui, "sqpick_manual", "");
console.log(JSON.stringify({
  count: g.side_quests.length,
  points: g.side_quests[0]?.points,
  progress: g.side_quests[0]?.progress,
  logged: g.log.some(e => e.text === "Side quest added manually (progress view)"),
  sheetKind: ui.sheet?.kind,
}));
""")
    assert js["count"] == 1
    assert js["points"] == 0
    assert js["progress"] == 0
    assert js["logged"]
    assert js["sheetKind"] == "quest"


def test_side_quest_picker_pagination_pages_forward_back_and_clamps():
    """Fix round 1, review finding 1: no test drove sqpick_page before this
    one. Nine entries in a single sphere is one more than PER_PAGE (8), so
    picking that sphere must show a pager and split the rows across two
    pages - real content assertions (the 9th entry's name is absent on page
    1 and present on page 2, and vice versa), not just a page-number check,
    since a stale render could show the wrong rows under a "correct" number.
    Also exercises sqpick_page's own clamp at both ends (acts_sqpick.js:
    Math.max(0, Math.min(pages - 1, sheet.page + arg)), which returns false
    - no change - once the requested step would go past either edge."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
const ui = newUi();
ui.sideQuests = Array.from({ length: 9 }, (_, i) => (
  { id: "q" + (i + 1), name: "Quest " + (i + 1), points: i + 1, sphere: "Neutral" }));
ui.sheet = { kind: "sqpick", sphere: null, selected: null, page: 0 };
perform(g, ui, "sqpick_sphere", "Neutral");
const page1Html = layout(g, ui);
const initialPage = ui.sheet.page;
const forward = perform(g, ui, "sqpick_page", "1");
const page2Html = layout(g, ui);
const pageAfterForward = ui.sheet.page;
const forwardClamped = perform(g, ui, "sqpick_page", "1");
const pageAfterForwardClamp = ui.sheet.page;
const back = perform(g, ui, "sqpick_page", "-1");
const page1AgainHtml = layout(g, ui);
const backClamped = perform(g, ui, "sqpick_page", "-1");
const pageAfterBackClamp = ui.sheet.page;
console.log(JSON.stringify({
  initialPage,
  page1HasFirst: page1Html.includes("Quest 1"),
  page1HasNinth: page1Html.includes("Quest 9"),
  page1Label: page1Html.includes('<span class="body secondary">1/2</span>'),
  forward, pageAfterForward,
  page2HasFirst: page2Html.includes("Quest 1"),
  page2HasNinth: page2Html.includes("Quest 9"),
  page2Label: page2Html.includes('<span class="body secondary">2/2</span>'),
  forwardClamped, pageAfterForwardClamp,
  back,
  page1AgainHasFirst: page1AgainHtml.includes("Quest 1"),
  page1AgainHasNinth: page1AgainHtml.includes("Quest 9"),
  backClamped, pageAfterBackClamp,
}));
""")
    assert js["initialPage"] == 0, "sqpick_sphere resets to page 0"
    assert js["page1HasFirst"] and not js["page1HasNinth"], "page 1 must hold the first 8 rows only"
    assert js["page1Label"], "the page readout must read 1/2 on page 1"
    assert js["forward"], "sqpick_page must report a change when it actually moves"
    assert js["pageAfterForward"] == 1
    assert js["page2HasNinth"] and not js["page2HasFirst"], "page 2 must hold the 9th row, not the first"
    assert js["page2Label"], "the page readout must read 2/2 on page 2"
    assert not js["forwardClamped"], "paging forward past the last page must be a no-op"
    assert js["pageAfterForwardClamp"] == 1, "a clamped page tap must not move the page"
    assert js["back"], "sqpick_page must report a change when it moves back"
    assert js["page1AgainHasFirst"] and not js["page1AgainHasNinth"], "paging back must restore page 1's rows"
    assert not js["backClamped"], "paging back past the first page must be a no-op"
    assert js["pageAfterBackClamp"] == 0, "a clamped page tap must not move the page"


# Task 7's fixture, shaped like the real catalog and like the twin's own
# (tests/test_resolution_modal.py's STAGES, which drives ResolutionModal
# through this same walk): stage 1 is one card worth 2 quest points, stage 2
# is a two-card fork. The fork's alternatives deliberately SHARE a front-face
# name and differ only on their backs - that is the majority case in the
# catalog (23 of 39 branch stages; Escape from Khazad-dum's stage 2 is
# "Search for an Exit" three times over), and it is why resolve_step.js's
# branchName reads the back face.
#
# Old One Lair carries questPointsKind: "na" - a condition stage, one of the
# 32 (of 116) branch alternatives in the catalog that print no quest points
# at all (review finding 1) - so the walk below doubles as the regression:
# it must never render "0 quest points" for this row, only for A Way Up's
# real printed 4.
_RESOLVE_STAGES = """
const STAGES = [
  { stage: 1, cards: [{ questPoints: 2, faces: [
      { side: "A", name: "Flies and Spiders", text: "Setup: search the encounter deck." },
      { side: "B", name: "Flies and Spiders", text: null }] }] },
  { stage: 2, branch: "choice", cards: [
      { questPoints: 0, questPointsKind: "na", faces: [
          { side: "A", name: "Search for an Exit", text: null },
          { side: "B", name: "Old One Lair", text: "This stage cannot be defeated until X." }] },
      { questPoints: 4, faces: [
          { side: "A", name: "Search for an Exit", text: "When Revealed: add 1 enemy to staging." },
          { side: "B", name: "A Way Up", text: "Progress cannot be placed here." }] }] },
];
"""


def test_resolution_sheet_walks_branch_advance_reveal_flip_to_all_resolved():
    """Task-7 brief step 1. The whole guided flow in one tap sequence, the
    twin's own (test_resolution_modal.py's
    test_branch_pick_then_advance_then_reveal_then_flip, plus the auto-open
    main.js does off pending_resolution): filling stage 1B's 2 quest points
    sets game.pending_resolution, afterTap() seats the sheet the way app.js
    does after every perform(), and deriveResolveStep() - the one function
    both the renderer and the acts read - walks branch -> advance -> reveal
    -> null. The reveal step must print BOTH faces (75 of 514 stage cards
    print their rules only on the back), and the branch rows must be told
    apart by their BACK names, since both alternatives here print the same
    front name."""
    js = node(_RESOLVE_STAGES + """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, STAGES);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "flip_to_b", "");                  // 1A -> 1B, 2 quest points
g.setWillpower(4); g.setStaging(0);
perform(g, ui, "resolve", "");
perform(g, ui, "apply_alloc", "");                // 2 of 4 progress lands, stage cleared
const pending = g.pending_resolution;
afterTap(g, ui);
const opened = ui.sheet && { ...ui.sheet };
const cleared = g.pending_resolution;

const branchStep = deriveResolveStep(g, ui);
const branchHtml = layout(g, ui);
perform(g, ui, "res_branch", "1");                // take the second path
const advanceStep = deriveResolveStep(g, ui);
const advanceHtml = layout(g, ui);
perform(g, ui, "res_advance", "");
const advanced = { stage_idx: g.stage_idx, card_idx: g.card_idx, side: g.quest.side,
                   branchPick: ui.sheet.branchPick, kind: deriveResolveStep(g, ui).kind };
const revealHtml = layout(g, ui);
perform(g, ui, "res_flip", "");
const flipped = { side: g.quest.side, points: g.quest.points, step: deriveResolveStep(g, ui) };
const doneHtml = layout(g, ui);
perform(g, ui, "res_close", "");
console.log(JSON.stringify({
  pending, opened, cleared,
  branchKind: branchStep.kind, branchMode: branchStep.mode,
  branchSheet: branchHtml.includes('class="sheet sheet-resolve"'),
  branchTitle: branchHtml.includes("Choose a path") && branchHtml.includes("First player chooses"),
  branchBackNames: branchHtml.includes("Old One Lair") && branchHtml.includes("A Way Up"),
  branchFrontName: branchHtml.includes("Search for an Exit"),
  branchText: branchHtml.includes("Progress cannot be placed here."),
  branchPoints: branchHtml.includes("4 quest points"),
  branchNoZeroPoints: branchHtml.includes("0 quest points"),
  branchTaps: (branchHtml.match(/data-act="res_branch"/g) || []).length,
  noRandomize: !branchHtml.includes('data-act="res_random"'),
  advanceKind: advanceStep.kind, advanceIdx: advanceStep.card_idx,
  advanceUnderfilled: advanceStep.underfilled,
  advanceCta: advanceHtml.includes('data-act="res_advance"') && advanceHtml.includes("Reveal Stage 2"),
  noWarning: !advanceHtml.includes("Progress hasn't reached target"),
  advanced,
  revealTitle: revealHtml.includes("Stage 2 revealed"),
  revealFaceA: revealHtml.includes("When Revealed: add 1 enemy to staging."),
  revealFaceB: revealHtml.includes("Progress cannot be placed here."),
  revealCaptions: revealHtml.includes("Side A") && revealHtml.includes("Side B"),
  revealCta: revealHtml.includes('data-act="res_flip"') && revealHtml.includes("4 qp"),
  flipped,
  doneTitle: doneHtml.includes("All resolved") && doneHtml.includes('data-act="res_close"'),
  closed: ui.sheet,
}));
""")
    assert js["pending"] == "auto"
    assert js["opened"] == {"kind": "resolve", "forced": False, "branchPick": None, "skippedSide": []}
    assert js["cleared"] is False, "afterTap must consume pending_resolution, like main.js's router"
    assert js["branchKind"] == "branch" and js["branchMode"] == "choice"
    assert js["branchSheet"] and js["branchTitle"]
    assert js["branchBackNames"], "fork rows are named off the BACK face"
    assert not js["branchFrontName"], "the shared front name would make both rows read alike"
    assert js["branchText"] and js["branchPoints"]
    assert not js["branchNoZeroPoints"], "Old One Lair prints no points (questPointsKind: \"na\") - never a 0 it didn't print"
    assert js["branchTaps"] == 2 and js["noRandomize"]
    assert js["advanceKind"] == "advance" and js["advanceIdx"] == 1
    assert js["advanceUnderfilled"] is False
    assert js["advanceCta"] and js["noWarning"]
    assert js["advanced"] == {"stage_idx": 1, "card_idx": 1, "side": "A",
                              "branchPick": None, "kind": "reveal"}
    assert js["revealTitle"] and js["revealCaptions"]
    assert js["revealFaceA"] and js["revealFaceB"], "both faces print - the back is where 75 stage cards keep their rules"
    assert js["revealCta"]
    assert js["flipped"] == {"side": "B", "points": 4, "step": None}
    assert js["doneTitle"]
    assert js["closed"] is None


def test_resolution_sheet_final_stage_offers_victory_and_not_yet():
    """Task-7 brief step 1, second walk. With no next stage, _questStep's
    victory branch is the step: it carries the final stage's BACK face, whose
    text is often the restriction that decides whether the game is actually
    won ("cannot be defeated while X is in play"). "Not yet" must CLOSE and
    log rather than re-derive - the step recomputes to the same victory while
    progress >= points, so leaving the sheet open made the tap read as a
    no-op (the twin's own continue_without_victory comment, from the
    2026-07-30 playtest). Victory is the only setGameOver in the sheet."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, [{ stage: 1, cards: [{ questPoints: 2, faces: [
  { side: "A", name: "The Last Stage", text: "Setup: shuffle the encounter deck." },
  { side: "B", name: "The Last Stage", text: "This stage cannot be defeated while X is in play." }] }] }]);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "flip_to_b", "");
g.setWillpower(4); g.setStaging(0);
perform(g, ui, "resolve", "");
perform(g, ui, "apply_alloc", "");
afterTap(g, ui);
const step = deriveResolveStep(g, ui);
const html = layout(g, ui);
perform(g, ui, "res_not_yet", "");
const declined = { sheet: ui.sheet, over: g.game_over, log: g.log.at(-1).text };
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
perform(g, ui, "res_victory", "");
console.log(JSON.stringify({
  kind: step.kind, cleared: step.cleared,
  title: html.includes("That was the final stage!") && html.includes("Quest 1B cleared"),
  restriction: html.includes("This stage cannot be defeated while X is in play."),
  ctas: html.includes('data-act="res_victory"') && html.includes('data-act="res_not_yet"'),
  declined,
  result: g.game_over?.result, sheet: ui.sheet,
  overLog: g.log.at(-1).text,
}));
""")
    assert js["kind"] == "victory" and js["cleared"] == "1B"
    assert js["title"] and js["ctas"]
    assert js["restriction"], "the final stage's back face is the reason \"Not yet\" exists"
    assert js["declined"]["sheet"] is None, "\"Not yet\" closes; re-deriving would put the same screen back"
    assert js["declined"]["over"] is None
    assert js["declined"]["log"] == "Victory declined - the stage is not defeated yet"
    assert js["result"] == "victory"
    assert js["sheet"] is None
    assert js["overLog"] == "GAME OVER - Victory! The final quest stage is complete"


def test_resolution_sheet_side_quests_then_a_forced_underfilled_advance():
    """The two branches the walk above cannot reach. (1) Side quests resolve
    one at a time, and "Leave as-is" holds the skipped one by IDENTITY - the
    twin's _skippedSideQuests - so completing a LATER one, which splices the
    list, does not un-skip it or re-offer it under its new index. The
    completion line is the twin's own, verbatim. (2) `forced` is the entry
    the quest row's Advance uses (pending_resolution = "forced"): it reaches
    the quest step with progress BELOW the target, which is exactly when the
    advance step has to say so, and res_advance spends the flag (and the
    branch pick) rather than carrying either into the next stage."""
    js = node(_RESOLVE_STAGES + """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, STAGES);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "flip_to_b", "");
g.quest.progress = 1;                                   // 1 of 2: NOT at its points
g.side_quests.push({ points: 1, progress: 2, name: "Gather Information" });
g.side_quests.push({ points: 2, progress: 2, name: "Prepare for Battle" });
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };

const first = deriveResolveStep(g, ui);
const sqHtml = layout(g, ui);
perform(g, ui, "res_side_skip", "");
const skipped = deriveResolveStep(g, ui);
perform(g, ui, "res_side_done", "");
const doneLog = g.log.at(-1).text;
const remaining = g.side_quests.map(s => s.name);
const settled = deriveResolveStep(g, ui);

// The quest row's own "Advance": resolve the stage even though 1 < 2.
ui.sheet = { kind: "resolve", forced: true, branchPick: 1, skippedSide: [] };
const forced = deriveResolveStep(g, ui);
const forcedHtml = layout(g, ui);
perform(g, ui, "res_advance", "");
console.log(JSON.stringify({
  first: { kind: first.kind, idx: first.idx, name: first.name },
  sqCtas: sqHtml.includes('data-act="res_side_done"') && sqHtml.includes('data-act="res_side_skip"'),
  sqProgress: sqHtml.includes("2/1 progress"),
  skipped: { kind: skipped.kind, idx: skipped.idx, name: skipped.name },
  doneLog, remaining, settled,
  forced: { kind: forced.kind, idx: forced.card_idx, underfilled: forced.underfilled },
  warning: forcedHtml.includes("Progress hasn&#39;t reached target - confirm"),
  advanced: { stage_idx: g.stage_idx, card_idx: g.card_idx, side: g.quest.side,
              forcedFlag: ui.sheet.forced, branchPick: ui.sheet.branchPick },
}));
""")
    assert js["first"] == {"kind": "side_quest", "idx": 0, "name": "Gather Information"}
    assert js["sqCtas"] and js["sqProgress"]
    assert js["skipped"] == {"kind": "side_quest", "idx": 1, "name": "Prepare for Battle"}
    assert js["doneLog"] == "Side quest 2 completed (resolution)"
    assert js["remaining"] == ["Gather Information"]
    assert js["settled"] is None, "a skipped side quest must stay skipped after a later one splices the list"
    assert js["forced"] == {"kind": "advance", "idx": 1, "underfilled": True}
    assert js["warning"], "an advance below the target has to say so"
    assert js["advanced"] == {"stage_idx": 1, "card_idx": 1, "side": "A",
                              "forcedFlag": False, "branchPick": None}


def test_resolution_sheet_branch_row_shows_the_cards_own_x_text_instead_of_a_number():
    """Review finding 1's other half: The Woodland Realm's stage 3 "To the
    Elvenking's Halls" is the one branch alternative in the whole catalog
    whose quest points are a coded X (questPointsKind: "x") rather than a
    number or a printed "-" - so stagePointsShape (xshape.js) must route it
    to the card's own questPointsX.text instead of a number, and it must
    never fall back to "0 quest points" the way a bare
    `card.questPoints ?? 0` used to. Progress is set straight on
    g.quest.progress (like the forced-advance test above) rather than
    walked through resolve/apply_alloc - only the derived branch step and
    its render matter here."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const XTEXT = "X is equal to the threat level of the player with the highest threat level.";
const STAGES = [
  { stage: 1, cards: [{ questPoints: 1, faces: [
      { side: "A", name: "On the Trail", text: "Setup: shuffle the encounter deck." },
      { side: "B", name: "On the Trail", text: null }] }] },
  { stage: 2, branch: "random", cards: [
      { questPoints: 15, faces: [
          { side: "A", name: "On the Trail", text: null },
          { side: "B", name: "The Forest of Great Fear", text: "When Revealed: search the encounter deck." }] },
      { questPoints: 0, questPointsKind: "x", questPointsX: { target: "highest_threat", text: XTEXT }, faces: [
          { side: "A", name: "On the Trail", text: null },
          { side: "B", name: "To the Elvenking's Halls", text: "This stage cannot be defeated until X." }] }] },
];
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, STAGES);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "flip_to_b", "");
g.quest.progress = g.quest.points;                // clear stage 1 without the full alloc walk
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
const step = deriveResolveStep(g, ui);
const html = layout(g, ui);
console.log(JSON.stringify({
  kind: step.kind,
  xText: html.includes(XTEXT),
  ownCardText: html.includes("This stage cannot be defeated until X."),
  numberPoints: html.includes("15 quest points"),
  noZeroPoints: html.includes("0 quest points"),
}));
""")
    assert js["kind"] == "branch"
    assert js["xText"], "the X alternative shows the card's own questPointsX.text, not a number"
    assert js["ownCardText"], "the card's own back-face text still prints too, same as any other row"
    assert js["numberPoints"], "the numeric sibling still renders its real points"
    assert not js["noZeroPoints"]


def test_resolution_sheet_flip_cta_omits_the_qp_suffix_for_a_condition_or_x_stage():
    """Review finding 3: the reveal step's "Flip to Side B -> N qp" CTA read
    card.questPoints unconditionally, so a condition stage (questPointsKind
    "na") or an X stage (questPointsKind "x") got the same "-> 0 qp" a real
    numeric stage gets. Gated on the same shape predicate as the branch rows
    (xshape.js's stagePointsShape) - the twin's own _drawReveal still prints
    "0 qp" here; a follow-up card fixes it there."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
function reveal(card) {
  const g = new GameState(1, 25);
  g.preloadScenario({ slug: "x", name: "X" }, [{ stage: 1, cards: [card] }]);
  g.view = "quest_setup";
  const ui = newUi();
  ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
  return layout(g, ui);
}
const condHtml = reveal({ questPoints: 0, questPointsKind: "na", faces: [
  { side: "A", name: "Cond Stage", text: "Setup: shuffle the encounter deck." },
  { side: "B", name: "Cond Stage", text: "Advances when the last enemy is defeated." }] });
const xHtml = reveal({ questPoints: 0, questPointsKind: "x",
  questPointsX: { target: "highest_threat", text: "X is equal to the threat level of the player with the highest threat level." },
  faces: [
    { side: "A", name: "X Stage", text: null },
    { side: "B", name: "X Stage", text: "This stage cannot be defeated until X." }] });
const numHtml = reveal({ questPoints: 3, faces: [
  { side: "A", name: "Num Stage", text: "Setup: shuffle the encounter deck." },
  { side: "B", name: "Num Stage", text: null }] });
console.log(JSON.stringify({
  condFlip: condHtml.includes(">Flip to Side B<"),
  condNoQp: !condHtml.includes("qp"),
  xFlip: xHtml.includes(">Flip to Side B → X<"),
  xNoZero: !xHtml.includes("0 qp"),
  numFlip: numHtml.includes(">Flip to Side B → 3 qp<"),
}));
""")
    assert js["condFlip"], "no printed target - no arrow, no qp suffix at all"
    assert js["condNoQp"]
    assert js["xFlip"], "an X stage's flip CTA names the shape, not a number"
    assert js["xNoZero"]
    assert js["numFlip"], "a real numeric stage keeps its own qp suffix"


def test_resolution_sheet_branch_row_omits_points_for_a_blank_zero_alternative():
    """Fix round 2 (re-review of round 1's finding 1): stagePointsShape only
    special-cased questPointsKind "na" and "x", but 48 stage faces
    catalog-wide - and 6 of the 116 branch alternatives, e.g. Passage Through
    Mirkwood's stage 3 "Don't Leave the Path!" - have questPoints: 0 with NO
    questPointsKind at all (the upstream TSV field was simply blank). Those
    six fell through to "number" and printed "0 quest points", a target the
    card never carries. Shaped exactly like the real catalog entry: one
    branch alternative with `questPoints: 0` and neither questPointsKind nor
    questPointsX, alongside a numeric sibling that must keep rendering its
    own real points."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const STAGES = [
  { stage: 1, cards: [{ questPoints: 1, faces: [
      { side: "A", name: "Setting Out", text: "Setup: shuffle the encounter deck." },
      { side: "B", name: "Setting Out", text: null }] }] },
  { stage: 2, branch: "choice", cards: [
      { questPoints: 0, faces: [
          { side: "A", name: "Don't Leave the Path!", text: null },
          { side: "B", name: "Off the Path", text: "This stage advances when the last enemy is defeated." }] },
      { questPoints: 6, faces: [
          { side: "A", name: "Don't Leave the Path!", text: "When Revealed: add 1 enemy to staging." },
          { side: "B", name: "On the Path", text: "Progress may be placed here." }] }] },
];
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, STAGES);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "flip_to_b", "");
g.quest.progress = g.quest.points;                // clear stage 1 without the full alloc walk
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
const step = deriveResolveStep(g, ui);
const html = layout(g, ui);
console.log(JSON.stringify({ kind: step.kind, html }));
""")
    assert js["kind"] == "branch"
    html = js["html"]
    assert "This stage advances when the last enemy is defeated." in html, (
        "the blank alternative's own card text still prints")
    assert "Progress may be placed here." in html
    assert "6 quest points" in html, "the numeric sibling still renders its real points"
    assert "0 quest points" not in html, (
        "a blank questPointsKind with questPoints: 0 must draw no number, like a printed dash")


def test_resolution_sheet_reveal_flip_cta_omits_qp_for_a_blank_zero_stage():
    """The reveal-step half of the same fix: a single-card stage (the far
    more common shape - 42 of the 48 blank-0 faces are single-card reveals,
    e.g. The Nin-in-Eilph's "Fleeing from Tharbad") with `questPoints: 0` and
    no questPointsKind must flip with a bare "Flip to Side B", never
    "-> 0 qp" - same predicate, same CTA gating as the na/x cases already
    covered above."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, [{ stage: 1, cards: [{ questPoints: 0, faces: [
  { side: "A", name: "Fleeing from Tharbad", text: "Setup: search the encounter deck." },
  { side: "B", name: "Fleeing from Tharbad", text: "This stage advances when the party disengages." }] }] }]);
g.view = "quest_setup";
const ui = newUi();
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
const html = layout(g, ui);
console.log(JSON.stringify({ html }));
""")
    html = js["html"]
    assert ">Flip to Side B<" in html, "no printed target - a bare flip CTA, no arrow, no qp suffix"
    assert "→ 0 qp" not in html
    assert "0 quest points" not in html


def test_resolution_sheet_reveal_prints_one_line_for_a_card_blank_on_both_faces():
    """Review finding 2: a stage card that prints no text on EITHER face used
    to draw two "No card text" blocks, one per caption - reading as "this
    stage has nothing to do" twice over. The twin's own _drawReveal folds
    this into QUEST_SETUP.none (viewcopy.js) instead, said once. Checked by
    counting .rsheet-face blocks rather than the sentence itself, since the
    background quest_setup pane (pane.js's renderQuestSetup) also has its
    OWN "has no Setup instructions" line for this same blank card
    ("Stage 1A", stage+side) - a different string from the sheet's own
    ("Stage 1", stage only), but both contain that phrase."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, [{ stage: 1, cards: [{ questPoints: 2, faces: [
  { side: "A", name: "Blank Stage", text: null },
  { side: "B", name: "Blank Stage", text: null }] }] }]);
g.view = "quest_setup";
const ui = newUi();
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
const html = layout(g, ui);
console.log(JSON.stringify({
  rsheetFaceBlocks: (html.match(/class="rsheet-face"/g) || []).length,
  sheetLine: html.includes("Stage 1 has no Setup instructions."),
  noCardTextLiteral: html.includes("No card text"),
  sideCaptionsAbsent: !html.includes(">Side A<") && !html.includes(">Side B<"),
}));
""")
    assert js["rsheetFaceBlocks"] == 1, "one block for the combined message, not one per blank face"
    assert js["sheetLine"]
    assert not js["noCardTextLiteral"]
    assert js["sideCaptionsAbsent"], "the both-blank case is not per-face, so it drops the Side A/B captions too"


def test_sailing_sheet_wheels_found_shifts_heading_and_cancel_leaves_it_unchanged():
    """SailingModal is the twin's canvas reference (docs/js/screens.js): the
    arrival shift (advanceView's planning -> quest_sailing branch,
    gamestate.js ~950) starts every sailing round 1 step off-course before
    the player ever opens the sheet, so heading is 1 (Off-course/Cloudy) by
    the time open_sailing runs - asserted here as the walk's own
    precondition. +1 wheel twice (sail_d) then Apply shifts heading back to
    0 (On-course) via shiftHeading(-v, why), logging the twin's own why
    string verbatim ("2 wheels found (sailing test)"). A second
    open/nudge/Cancel leaves heading untouched and adds no log line - only
    Apply ever calls shiftHeading. The stepper's own -3..8 clamp
    (acts_sailing.js, NOT the 0..3 heading-index clamp the RESULT preview
    uses) is asserted at its floor: a further sail_d -1 is a no-op on the
    draft and the rendered stepper switches to the unbevelled step-off span,
    the same convention pane.js's allocStep uses."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25);
g.advanceView();               // quest_setup -> resource
g.sailing = true;
g.advanceView();               // resource -> planning
g.advanceView();               // planning -> quest_sailing (arrival shift: heading 0 -> 1)
const ui = newUi();
const preHeading = g.heading;
const paneHtml = layout(g, ui);

perform(g, ui, "open_sailing", "");
const opened = { ...ui.sheet };
const inRangeChanged = perform(g, ui, "sail_d", "1");
perform(g, ui, "sail_d", "1");
const draftV = ui.sheet.v;
const sheetHtml = layout(g, ui);
perform(g, ui, "sail_apply", "");
const afterApply = { heading: g.heading, sheet: ui.sheet, log: g.log.at(-1).text };

// A fresh open, nudged off-course, then Cancel - no shift, no log line.
perform(g, ui, "open_sailing", "");
perform(g, ui, "sail_d", "-1");
perform(g, ui, "sail_cancel", "");
const afterCancel = { heading: g.heading, sheet: ui.sheet, log: g.log.at(-1).text };

// The floor: nudge to -3, then past it - the draft holds, the stepper
// renders step-off instead of a live button, and perform() must report the
// 4th tap (already pinned at -3) as no real change so it never reaches
// game.addDelta().
perform(g, ui, "open_sailing", "");
let pastFloorChanged;
for (let i = 0; i < 4; i++) pastFloorChanged = perform(g, ui, "sail_d", "-1");
const floored = ui.sheet.v;
const flooredHtml = layout(g, ui);

// The ceiling: the same no-op guard at the other end (8) - 8 taps reach it,
// the 9th is pinned and must report false.
perform(g, ui, "open_sailing", "");
let pastCeilingChanged;
for (let i = 0; i < 9; i++) pastCeilingChanged = perform(g, ui, "sail_d", "1");
const ceilinged = ui.sheet.v;

console.log(JSON.stringify({
  preHeading,
  paneHasCta: paneHtml.includes('data-act="open_sailing"'),
  opened,
  inRangeChanged,
  draftV,
  sheetHasSheet: sheetHtml.includes('class="sheet sheet-sailing"'),
  sheetHasResult: sheetHtml.includes("On-course (Sunny)"),
  sheetHasSubline: sheetHtml.includes("2 wheels found - shift on-course"),
  afterApply, afterCancel,
  floored, flooredHasStepOff: flooredHtml.includes('step step-sm step-off'),
  pastFloorChanged,
  ceilinged, pastCeilingChanged,
}));
""")
    assert js["preHeading"] == 1
    assert js["paneHasCta"]
    assert js["opened"] == {"kind": "sailing", "v": 0}
    assert js["inRangeChanged"] is True, "an in-range nudge is a real change"
    assert js["draftV"] == 2
    assert js["sheetHasSheet"]
    # RESULT preview (sheet_sailing.js's headingLine()) and the sub-line
    # (subLine(), CHROME.sailWheelsFound) for the +2-wheels draft: heading 1
    # (Off-course/Cloudy) minus 2 clamps to HEADINGS[0] (On-course/Sunny).
    assert js["sheetHasResult"], "RESULT preview must show 'On-course (Sunny)' for the +2 draft"
    assert js["sheetHasSubline"], "sub-line must show '2 wheels found - shift on-course'"
    assert js["afterApply"] == {
        "heading": 0, "sheet": None,
        "log": "Sailing: heading Off-course (Cloudy) -> On-course (Sunny) "
               "(shifted on-course, 2 wheels found (sailing test))",
    }
    assert js["afterCancel"]["heading"] == 0            # unchanged by cancel
    assert js["afterCancel"]["sheet"] is None
    assert js["afterCancel"]["log"] == js["afterApply"]["log"], "cancel must not log"
    assert js["floored"] == -3
    assert js["flooredHasStepOff"]
    assert js["pastFloorChanged"] is False, "clamped at the floor: sail_d must report no change"
    assert js["ceilinged"] == 8
    assert js["pastCeilingChanged"] is False, "clamped at the ceiling: sail_d must report no change"


def test_chip_labels_are_composed_with_h():
    """chip()/cta() in primitives.js insert `label` via raw() (see
    test_h_escapes_interpolations_but_not_raw above), so a label built from
    interpolated content must be composed with the escaping h`` tag from
    dom.js - a bare JS template literal skips escaping entirely once raw()
    unwraps it. A static scan under node is awkward for this one (it is a
    source-shape check, not a runtime behavior), so just grep the files
    directly for the offending shape."""
    import re

    tablet_js_dir = os.path.join(ROOT, "docs", "tablet", "js")
    bad_pattern = re.compile(r"label:\s*`")
    allowed = re.compile(r"label:\s*(h`|CHROME\.|raw\()")
    violations = []
    for fname in sorted(os.listdir(tablet_js_dir)):
        if not fname.endswith(".js"):
            continue
        with open(os.path.join(tablet_js_dir, fname)) as f:
            for lineno, line in enumerate(f, 1):
                if bad_pattern.search(line) and not allowed.search(line):
                    violations.append("%s:%d: %s" % (fname, lineno, line.strip()))
    assert not violations, (
        "label built from a plain template literal, bypassing h`` escaping "
        "before raw() unwraps it:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Final fix wave (milestone 3 review): C1, I2, I3, I4, M5, M8, M9, Rule 3b.
# ---------------------------------------------------------------------------


def test_quest_sheet_force_advance_button_renders_only_with_a_stage_tree():
    """C1: "Advance anyway" (acts_quest.js's quest_force) is only offered
    when the game has a stage tree at all - QuestConfigModal's own force_adv
    button is gated the same way (docs/js/screens.js ~2244-2249): a
    custom/manual game has no guided resolution flow for it to open."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);

const bare = new GameState(1, 25); bare.advanceView();
const bareUi = newUi();
perform(bare, bareUi, "open_quest", "");
const bareHtml = layout(bare, bareUi);

const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, [{ stage: 1, cards: [{ questPoints: 3, faces: [
  { side: "A", name: "X", text: null }, { side: "B", name: "X", text: null }] }] }]);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "open_quest", "");
const html = layout(g, ui);
console.log(JSON.stringify({
  bareHasButton: bareHtml.includes('data-act="quest_force"'),
  hasButton: html.includes('data-act="quest_force"'),
  label: html.includes("Advance anyway"),
}));
""")
    assert not js["bareHasButton"], "a custom/manual game has no guided resolution flow to force-open"
    assert js["hasButton"] and js["label"]


def test_quest_sheet_force_advance_walks_a_condition_stage_then_recovers_after_a_dismiss():
    """C1, both halves of the finding. (a) A condition-mode stage (points 0,
    so quest_done's ordinary needsResolution() check never fires on its own)
    still needs a way into the guided flow - quest_force sets the SAME
    pending_resolution = "forced" flag QuestConfigModal's force_adv sets, and
    resolve_step.js's `sheet.forced` is what lets the quest step fire despite
    the target never being reached. (b) Recovery: dismissing the resulting
    resolve sheet with sheet_close (side A, quest.points back at 0 after the
    advance) must not strand the player - reopening the quest sheet and
    forcing again has to walk the SAME interrupted-reveal-first precedence
    resolve_step.js documents, not skip straight to a stale "advance"."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const STAGES = [
  { stage: 1, cards: [{ questPoints: 0, questPointsKind: "na", faces: [
      { side: "A", name: "The Bell Tolls", text: "Setup: shuffle the encounter deck." },
      { side: "B", name: "The Bell Tolls", text: "This stage advances when the bell is struck three times." }] }] },
  { stage: 2, cards: [{ questPoints: 3, faces: [
      { side: "A", name: "The Answer", text: "When Revealed: add 1 enemy to staging." },
      { side: "B", name: "The Answer", text: null }] }] },
];
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, STAGES);
g.view = "quest_setup";
const ui = newUi();

perform(g, ui, "flip_to_b", "");                    // 1A -> 1B: condition mode, 0 points
const mode = g.quest.mode;
perform(g, ui, "open_quest", "");
const forced = perform(g, ui, "quest_force", "");
afterTap(g, ui);
const opened = { ...ui.sheet };
const advanceStep = deriveResolveStep(g, ui);
perform(g, ui, "res_advance", "");
const advanced = { stage_idx: g.stage_idx, side: g.quest.side, points: g.quest.points };

// (b) recovery: dismiss via the scrim rather than a resolve-sheet CTA, at
// the freshly-advanced side A / 0 points, then force again.
perform(g, ui, "sheet_close", "");
const afterDismiss = { sheet: ui.sheet, pending: g.pending_resolution };
perform(g, ui, "open_quest", "");
perform(g, ui, "quest_force", "");
afterTap(g, ui);
const reopened = { ...ui.sheet };
const revealStep = deriveResolveStep(g, ui);
perform(g, ui, "res_flip", "");
const flippedSide = g.quest.side;

console.log(JSON.stringify({
  mode, forced, opened, advanceKind: advanceStep.kind, advanceUnderfilled: advanceStep.underfilled,
  advanced, afterDismiss, reopened, revealKind: revealStep.kind, flippedSide,
}));
""")
    assert js["mode"] == "condition"
    assert js["forced"] is True
    assert js["opened"] == {"kind": "resolve", "forced": True, "branchPick": None, "skippedSide": []}
    assert js["advanceKind"] == "advance"
    assert js["advanceUnderfilled"] is False, "a condition stage prints no target, so it is never \"underfilled\""
    assert js["advanced"] == {"stage_idx": 1, "side": "A", "points": 0}
    assert js["afterDismiss"] == {"sheet": None, "pending": False}
    assert js["reopened"] == {"kind": "resolve", "forced": True, "branchPick": None, "skippedSide": []}
    assert js["revealKind"] == "reveal", "an interrupted flip (side A) takes precedence over the forced flag"
    assert js["flippedSide"] == "B"


def test_resolve_step_reports_all_resolved_instead_of_crashing_on_empty_stages():
    """I2: a resume whose bundle failed to (re)hydrate leaves game.stages
    == [] - fromDict()'s own default, since toDict() deliberately never
    saves `stages` (docs/js/gamestate.js). deriveResolveStep used to index
    g.stages[g.stage_idx] unconditionally the moment a quest already at its
    points (or a forced advance) reached questStep(), crashing layout() on
    every render. It must instead report nothing left to resolve. node()'s
    own non-zero-exit check is what proves this no longer throws."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi } from "./actions.js";
import { deriveResolveStep } from "./resolve_step.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
g.stages = [];                              // simulate a resume with no (re)hydrated stage tree
g.quest.points = 2; g.quest.progress = 2;   // already "at its points"
const ui = newUi();
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
const atPoints = deriveResolveStep(g, ui);
const atPointsHtml = layout(g, ui);

g.quest.points = 0; g.quest.progress = 0;   // not at its points, but forced
ui.sheet = { kind: "resolve", forced: true, branchPick: null, skippedSide: [] };
const forced = deriveResolveStep(g, ui);
const forcedHtml = layout(g, ui);

console.log(JSON.stringify({
  atPoints, atPointsAllResolved: atPointsHtml.includes("All resolved"),
  forced, forcedAllResolved: forcedHtml.includes("All resolved"),
}));
""")
    assert js["atPoints"] is None
    assert js["atPointsAllResolved"]
    assert js["forced"] is None
    assert js["forcedAllResolved"]


def test_quest_sheet_scrim_close_flags_resolution_same_as_done():
    """I3: acts_sheets.js's sheet_close used to just clear ui.sheet for
    every sheet kind, including the quest sheet - so a location edited up to
    its own quest points and dismissed via the scrim (rather than the
    sheet's own Done) never ran needsResolution() at all. Factored into
    closeQuestSheet() (acts_quest.js), now shared by quest_done and this
    scrim path - and it must NOT fire early, before the location is actually
    at its points, or for a scrim close on some other sheet kind."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView();
g.active_locations.push({ points: 3, progress: 1, name: "Sarn Ford", threat: 2 });
const ui = newUi();

perform(g, ui, "open_staging", "");
perform(g, ui, "sheet_close", "");
const otherKind = { pending: g.pending_resolution, closed: ui.sheet === null };

perform(g, ui, "open_quest", "");
perform(g, ui, "sheet_close", "");
const early = { pending: g.pending_resolution, closed: ui.sheet === null };

perform(g, ui, "open_quest", "");
perform(g, ui, "lP+", "0"); perform(g, ui, "lP+", "0");
const progress = g.active_locations[0].progress;
perform(g, ui, "sheet_close", "");
console.log(JSON.stringify({
  otherKind, early, progress, closed: ui.sheet === null, pending: g.pending_resolution,
}));
""")
    assert js["otherKind"] == {"pending": False, "closed": True}, "a scrim close on a non-quest sheet must not run this check"
    assert js["early"] == {"pending": False, "closed": True}, "not at its points yet: no false-positive resolution"
    assert js["progress"] == 3
    assert js["closed"]
    assert js["pending"] == "auto"


def test_elim_sheet_scrim_carries_no_dismiss_act():
    """M5: elimination is a required one-tap prompt, not an editor - every
    other sheet's scrim is a plain dismiss (data-act="sheet_close"), but a
    tap outside the elim sheet used to close it only for afterTap to
    re-seat pending_elim in the very same tap (actions.js): the scrim now
    renders with no data-act at all for kind "elim"."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView(); const ui = newUi();
perform(g, ui, "thr", "0:25"); afterTap(g, ui);   // 25 -> 50, crosses
const elimHtml = layout(g, ui);
perform(g, ui, "elim_confirm", "");
perform(g, ui, "open_staging", "");
const stagingHtml = layout(g, ui);
console.log(JSON.stringify({
  elimScrimNoAct: elimHtml.includes('<div class="scrim"><section class="sheet sheet-elim"'),
  stagingScrimHasAct: stagingHtml.includes('<div class="scrim" data-act="sheet_close"><section class="sheet sheet-staging"'),
}));
""")
    assert js["elimScrimNoAct"], "the elim sheet's scrim must carry no data-act"
    assert js["stagingScrimHasAct"], "every other sheet keeps its dismissible scrim"


def test_all_thr_reports_no_change_when_every_living_player_is_clamped():
    """M8: all_thr always reported a change, even when nudging every living
    player's threat left every one of them exactly where they started (all
    already at the threat floor, tapping -1) - a no-op tap that still
    recorded a delta and forced a re-render."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 0); g.advanceView();   // both players already at threat 0
const ui = newUi();
const noop = dispatch(g, ui, "all_thr", "-1");    // clamped: stays 0 for both
const real = dispatch(g, ui, "all_thr", "1");     // 0 -> 1 for both: a real change
console.log(JSON.stringify({ noop, real, threats: g.players.map(p => p.threat) }));
""")
    assert js["noop"] is False, "every living player already clamped at 0: all_thr must report no change"
    assert js["real"] is True
    assert js["threats"] == [1, 1]


def test_players_sheet_title_carries_no_stale_game_wide_elimination_figure():
    """M9: the title used to print game.elimination_threat - the GAME's
    default level - while elim_setlvl recalibrates a level PER PLAYER
    (p.elimination). Recalibrating one player's level away from the default
    left a header figure that named a level no row on screen still used;
    each row already prints its own "N to M", so the title carries no
    number of its own now."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 45); g.advanceView(); const ui = newUi();
perform(g, ui, "thr", "0:5"); afterTap(g, ui);                       // P1: 45 -> 50, crosses
perform(g, ui, "elim_lvl", "10"); perform(g, ui, "elim_setlvl", ""); // P1's own level -> 60
perform(g, ui, "open_players", "");
const html = layout(g, ui);
console.log(JSON.stringify({
  title: html.includes('<h1 class="display">Players</h1>'),
  noStaleFigure: !html.includes("elimination at"),
  p1Row: html.includes("10 to 60"),
  p2Row: html.includes("5 to 50"),
}));
""")
    assert js["title"]
    assert js["noStaleFigure"]
    assert js["p1Row"], "P1's own recalibrated level (60), 10 short of it"
    assert js["p2Row"], "P2 stays at the untouched default level (50)"


def test_randomize_row_is_a_body_cta_not_a_label_chip():
    """Rule 3b review finding: "Randomize for me" is a sentence offering an
    action, the same shape as the branch rows above it in the same step -
    not a 13px ALL-CAPS chip naming a slot (design system rule 3b)."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const STAGES = [
  { stage: 1, cards: [{ questPoints: 1, faces: [
      { side: "A", name: "On the Trail", text: null },
      { side: "B", name: "On the Trail", text: null }] }] },
  { stage: 2, branch: "random", cards: [
      { questPoints: 2, faces: [
          { side: "A", name: "On the Trail", text: null },
          { side: "B", name: "Path One", text: "Path one text." }] },
      { questPoints: 3, faces: [
          { side: "A", name: "On the Trail", text: null },
          { side: "B", name: "Path Two", text: "Path two text." }] }] },
];
const g = new GameState(1, 25);
g.preloadScenario({ slug: "x", name: "X" }, STAGES);
g.view = "quest_setup";
const ui = newUi();
perform(g, ui, "flip_to_b", "");
g.quest.progress = g.quest.points;
ui.sheet = { kind: "resolve", forced: false, branchPick: null, skippedSide: [] };
const html = layout(g, ui);
console.log(JSON.stringify({
  isCta: /<button type="button" class="cta cta-plain"[^>]*data-act="res_random"/.test(html),
  isChip: /class="chip[^"]*"[^>]*data-act="res_random"/.test(html),
  label: html.includes("Randomize for me"),
}));
""")
    assert js["isCta"], "the randomize action must render as a cta"
    assert not js["isChip"]
    assert js["label"]


def test_transport_acts_move_the_cursor_without_recording_a_delta():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "advance", ""); perform(g, ui, "stg+", "");
const n0 = g.deltas.length;
const undo = perform(g, ui, "rw_undo", "");
const after = { step: g.replay_step, staging: g.staging, n: g.deltas.length };
const redo = perform(g, ui, "rw_redo", "");
const first = perform(g, ui, "rw_first", "");
const atFirst = { step: g.replay_step, view: g.view, staging: g.staging };
const last = perform(g, ui, "rw_last", "");
const noop = perform(g, ui, "rw_redo", "");
console.log(JSON.stringify({ n0, undo, after, redo, first, atFirst, last, noop, n1: g.deltas.length, step: g.replay_step }));
""")
    assert js["n0"] == 3 and js["n1"] == 3           # no cursor move became a delta
    assert js["undo"] is True and js["after"] == {"step": 1, "staging": 1, "n": 3}
    assert js["redo"] is True and js["first"] is True
    assert js["atFirst"] == {"step": -1, "view": "resource", "staging": 0}
    assert js["last"] is True and js["step"] == 2 and js["noop"] is False


def test_a_tick_tap_rewinds_to_the_entry_of_that_view_this_round():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { renderStrip } from "./strip.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "advance", ""); perform(g, ui, "stg+", ""); perform(g, ui, "stg+", "");
const before = renderStrip(g, ui);
const moved = perform(g, ui, "rw_tick", "planning");
const inert = perform(g, ui, "rw_tick", "combat_shadow");
console.log(JSON.stringify({ moved, inert, step: g.replay_step, staging: g.staging, view: g.view,
  planningIsButton: /data-act="rw_tick" data-arg="planning"/.test(before),
  futureIsNotButton: !/data-act="rw_tick" data-arg="combat_shadow"/.test(before),
  // Three taps in: canUndo() is true (rw_first/rw_undo are live buttons) and
  // canRedo() is false (rw_redo/rw_last are inert .is-off spans with no
  // data-act - transportButton()'s off case, same "not a tap target at all"
  // shape as pane.js's allocStep()) - so this checks the transport rendered
  // all four controls, on or off, rather than asserting a data-act that the
  // two at-the-end ones correctly do not have.
  transport: (before.match(/class="tbtn/g) || []).length === 4,
  readout: /Step 3\\/3/.test(before) }));
""")
    assert js["moved"] is True and js["inert"] is False
    assert js == {**js, "step": 0, "staging": 0, "view": "planning"}
    assert js["planningIsButton"] and js["futureIsNotButton"] and js["transport"] and js["readout"]


def test_round_granularity_transport_crosses_a_round_boundary():
    """rw_round_back / rw_round_fwd move the cursor a WHOLE round, not a tap:
    the two acts that the strip's four-button transport does not expose but
    the Game Log's six-control one does. Two rounds are driven under the
    bands window policy (the client's own, app.js), with taps on both sides
    of the boundary so a whole-round move has somewhere to land."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", "");
perform(g, ui, "advance", "");
perform(g, ui, "endround", "");          // round 1 -> 2
perform(g, ui, "stg+", "");
const atEnd = { round: g.round, step: g.replay_step };
const back = perform(g, ui, "rw_round_back", "");
const afterBack = { round: g.round, step: g.replay_step };
const fwd = perform(g, ui, "rw_round_fwd", "");
const afterFwd = { round: g.round, step: g.replay_step };
while (perform(g, ui, "rw_round_fwd", ""));   // run the cursor to the end
const noMore = perform(g, ui, "rw_round_fwd", "");
console.log(JSON.stringify({ atEnd, back, afterBack, fwd, afterFwd, noMore,
  step: g.replay_step, n: g.deltas.length, staging: g.staging }));
""")
    assert js["atEnd"]["round"] == 2
    assert js["back"] is True
    assert js["afterBack"]["round"] == 1, "one round back lands in round 1"
    assert js["afterBack"]["step"] < js["atEnd"]["step"]
    # Forward-by-round lands on the FIRST delta of round 2, not the last one:
    # applyDeltasUntilRoundChange stops at the change, it does not run the
    # round out. Round 2 is back, the cursor is ahead of where the back-step
    # left it, and a second forward move finds no further boundary.
    assert js["fwd"] is True and js["afterFwd"]["round"] == 2
    assert js["afterBack"]["step"] < js["afterFwd"]["step"] <= js["atEnd"]["step"]
    assert js["noMore"] is False, "at the last delta - nowhere forward to go"
    assert js["step"] == js["atEnd"]["step"] and js["staging"] == 2


# --- The Game Log screen (milestone 4, Task 3) -------------------------------
# Every one of these drives the MODEL and reads its real log strings back,
# rather than asserting against a fixture: the filters are text predicates
# (logfilter.js's own comment), so a reworded log line has to fail here.
#
# WINDOW_POLICY_BANDS is this client's own policy (app.js sets it at boot) and
# these three need it for the same reason the sibling transport tests do: the
# default policy walks the aw_ window views, and a window is deliberately not
# logged as a phase - "advance" out of `resource` would land on aw_resource
# and write no "Phase:" line at all.
def test_log_filters_sort_real_log_lines():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { matches } from "./logfilter.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "advance", "");                    // Phase: Planning? (phase change logs)
perform(g, ui, "stg+", "");                       // Staging area threat 1
perform(g, ui, "all_thr", "1");                   // All players threat +1
g.setWillpower(4); g.setStaging(0);
const before = g.log.filter(e => matches("skips", e)).map(e => e.text);
// A real skip, taken the way a player takes one: the encounter step is where
// skipsFrom() offers "No enemies. Skip combat." under the bands policy, and
// acts_play.js's `skip` act is what the offer's button carries.
g.view = "enc_checks";
const offer = g.skipOffer();
const took = perform(g, ui, "skip", offer.skip.id);
const byFilter = {};
for (const f of ["all","threat","quest","phases","skips"]) byFilter[f] = g.log.filter(e => matches(f, e)).map(e => e.text);
console.log(JSON.stringify({ ...byFilter, before, took, offered: offer.skip.id, view: g.view }));
""")
    assert any(t.startswith("All players threat") for t in js["threat"])
    assert any(t.startswith("Staging area threat") for t in js["threat"])
    assert all(t.startswith("Phase:") for t in js["phases"]) and js["phases"]
    assert js["before"] == [], "nothing was skipped before the skip"
    assert js["took"] is True and js["offered"] == "combat_empty"
    assert len(js["skips"]) == 1 and js["skips"][0].startswith("Skipped ")
    assert js["skips"][0] in js["all"]
    assert len(js["all"]) >= len(js["threat"])


def test_log_screen_greys_undone_rows_selects_and_rewinds():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { newUi, perform, afterTap } from "./actions.js";
import { layout } from "./layout.js";
import { renderRail } from "./rail.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "stg+", ""); perform(g, ui, "advance", "");
const rail = renderRail(g, ui);
perform(g, ui, "open_log", "");
const opened = layout(g, ui);
perform(g, ui, "rw_undo", ""); perform(g, ui, "rw_undo", "");
const afterUndo = layout(g, ui);
// The two stepper taps are ONE row, and it belongs to the second of them
// (gamestate.js restamps a coalesced row - milestone 4 fix wave, F1), so
// rewinding to it lands on the staging value the row actually states.
const target = g.log.find(e => e.text === "Staging area threat 2");
perform(g, ui, "log_sel", String(target.seq));
const selected = layout(g, ui);
const rewound = perform(g, ui, "log_rewind", "");
perform(g, ui, "log_close", "");
console.log(JSON.stringify({
  openChip: /data-act="open_log"/.test(rail),
  isLogScreen: /class="logscreen"/.test(opened) && !/class="strip"/.test(opened),
  filters: ["all","threat","quest","phases","skips"].every(f => opened.includes(`data-arg="${f}"`)),
  transport6: (opened.match(/class="tbtn/g) || []).length,
  // Available controls are <button>s with an act; unavailable ones are the
  // inert span the strip uses - same off state on both surfaces (C2).
  transportOn: ["rw_first","rw_round_back","rw_undo"].every(a => opened.includes(`data-act="${a}"`)),
  transportOffActs: ["rw_redo","rw_round_fwd","rw_last"].some(a => opened.includes(`data-act="${a}"`)),
  transportOffSpans: (opened.match(/<span class="tbtn is-off"/g) || []).length,
  transportDisabled: /disabled/.test(opened),
  undoneCount: (afterUndo.match(/is-undone/g) || []).length,
  rewindOff: /class="cta[^"]*is-off[^"]*"[^>]*data-act="log_rewind"/.test(afterUndo) || !/data-act="log_rewind"/.test(afterUndo),
  rewindOn: /data-act="log_rewind"/.test(selected) && /is-sel/.test(selected),
  rewound, step: g.replay_step, staging: g.staging, screen: ui.screen,
  sidePanel: /class="log-side"/.test(opened), export: /data-act="export_log"/.test(opened),
}));
""")
    assert js["openChip"] and js["isLogScreen"] and js["filters"]
    # Six controls, always: three live (the cursor is at the end of history,
    # so only the backward half has anywhere to go) and three inert spans
    # carrying no act at all.
    assert js["transport6"] == 6
    assert js["transportOn"] and js["transportOffActs"] is False
    assert js["transportOffSpans"] == 3 and js["transportDisabled"] is False
    assert js["undoneCount"] >= 1                     # the advance's row(s) greyed after the undos
    assert js["rewindOff"] and js["rewindOn"]
    assert js["rewound"] is True and js["step"] == 1 and js["staging"] == 2
    assert js["screen"] == "play" and js["sidePanel"] and js["export"]


def test_export_sheet_carries_the_log_as_plain_text():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { layout } from "./layout.js";
import { logText } from "./logfilter.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "open_log", ""); perform(g, ui, "export_log", "");
const html = layout(g, ui);
console.log(JSON.stringify({ text: logText(g), hasTextarea: /<textarea[^>]*readonly/.test(html),
  hasCopy: /data-act="copy_log"/.test(html), inHtml: html.includes("Staging area threat 1") }));
""")
    assert "Staging area threat 1" in js["text"] and js["text"].startswith("R1.")
    assert js["hasTextarea"] and js["hasCopy"] and js["inHtml"]


def test_a_filter_that_matches_nothing_says_so():
    """An empty filtered list and a broken screen look identical - one
    sentence tells them apart. Driven with the Skips filter on a game that
    never skipped anything, which is the reachable case (the transport, the
    filter row and the side panel all still render)."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { layout } from "./layout.js";
import { CHROME } from "./copy.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "open_log", "");
const all = layout(g, ui);
const changed = perform(g, ui, "log_filter", "skips");
const empty = layout(g, ui);
console.log(JSON.stringify({
  changed, copy: CHROME.logEmptyFilter,
  allHasRows: /data-act="log_sel"/.test(all), allHasCopy: all.includes(CHROME.logEmptyFilter),
  emptyHasRows: /data-act="log_sel"/.test(empty), emptyHasCopy: empty.includes(CHROME.logEmptyFilter),
  emptySentence: /<p class="body secondary">No lines match this filter\\.<\\/p>/.test(empty),
  stillHasTransport: /class="transport"/.test(empty) && /class="log-side"/.test(empty),
}));
""")
    assert js["changed"] is True and js["copy"] == "No lines match this filter."
    assert js["allHasRows"] and not js["allHasCopy"]
    assert not js["emptyHasRows"] and js["emptyHasCopy"] and js["emptySentence"]
    assert js["stillHasTransport"]


def test_log_filter_through_dispatch_validates_its_arg_and_resets_the_selection():
    """The act, not the renderer: a valid filter changes ui.log.filter and
    drops the selection (a row chosen under All may not be on screen under
    Phases); the same filter again is a no-op, so app.js does not re-render or
    journal one; an arg that is not in FILTERS changes nothing at all."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "open_log", "");
const row = g.log.find(e => typeof e.delta_i === "number");
perform(g, ui, "log_sel", String(row.seq));
const selBefore = ui.log.sel;
const first = perform(g, ui, "log_filter", "phases");
const after = { ...ui.log };
const again = perform(g, ui, "log_filter", "phases");
const bogus = perform(g, ui, "log_filter", "nonsense");
console.log(JSON.stringify({ selBefore, first, after, again, bogus, end: { ...ui.log } }));
""")
    assert js["selBefore"] is not None
    assert js["first"] is True and js["after"] == {"filter": "phases", "sel": None}
    assert js["again"] is False, "the filter is already this one - nothing changed"
    assert js["bogus"] is False and js["end"] == {"filter": "phases", "sel": None}


def test_the_export_textarea_escapes_each_character_exactly_once():
    """The export sheet interpolates logText() into a <textarea> through h``,
    which escapes it once - and only once. A second pass (a nested h`` landing
    in an outer template as a plain string, the bug test_no_nested_h_without_
    raw scans for) would ship "&amp;gt;" and the player would copy that."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { layout } from "./layout.js";
import { logText } from "./logfilter.js";
const g = new GameState(2); g.view = "travel"; const ui = newUi();
// A location name a player typed, then a change: "Changed active location
// (Web & <Spiders> at 0/2 discarded) -> Deep Marsh (3 quest points)" carries
// all three characters in one real log line.
let s = g.beginAction(); g.travelTo(2, 0, "Web & <Spiders>"); g.addDelta(s);
s = g.beginAction(); g.changeLocation(3, 0, "Deep Marsh"); g.addDelta(s);
perform(g, ui, "open_log", ""); perform(g, ui, "export_log", "");
const html = layout(g, ui);
const area = html.match(/<textarea[^>]*>([\\s\\S]*?)<\\/textarea>/)[1];
console.log(JSON.stringify({
  plain: logText(g).includes("(Web & <Spiders> at 0/2 discarded) -> Deep Marsh"),
  area, ok: area.includes("(Web &amp; &lt;Spiders&gt; at 0/2 discarded) -&gt; Deep Marsh"),
  doubled: /&amp;(gt|lt|amp);/.test(area),
}));
""")
    assert js["plain"], "the model wrote the line the export is meant to carry"
    assert js["ok"], js["area"]
    assert js["doubled"] is False, "escaped twice: " + js["area"]


def test_log_rewind_with_no_selection_does_nothing():
    """The CTA is only live while a rewindable row is selected, so this is the
    act's own guard rather than a reachable tap - but "returns false" is what
    keeps app.js from re-rendering and Session.record()ing a no-op, and what
    keeps a stale ui.log.sel (a row a truncation dropped) from moving the
    cursor somewhere arbitrary."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "open_log", "");
const noSel = perform(g, ui, "log_rewind", "");
ui.log.sel = 9999;                                   // a row that is not in the log
const staleSel = perform(g, ui, "log_rewind", "");
console.log(JSON.stringify({ noSel, staleSel, step: g.replay_step, staging: g.staging }));
""")
    assert js["noSel"] is False and js["staleSel"] is False
    assert js["step"] == 0 and js["staging"] == 1     # the cursor never moved


def test_log_rewind_goes_through_the_one_cursor_path():
    """rewindToIndex() (acts_transport.js) is the single code path for a
    cursor move to a known index, so log_rewind inherits the ui reset every
    other transport act does: a rewind past the point where progress was
    allocated must not leave ui.alloc describing a state that no longer
    exists. The export sheet is the deliberate exception - the cursor moving
    under it is what its transport is for."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "advance", "");
perform(g, ui, "open_log", "");
perform(g, ui, "export_log", "");
ui.alloc = { quest: 3, side: {} }; ui.placed = true;
const target = g.log.find(e => e.delta_i === 0);
const moved = perform(g, ui, "log_sel", String(target.seq)) && perform(g, ui, "log_rewind", "");
console.log(JSON.stringify({ moved, alloc: ui.alloc, placed: ui.placed,
  sheet: ui.sheet && ui.sheet.kind, step: g.replay_step, staging: g.staging }));
""")
    assert js["moved"] is True and js["step"] == 0 and js["staging"] == 1
    assert js["alloc"] is None and js["placed"] is False
    assert js["sheet"] == "export", "a cursor move on the log screen leaves its own sheet up"


# -- The Rules modal (Task 3, milestone 5) -----------------------------------

def test_rules_sections_map_covers_every_flow_view():
    """sectionsFor() (rules_map.js) is the pane's own Rules Reference lookup -
    every phase view the tablet can land on (flowViews() under the bands
    policy, since bands is the only policy this client runs) must resolve to
    at least one section id, except quest_setup/quest_sailing: neither has a
    Rules Reference section of its own (stage-1A setup text and the sailing
    test are this tracker's own affordances, not numbered book steps) - the
    interfaces note both are chip-less for exactly that reason. flowViews()
    under WINDOW_POLICY_BANDS never actually returns either one (they are not
    in VIEW_ORDER at all), so the filter below is defensive documentation,
    not a functional exclusion - see gamestate.js's own VIEW_ORDER."""
    js = node("""
import { setWindowPolicy, WINDOW_POLICY_BANDS, flowViews } from "../../js/gamestate.js";
import { sectionsFor } from "./rules_map.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const views = flowViews().filter(v => v !== "quest_setup" && v !== "quest_sailing");
console.log(JSON.stringify({
  views,
  covered: views.every(v => sectionsFor(v).length > 0),
  excluded: { quest_setup: sectionsFor("quest_setup"), quest_sailing: sectionsFor("quest_sailing") },
}));
""")
    assert len(js["views"]) > 0
    assert js["covered"], "every flow view except quest_setup/quest_sailing needs a section id: %r" % js["views"]
    assert js["excluded"] == {"quest_setup": [], "quest_sailing": []}


def test_resource_pane_bands_carry_the_rules_chips_from_the_map():
    """pane.js wires each of resource's two direct band() calls to
    sectionsFor("resource")'s own ids in order - the framework band
    (PHASE_FRAMEWORK.resource, "1.1 Beginning of the Resource phase") and the
    window band (ACTION_WINDOW_TIPS.resource[0], "1.2-1.3 Gain resources and
    draw cards") - rather than a hand-typed id that could drift from
    rules_map.js's own VIEW_SECTIONS."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2); g.view = "resource";
const html = renderPane(g, { alloc: null, placed: false });
console.log(JSON.stringify({
  html,
  chips: [...html.matchAll(/data-act="open_rules" data-arg="([^"]*)"/g)].map(m => m[1]),
}));
""")
    assert js["chips"] == ["1.1", "1.2"], js["html"]


def test_rules_sheet_renders_fixture_text_verbatim_with_prev_next_chips():
    """A fixture ui.rules (placeholder prose - never real rulebook text, per
    CLAUDE.md's data policy on verbatim third-party content) stands in for a
    built rules_text.json. The Official text block must show the fixture's
    own paragraphs unchanged, the header must name the section, and the
    Related row's prev/next chips must be rules_map.js's own STEP_ORDER
    neighbours of "6.2" (combat_shadow's "6.1", then combat_enemy's "6.3") -
    not anything hand-picked."""
    js = node("""
import { renderRulesSheet } from "./sheet_rules.js";
const fixture = {
  sections: {
    "6.2": { ids: ["6.2"], title: "Deal shadow cards",
      text: "Fixture paragraph one.\\n\\nFixture paragraph two.", see_also: ["Shadow Effect"] },
  },
  glossary: {}, faq: [],
  source: { page: "https://example.test/rules", sha256: "abc", pin: "def" },
};
const ui = { sheet: { kind: "rules", section: "6.2" }, rules: fixture };
const html = renderRulesSheet({}, ui);
console.log(JSON.stringify({
  html,
  hasHeader: html.includes("§6.2"),
  hasBodyText: html.includes('<p class="body">Fixture paragraph one.</p>')
    && html.includes('<p class="body">Fixture paragraph two.</p>'),
  chips: [...html.matchAll(/data-act="open_rules" data-arg="([^"]*)"/g)].map(m => m[1]),
}));
""")
    assert js["hasHeader"], js["html"]
    assert js["hasBodyText"], js["html"]
    assert "6.1" in js["chips"] and "6.3" in js["chips"], js["chips"]


def test_rules_sheet_degrades_when_rules_text_is_unavailable():
    """ui.rules null (no rules_text.json this build - db.rulesText()'s own
    "PROPAGATES on failure... returns null" contract) degrades the Official
    text block to CHROME.rulesUnavailable rather than a blank sheet or a
    crash (CLAUDE.md iron rule 4: no placeholder rules text ships). The
    footer's Open-the-rulebook link still works, falling back to copy.js's
    pinned page URL since there is no ui.rules.source.page to prefer."""
    js = node("""
import { renderRulesSheet } from "./sheet_rules.js";
import { CHROME, rulesPageUrl } from "./copy.js";
const ui = { sheet: { kind: "rules", section: "6.2" }, rules: null };
const html = renderRulesSheet({}, ui);
console.log(JSON.stringify({
  html,
  unavailable: html.includes(CHROME.rulesUnavailable),
  hasLink: html.includes('href="' + rulesPageUrl + '"') && html.includes('target="_blank"'),
}));
""")
    assert js["unavailable"], js["html"]
    assert js["hasLink"], js["html"]


def test_elim_sheet_rules_chip_opens_glossary_then_returns_to_elim():
    """The elimination sheet's own "Rules · Player Elimination ›" chip opens
    the Rules modal on the glossary term, REPLACING the elim sheet - fine,
    because opening it never touches game.pending_elim, so afterTap()
    (actions.js) re-seats the elim sheet the instant sheet_close
    (acts_sheets.js) clears ui.sheet back to null. Same re-seat mechanism
    sheets.js's own elim-scrim comment documents for a scrim tap; this test
    covers reaching it via another sheet's own act instead."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 45); g.advanceView(); const ui = newUi();
ui.rules = { sections: {}, faq: [], glossary: {
  "Player Elimination": { title: "Player Elimination", text: "Fixture glossary text.", see_also: [] },
} };
perform(g, ui, "thr", "0:5"); afterTap(g, ui);            // P1: 45 -> 50, crosses
const openedElim = { kind: ui.sheet.kind, i: ui.sheet.i };
const opened = perform(g, ui, "open_rules", "term:Player Elimination");
afterTap(g, ui);
const rulesSheet = { kind: ui.sheet.kind, term: ui.sheet.term };
const glossaryShown = layout(g, ui).includes("Fixture glossary text.");
perform(g, ui, "sheet_close", "");
afterTap(g, ui);
console.log(JSON.stringify({
  openedElim, opened, rulesSheet, glossaryShown,
  afterClose: { kind: ui.sheet && ui.sheet.kind, i: ui.sheet && ui.sheet.i },
  pendingElim: g.pending_elim,
}));
""")
    assert js["openedElim"] == {"kind": "elim", "i": 0}
    assert js["opened"] is True
    assert js["rulesSheet"] == {"kind": "rules", "term": "Player Elimination"}
    assert js["glossaryShown"], "the fixture glossary text must render verbatim"
    assert js["afterClose"] == {"kind": "elim", "i": 0}, "the elim sheet must return, flag persisted"
    assert js["pendingElim"] == 0, "the elimination flag must survive the rules detour"
