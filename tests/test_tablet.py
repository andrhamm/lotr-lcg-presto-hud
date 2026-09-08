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
console.log(JSON.stringify({ segs: (html.match(/class="seg[" ]/g) || []).length,
  current: (html.match(/is-current/g) || []).length,
  currentView: /data-view="quest_staging"[^>]*is-current|is-current[^>]*data-view="quest_staging"/.test(html),
  // Scoped to the flow, not the whole strip: the legend's swatches reuse the
  // tick classes on purpose (a key has to be drawn in the same ink as the
  // thing it names), so counting them as ticks would be counting the key.
  windows: ((html.split('class="strip-flow"').pop()).match(/tick-window/g) || []).length,
  legend: [...html.matchAll(/class="legend-item"><i class="tick tick-(\\w+)[^>]*><\\/i>([^<]+)</g)]
    .map(m => [m[1], m[2]]),
  aw: html.includes("aw_"),
  planningWindow: /data-view="planning"[^>]*tick-window|tick-window[^>]*data-view="planning"/.test(html),
  round: html.includes(">1<") }));
""")
    assert js["segs"] == 8
    assert js["current"] == 1 and js["currentView"]
    assert js["windows"] == 11         # 8 aw_ windows + planning + the two combat windows
    # The legend NAMES the two marks. Without it the timeline is shapes a
    # player is expected to already understand, and the distinction it
    # encodes - what happens anyway, versus when you are allowed to act - is
    # the one this tracker exists to teach ("An action ability may only be
    # triggered during an action window", Rules Reference).
    assert js["legend"] == [["framework", "Framework"], ["window", "Action window"]]
    assert js["aw"] is False           # window views are ticks, never named
    assert js["planningWindow"]        # Planning's own tick IS the round's window tick
    assert js["round"]


def test_strip_marks_the_combat_segment_skippable_when_the_offer_is_promoted():
    js = node(r"""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("enc_checks");
const a = renderStrip(g, newUi());
g.setEngaged(0, 1);
const b = renderStrip(g, newUi());
console.log(JSON.stringify({ promoted: /data-phase="Combat"[^>]*is-skippable/.test(a),
  demoted: /data-phase="Combat"[^>]*is-skippable/.test(b),
  tag: /data-phase="Combat"[\s\S]*?<span class="skip-note label">Skip</.test(a),
  noStepId: !a.includes(">6.P<") }));
""")
    assert js["promoted"] and js["tag"]
    assert js["demoted"] is False
    # The tag says "Skip", not the landing's internal step id: "6.P" is not a
    # thing a player has ever seen, and it used to sit on top of the phase
    # name of the very segment it was labelling.
    assert js["noStepId"]


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
    js = node(r"""
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
  encounterTag: /data-phase="Encounter"[\s\S]*?<span class="skip-note label">Skip</.test(html),
}));
""")
    # The whole segment lighting up IS the proof that the off-flow landing
    # resolved: an unmapped aw_ id sinks the range check and nothing lights.
    assert js["encounterSkippable"]
    assert js["encounterTag"]
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


# The tablet-density picker fixture (Task 2, milestone 6): two sources
# (official/alep) x two cycles each x two scenarios each, plus one
# "- Nightmare"-named row and one zero-stage row planted in the official
# C1 cycle - groupByCycle/cyclesFor (quest_catalog.js) must drop both from
# every rendered group, the same filtering the twin's own picker screens
# already rely on (kind=="nightmare", stageCount<=0, the name suffix, and
# source itself). Cycle names are not in CYCLE_ORDER, so they sort by
# first-seen order in the array - C1/A1 come first in each source.
NG_FIXTURE = """
const index = { scenarios: [
  { slug: "o1a", name: "Official 1A", pack: "P", cycle: "C1", kind: "quest", source: "official", order: 1, stageCount: 2, releaseDate: "2011-01" },
  { slug: "o1b", name: "Official 1B", pack: "P", cycle: "C1", kind: "quest", source: "official", order: 2, stageCount: 3, releaseDate: "2011-02" },
  { slug: "o1nm", name: "Official 1A - Nightmare", pack: "P", cycle: "C1", kind: "quest", source: "official", order: 3, stageCount: 3, releaseDate: "2011-03" },
  { slug: "o1z", name: "Official 1 Zero", pack: "P", cycle: "C1", kind: "quest", source: "official", order: 4, stageCount: 0, releaseDate: "2011-04" },
  { slug: "o2a", name: "Official 2A", pack: "P", cycle: "C2", kind: "quest", source: "official", order: 1, stageCount: 2, releaseDate: "2013-01" },
  { slug: "o2b", name: "Official 2B", pack: "P", cycle: "C2", kind: "quest", source: "official", order: 2, stageCount: 3, releaseDate: "2013-02" },
  { slug: "a1a", name: "Community 1A", pack: "Q", cycle: "A1", kind: "quest", source: "alep", order: 1, stageCount: 2, releaseDate: "2021-01" },
  { slug: "a1b", name: "Community 1B", pack: "Q", cycle: "A1", kind: "quest", source: "alep", order: 2, stageCount: 3, releaseDate: "2021-02" },
  { slug: "a2a", name: "Community 2A", pack: "Q", cycle: "A2", kind: "quest", source: "alep", order: 1, stageCount: 2, releaseDate: "2022-01" },
  { slug: "a2b", name: "Community 2B", pack: "Q", cycle: "A2", kind: "quest", source: "alep", order: 2, stageCount: 3, releaseDate: "2022-02" },
] };
"""


def test_new_game_chooser_opens_on_the_cycle_list_for_the_official_source():
    """renderNewGame(game, ui) is master/detail (M7): a DRILL-IN list on the
    left, the chosen scenario's own detail on the right. The list opens on
    the cycles - grouped by quest_catalog.js's own cyclesFor rather than a
    second copy of that filtering - and shows no scenario rows at all until
    one is entered. The community cycles stay out of the official list."""
    js = node(NG_FIXTURE + """
import { renderNewGame } from "./newgame.js";
const html = renderNewGame(null, { picker: { index, drill: "cycles" } });
const officialChip = /<button[^>]*data-act="ng_source" data-arg="official"[^>]*>/.exec(html)[0];
const communityChip = /<button[^>]*data-act="ng_source" data-arg="alep"[^>]*>/.exec(html)[0];
console.log(JSON.stringify({
  officialGold: officialChip.includes("chip-gold"),
  communityTan: communityChip.includes("chip-tan"),
  hasC1: html.includes('data-arg="C1"'), hasC2: html.includes('data-arg="C2"'),
  hasA1: html.includes('data-arg="A1"'),
  anyScenarioRow: html.includes('data-act="pick_scenario"'),
  hasEmptyState: html.includes("detail-empty"),
}));
""")
    assert js["officialGold"] and js["communityTan"]
    assert js["hasC1"] and js["hasC2"]   # both official cycles are listed...
    assert not js["hasA1"]                # ...and no community one
    assert not js["anyScenarioRow"]       # nothing drilled into yet
    assert js["hasEmptyState"]            # so the detail side says what to do


def test_new_game_chooser_ng_source_resets_the_drill_and_the_selection():
    """ng_source (acts_newgame.js) is ui-only and dispatch()-routed:
    switching source resets ui.picker.cycle to THAT source's own first
    cycle, since the two catalogs never share a cycle name - and with M7
    also resets the drill to the cycle list and drops the selected slug,
    which belongs to a quest the new list does not contain."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { renderNewGame } from "./newgame.js";
const g = new GameState();
const ui = { picker: { index, source: "official", cycle: "C1", drill: "scenarios", slug: "o1a" } };
const changed = dispatch(g, ui, "ng_source", "alep");
const entered = dispatch(g, ui, "ng_cycle", "A1");
const html = renderNewGame(g, ui);
console.log(JSON.stringify({
  changed, entered, source: ui.picker.source, cycle: ui.picker.cycle,
  drillReset: ui.picker.drill, slug: ui.picker.slug,
  hasA1a: html.includes('data-arg="a1a"'), hasA1b: html.includes('data-arg="a1b"'),
  hasO1a: html.includes('data-arg="o1a"'),
}));
""")
    assert js["changed"] is True and js["entered"] is True
    assert js["source"] == "alep" and js["cycle"] == "A1"
    # The reset lands before the re-entry, so what it wrote is observable in
    # ui.picker.slug alone; ui.picker.drill is back at "scenarios" by now.
    assert js["slug"] is None
    assert js["hasA1a"] and js["hasA1b"]
    assert not js["hasO1a"]


def test_new_game_chooser_ng_cycle_drills_in_and_ng_cycles_comes_back_up():
    """The left column has two states and one act each way. Entering a cycle
    lists ITS quests and only those - never the sibling cycle's, never the
    other source's, and never the "- Nightmare" row or the zero-stage row
    planted alongside them (groupByCycle's own exclusions). Coming back up
    puts the cycles back."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { renderNewGame } from "./newgame.js";
const g = new GameState();
const ui = { picker: { index, source: "official", cycle: "C1", drill: "cycles" } };
const entered = dispatch(g, ui, "ng_cycle", "C1");
const inC1 = renderNewGame(g, ui);
const switched = dispatch(g, ui, "ng_cycle", "C2");
const inC2 = renderNewGame(g, ui);
const up = dispatch(g, ui, "ng_cycles", "");
const upNoop = dispatch(g, ui, "ng_cycles", "");
const atTop = renderNewGame(g, ui);
console.log(JSON.stringify({
  entered, switched, up, upNoop, drill: ui.picker.drill,
  c1HasO1a: inC1.includes('data-arg="o1a"'), c1HasO1b: inC1.includes('data-arg="o1b"'),
  c1HasO1nm: inC1.includes('data-arg="o1nm"'), c1HasO1z: inC1.includes('data-arg="o1z"'),
  c1HasO2a: inC1.includes('data-arg="o2a"'), c1HasA1a: inC1.includes('data-arg="a1a"'),
  c2HasO2a: inC2.includes('data-arg="o2a"'), c2HasO1a: inC2.includes('data-arg="o1a"'),
  backUpHasCycles: atTop.includes('data-act="ng_cycle"'),
  backUpHasScenarios: atTop.includes('data-act="pick_scenario"'),
}));
""")
    assert js["entered"] is True and js["switched"] is True
    assert js["up"] is True and js["upNoop"] is False   # already at the top
    assert js["drill"] == "cycles"
    assert js["c1HasO1a"] and js["c1HasO1b"]
    assert not js["c1HasO1nm"] and not js["c1HasO1z"]
    assert not js["c1HasO2a"] and not js["c1HasA1a"]
    assert js["c2HasO2a"] and not js["c2HasO1a"]
    assert js["backUpHasCycles"] and not js["backUpHasScenarios"]


def test_new_game_chooser_continue_appears_only_once_a_quest_is_picked():
    """The Continue CTA is gated on ui.picker.slug, and the detail beside it
    is gated on ui.overview being the seat for THAT slug: ui.overview
    survives a game (boot seats it read-only for a resumed save), so
    rendering it on the strength of its mere existence would show the last
    game's quest under a fresh picker."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { overviewFor } from "./overview.js";
import { renderNewGame } from "./newgame.js";
const g = new GameState();
const bundle = { stages: [{ id: 1 }], locations: [], tips: null };
const base = { index, source: "official", cycle: "C1", drill: "scenarios" };
const noPick = renderNewGame(g, { picker: { ...base } });
// A stale seat from an earlier game, with nothing picked in THIS picker.
const stale = renderNewGame(g, { picker: { ...base }, overview: overviewFor(index, "o1b", bundle) });
const picked = renderNewGame(g, { picker: { ...base, slug: "o1a" },
                                  overview: overviewFor(index, "o1a", bundle) });
const ui = { screen: "newgame", picker: { ...base, slug: "o1a" } };
const wentOn = dispatch(g, ui, "go_players", "");
const blocked = dispatch(g, { screen: "newgame", picker: { ...base, slug: null } }, "go_players", "");
console.log(JSON.stringify({
  noPickCta: noPick.includes('data-act="go_players"'),
  staleCta: stale.includes('data-act="go_players"'),
  // The LIST names every quest in the cycle either way - what must not
  // appear is the stale seat's DETAIL, so this looks for the detail grid,
  // not for the name.
  staleShowsOther: stale.includes("ov-grid"),
  staleEmpty: stale.includes("detail-empty"),
  pickedCta: picked.includes('data-act="go_players"'),
  pickedTitle: picked.includes(">Official 1A<"),
  pickedSelectedRow: /data-act="pick_scenario" data-arg="o1a"/.test(picked)
    && /class="[^"]*is-selected[^"]*"[^>]*data-arg="o1a"/.test(picked),
  wentOn, screen: ui.screen, blocked,
}));
""")
    assert not js["noPickCta"]
    assert not js["staleCta"] and not js["staleShowsOther"] and js["staleEmpty"]
    assert js["pickedCta"] and js["pickedTitle"] and js["pickedSelectedRow"]
    assert js["wentOn"] is True and js["screen"] == "players"
    assert js["blocked"] is False


def test_new_game_picker_players_and_threat_acts_still_work_through_dispatch():
    """ng_players/ng_threat± moved verbatim out of app.js's own hand-rolled
    `if` chain into acts_newgame.js (Task 2) - same behaviour, now reached
    through the shared dispatch() table instead of a bespoke check."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
const g = new GameState();
const ui = { picker: { index: { scenarios: [] }, players: 2, threats: [25, 25], source: "official", cycle: null } };
const playersChanged = dispatch(g, ui, "ng_players", "3");
const threatChanged = dispatch(g, ui, "ng_threat+", "0");
console.log(JSON.stringify({
  playersChanged, threatChanged,
  players: ui.picker.players, threats: ui.picker.threats,
}));
""")
    assert js["playersChanged"] is True and js["threatChanged"] is True
    assert js["players"] == 3
    assert js["threats"] == [26, 25, 25]


def test_every_card_with_art_opens_the_quick_view_and_two_sided_cards_flip():
    """A 96px thumbnail is an identifier, not something you can read, so every
    card the client draws opens a quick view of the printed card - which is
    the authority for what it does (iron rule 4), so this shows it rather than
    describing it.

    The face image FILENAMES ride in the element's dataset: 198 catalog
    encounter cards carry two DIFFERENT ones ("<id>.jpg" and "<id>.B.jpg"), so
    the flip is real rather than a control that shows one picture twice, and a
    one-sided card is offered no flip at all. app.js reads them off the tapped
    element, so the modal needs no card index and the renderers stay pure."""
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { cardImage, faceFiles } from "./cardimage.js";
import { renderCardSheet } from "./sheet_card.js";
const prefix = "https://art.example.invalid/";
const twoSided = { id: "x", image: "x.jpg", name: "The Watcher",
  faces: [{ image: "x.jpg" }, { image: "x.B.jpg" }] };
const oneSided = { id: "y", image: "y.jpg", name: "Forest Spider", faces: [{ image: "y.jpg" }] };
const noArt = { name: "Hand-typed" };
const g = new GameState();
// The seat holds every card on the screen behind it, in the order the screen
// shows them, plus which one is open.
const ui = { imagePrefix: prefix, sheet: { kind: "card", at: 0, face: 0, cards: [
  { name: "The Watcher", files: ["x.jpg", "x.B.jpg"], facts: [["quantity", "1"]] },
  { name: "Forest Spider", files: ["y.jpg"], facts: [] },
] } };
const front = renderCardSheet(g, ui);
const flipped = dispatch(g, ui, "card_flip", "");
const back = renderCardSheet(g, ui);
const wrapped = dispatch(g, ui, "card_flip", "");   // wraps, never clamps
const oneUi = { imagePrefix: prefix, sheet: { kind: "card", at: 0, face: 0,
  cards: [{ name: "Forest Spider", files: ["y.jpg"], facts: [] }] } };
console.log(JSON.stringify({
  twoFiles: faceFiles(twoSided), oneFile: faceFiles(oneSided), noFiles: faceFiles(noArt),
  twoMarkup: cardImage({ prefix, ...twoSided }),
  noArtMarkup: cardImage({ prefix, ...noArt }),
  frontSrc: /class="cardview-art" src="([^"]+)"/.exec(front)?.[1],
  backSrc: /class="cardview-art" src="([^"]+)"/.exec(back)?.[1],
  flipped, wrapped, faceAfterWrap: ui.sheet.face,
  twoHasFlip: front.includes('data-act="card_flip"'),
  oneHasFlip: renderCardSheet(g, oneUi).includes('data-act="card_flip"'),
  // The pager: only where there is somewhere to page to, and it wraps.
  twoHasPager: front.includes('data-act="card_next"'),
  onePagerless: !renderCardSheet(g, oneUi).includes('data-act="card_next"'),
  position: /class="label">(\\d+ \\/ \\d+)</.exec(front)?.[1],
  paged: dispatch(g, ui, "card_next", ""),
  atAfterNext: ui.sheet.at,
  nameAfterNext: /<h1 class="display">([^<]*)</.exec(renderCardSheet(g, ui))?.[1],
  faceResetOnPage: ui.sheet.face,
  wrappedRound: (() => { dispatch(g, ui, "card_next", ""); return ui.sheet.at; })(),
}));
""")
    assert js["twoFiles"] == ["x.jpg", "x.B.jpg"]
    assert js["oneFile"] == ["y.jpg"]
    assert js["noFiles"] == []
    # The card is a button carrying its own faces...
    assert 'data-act="open_card"' in js["twoMarkup"]
    assert 'data-files="x.jpg,x.B.jpg"' in js["twoMarkup"]
    # ...and a card with no art is inert: nothing to enlarge.
    assert 'data-act="open_card"' not in js["noArtMarkup"]
    assert "<figure" in js["noArtMarkup"]
    # The flip really changes the picture, and wraps back round.
    assert js["frontSrc"].endswith("x.jpg") and js["backSrc"].endswith("x.B.jpg")
    assert js["flipped"] is True and js["wrapped"] is True
    assert js["faceAfterWrap"] == 0
    # Offered only where there is a second side to see.
    assert js["twoHasFlip"] and not js["oneHasFlip"]
    # The pager exists only with somewhere to go, says where you are, wraps,
    # and resets the face - "which side am I on" belongs to the card you were
    # looking at, not the next one.
    assert js["twoHasPager"] and js["onePagerless"]
    assert js["position"] == "1 / 2"
    assert js["paged"] is True and js["atAfterNext"] == 1
    assert js["nameAfterNext"] == "Forest Spider"
    assert js["faceResetOnPage"] == 0
    assert js["wrappedRound"] == 0


def test_retapping_what_is_already_selected_changes_nothing():
    """render() replaces the whole DOM, so a re-render tears down and
    re-resolves every icon and card <img> - the flash you get from tapping the
    row that is already selected. The acts that could do that now return false
    for a no-op, which is what stops app.js re-rendering at all."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
const g = new GameState();
const ui = { screen: "newgame",
  picker: { index, source: "official", cycle: "C1", drill: "scenarios", slug: "o1a", stage: "2" } };
console.log(JSON.stringify({
  sameCycle: dispatch(g, ui, "ng_cycle", "C1"),      // already inside it
  otherCycle: dispatch(g, ui, "ng_cycle", "C2"),     // a real move
  sameStage: dispatch(g, { ...ui, picker: { ...ui.picker, stage: "2" } }, "ng_stage", "2"),
  otherStage: dispatch(g, { ...ui, picker: { ...ui.picker, stage: "2" } }, "ng_stage", "1"),
  sameSource: dispatch(g, ui, "ng_source", "official"),
}));
""")
    assert js["sameCycle"] is False and js["otherCycle"] is True
    assert js["sameStage"] is False and js["otherStage"] is True
    assert js["sameSource"] is False


def test_clearing_the_cycle_clears_everything_downstream_of_it():
    """Deselecting the cycle used to leave the chosen scenario loaded under a
    list that no longer contained it: its stages still in the rail, its detail
    still in the pane, its name still in the app bar, and Continue still armed
    - a state you could start a game from with no visible selection anywhere.

    The cycle is the root of that chain, so clearing it clears the chain."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { overviewFor } from "./overview.js";
import { renderNewGame } from "./newgame.js";
const g = new GameState();
const bundle = { stages: [{ id: 1, stage: 1, cards: [{ faces: [] }] }], locations: [], tips: null };
const ui = { screen: "newgame", overview: overviewFor(index, "o1a", bundle),
  picker: { index, source: "official", cycle: "C1", drill: "scenarios",
            slug: "o1a", stage: "1" } };
const before = renderNewGame(g, ui);
const changed = dispatch(g, ui, "ng_cycles", "");
const after = renderNewGame(g, ui);
console.log(JSON.stringify({
  changed, slug: ui.picker.slug, stage: ui.picker.stage, drill: ui.picker.drill,
  beforeHadStages: before.includes("stage-list"),
  afterHasStages: after.includes("stage-list"),
  afterHasDetail: after.includes("ov-grid"),
  afterEmpty: after.includes("detail-empty"),
  afterContinueArmed: /class="[^"]*cta[^"]*"[^>]*data-act="go_players"/.test(after),
  afterContinueShown: after.includes("cta-ok"),
}));
""")
    assert js["changed"] is True
    assert js["beforeHadStages"]                  # it really was loaded...
    assert js["slug"] is None and js["stage"] == "overview"
    assert js["drill"] == "cycles"
    assert not js["afterHasStages"] and not js["afterHasDetail"]
    assert js["afterEmpty"]                       # ...and the pane says so
    # Continue is still VISIBLE, just inert - a control that vanishes cannot
    # tell you it exists.
    assert not js["afterContinueArmed"] and js["afterContinueShown"]


def test_an_icon_the_build_never_exported_is_never_requested():
    """The client derives an icon slug from a printed NAME, and plenty of
    names have no symbol in the pack - 8 of the catalog's 17 cycles are
    groupings this project invented rather than printed cycles, plus a long
    tail of encounter sets. It used to find that out by asking for the file
    and watching it 404, which paints the browser's own broken-image glyph for
    a frame before any handler can replace it.

    build_icons.py writes a manifest beside its SVG export, so the answer is
    known before the request: a slug that is not in it renders the placeholder
    directly and asks the network for nothing.

    Without the manifest (a build that never ran --svg-out - the device deploy
    does not, and has no use for SVGs) the behaviour is exactly what it was,
    so a missing manifest costs the flash back and nothing else."""
    js = node("""
import { setIcon, cycleIcon, iconSlugs } from "./seticon.js";
const have = new Set(["passage-through-mirkwood", "dwarrowdelf-cycle"]);
console.log(JSON.stringify({
  // Present: a real <img>, and no placeholder-only wrapper.
  present: setIcon("Passage Through Mirkwood", 36, have),
  // Absent: no <img> at all, so nothing 404s.
  absent: setIcon("Core Set (Mirkwood Paths)", 36, have),
  // A cycle resolves through its own "-cycle" chain against the same set.
  cyclePresent: cycleIcon("The Dwarrowdelf", 30, have),
  cycleAbsent: cycleIcon("Hobbit Saga", 30, have),
  // No manifest: ask, exactly as before.
  unknown: setIcon("Core Set (Mirkwood Paths)", 36, null),
  chain: iconSlugs("Crossings of Poros"),
}));
""")
    assert "<img" in js["present"] and "passage-through-mirkwood.svg" in js["present"]
    assert "<img" not in js["absent"] and "is-missing" in js["absent"]
    assert "<img" in js["cyclePresent"] and "dwarrowdelf-cycle.svg" in js["cyclePresent"]
    assert "<img" not in js["cycleAbsent"] and "is-missing" in js["cycleAbsent"]
    # No manifest -> the previous optimistic behaviour, unchanged.
    assert "<img" in js["unknown"]
    # ...and the fallback chain itself is untouched by any of this.
    assert js["chain"][0] == "crossings-of-poros"
    assert "the-crossings-of-poros" in js["chain"]


def test_the_rail_never_nests_a_button_inside_a_button():
    """A <button> inside a <button> is invalid markup and iOS resolves it
    however it likes, so any row that carries its OWN control is a div with
    the act on it instead. app.js delegates on the closest [data-act], so the
    inner control takes its own taps and the rest of the row still selects.

    That is: cycle rows in the top-level list are plain buttons (nothing
    inside them to tap), while the chosen-cycle row and the scenario rows are
    divs - the first because of its ✕, the second because of the checkmark
    that locks the choice in."""
    js = node(NG_FIXTURE + r"""
import { renderNewGame } from "./newgame.js";
const cycles = renderNewGame(null, { picker: { index, drill: "cycles" } });
const scenarios = renderNewGame(null, { picker: { index, cycle: "C1", drill: "scenarios", slug: "o1a" } });
const all = cycles + scenarios;
// A button whose markup contains another <button> before its own close tag.
const nested = /<button\b[^>]*>(?:(?!<\/button>)[\s\S])*<button\b/.test(all);
console.log(JSON.stringify({
  nested,
  cycleRowsAreButtons: [...cycles.matchAll(/<(\w+)[^>]*class="[^"]*drill-row[^"]*"/g)]
    .map(m => m[1]),
  currentIsDiv: /<div[^>]*class="[^"]*drill-current/.test(scenarios),
  scenarioIsDiv: /<div[^>]*class="[^"]*drill-scenario/.test(scenarios),
  // The lock mark wears the SAME glyph treatment as the chosen cycle's ✕
  // (.drill-x) - one vocabulary for one kind of control in one column.
  markIsButton: /<button[^>]*class="drill-x"[^>]*data-act="ng_lock"/.test(scenarios),
  markSharesCycleGlyph: (scenarios.match(/class="drill-x"/g) || []).length >= 2,
  rowsStillAct: (scenarios.match(/data-act="pick_scenario"/g) || []).length,
}));
""")
    assert js["nested"] is False
    assert js["cycleRowsAreButtons"] and set(js["cycleRowsAreButtons"]) == {"button"}
    assert js["currentIsDiv"] and js["scenarioIsDiv"]
    assert js["markIsButton"] and js["markSharesCycleGlyph"]
    assert js["rowsStillAct"] >= 2


def test_stage_count_is_singular_for_one_stage_and_only_the_detail_prints_it():
    """copy.js's stagesCount ("%s stages") printed the ungrammatical "1
    stages" for the 8 catalog scenarios with exactly one stage. The one
    remaining render site - overview.js's header - picks stagesCountOne
    instead when the count is 1.

    The chooser's rows no longer print a count at all: it is metadata about a
    quest you have not chosen, it does not help you choose, and the detail
    beside the list prints it (and the stages themselves) the moment you
    do."""
    js = node(OV_FIXTURE + r"""
import { GameState } from "../../js/gamestate.js";
import { renderNewGame } from "./newgame.js";
import { renderOverview } from "./overview.js";
const oneStageIndex = { scenarios: [
  { slug: "one-stage", name: "One Stage Quest", pack: "P", cycle: "C1",
    kind: "quest", source: "official", order: 1, stageCount: 1, releaseDate: "2011-01" },
] };
const pickerHtml = renderNewGame(null, { picker: { index: oneStageIndex, cycle: "C1", drill: "scenarios" } });
const ovHtml = renderOverview(new GameState(),
  uiFor({ entry: { ...entry, stageCount: 1 } }));
// Scoped to the ROW, not the page - and to the row's LABEL span, which is
// where the count lived and is the only thing on this row that was ever
// LABEL. Matching the word "stage" instead would hit the set icon's own
// src ("one-stage-quest.svg"), which is how this assertion first passed
// while proving nothing.
const row = /<div[^>]*data-act="pick_scenario"[\s\S]*?<\/div>/.exec(pickerHtml)?.[0] ?? "";
console.log(JSON.stringify({
  pickerHasRow: row.includes('data-arg="one-stage"'),
  pickerAnyCount: /class="label"/.test(row),
  ovSingular: ovHtml.includes("1 stage<"),
  ovPlural: ovHtml.includes("1 stages"),
}));
""")
    assert js["pickerHasRow"]        # the row is there...
    assert not js["pickerAnyCount"]  # ...carrying no count
    assert js["ovSingular"]
    assert not js["ovPlural"]


def test_icon_slug_chain_covers_the_three_ways_the_pack_diverges():
    """setIcon emits a CHAIN of candidate slugs, not one - the community icon
    pack does not always file a set under the name FFG prints. Three rules,
    and the order matters: the printed name first, so a set the pack files
    correctly never pays for anyone else's divergence.

    The alias entry is the only one that is a list rather than a rule, and it
    is cited in the module: Learn to Play names the Core Set's second
    scenario and its encounter set "Journey Down the Anduin"; the pack ships
    the symbol as journey-along-the-anduin.svg."""
    js = node("""
import { iconSlugs, setIcon } from "./seticon.js";
console.log(JSON.stringify({
  plain: iconSlugs("Passage Through Mirkwood"),
  apostrophe: iconSlugs("Sauron's Reach"),
  curly: iconSlugs("Sauron\u2019s Reach"),
  article: iconSlugs("Crossings of Poros"),
  alias: iconSlugs("Journey Down the Anduin"),
  markup: setIcon("Crossings of Poros", 36),
}));
""")
    # The printed name is always tried first.
    assert js["plain"][0] == "passage-through-mirkwood"
    assert js["apostrophe"][0] == "sauron-s-reach"
    assert js["article"][0] == "crossings-of-poros"
    assert js["alias"][0] == "journey-down-the-anduin"
    # ...then each rule's alternate, and no duplicates anywhere.
    assert "saurons-reach" in js["apostrophe"]
    assert js["curly"] == js["apostrophe"]      # a curly apostrophe too
    assert "the-crossings-of-poros" in js["article"]
    assert "journey-along-the-anduin" in js["alias"]
    for key, chain in js.items():
        if key == "markup":
            continue
        assert len(chain) == len(set(chain)), "%s repeats a slug: %s" % (key, chain)
    # The markup carries the rest of the chain for app.js's error listener to
    # walk, and the placeholder glyph behind it.
    assert 'src="' in js["markup"] and "crossings-of-poros.svg" in js["markup"]
    assert 'data-alt="' in js["markup"] and "the-crossings-of-poros.svg" in js["markup"]


def test_a_new_game_is_at_most_five_taps_from_the_landing_screen():
    """Spec R1 (the tap budget), re-counted for the M7 flow. The budget grew
    by two deliberate taps and the reason is worth holding onto:

      home_new       the landing screen exists now, so a player with a save
                     is asked which game they mean instead of being dropped
                     into one;
      ng_cycle       enter the cycle (the list is a drill-in, not a
                     preselected column);
      pick_scenario  fills the detail beside the list - it no longer LEAVES
                     the screen, so comparing a second quest costs one more
                     tap, not three;
      go_players     Continue;
      begin_setup    start.

    Five from a cold launch, six with a source switch. The two extra taps buy
    a landing screen and a players step; the round loop itself is untouched
    (tests/test_tap_budget.py is what guards that)."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { overviewFor, scenarioMetaFor } from "./overview.js";
const g = new GameState();
const bundle = { stages: [{ id: 1 }], locations: [], tips: null };

function run(source) {
  const ui = { screen: "home",
               picker: { index, players: 2, threats: [25, 25],
                         source: "official", cycle: "C1", drill: "cycles", slug: null } };
  const taps = [];
  // home_new and pick_scenario/begin_setup are app.js's (they await a fetch
  // or rebind `game`), so they are counted here and simulated; every other
  // tap goes through the real dispatch table.
  taps.push("home_new"); ui.screen = "newgame";
  if (source === "alep") { taps.push("ng_source"); dispatch(g, ui, "ng_source", "alep"); }
  const cycle = source === "alep" ? "A1" : "C1";
  const slug = source === "alep" ? "a1a" : "o1a";
  taps.push("ng_cycle"); dispatch(g, ui, "ng_cycle", cycle);
  taps.push("pick_scenario");
  ui.overview = overviewFor(index, slug, bundle);
  ui.picker.slug = slug;
  taps.push("go_players"); dispatch(g, ui, "go_players", "");
  taps.push("begin_setup");
  const meta = scenarioMetaFor(ui.overview.entry, ui.overview.difficulty);
  return { n: taps.length, screen: ui.screen, mode: meta.mode, nightmare: meta.nightmare };
}
console.log(JSON.stringify({ official: run("official"), alep: run("alep") }));
""")
    assert js["official"]["n"] == 5, "official path: %s taps" % js["official"]["n"]
    assert js["alep"]["n"] == 6, "alep path: %s taps" % js["alep"]["n"]
    assert js["official"]["screen"] == "players"
    for path in ("official", "alep"):
        assert js[path]["mode"] == "Standard" and js[path]["nightmare"] is False


def test_overview_for_builds_the_seat_pick_scenario_hands_to_ui_overview():
    """pick_scenario itself can't be driven under node (it awaits
    db.bundle()) - overviewFor(index, slug, bundle) is the pure helper it
    calls once the bundle has loaded, exported from overview.js (it lived in
    newgame.js while that screen was a placeholder) so these tests can cover
    the shape without a live DataClient."""
    js = node(NG_FIXTURE + """
import { overviewFor } from "./overview.js";
const bundle = { stages: [{ id: 1 }], locations: [], tips: null };
const found = overviewFor(index, "o1a", bundle);
const missing = overviewFor(index, "no-such-slug", bundle);
console.log(JSON.stringify({
  slug: found.slug, name: found.entry?.name, difficulty: found.difficulty,
  readonly: found.readonly, hasBundle: found.bundle === bundle,
  missingEntry: missing.entry,
}));
""")
    assert js["slug"] == "o1a" and js["name"] == "Official 1A"
    assert js["difficulty"] == "Standard" and js["readonly"] is False
    assert js["hasBundle"]
    assert js["missingEntry"] is None


def test_scenario_detail_is_one_renderer_on_both_of_its_hosts():
    """The chooser's detail column and the in-game reference screen are the
    same function (renderScenarioDetail), on a bundle with none of the
    optional pieces (no scenario record, no cards, a stage entry with no
    cards key at all): both draw the title rather than throwing on a missing
    field, and every section degrades to nothing on its own.

    What differs is only the host's own footer. The whole-screen host has
    exactly one way out (Close) because it has exactly one caller - the
    in-game reference; the chooser brings Continue instead, and never the
    overview's own footer."""
    js = node(NG_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { overviewFor } from "./overview.js";
import { layout } from "./layout.js";
const bundle = { stages: [{ id: 1 }], locations: [], tips: null };
const overview = overviewFor(index, "o1a", bundle, { readonly: true });
const screenHtml = layout(new GameState(), { screen: "overview", overview });
const chooserHtml = layout(new GameState(), {
  screen: "newgame",
  picker: { index, source: "official", cycle: "C1", drill: "scenarios", slug: "o1a" },
  overview,
});
console.log(JSON.stringify({
  screenTitle: screenHtml.includes(">Official 1A<"),
  screenClose: screenHtml.includes('data-act="ov_close"'),
  screenBeginSetup: screenHtml.includes('data-act="begin_setup"'),
  screenBack: screenHtml.includes('data-act="ov_back"'),
  chooserTitle: chooserHtml.includes(">Official 1A<"),
  chooserContinue: chooserHtml.includes('data-act="go_players"'),
  chooserOvFoot: chooserHtml.includes("ov-foot"),
}));
""")
    assert js["screenTitle"] and js["screenClose"]
    # The pre-game footer is gone with the pre-game SCREEN: setup starts from
    # the players step now, and there is nothing to go "back" from.
    assert not js["screenBeginSetup"] and not js["screenBack"]
    assert js["chooserTitle"] and js["chooserContinue"]
    assert not js["chooserOvFoot"]


# The Scenario overview's fixture (Task 3, milestone 6). The entry is the
# index row - a scenario that prints a Hard Mode card AND has a Nightmare
# deck, which no real scenario does (of 349, exactly 1 prints Hard and 68
# have Nightmare, and no scenario has both) but which is what puts every rung
# of the ladder on screen at once. The bundle is db.bundle()'s own shape:
#   - three stages: an ordinary one with printed points, a two-alternative
#     branch stage (named off the BACK face, like the resolution sheet's own
#     fork list), and a condition stage whose questPointsKind is "na" - it
#     must print NO number, never the 0 the field carries;
#   - encounter groups holding this scenario's own two enemies (quantity 3
#     and 2) and one location, PLUS one card from a set it merely gathers,
#     which belongs to that set's own file and not to this scenario's grid;
#   - a three-name gather list, two of which are therefore "shared";
#   - tips for the slug, so the notes section has a group and a source link.
OV_FIXTURE = """
const entry = { slug: "ov1", name: "Overview One", pack: "Pack P", cycle: "Cycle C",
  kind: "quest", source: "official", modes: ["Hard Mode"], hasNightmare: true,
  stageCount: 4, maxCardThreat: 3, hasXThreat: false };
const index = { scenarios: [entry] };
const bundle = {
  scenario: {
    slug: "ov1", name: "Overview One",
    includedSets: ["Overview One", "Gathered Set", "Other Set"],
    modes: [{ name: "Hard Mode", faces: [{ text: "Hard mode: the printed card's own text." }] }],
    encounter: {
      enemy: [
        { id: "e1", image: "e1.jpg", name: "First Enemy", encounterSet: "Overview One",
          quantity: 3, type: "Enemy",
          faces: [{ engagementCost: 25, threat: 2, attack: 2, defense: 1, hitPoints: 4 }] },
        { id: "e2", image: "e2.jpg", name: "Second Enemy", encounterSet: "Overview One",
          quantity: 2, type: "Enemy",
          faces: [{ engagementCost: 30, threat: 3, attack: 3, defense: 2, hitPoints: 5 }] },
        { id: "e3", image: "e3.jpg", name: "Gathered Enemy", encounterSet: "Gathered Set",
          quantity: 4, type: "Enemy", faces: [{ engagementCost: 10 }] },
      ],
      location: [
        { id: "l1", image: "l1.jpg", name: "First Location", encounterSet: "Overview One",
          quantity: 2, type: "Location", faces: [{ threat: 1, questPoints: 3 }] },
      ],
    },
  },
  stages: [
    { stage: 1, cards: [{ questPoints: 8,
        faces: [{ name: "Flies Ahead", side: "A" }, { name: "Into the Wood", side: "B" }] }] },
    { stage: 2, branch: "choice", cards: [
      { questPoints: 13, faces: [{ name: "Through the Marsh", side: "A" }, { name: "Left Path", side: "B" }] },
      { questPoints: 13, faces: [{ name: "Through the Marsh", side: "A" }, { name: "Right Path", side: "B" }] },
    ] },
    { stage: 3, questPointsKind: "na", cards: [{ questPoints: 0, questPointsKind: "na",
        faces: [{ name: "The Last Stand", side: "A" }, { name: "Hold the Line", side: "B" }] }] },
    { stage: 4, cards: [{ questPointsX: { text: "X is the number of players." },
        faces: [{ name: "The Open Ground", side: "A" }, { name: "Many Foes", side: "B" }] }] },
  ],
  locations: [],
  tips: { ov1: { attribution: { name: "Vision of the Palantir", url: "https://example.invalid/ov1" },
                 general: ["Keep a location in play for the extra progress."],
                 stages: { "1": ["The spiders come out early."] } } },
};
const uiFor = (over) => ({ screen: "overview", tips: bundle.tips, scenarioSlug: "ov1",
  imagePrefix: "https://art.example.invalid/",
  overview: { slug: "ov1", entry, bundle, difficulty: "Standard", readonly: false, ...over } });
"""


def test_overview_difficulty_ladder_is_easy_standard_hard_nightmare():
    """difficulty.js is a pure port of ScenarioOptionsScreen's own
    difficultyOptions()/_scenarioModes() (docs/js/screens_other.js): Easy and
    Standard always (Easy is a general rule, Learn to Play p.28), the printed
    Mode cards this scenario actually ships, then Nightmare when it has a
    deck - and the selected rung is the gold one."""
    js = node(OV_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { renderOverview } from "./overview.js";
import { difficultyOptions } from "./difficulty.js";
const html = renderOverview(new GameState(), uiFor({}));
console.log(JSON.stringify({
  opts: difficultyOptions(entry),
  bare: difficultyOptions({}),
  args: [...html.matchAll(/data-act="ov_difficulty" data-arg="([^"]+)"/g)].map(m => m[1]),
  standardGold: /<button[^>]*data-arg="Standard"[^>]*class=|class="[^"]*chip-gold[^"]*"[^>]*data-act="ov_difficulty" data-arg="Standard"/.test(html),
  goldArg: /class="chip chip-gold"[^>]*data-act="ov_difficulty" data-arg="([^"]+)"/.exec(html)?.[1] ?? "",
}));
""")
    assert js["opts"] == ["Easy", "Standard", "Hard", "Nightmare"]
    assert js["bare"] == ["Easy", "Standard"]      # a scenario with neither
    assert js["args"] == ["Easy", "Standard", "Hard", "Nightmare"]
    assert js["goldArg"] == "Standard"


def test_overview_ov_difficulty_selects_nightmare_and_prints_the_verified_tip():
    """The tip is viewcopy's MODE_TIPS sentence VERBATIM - the one home both
    twins read, with the rulebook citations in viewcopy.py - never a sentence
    this screen wrote. A printed Mode card shows its own text instead, and an
    option the scenario does not offer is refused outright rather than
    quietly selected."""
    js = node(OV_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { renderOverview } from "./overview.js";
import { MODE_TIPS } from "../../js/viewcopy.js";
const g = new GameState();
const ui = uiFor({});
const standard = renderOverview(g, ui);
const nightmare = dispatch(g, ui, "ov_difficulty", "Nightmare");
const nmHtml = renderOverview(g, ui);
const again = dispatch(g, ui, "ov_difficulty", "Nightmare");
const bogus = dispatch(g, ui, "ov_difficulty", "Bogus");
const hard = dispatch(g, ui, "ov_difficulty", "Hard");
const hardHtml = renderOverview(g, ui);
console.log(JSON.stringify({
  nightmare, again, bogus, hard, after: ui.overview.difficulty,
  standardTip: standard.includes(MODE_TIPS.Nightmare) || standard.includes(MODE_TIPS.Easy),
  nmTip: nmHtml.includes(MODE_TIPS.Nightmare),
  nmGold: /class="chip chip-gold"[^>]*data-arg="Nightmare"/.test(nmHtml),
  hardTip: hardHtml.includes("Hard mode: the printed card&#39;s own text."),
}));
""")
    assert js["nightmare"] is True and js["again"] is False
    assert js["bogus"] is False and js["hard"] is True
    assert js["after"] == "Hard"        # Bogus never landed
    assert js["nmTip"] and js["nmGold"]
    assert not js["standardTip"]        # Standard says nothing at all
    assert js["hardTip"]                # the printed Mode card's own text


def test_the_stage_list_moved_to_the_left_column_and_never_prints_a_zero():
    """The stages left the detail pane: they are the chooser's third list now,
    under CYCLE and SCENARIOS, with Overview as the first row and the default.
    Three repeated STAGE blocks in the middle column is what that replaced.

    The rows keep R7's rules. A condition stage prints no target at all - ~137
    of ~400 stage cards advance on a condition, and no stage card ever prints
    a 0 (xshape.js's stagePointsShape) - and a branch stage names itself by
    its count rather than by one of its alternatives, since which card the
    quest deck turns up is not knowable from here."""
    js = node(OV_FIXTURE + r"""
import { GameState } from "../../js/gamestate.js";
import { renderNewGame } from "./newgame.js";
const idx = { scenarios: [{ slug: "ov1", name: "Overview One", pack: "P", cycle: "C1",
  kind: "quest", source: "official", order: 1, stageCount: 4, releaseDate: "2011-01" }] };
const ui = uiFor({});
ui.picker = { index: idx, source: "official", cycle: "C1", drill: "scenarios", slug: "ov1" };
const html = renderNewGame(new GameState(), ui);
const sect = /class="drill-list stage-list">([\s\S]*?)<\/div>\s*<\/div>/.exec(html)?.[1] ?? html;
const rows = [...sect.matchAll(/data-arg="([^"]*)"[^>]*>([\s\S]*?)<\/button>/g)]
  .map(m => [m[1], m[2].replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim()]);
console.log(JSON.stringify({ rows, overviewFirst: rows[0]?.[0] }));
""")
    args = [r[0] for r in js["rows"]]
    text = {r[0]: r[1] for r in js["rows"]}
    assert js["overviewFirst"] == "overview"        # Overview is row one...
    assert args == ["overview", "1", "2", "3", "4"]
    assert "Overview" in text["overview"]
    assert "8 QP" in text["1"]
    # Stage 3 advances on a condition: a dash, never a 0.
    assert "QP" not in text["3"] and "0" not in text["3"]
    # Stage 2 is the branch: named by its count, not by one alternative.
    assert "2 alternatives" in text["2"]
    assert "Left Path" not in text["2"] and "Right Path" not in text["2"]


def test_overview_cards_are_the_scenarios_own_set_with_counts_and_printed_values():
    """R5: the scenario's own cards, grouped by type, each with how many
    copies it ships. A card from a set this quest merely
    GATHERS lives in that set's own file, not in this grid - the shared-sets
    chips are what say it is coming. Every value is the card's own; a null
    field is absent, never a 0 the card does not print."""
    js = node(OV_FIXTURE + r"""
import { GameState } from "../../js/gamestate.js";
import { renderOverview } from "./overview.js";
const html = renderOverview(new GameState(), uiFor({}));
const caps = [...html.matchAll(/<span class="body card-cap">([\s\S]*?)<\/span><\/button>/g)]
  .map(m => m[1].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim());
console.log(JSON.stringify({
  caps,
  headings: [...html.matchAll(/<div class="ov-type"><div class="label">([^<]+)</g)].map(m => m[1]),
  art: [...html.matchAll(/<img src="([^"]+)"/g)].map(m => m[1]).filter(u => u.includes("art.example")),
}));
""")
    # The name and the copy count. The stat line is NOT transcribed under the
    # picture of it - it is in the quick view's fact table, where a table of
    # numbers belongs; see cardCaption's own note.
    assert js["caps"] == [
        "First Enemy · ×3",
        "Second Enemy · ×2",
        "First Location · ×2",
    ]
    assert js["headings"] == ["Enemies", "Locations"]
    assert js["art"] == ["https://art.example.invalid/e1.jpg",
                         "https://art.example.invalid/e2.jpg",
                         "https://art.example.invalid/l1.jpg"]


def test_overview_sets_to_gather_is_the_whole_list_and_nothing_repeats_it():
    """Sets to gather is the gather list entire (the twin's _gatherSets,
    falling back to the scenario's own name when the enrichment never covered
    it), and it is not tappable - nothing here is a button.

    There is no second list. A "Shared sets" section used to print that same
    list minus this scenario's own set, in the sidebar, which is by
    construction a subset of the rows already above it - the same names, the
    same icons, no new fact. Removed."""
    js = node(OV_FIXTURE + r"""
import { GameState } from "../../js/gamestate.js";
import { renderOverview } from "./overview.js";
const html = renderOverview(new GameState(), uiFor({}));
const noSets = renderOverview(new GameState(), uiFor({
  bundle: { ...bundle, scenario: { ...bundle.scenario, includedSets: undefined } } }));
const gather = /class="ov-sets">([\s\S]*?)<\/ul>/.exec(html)?.[1] ?? "";
console.log(JSON.stringify({
  gather: [...gather.matchAll(/<span class="body">([^<]+)</g)].map(m => m[1]),
  gatherTappable: gather.includes("data-act"),
  anySecondList: html.includes("ov-chips") || html.includes("Shared sets"),
  fallback: [...(/class="ov-sets">([\s\S]*?)<\/ul>/.exec(noSets)?.[1] ?? "")
    .matchAll(/<span class="body">([^<]+)</g)].map(m => m[1]),
}));
""")
    assert js["gather"] == ["Overview One", "Gathered Set", "Other Set"]
    assert not js["gatherTappable"]
    assert not js["anySecondList"]
    assert js["fallback"] == ["Overview One"]   # no enrichment: its own set


def test_tips_render_as_fixed_slots_at_the_scope_being_shown():
    """The tips are SLOTS, not a list: the same set in the same order every
    time, and an empty one drawn as empty rather than dropped. That is the
    whole point - a player learns once where pacing advice lives and then
    always looks there, which a list that varies per scenario cannot offer.

    The frame arrives WITH THE DATA. Every tip in tips.json is unclassified
    today and lands in `notes`, so drawing all six slots for those scenarios
    put five identical "Nothing recorded yet." rows on the screen - half the
    panel saying nothing, on every scenario. Until a scenario has one
    classified tip, only its filled slots are drawn; after, the full frame.

    Scope follows the left column's selection: the overview shows the
    scenario's general tips, a selected stage shows only that stage's. A
    stage's advice is only findable if it is not mixed in with every other
    stage's.

    Both tip shapes are accepted - a plain string (every tip in tips.json
    today) lands in `notes`; {kind, text} lands in its named slot - so the
    classification pass can land scenario by scenario with no flag day."""
    js = node(OV_FIXTURE + r"""
import { GameState } from "../../js/gamestate.js";
import { renderOverview } from "./overview.js";
import { TIP_SLOTS, slotted } from "./notes.js";
const ov = renderOverview(new GameState(), uiFor({}));
const stageUi = uiFor({});
stageUi.picker = { stage: "1" };
const st = renderOverview(new GameState(), stageUi);
const none = renderOverview(new GameState(), uiFor({ slug: "no-tips-here" }));
// The same scenario once ONE tip carries a kind: the whole frame appears.
const classifiedUi = uiFor({});
classifiedUi.tips = { ov1: { ...bundle.tips.ov1,
  general: [{ kind: "pacing", text: "Build first, push at stage 2." }] } };
const cls = renderOverview(new GameState(), classifiedUi);
const labels = h => [...h.matchAll(/<div class="tipslot[^"]*">\s*<span class="label">([^<]+)</g)].map(m => m[1]);
console.log(JSON.stringify({
  slots: TIP_SLOTS,
  ovLabels: labels(ov),
  stLabels: labels(st),
  clsLabels: labels(cls),
  clsEmpty: (cls.match(/tipslot [^"]*is-empty/g) || []).length,
  ovBare: (ov.match(/tipslot is-bare/g) || []).length,
  clsBare: (cls.match(/tipslot[^"]*is-bare/g) || []).length,
  ovHasGeneral: ov.includes("Keep a location in play for the extra progress."),
  stHasGeneral: st.includes("Keep a location in play for the extra progress."),
  emptySlots: (ov.match(/tipslot is-empty/g) || []).length,
  noneHasSlots: none.includes("tipslot"),
  classified: slotted([{ kind: "pacing", text: "Stall." }, "plain one"]) 
    .filter(s => s.items.length).map(s => [s.kind, s.items]),
}));
""")
    # Unclassified today: only the slot that holds something is drawn, on
    # both scopes - no wall of "Nothing recorded yet." - and it carries no
    # row label either, because the panel's own heading already says Notes.
    assert js["ovLabels"] == []
    assert js["stLabels"] == js["ovLabels"]
    assert js["ovBare"] == 1 and js["clsBare"] == 0
    assert js["emptySlots"] == 0
    # ...and the scopes really are different content.
    assert js["ovHasGeneral"] and not js["stHasGeneral"]
    # One classified tip brings the whole frame, in its fixed order, with the
    # empty slots drawn as empty - which is what the frame is for.
    assert js["clsLabels"] == ["Pacing", "Before you advance", "Watch for",
                               "Avoid", "Player count", "Notes"]
    assert js["clsEmpty"] == 5
    # A scenario with no tips at all draws no panel, not an empty shell.
    assert not js["noneHasSlots"]
    # Both tip shapes, routed.
    assert js["classified"] == [["pacing", ["Stall."]], ["notes", ["plain one"]]]


def test_overview_readonly_swaps_the_ladder_for_a_badge_and_the_footer_for_close():
    """The read-only variant (open_overview, from the QUEST zone's stage
    pill mid-game): the difficulty is settled, so there is no ladder to tap
    and no game to begin - a LABEL badge naming the mode, and Close."""
    js = node(OV_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { renderOverview } from "./overview.js";
import { MODE_TIPS } from "../../js/viewcopy.js";
const html = renderOverview(new GameState(), uiFor({ readonly: true, difficulty: "Nightmare" }));
console.log(JSON.stringify({
  ladder: html.includes("ov_difficulty"),
  badge: /<span class="ov-badge label">([^<]+)</.exec(html)?.[1] ?? "",
  tip: html.includes(MODE_TIPS.Nightmare),
  close: html.includes('data-act="ov_close"'),
  begin: html.includes('data-act="begin_setup"'),
  back: html.includes('data-act="ov_back"'),
  sets: html.includes(">Gathered Set<"),
  stages: html.includes(">Left Path<"),
}));
""")
    assert not js["ladder"]
    assert js["badge"] == "Nightmare"
    assert js["tip"]                      # the mode's own verified sentence stays
    assert js["close"]
    assert not js["begin"] and not js["back"]
    assert js["sets"]                     # everything else is the same screen
    # The in-game reference has no stage list to select from, so it is always
    # the overview - and the overview no longer carries the stage cards.
    assert not js["stages"]


def test_overview_acts_open_from_the_stage_pill_and_close_back_to_play():
    """The rail's stage pill name is the way in (a real button, so it takes
    the 44px floor with it); open_overview flips the seat read-only at the
    GAME's own mode, not whatever the ladder was last left on, and ov_close
    goes back to play. ov_back is gone with M7: the overview is no longer a
    screen you leave the picker for, so there is nothing to go back from."""
    js = node(OV_FIXTURE + """
import { GameState } from "../../js/gamestate.js";
import { dispatch } from "./actions.js";
import { renderRail } from "./rail.js";
const g = new GameState(2);
g.preloadScenario({ slug: "ov1", name: "Overview One", mode: "Nightmare", nightmare: true },
                  bundle.stages);
const ui = uiFor({ difficulty: "Easy" });
ui.screen = "play";
const rail = renderRail(g, ui);
const opened = dispatch(g, ui, "open_overview", "");
const afterOpen = { screen: ui.screen, readonly: ui.overview.readonly, difficulty: ui.overview.difficulty };
const closed = dispatch(g, ui, "ov_close", "");
const screenAfterClose = ui.screen;
const back = dispatch(g, ui, "ov_back", "");
const screenAfterBack = ui.screen;
const bare = new GameState(2);
const bareUi = { screen: "play", overview: null };
console.log(JSON.stringify({
  pillBtn: /<button type="button" class="body pill-name pill-name-btn" data-act="open_overview">([^<]*)</.exec(rail)?.[1] ?? "",
  barePill: renderRail(bare, bareUi).includes("open_overview"),
  opened, afterOpen, closed, screenAfterClose, back, screenAfterBack,
  declined: dispatch(bare, bareUi, "open_overview", ""),
}));
""")
    assert js["pillBtn"] == "Flies Ahead"
    assert not js["barePill"]        # no scenario, no way in
    assert js["opened"] is True
    assert js["afterOpen"] == {"screen": "overview", "readonly": True, "difficulty": "Nightmare"}
    assert js["closed"] is True and js["screenAfterClose"] == "play"
    assert js["back"] is False and js["screenAfterBack"] == "play"
    assert js["declined"] is False


def test_scenario_meta_for_carries_the_ladder_pick_into_the_game():
    """begin_setup's own meta, as a pure helper (app.js can't be driven under
    node): the ladder's pick becomes the game's `mode`, and only "Nightmare"
    sets the `nightmare` flag. maxCardThreat/hasXThreat ride along untouched
    - the staging estimate reads them, and losing them would cost the
    estimate silently rather than crash."""
    js = node(OV_FIXTURE + """
import { scenarioMetaFor } from "./overview.js";
console.log(JSON.stringify({
  nm: scenarioMetaFor(entry, "Nightmare"),
  easy: scenarioMetaFor(entry, "Easy"),
  none: scenarioMetaFor(null, "Standard"),
}));
""")
    assert js["nm"] == {
        "slug": "ov1", "name": "Overview One", "pack": "Pack P", "cycle": "Cycle C",
        "source": "official", "kind": "quest", "nightmare": True, "mode": "Nightmare",
        "maxCardThreat": 3, "hasXThreat": False,
    }
    assert js["easy"]["nightmare"] is False and js["easy"]["mode"] == "Easy"
    assert js["none"]["mode"] == "Standard" and js["none"]["nightmare"] is False


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
    assert '<span class="label">Passage Through Mirkwood</span>' in js["setHeaderHtml"], \
        "the set header must render as markup, not escaped text"
    assert '<div class="locpick-group-head">' in js["setHeaderHtml"]
    # Task 5: the set icon sits before the label, sourced from the SVG pack
    # tools/build_icons.py exports (slugify() applied to the set name).
    assert 'icons/svg/passage-through-mirkwood.svg"' in js["setHeaderHtml"]
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


def test_side_quest_picker_row_tap_appends_and_reopens_the_quest_sheet():
    """Task-6 brief step 1: pick a sphere, then a quest inside it. The row
    tap IS the add - it pushes {points, progress:0, name} and logs the
    verbatim "Side quest added: ..." line (SideQuestPickModal's own onButton
    "add" branch, docs/js/screens.js), then reopens the quest sheet.

    The twin's separate Add confirm is deliberately NOT mirrored. On its
    canvas modal a row tap also has to do the paging, so the confirm is
    load-bearing there; here it was a second tap for one decision, and it is
    what made the sheet narrate its own flow in prose ("Lore - pick one,
    then Add."). A mis-tap is undone in one by the quest sheet's own
    remove."""
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
    everything already fits on one page.

    The chosen sphere is a CRUMB, drawn the way the scenario chooser draws
    the chosen cycle - a LABEL, then the choice on a gold-edged row with an X
    that clears it (.drill-current, sqpick_back). It was a "< Spheres" chip
    down in the footer, which put "go back a step" in the row reserved for
    leaving and committing. And there is no instruction sentence: the step
    is shown, not narrated."""
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
perform(g, ui, "sqpick_back", "");
const backSphere = ui.sheet.sphere;
perform(g, ui, "sqpick_cancel", "");
console.log(JSON.stringify({
  noSphereRow: sphereHtml.includes("No sphere") && sphereHtml.includes('data-act="sqpick_sphere"') && sphereHtml.includes('data-arg="No sphere"'),
  noPager: !sphereHtml.includes("sqpick-pager") && !sphereHtml.includes('data-act="sqpick_page"'),
  name: questHtml.includes("Fortune or Fate"),
  pts: questHtml.includes("3 pts"),
  text: questHtml.includes("Draw the top card of the encounter deck."),
  crumb: /<div class="label">Sphere<\/div>\s*<div class="drill-row drill-current" data-act="sqpick_back"/.test(questHtml)
    && questHtml.includes(">Neutral<"),
  noProse: !questHtml.includes("pick one") && !sphereHtml.includes("Pick a sphere"),
  backSphere,
  cancelKind: ui.sheet?.kind,
  cancelCount: g.side_quests.length,
}));
""")
    assert js["noSphereRow"], "an entry with no printed sphere must bucket under \"No sphere\""
    assert js["noPager"], "two rows on one page must not draw a pager"
    assert js["name"] and js["pts"]
    assert js["text"], "the card's own printed text must render, not be dropped"
    assert js["crumb"], "the chosen sphere is a clearable crumb, not a footer chip"
    assert js["noProse"], "the sheet must not narrate its own flow in prose"
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


def test_the_threat_helm_is_drawn_only_where_the_number_is_threat():
    """The staging rail and the staging sheet count three different things -
    threat, enemies, locations - and all three used to be drawn beside the
    black threat helm, because the icon set has no enemy or location mask.
    That put the threat mark next to a count of locations, which reads as
    "threat 3" about a number that is not threat. The honest answer to a
    missing mask is no mark; the caption above each number names it."""
    js = node(r"""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
import { renderStagingSheet } from "./sheet_staging.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView();
const ui = newUi();
const rail = layout(g, ui);
perform(g, ui, "open_staging", "");
const sheet = renderStagingSheet(g, ui);
// One pill/row per counted thing; count how many carry an <svg> mark.
// Scoped to the STAGING grid - the quest zone's own progress pills use the
// trail mark, which is right there and not what this is about.
const grid = /<div class="staging-grid">([\s\S]*?)<\/div><\/div>/.exec(rail)?.[1] ?? "";
const rowsMarked = [...sheet.matchAll(/<span class="ssheet-val">(<svg)?/g)].filter(m => m[1]).length;
console.log(JSON.stringify({
  pills: (grid.match(/<div class="pill-stat">/g) || []).length,
  pillsMarked: [...grid.matchAll(/<div class="pill-stat">(<svg)?/g)].filter(m => m[1]).length,
  rows: (sheet.match(/<span class="ssheet-val">/g) || []).length,
  rowsMarked,
}));
""")
    assert js["pills"] == 3 and js["rows"] == 3
    assert js["pillsMarked"] == 1, "only THREAT wears the helm in the rail"
    assert js["rowsMarked"] == 1, "only THREAT wears the helm in the sheet"


def test_players_sheet_title_carries_no_stale_game_wide_elimination_figure():
    """M9: the title used to print game.elimination_threat - the GAME's
    default level - while elim_setlvl recalibrates a level PER PLAYER
    (p.elimination). Recalibrating one player's level away from the default
    left a header figure that named a level no row on screen still used;
    each row already prints its own distance and its own level, so the title
    carries no number of its own now."""
    js = node(r"""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, afterTap, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 45); g.advanceView(); const ui = newUi();
perform(g, ui, "thr", "0:5"); afterTap(g, ui);                       // P1: 45 -> 50, crosses
perform(g, ui, "elim_lvl", "10"); perform(g, ui, "elim_setlvl", ""); // P1's own level -> 60
perform(g, ui, "open_players", "");
const html = layout(g, ui);
const title = /<h1 class="display">([^<]*)</.exec(html)?.[1] ?? "";
console.log(JSON.stringify({
  title: html.includes('<h1 class="display">Players</h1>'),
  // Scoped to the TITLE's own text: each row names its own level, and that
  // is the point - only a game-wide figure up here would be the stale one.
  noStaleFigure: !/[0-9]/.test(title),
  p1Row: html.includes("10 to elimination at 60"),
  p2Row: html.includes("5 to elimination at 50"),
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
    assert js["planningIsButton"] and js["futureIsNotButton"]
    # The strip carries NO separate transport any more: every tick a delta
    # reached this round is itself the rewind target, so four buttons beside
    # the round number were a second control for a job the timeline already
    # does - and they sat where the eye lands first. The Game Log screen keeps
    # its own six-control transport, where moving by ROUND is the point.
    assert not js["transport"] and not js["readout"]


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

def test_every_flow_view_pane_renders_a_rules_chip_in_its_own_section():
    """Fix round 1, finding 1: sectionsFor() (rules_map.js) mapping every
    view to section ids was never proof a CHIP actually reached the screen -
    planning/combat_enemy rendered solely through renderLoop() (loops.js),
    which didn't take a `section` at all, so those two panes carried no
    "Rules §n ›" chip whatsoever, and enc_checks/combat_player's own loop-
    drawn framework/window band was silently chip-less too (the pane's OWN
    extra band next to it still had one). This is a render assertion, not a
    sectionsFor() one: for every flow view but quest_setup/quest_sailing
    (neither has a Rules Reference section of its own - stage-1A setup text
    and the sailing test are this tracker's own affordances, not numbered
    book steps; flowViews() under WINDOW_POLICY_BANDS never actually returns
    either one, so excluding them here is defensive documentation, not a
    functional exclusion), renderPane() must carry at least one
    data-act="open_rules" chip whose arg is one of sectionsFor(view)'s own
    ids - never a hand-picked or stale one. planning and combat_enemy get an
    exact-value check since their own loop-framing band is the ONLY chip on
    the pane (no second, pane-built band to fall back on)."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, flowViews } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { sectionsFor } from "./rules_map.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const out = {};
for (const v of flowViews().filter(x => x !== "quest_setup" && x !== "quest_sailing")) {
  const g = new GameState(4, 25); g.advanceView(); g.enterView(v);
  if (v === "quest_resolution") { g.setWillpower(9); g.setStaging(2); g.resolveQuest(9, 2); g.pending_budget = 7; }
  const html = renderPane(g, newUi());
  out[v] = {
    chips: [...html.matchAll(/data-act="open_rules" data-arg="([^"]*)"/g)].map(m => m[1]),
    allowed: sectionsFor(v),
  };
}
console.log(JSON.stringify({
  out,
  excluded: { quest_setup: sectionsFor("quest_setup"), quest_sailing: sectionsFor("quest_sailing") },
}));
""")
    out = js["out"]
    assert len(out) > 0
    for v, r in out.items():
        assert len(r["chips"]) > 0, "no Rules chip rendered on %r's pane: %r" % (v, r)
        assert set(r["chips"]) <= set(r["allowed"]), (v, r)
    assert out["planning"]["chips"] == ["2.2"], out["planning"]
    assert out["combat_enemy"]["chips"] == ["6.3"], out["combat_enemy"]
    assert js["excluded"] == {"quest_setup": [], "quest_sailing": []}


def test_resource_pane_bands_carry_the_rules_chips_from_the_map():
    """pane.js wires each of resource's two direct band() calls to the
    sectionsFor("resource") id whose phases.py label that band's own text
    describes: the framework band IS the work ("1.2-1.3 Gain resources and
    draw cards"), and the window band's tip - "Anything played now happens
    before the planning phase begins" - is about the phase ENDING ("1.4 End
    of the Resource phase"). The M5 final review found these inverted (1.1
    on the framework band, the work step on the window band); the broader
    pin is the test below."""
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
    assert js["chips"] == ["1.2", "1.4"], js["html"]


# Every "Rules §n ›" chip a pane emits, in render order, as
# (section id, the phases.py STEPS label that id falls under, the opening
# words of the band the chip sits in). Written by hand FROM docs/js/phases.js's
# own labels - deliberately not derived from rules_map.js, which is the thing
# under test: an inversion inside a view's own allowed set (the M5 final
# review's finding - the resource/combat_shadow/refresh framework bands cited
# their phase's "Beginning of the ..." step while their window bands cited the
# work step) stays inside sectionsFor(view) and so passes every set-membership
# check. The rule this table encodes: a chip cites the step whose label
# describes the band's own text.
PANE_CHIPS = {
    "resource": [
        ("1.2", "1.2-1.3 Gain resources and draw cards",
         "Each hero gains a resource and each player draws a card"),
        ("1.4", "1.4 End of the Resource phase",
         "Anything played now happens before the planning phase begins."),
    ],
    "planning": [
        ("2.2", "2.2-2.3 Play cards in turn order - player actions throughout",
         "In player order, each player becomes the active player once."),
    ],
    "quest_commit": [
        ("3.2", "3.2 Commit characters to the quest",
         "In player order, exhaust characters to commit them"),
    ],
    "quest_staging": [
        ("3.3", "3.3 Staging", "Reveal 1 encounter card per player."),
        ("3.3", "3.3 Staging", "Responses to the reveal."),
    ],
    # The outcome band above this one carries NO chip: its text is whatever
    # resolveQuest() just produced, so "3.4 Quest resolution" would open a
    # Timing summary quoting a string that changes every round.
    "quest_resolution": [
        ("3.5", "3.5 End of the Quest phase",
         "This is the last action window before travel."),
    ],
    "travel": [
        ("4.2", "4.2 Travel opportunity",
         "Travel to one location in the staging area."),
        ("4.3", "4.3 End of the Travel phase",
         "This is the last action window in the travel phase."),
    ],
    "travel_blocked": [
        ("4.1", "4.1 Beginning of the Travel phase",
         "A location is already active, so there is no travel this phase."),
        ("4.3", "4.3 End of the Travel phase",
         "This is the last action window in the travel phase."),
    ],
    "enc_optional": [
        ("5.2", "5.2 Optional engagement",
         "In player order, each player may engage 1 enemy in the staging area."),
    ],
    "enc_checks": [
        ("5.3", "5.3 Engagement checks",
         "Not optional. In player order, each player engages one enemy at a time."),
        ("5.4", "5.4 End of the Encounter phase",
         "This is the last action window before combat."),
    ],
    "combat_shadow": [
        ("6.2", "6.2 Deal shadow cards",
         "In player order, deal 1 facedown shadow card"),
        ("6.1", "6.1 Beginning of the Combat phase", "Responses."),
    ],
    "combat_enemy": [
        ("6.3", "6.3-6.6 Enemy attacks",
         "In player order, one attack per engaged enemy."),
    ],
    "combat_player": [
        ("6.8a", "6.7-6.10 Player attacks",
         "In player order, each player may attack."),
        ("6.11", "6.11 End of the Combat phase",
         "Lower threat now or refresh may eliminate."),
    ],
    "refresh": [
        ("7.2", "7.2-7.4 Ready cards, raise threat, pass P1 token",
         "Simultaneously ready all exhausted cards."),
        ("7.1", "7.1 Beginning of the Refresh phase", "Responses."),
    ],
    "round_end": [
        ("7.5", "7.5 End of the Refresh phase",
         'Resolve any "at the end of the round" effects.'),
    ],
}


def test_every_pane_chip_cites_the_step_its_own_band_describes():
    """M5 final review, CRITICAL: three views handed the phase-begins id to
    the band doing the phase's WORK and the work id to the response window -
    resource (1.1 <-> 1.2), combat_shadow (6.1 <-> 6.2) and refresh
    (7.1 <-> 7.2). Every existing chip test passed anyway, because each wrong
    id was still one of sectionsFor(view)'s own, so nothing compared a chip
    to the TEXT of the band carrying it.

    This does. It pulls (section id, band text) pairs straight out of the
    rendered HTML in render order and compares them to PANE_CHIPS above, a
    hand-written table built from docs/js/phases.js's STEPS labels (the
    generated mirror of phases.py, the repo's verified turn sequence). The
    label each id falls under is asserted too, resolved out of phases.js by
    parsing the leading "N.M" / "N.M-N.K" range off each STEPS label - so
    "6.8a" resolving to "6.7-6.10 Player attacks" is read from the generated
    file, never re-typed here.

    Also the coverage assertion for the second review finding: every chip a
    pane emits must have a rules_map.js SECTION_SUMMARY entry, so no live
    chip can open the Rules sheet with the Timing block missing."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { STEPS } from "../../js/phases.js";
import { renderPane } from "./pane.js";
import { SECTION_SUMMARY } from "./rules_map.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);

// h``'s escaping, undone, so the expectation table can be written as the
// plain prose viewcopy.js holds (apostrophes and quotes included). &amp;
// last: a source "&lt;" escapes to "&amp;lt;" and must come back as "&lt;".
const unesc = s => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");

// Every band() (primitives.js) in render order, keeping only those that
// carry a Rules chip, as [section id, the band's own first .body line].
// Splitting on the band opener bounds each fragment at the next band, so a
// chip-less band (a loop's closing note) can never be handed the next
// band's chip.
function chipBands(html) {
  return html.split('class="band ').slice(1).map(f => {
    // A band that cites a rules section IS the control now (the citation is
    // a corner label, not a chip), and both the kind heading and the citation
    // live in a .band-head row - so the band's own sentence is the first
    // .body paragraph after that row, not .band-text's first child.
    const text = /<div class="band-text"><div class="band-head">[\\s\\S]*?<\\/div><p class="body">([\\s\\S]*?)<\\/p>/.exec(f);
    const chip = /data-act="open_rules" data-arg="([^"]*)"/.exec(f);
    return text && chip ? [chip[1], unesc(text[1])] : null;
  }).filter(Boolean);
}

// A rules_map.js id -> the phases.js STEPS label covering it. Ranges are
// parsed off the label itself ("1.2-1.3 Gain resources...", "6.7-6.10 Player
// attacks"), and a step letter is dropped first ("6.8a" -> 6.8), so this
// reads the generated file rather than restating it.
function stepLabelFor(id) {
  const [maj, min] = id.replace(/[a-z]+$/, "").split(".").map(Number);
  for (const s of STEPS) {
    const m = /^(\\d+)\\.(\\d+)(?:-(\\d+)\\.(\\d+))?\\s/.exec(s.label);
    if (!m) continue;
    const loMaj = Number(m[1]), loMin = Number(m[2]);
    const hiMaj = m[3] ? Number(m[3]) : loMaj, hiMin = m[3] ? Number(m[4]) : loMin;
    if (maj === loMaj && maj === hiMaj && min >= loMin && min <= hiMin) return s.label;
  }
  return null;
}

const CASES = [
  ["resource", "resource", null],
  ["planning", "planning", null],
  ["quest_commit", "quest_commit", null],
  ["quest_staging", "quest_staging", null],
  ["quest_resolution", "quest_resolution",
   g => { g.setWillpower(9); g.setStaging(2); g.resolveQuest(9, 2); g.pending_budget = 7; }],
  ["travel", "travel", null],
  ["travel_blocked", "travel", g => g.travelTo(4, 0, "Forest Gate")],
  ["enc_optional", "enc_optional", null],
  ["enc_checks", "enc_checks", null],
  ["combat_shadow", "combat_shadow", null],
  ["combat_enemy", "combat_enemy", null],
  ["combat_player", "combat_player", null],
  ["refresh", "refresh", null],
  ["round_end", "round_end", null],
];

const bands = {};
for (const [key, view, setup] of CASES) {
  const g = new GameState(4, 25); g.advanceView(); g.enterView(view);
  if (setup) setup(g);
  bands[key] = chipBands(renderPane(g, newUi()));
}
const ids = [...new Set(Object.values(bands).flat().map(b => b[0]))];
const labels = {};
for (const id of ids) labels[id] = stepLabelFor(id);
console.log(JSON.stringify({ bands, labels, summarised: Object.keys(SECTION_SUMMARY) }));
""")
    assert set(js["bands"]) == set(PANE_CHIPS), (sorted(js["bands"]), sorted(PANE_CHIPS))
    for key, expected in PANE_CHIPS.items():
        got = js["bands"][key]
        assert [g[0] for g in got] == [e[0] for e in expected], (
            "%s emits chips %r, expected %r" % (key, got, expected))
        for (sec_id, label, opening), (got_id, got_text) in zip(expected, got):
            assert got_text.startswith(opening), (
                "%s's §%s chip sits on a band reading %r, expected it to open %r"
                % (key, sec_id, got_text, opening))
            assert js["labels"][sec_id] == label, (
                "§%s is %r in phases.js, but the table under test says %r"
                % (sec_id, js["labels"][sec_id], label))
    emitted = {b[0] for bs in js["bands"].values() for b in bs}
    missing = sorted(emitted - set(js["summarised"]))
    assert not missing, (
        "these live chips open the Rules sheet with no Timing summary: %r" % missing)



def test_section_summary_text_matches_the_pane_it_is_quoting():
    """Fix round 1, finding 3: SECTION_SUMMARY's whole reason to exist is
    "the sheet and the pane can never say two different things about the
    same rule" (rules_map.js's own comment) - assert that promise directly
    rather than trust it, by rendering, for every id in SECTION_SUMMARY, the
    one pane view that owns it (its own `view` field) and checking the
    summary's exact text is somewhere in that pane's own rendered HTML - not
    a plausible-looking paraphrase of it. Reads `spec.text` back out of the
    loaded module rather than re-typing an expected string per id, so this
    test itself can't drift from rules_map.js either.

    Also exercises the "tips" parity fix (1.4/3.5 must show
    ACTION_WINDOW_TIPS[view][0], not the old summaryFor()'s blanket
    `.join(" ")` of the whole array - see rules_map.js's bandTextFor), the
    four loop framings the M5 final review found unsummarised (2.2, 5.3,
    6.3, 6.8a - LOOP_FLOW[view].intro, drawn by loops.js), and 6.11's
    COMBAT_LAST_CHANCE.

    travel is rendered TWICE, because its first band is the one place a view
    swaps which copy it shows: TRAVEL.blocked (4.1) with a location already
    active, TRAVEL.open (4.2) without. Before the fix both ids resolved to
    TRAVEL.open, so 4.1's own chip opened a Timing block describing travel
    as on offer on the very pane that had just said there is none - and a
    single fresh-game render could never catch it, since a fresh game has no
    active location. Which id belongs to which band is pinned exactly by
    test_every_pane_chip_cites_the_step_its_own_band_describes above."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
import { SECTION_SUMMARY } from "./rules_map.js";
import { esc } from "./dom.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
// Every state a view can render a DIFFERENT band in - travel is the only
// one today. A summary must appear on at least one of its view's variants.
const VARIANTS = { travel: [null, g => g.travelTo(4, 0, "Forest Gate")] };
const rendered = {};
const out = {};
for (const [id, spec] of Object.entries(SECTION_SUMMARY)) {
  if (!(spec.view in rendered)) {
    rendered[spec.view] = (VARIANTS[spec.view] ?? [null]).map(setup => {
      const g = new GameState(4, 25); g.advanceView(); g.enterView(spec.view);
      if (setup) setup(g);
      return renderPane(g, newUi());
    });
  }
  // The band's own text is HTML-escaped by h`` on the way into the pane
  // (dom.js's esc()), so a summary containing a quote or apostrophe (e.g.
  // combat_shadow's "that player's engaged enemies") never matches a raw
  // includes() against the unescaped spec.text - compare against the same
  // escaped form the pane itself renders.
  out[id] = { view: spec.view, text: spec.text,
              present: rendered[spec.view].some(html => html.includes(esc(spec.text))) };
}
console.log(JSON.stringify(out));
""")
    assert len(js) >= 20, "expected every SECTION_SUMMARY id to be exercised: %r" % js
    for sec_id, r in js.items():
        assert r["present"], (
            "SECTION_SUMMARY[%r]'s text %r does not appear verbatim on the %r pane"
            % (sec_id, r["text"], r["view"]))


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
    "PROPAGATES on failure... returns null" contract) DROPS the Official text
    block rather than a blank sheet or a crash (CLAUDE.md iron rule 4: no
    placeholder rules text ships). It used to draw the heading "Official
    text" over the sentence "The official text is not in this build." - a
    heading for content that does not exist, and an apology for it. The sheet
    says what it does have instead: the tracker's own summary, headed as
    such, and the footer's link to the book - which still works, falling back
    to copy.js's pinned page URL since there is no ui.rules.source.page to
    prefer.

    Fix round 1, finding 2 (ruling reversed from the original brief's
    wording): the spec's own Risks section says a build shipped without the
    rules artifact "shows the summary and the product-page link" - so the
    Timing block and the Related prev/next chips must SURVIVE a null
    ui.rules (both are static lookups, SECTION_SUMMARY/STEP_ORDER, that
    never read `rules` at all); only the verbatim official excerpt degrades.
    Also asserts no `.rules-body` wrapper renders - the class the real
    official-text paragraphs are wrapped in (sheet_rules.js's officialBlock)
    - so there is no way a fabricated rules paragraph could sneak onto the
    unavailable path."""
    js = node("""
import { renderRulesSheet } from "./sheet_rules.js";
import { CHROME, rulesPageUrl } from "./copy.js";
import { PHASE_FRAMEWORK } from "../../js/viewcopy.js";
import { esc } from "./dom.js";
const ui = { sheet: { kind: "rules", section: "6.2" }, rules: null };
const html = renderRulesSheet({}, ui);
console.log(JSON.stringify({
  html,
  noApology: !/Official text/.test(html) && !/not in this build/.test(html),
  hasLink: html.includes('href="' + rulesPageUrl + '"') && html.includes('target="_blank"'),
  // 6.2 "Deal shadow cards" summarises with the band that describes dealing
  // them - PHASE_FRAMEWORK, not the bare "Responses." window band, which is
  // 6.1 (the M5 final review's inversion fix).
  timingPresent: html.includes(esc(PHASE_FRAMEWORK.combat_shadow)),
  relatedChips: [...html.matchAll(/data-act="open_rules" data-arg="([^"]*)"/g)].map(m => m[1]),
  noOfficialBody: !html.includes('class="rules-body"'),
}));
""")
    assert js["noApology"], js["html"]
    assert js["hasLink"], js["html"]
    assert js["timingPresent"], "the Timing block must survive a missing rules build: %r" % js["html"]
    assert "6.1" in js["relatedChips"] and "6.3" in js["relatedChips"], (
        "Related prev/next chips must survive a missing rules build: %r" % js["relatedChips"])
    assert js["noOfficialBody"], "no fabricated rules text may render when ui.rules is null: %r" % js["html"]


def test_open_rules_with_an_empty_arg_opens_nothing():
    """M5 final review, minor: every open_rules chip today passes a real
    section id or a "term:" arg, but the handler seated a sheet from
    whatever it got - an empty arg produced `{kind:"rules", section:""}`, a
    modal headed "§" with no official text, no summary and no Related chips.
    Declining is `false`, not `null`: this handler owns the act, it just has
    nothing to open, and dispatch() (actions.js) treats null as "keep
    looking" - which would end at its own `return false` anyway, but says
    the wrong thing."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
const empty = perform(g, ui, "open_rules", "");
const afterEmpty = ui.sheet;
const real = perform(g, ui, "open_rules", "6.2");
console.log(JSON.stringify({ empty, afterEmpty, real, sheet: ui.sheet }));
""")
    assert js["empty"] is False and js["afterEmpty"] is None
    assert js["real"] is True and js["sheet"] == {"kind": "rules", "section": "6.2"}


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


# The fixture below stands in for a scenario's real tips.json entry
# (build_tips.py's distillation) - a placeholder attribution URL, never a
# real one, per CLAUDE.md's data policy on verbatim vs. derived content:
# this is a fixture for a test, not something that ships.
_NOTES_FIXTURE = """{ "passage-through-mirkwood": {
  attribution: { name: "Vision of the Palantir", url: "https://example.invalid/votp" },
  general: ["g1", "g2", "g3", "g4"],
  stages: { "2": ["s2a"] },
} }"""

_NOTES_FIXTURE_EMPTY_URL = """{ "the-withered-heath": {
  attribution: { name: "quests/the-withered-heath.md", url: "" },
  general: ["tip1", "tip2"],
  stages: {},
} }"""


def test_notes_panel_shows_general_tips_and_the_source_link_at_stage_one():
    """notesFor() (notes.js) falls back to a scenario's general tips when
    the current stage (1, the default) has no group of its own in the
    fixture - R9's first half. At most three show (the panel's own 3-item
    cap), and the citation is a real <a> carrying the fixture's own href and
    rel="noopener" - CLAUDE.md iron rule 4: this is tips.json's own text plus
    a link back to it, never a paraphrase.

    It is a CITATION, not a control: quiet LABEL ink at the trailing edge
    (primitives.js's sourceCite), not the bevelled chip a button wears. "More
    notes" beside it is a control, and keeps the chip."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25);
const ui = newUi();
ui.scenarioSlug = "passage-through-mirkwood";
ui.tips = %s;
const html = renderPane(g, ui);
console.log(JSON.stringify({
  html,
  hasNotes: html.includes('class="notes"'),
  hasG1: html.includes(">g1<"), hasG2: html.includes(">g2<"), hasG3: html.includes(">g3<"),
  hasG4: html.includes(">g4<"),
  hasHeader: html.includes("Notes \\u00b7 General"),
  linkHref: (html.match(/<a class="label cite" href="([^"]*)"/) || [])[1],
  hasNoopener: html.includes('rel="noopener"'),
  citeIsNotAChip: !/<a[^>]*class="[^"]*chip/.test(html),
}));
""" % _NOTES_FIXTURE)
    assert js["hasNotes"], js["html"]
    assert js["hasG1"] and js["hasG2"] and js["hasG3"], js["html"]
    assert not js["hasG4"], "the panel must cap at three tips"
    assert js["hasHeader"], js["html"]
    assert js["linkHref"] == "https://example.invalid/votp"
    assert js["hasNoopener"], js["html"]
    assert js["citeIsNotAChip"], "a citation must not wear a control's bevel"


def test_notes_panel_shows_the_current_stages_tips_over_general():
    """Once stage_n reaches a stage the fixture has its own group for,
    that group wins over general (R9) - here stage 2's single tip, scoped
    "Stage 2" via CHROME.scopeStage, not folded in alongside general."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25);
g.quest.stage_n = 2;
const ui = newUi();
ui.scenarioSlug = "passage-through-mirkwood";
ui.tips = %s;
const html = renderPane(g, ui);
console.log(JSON.stringify({
  html,
  hasS2a: html.includes(">s2a<"),
  hasHeader: html.includes("Notes \\u00b7 Stage 2"),
  hasG1: html.includes(">g1<"),
}));
""" % _NOTES_FIXTURE)
    assert js["hasS2a"], js["html"]
    assert js["hasHeader"], js["html"]
    assert not js["hasG1"], "a stage's own tips replace general, not add to them"


def test_open_notes_lists_every_group_general_then_stages_in_order():
    """acts_notes.js's open_notes seats {kind:"notes"}; sheet_notes.js's
    renderNotesSheet then lists notes.js's allNotes() in full - General
    first, then each stage in numeric order (R9's second half), with none of
    the panel's 3-item cap.

    The source is cited ONCE, at the foot. Every group in a scenario cites
    the same article, so a link per group printed the identical full-width
    bar under each of them - four of them on Passage Through Mirkwood, taking
    as much of the sheet as the notes did. The dedupe is by (name, url), so a
    tips.json that ever does attribute per stage still lists each source it
    actually used."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { dispatch, newUi } from "./actions.js";
import { renderSheet } from "./sheets.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25);
const ui = newUi();
ui.scenarioSlug = "passage-through-mirkwood";
ui.tips = %s;
const opened = dispatch(g, ui, "open_notes", "");
const html = renderSheet(g, ui);
console.log(JSON.stringify({
  opened, kind: ui.sheet.kind, html,
  hasG4: html.includes(">g4<"),
  hasS2a: html.includes(">s2a<"),
  generalBeforeStage: html.indexOf("General") < html.indexOf("Stage 2"),
  citeCount: (html.match(/class="label cite"/g) || []).length,
  citeAfterNotes: html.indexOf("cite-row") > html.lastIndexOf(">s2a<"),
}));
""" % _NOTES_FIXTURE)
    assert js["opened"] is True
    assert js["kind"] == "notes"
    assert js["hasG4"], "the sheet carries no 3-item cap"
    assert js["hasS2a"], js["html"]
    assert js["generalBeforeStage"], "General must list before Stage 2"
    assert js["citeCount"] == 1, "one source, cited once - not once per group"
    assert js["citeAfterNotes"], "the citation sits at the foot, under the notes"


def test_notes_panel_renders_nothing_for_a_scenario_absent_from_tips():
    """A scenario tips.json has never heard of - or a bare game with no
    scenario at all (ui.scenarioSlug/ui.tips both null, newUi()'s default)
    - renders no .notes markup, never an empty shell (R9: "a scenario
    absent from tips renders no panel")."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const ui = newUi();
ui.scenarioSlug = "some-other-quest";
ui.tips = %s;
const html = renderPane(new GameState(2, 25), ui);
const bareHtml = renderPane(new GameState(2, 25), newUi());
console.log(JSON.stringify({
  hasNotes: html.includes('class="notes"'),
  bareHasNotes: bareHtml.includes('class="notes"'),
}));
""" % _NOTES_FIXTURE)
    assert not js["hasNotes"], "a scenario slug absent from tips must render no panel at all"
    assert not js["bareHasNotes"], "a bare game with no scenario must render no panel at all"


def test_notes_panel_renders_source_as_plain_label_when_url_is_empty():
    """When attribution.url is empty (tips from quests/*.md callouts),
    render the source name as a plain <span class="label">, not as an <a>
    anchor. The name is still present."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25);
const ui = newUi();
ui.scenarioSlug = "the-withered-heath";
ui.tips = %s;
const html = renderPane(g, ui);
console.log(JSON.stringify({
  html,
  hasNotes: html.includes('class="notes"'),
  hasTip: html.includes(">tip1<"),
  hasName: html.includes("quests/the-withered-heath.md"),
  hasAnchor: html.includes('<a class="chip chip-tan"'),
}));
""" % _NOTES_FIXTURE_EMPTY_URL)
    assert js["hasNotes"], js["html"]
    assert js["hasTip"], js["html"]
    assert js["hasName"], "the source name must still be present"
    assert not js["hasAnchor"], "empty URL must render as plain label, not anchor"


def test_location_picker_group_header_shows_the_sets_own_icon():
    """Task 5: sheet_locpick.js's group header leads with the set's own icon
    (seticon.js) before its LABEL name - sourced from the SVGs
    tools/build_icons.py exports beside icons.json (docs/data/icons/svg/
    <slug>.svg, commit abfbd80), addressed by quest_catalog.js's slugify()
    applied to the printed set name (seticon.js's own rule, not a second
    copy of build_icons._slug - see the slug-parity test below)."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(1, 25); g.advanceView(); g.enterView("travel");
const ui = newUi();
ui.locations = [{ id: "a", name: "Old Forest Road", points: 3, threat: 1, set: "Passage Through Mirkwood" }];
perform(g, ui, "open_locpick", "new::play");
console.log(JSON.stringify({ html: layout(g, ui) }));
""")
    assert 'class="seticon"' in js["html"]
    assert '<img src="' in js["html"]
    assert 'icons/svg/passage-through-mirkwood.svg"' in js["html"]


def test_stage_pill_shows_the_scenario_set_icon_only_when_named():
    """rail.js's stage pill (Task 5): the scenario's own set icon goes
    before the "Stage n" label when `game.scenario?.name` is set. A bare
    game with no preloaded scenario (newUi()'s default GameState) has no
    name to build a slug from at all, so the pill omits the icon rather than
    guessing - that is a different case from a NAMED set with no matching
    SVG file, which is the fallback-glyph path seticon.js's own comment
    documents, not this one."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderRail } from "./rail.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const named = new GameState(1, 25); named.advanceView();
named.preloadScenario({ slug: "x", name: "Passage Through Mirkwood" }, [{ stage: 1, cards: [{}] }]);
const bare = new GameState(1, 25); bare.advanceView();
console.log(JSON.stringify({
  namedHtml: renderRail(named, newUi()),
  bareHtml: renderRail(bare, newUi()),
}));
""")
    assert 'class="seticon"' in js["namedHtml"]
    assert 'icons/svg/passage-through-mirkwood.svg"' in js["namedHtml"]
    assert 'class="seticon"' not in js["bareHtml"]


def test_seticon_slug_matches_build_icons_pack_naming_for_the_three_mirkwood_sets():
    """seticon.js derives its filename by applying quest_catalog.js's own
    slugify() to the printed SET NAME - deliberately not a client-side copy
    of tools/build_icons.py's _slug() (which instead lowercases the PACK'S
    OWN FILENAME). The two rules give the same slug for a plain multi-word
    name with no punctuation - the shape build_icons._slug's docstring names
    as its own convention ("passage_through_mirkwood.svg" ->
    "passage-through-mirkwood") - which is pinned here for the three sets
    task-5-brief.md calls out, so a future edit to either rule can't drift
    silently. An apostrophe (e.g. "The Steward's Fear") is a known, accepted
    mismatch class - see seticon.js's own comment - and is deliberately not
    asserted here; that case just falls back to the placeholder glyph."""
    import tools.build_icons as build_icons
    names = ["Passage Through Mirkwood", "Dol Guldur Orcs", "Spiders of Mirkwood"]
    expected = [build_icons._slug(n.lower().replace(" ", "_") + ".svg") for n in names]
    js = node("""
import { slugify } from "../../js/quest_catalog.js";
console.log(JSON.stringify(%s.map(slugify)));
""" % json.dumps(names))
    assert js == expected


# --- Task 6: card images ----------------------------------------------------

_PREFIX = "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/"
_CARD_ID = "51223bd0-ffd1-11df-a976-0801200c9099"     # Old Forest Road, Core Set


def test_location_picker_rows_carry_the_card_art_from_the_pinned_prefix():
    """Task 6: a picker row leads with the location's own printed art. The
    URL is the pinned image prefix (tools/data/cardDb.SOURCE.txt's
    `image_prefix=`, surfaced as index.json's `imagePrefix` and seated on
    `ui.imagePrefix` by app.js) joined to the FILENAME the card record
    carries - not one rebuilt from the id, because 24 of 1016 catalog
    locations print on the back of a two-sided card and carry "<id>.B.jpg".

    The name and the printed threat/quest points live in the figure's
    caption, so they are written once: when the art cannot be shown the
    caption is the whole row and it still says which location this is."""
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
function pick(prefix) {
  const g = new GameState(1, 25); g.advanceView(); g.enterView("travel");
  const ui = newUi();
  ui.imagePrefix = prefix;
  ui.locations = [{ id: "%s", image: "%s.jpg", name: "Old Forest Road",
                    points: 3, threat: 1, set: "Passage Through Mirkwood" },
                  { id: "b-side", image: "b-side.B.jpg", name: "Shrine to Morgoth",
                    points: 4, threat: 2, set: "Passage Through Mirkwood" },
                  { id: "no-image-field", name: "Forest Gate",
                    points: 4, threat: 2, set: "Passage Through Mirkwood" },
                  { name: "Hand-typed", points: 1, threat: 0, set: "" }];
  perform(g, ui, "open_locpick", "new::play");
  return layout(g, ui);
}
console.log(JSON.stringify({ withArt: pick("%s"), noPrefix: pick(null) }));
""" % (_CARD_ID, _CARD_ID, _PREFIX))
    art = js["withArt"]
    # A card with art is a BUTTON now: every card on screen opens the quick
    # view. The row around it is a plain div for the same reason - a <button>
    # inside a <button> is invalid, and app.js delegates on the closest
    # [data-act], so the card takes its own taps and the rest of the row still
    # selects the location.
    assert '<button type="button" class="card-frame" data-act="open_card"' in art
    assert 'class="locpick-row" data-act="locpick_row"' in art
    assert '<button type="button" class="locpick-row"' not in art
    assert 'src="%s%s.jpg"' % (_PREFIX, _CARD_ID) in art
    assert 'loading="lazy"' in art and 'alt=""' in art
    # The printed filename wins over "<id>.jpg" - a back-face location must
    # not render the front of the card.
    assert 'src="%sb-side.B.jpg"' % _PREFIX in art
    # An entry with no `image` field at all (a picker entry from a game saved
    # before quest_catalog carried one) falls back to "<id>.jpg" rather than
    # losing its picture.
    assert 'src="%sno-image-field.jpg"' % _PREFIX in art
    # An entry with neither is caption-only - no <img> to 404.
    # An entry with neither is caption-only - no <img> to 404, and nothing to
    # enlarge either, so it stays an inert <figure>. A control that opens an
    # empty modal is worse than no control.
    assert '<figure class="card-frame"><figcaption class="body">Hand-typed' in art
    # The caption is the name plus the numbers the row has always shown.
    assert ">Old Forest Road <span class=\"card-copies\">· threat 1 · 3 quest points</span>" in art

    # No pinned prefix (an index built before the pin, or a catalog that
    # would not load): not one card <img> anywhere, and the rows still read.
    # (The set-group header's own icon is a separate <img>; it is unaffected.)
    assert 'class="card-frame"><img' not in js["noPrefix"]
    # With no prefix there is no URL to enlarge, so no card is tappable.
    assert 'data-act="open_card"' not in js["noPrefix"]
    assert '<figure class="card-frame"><figcaption' in js["noPrefix"]
    assert ('Old Forest Road <span class="card-copies">· threat 1 · 3 quest points'
            in js["noPrefix"])


def test_the_image_prefetch_fires_on_begin_setup_not_on_the_pick():
    """The spec's prefetch is "Begin setup prefetches". It used to fire from
    pick_scenario, which was correct when picking a scenario STARTED the
    game - milestone 6's Task 2 split that act in two, so picking now only
    opens the Scenario overview, a screen a player may well back out of to
    read another quest. Left there it spent the bandwidth on every scenario
    browsed rather than the one committed to (M5 final review).

    app.js is the one tablet module that is not a pure string builder (it
    touches navigator, db and the DOM), so node() cannot drive it - this
    reads the source and checks every prefetchCardImages() CALL sits inside
    the begin_setup branch, between it and the act that follows."""
    src = open(os.path.join(ROOT, "docs", "tablet", "js", "app.js"), encoding="utf-8").read()
    begin = src.index('if (act === "begin_setup") {')
    after = src.index('if (act === "copy_log")', begin)
    pick = src.index('if (act === "pick_scenario") {')
    calls = [m.start() for m in re.finditer(r"(?<!function )prefetchCardImages\(", src)]
    assert calls, "no prefetchCardImages() call site left in app.js"
    for at in calls:
        assert begin < at < after, (
            "prefetchCardImages() at offset %d is outside the begin_setup branch "
            "(begin_setup at %d, pick_scenario at %d)" % (at, begin, pick))


def test_card_image_urls_cover_the_scenario_and_every_set_it_gathers():
    """`imageUrls(bundle, prefix)` is what app.js posts to the service worker
    when the players commit to a scenario. This is the FALLBACK path - a
    bundle with no `images` key at all, an old save or a twin mid-upgrade -
    which has to keep covering the same union locationsFor() does - a
    scenario's own scenarios/<slug>.json holds only cards whose encounterSet
    IS its set, so Passage Through Mirkwood's own file has 2 of its 6
    locations - which db.bundle() used to pin in two pieces: the scenario's
    own file (every encounter.* group, all card types) and `locations`, the
    already-flattened union across the gather list. See
    test_card_image_urls_prefers_the_pinned_images_list_when_present for the
    new bundle.images fast path this now falls back FROM.

    Each url once, and [] with no prefix so the worker is never asked to warm
    a cache it could not fill."""
    js = node("""
import { imageUrls, cardUrl } from "./cardimage.js";
const bundle = {
  scenario: { encounter: {
    location: [{ id: "own-1", image: "own-1.jpg" }, { id: "own-2", image: "own-2.jpg" }],
    enemy: [{ id: "enemy-1", image: "enemy-1.jpg" }],
    treachery: [{ id: "trick-1", image: "trick-1.jpg" }],
  } },
  locations: [
    { id: "own-1", image: "own-1.jpg" },              // already seen: once only
    { id: "gathered-1", image: "gathered-1.jpg" },
    { id: "gathered-2", image: "gathered-2.B.jpg" },  // a back-face location
    { id: "no-art" },                                 // no image field at all
    { id: "hotlink", image: "https://s3.amazonaws.com/hallofbeorn/x.jpg" },
  ],
};
console.log(JSON.stringify({
  urls: imageUrls(bundle, "%s"),
  noPrefix: imageUrls(bundle, null),
  emptyBundle: imageUrls({}, "%s"),
  idFallback: cardUrl("%s", { id: "plain" }),
  absoluteKept: cardUrl("%s", { image: "https://elsewhere.test/a.jpg" }),
  nothing: cardUrl("%s", {}),
}));
""" % (_PREFIX, _PREFIX, _PREFIX, _PREFIX, _PREFIX))
    p = _PREFIX
    assert js["urls"] == [
        p + "own-1.jpg", p + "own-2.jpg", p + "enemy-1.jpg", p + "trick-1.jpg",
        p + "gathered-1.jpg", p + "gathered-2.B.jpg", p + "no-art.jpg",
    ], "own set (every card type) then the gather list's, each url once"
    # A Hall of Beorn hotlink is not under the prefix, so sw.js's isImage()
    # could never serve it from the image cache - prefetching it is a wasted
    # request, not a warm one.
    assert not any("hallofbeorn" in u for u in js["urls"])
    assert js["noPrefix"] == [] and js["emptyBundle"] == []
    assert js["idFallback"] == p + "plain.jpg"
    assert js["absoluteKept"] == "https://elsewhere.test/a.jpg"
    assert js["nothing"] is None


def test_card_image_urls_prefers_the_pinned_images_list_when_present():
    """Task 6b's ruling: db.bundle() now pins `images` itself - every card,
    every type, across the scenario's own set AND its gathered sets
    (quest_catalog's cardImagesFor()/card_images_for()) - computed in the
    same pass that reads the gathered packs for `locations`, rather than
    imageUrls() reassembling a narrower union from `scenario`/`locations`
    after the fact. When `images` is present it is what wins outright, even
    if `scenario`/`locations` disagree with it - there is nothing left for
    imageUrls() to reconstruct."""
    js = node("""
import { imageUrls } from "./cardimage.js";
const bundle = {
  images: [
    { id: "own-1", image: "own-1.jpg" },
    { id: "gathered-1", image: "gathered-1.B.jpg" },
    { id: "gathered-1", image: "gathered-1.B.jpg" },  // duplicate: once only
    { id: "no-art" },                                 // no image field
    { id: "hotlink", image: "https://s3.amazonaws.com/hallofbeorn/x.jpg" },
  ],
  // Deliberately does NOT list "own-1"/"gathered-1" - proves images wins
  // outright rather than being unioned with the old scenario/locations shape.
  scenario: { encounter: { location: [{ id: "stale-only-here", image: "stale.jpg" }] } },
  locations: [],
};
console.log(JSON.stringify({
  urls: imageUrls(bundle, "%s"),
  noPrefix: imageUrls(bundle, null),
}));
""" % _PREFIX)
    p = _PREFIX
    assert js["urls"] == [p + "own-1.jpg", p + "gathered-1.B.jpg", p + "no-art.jpg"]
    assert "stale.jpg" not in " ".join(js["urls"]), \
        "images present must win outright, not merge with the old union"
    assert js["noPrefix"] == []
