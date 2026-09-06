// Step 1 of setup: the scenario chooser.
//
// Master/detail, not three columns of lists. The left column is a DRILL-IN -
// cycles, and tapping one replaces the list with that cycle's quests plus a
// way back up - and the right two thirds is the scenario's own detail,
// rendered by overview.js's renderScenarioDetail(). That is the same
// function the in-game "scenario details" route draws, so what a player
// reads while choosing and what they can re-read mid-game cannot drift.
//
// The three-column version this replaces put Players (count + threats) in
// the leftmost column, where it was the first thing on screen and the last
// thing anyone needed; it is its own step now (players_setup.js), after the
// quest is chosen.
//
// Reads only what it is handed via `ui.picker` ({ index, source, cycle,
// drill, slug, error }) plus `ui.overview` for the detail - never storage,
// never the network. app.js owns every fetch (pick_scenario awaits
// db.bundle()); acts_newgame.js owns the ui-only edits.
import { h, raw, cx, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { setupHead } from "./setup_head.js";
import { renderScenarioDetail } from "./overview.js";
import { cyclesFor, groupByCycle } from "../../js/quest_catalog.js";
import { setIcon } from "./seticon.js";

function sourceToggle(source) {
  const chips = [
    { key: "official", label: CHROME.official },
    { key: "alep", label: CHROME.community },
  ].map(s => chip({ act: "ng_source", arg: s.key, label: s.label, tone: s.key === source ? "gold" : "tan" })).join("");
  return h`<div class="source-toggle">${raw(chips)}</div>`;
}

// One cycle: BODY name (a name a player reads) plus its LABEL metadata -
// scenario count and the group's earliest release year, when known
// (cyclesFor's `date` is a "YYYY-MM" string or null - a synthetic/minimal
// index that never set releaseDate at all, same degrade as everywhere else
// that field is read). The trailing chevron says the row goes somewhere,
// which on a drill-in list is the whole contract of the row.
function cycleRow(g) {
  const year = g.date ? g.date.slice(0, 4) : "";
  const meta = year ? `${g.count} · ${year}` : String(g.count);
  return h`<button type="button" class="drill-row" data-act="ng_cycle" data-arg="${g.cycle}">
<span class="body">${g.cycle}</span>
<span class="label">${meta}</span>
<span class="drill-chev" aria-hidden="true">›</span>
</button>`;
}

// One scenario inside a cycle. Selected state is what tells the player which
// quest the detail on the right belongs to - without it the two halves of
// the screen read as unrelated. Scenario names are catalog text, not ours -
// h`` escapes them (names carry apostrophes, e.g. "The Steward's Fear").
function scenarioRow(scn, selected) {
  return h`<button type="button" class="${cx("drill-row", "drill-scenario", scn.slug === selected && "is-selected")}" data-act="pick_scenario" data-arg="${scn.slug}">
${raw(setIcon(scn.name ?? "", 26))}
<span class="body">${scn.name ?? ""}</span>
<span class="label">${(scn.stageCount ?? 0) === 1 ? CHROME.stagesCountOne : fmt(CHROME.stagesCount, scn.stageCount ?? 0)}</span>
</button>`;
}

// The list half. Two states, never both: the cycles, or one cycle's quests
// with a row back up to the cycles. The header row of the drilled-in state
// names the cycle you are inside - a list of quest names with no cycle
// heading is where "which cycle am I in?" becomes a guess.
function drillList(p, cycles, scenarios) {
  if (p.drill !== "scenarios") {
    return h`<div class="drill-list">${raw(cycles.map(cycleRow).join(""))}</div>`;
  }
  const back = h`<button type="button" class="drill-row drill-back" data-act="ng_cycles">
<span class="body">${CHROME.allCycles}</span></button>`;
  return h`<div class="drill-list">${raw(back)}
<div class="drill-heading label">${p.cycle ?? ""}</div>
${raw(scenarios.map(s => scenarioRow(s, p.slug)).join(""))}</div>`;
}

// The detail half before anything is picked. One sentence, BODY, saying what
// to do - not a description of the screen, and not an empty panel.
function emptyDetail() {
  return h`<div class="detail-empty"><p class="body secondary">${CHROME.chooseScenarioEmpty}</p></div>`;
}

export function renderNewGame(game, ui) {
  const p = ui.picker ?? {};
  const head = setupHead({
    step: 1, title: CHROME.chooseScenarioTitle, hint: CHROME.chooseScenarioHint,
    back: "go_home",
  });

  // A catalog that never loaded costs the player the rows, not the screen:
  // the error goes where the quests would have been, and the detail side
  // keeps its own empty state rather than showing the failure twice.
  if (p.error) {
    return h`<main class="pane setup">${raw(head)}<div class="setup-grid">
<div class="setup-list"><div class="well"><p class="body">${p.error}</p></div></div>
<div class="setup-detail">${raw(emptyDetail())}</div>
</div></main>`;
  }

  const source = p.source ?? "official";
  const cycles = cyclesFor(p.index ?? {}, source);
  const cycle = p.cycle ?? cycles[0]?.cycle ?? null;
  const group = groupByCycle(p.index?.scenarios ?? [], source).find(g => g.cycle === cycle);
  const scenarios = group?.scenarios ?? [];

  // The detail is the picked scenario's, and only when the seat app.js built
  // is actually for the row that is selected: ui.overview survives a game
  // (boot seats it read-only for a resumed save), so rendering it on the
  // strength of its mere existence would show the last game's quest under a
  // fresh picker.
  const picked = p.slug && ui.overview?.slug === p.slug;
  const detail = picked ? renderScenarioDetail(game, ui) : emptyDetail();
  const foot = picked
    ? h`<div class="cta-row detail-foot">${raw(cta({ act: "go_players", label: h`${CHROME.continueToPlayers}`, tone: "ok" }))}</div>`
    : "";

  return h`<main class="pane setup">${raw(head)}<div class="setup-grid">
<div class="setup-list">${raw(sourceToggle(source))}${raw(drillList({ ...p, cycle }, cycles, scenarios))}</div>
<div class="setup-detail">${raw(detail)}${raw(foot)}</div>
</div></main>`;
}
