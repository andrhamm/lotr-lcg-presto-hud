// The new-game / picker screen at tablet density (Task 2, milestone 6):
// three columns - Players, Cycles, Scenarios - instead of the phone-era
// flat list. app.js owns every catalog fetch and the async new_game/
// pick_scenario/begin_setup acts; acts_newgame.js owns the ui-only edits
// (ng_source/ng_cycle/ng_players/ng_threat±); this module only reads what
// it is handed via `ui.picker = { index, players, threats, source, cycle,
// error }` and never touches storage or the network itself. Cycle/scenario
// grouping is quest_catalog.js's own groupByCycle/cyclesFor - the exact
// logic the twin's picker screens use, not a second copy of it - so the
// nightmare/zero-stage exclusions live in one place. (There is no resume
// path here yet - a resumed save skips this screen entirely, straight to
// "play"; review finding M11 deleted a resume chip that a save flag never
// actually set.)
//
// Picking a scenario no longer starts the game: it opens the Scenario
// overview, which is overview.js's - including `overviewFor`, the pure seat
// app.js hands ui.overview, which lived here while that screen was still a
// placeholder (Task 3).
import { h, raw, cx, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, counter } from "./primitives.js";
import { cyclesFor, groupByCycle } from "../../js/quest_catalog.js";
import { icon } from "../../js/icons_svg.js";
import { setIcon } from "./seticon.js";
import { THREAT_RED, THREAT_SHADOW } from "./palette.js";

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
// that field is read).
function cycleRow(g, selectedCycle) {
  const year = g.date ? g.date.slice(0, 4) : "";
  const meta = year ? `${g.count} · ${year}` : String(g.count);
  return h`<button type="button" class="${cx("cycle-row", g.cycle === selectedCycle && "is-selected")}" data-act="ng_cycle" data-arg="${g.cycle}">
<span class="body">${g.cycle}</span>
<span class="label">${meta}</span>
</button>`;
}

// One scenario: its set icon + name (BODY, sentence case as printed - never
// the chip's ALL-CAPS LABEL treatment), the pack line under it at the body
// secondary tier, and the stage count as LABEL (dense tabular metadata, not
// a sentence a player reads). Scenario names and pack names are catalog
// text, not ours - h`` escapes both (names can carry an apostrophe, e.g.
// "The Steward's Fear").
function scenarioRow(scn) {
  return h`<button type="button" class="scenario-row" data-act="pick_scenario" data-arg="${scn.slug}">
<div class="scenario-head">${raw(setIcon(scn.name ?? "", 28))}<span class="body">${scn.name ?? ""}</span></div>
<span class="body secondary">${scn.pack ?? ""}</span>
<span class="label">${fmt(CHROME.stagesCount, scn.stageCount ?? 0)}</span>
</button>`;
}

function playerChips(count) {
  const chips = [1, 2, 3, 4].map(n => chip({
    act: "ng_players", arg: n, label: String(n), tone: n === count ? "gold" : "tan",
    extraClass: "chip-square",
  })).join("");
  return h`<div class="player-chips">${raw(chips)}</div>`;
}

function threatCounters(threats) {
  // Plain template, not h`` - counter() escapes `label` itself (see
  // primitives.js); pre-escaping here would double-escape it. Numerals and
  // CHROME.threat carry nothing that needs escaping anyway, but the two
  // escaping layers must stay each other's job, not stacked.
  const cells = threats.map((t, i) => counter({
    label: h`P${i + 1} ${CHROME.threat}`,
    icon: icon("THREAT", 34, THREAT_RED, THREAT_SHADOW),
    value: t, act: "ng_threat", arg: i,
  })).join("");
  return h`<div class="threat-row">${raw(cells)}</div>`;
}

function playersColumn(players, threats) {
  return h`<div class="newgame-col newgame-players">
<div class="label">${CHROME.players}</div>
${raw(playerChips(players))}
${raw(threatCounters(threats))}
</div>`;
}

export function renderNewGame(ui) {
  const p = ui.picker ?? {};
  const players = p.players ?? 2;
  const threats = p.threats ?? Array(players).fill(25);
  const playersCol = playersColumn(players, threats);

  if (p.error) {
    const cyclesCol = h`<div class="newgame-col newgame-cycles"><div class="label">${CHROME.cycles}</div></div>`;
    const scenariosCol = h`<div class="newgame-col newgame-scenarios"><div class="label">${CHROME.scenarios}</div><div class="well"><p class="body">${p.error}</p></div></div>`;
    return h`<main class="pane newgame"><div class="newgame-grid">${raw(playersCol)}${raw(cyclesCol)}${raw(scenariosCol)}</div></main>`;
  }

  const source = p.source ?? "official";
  const cycles = cyclesFor(p.index ?? {}, source);
  const cycle = p.cycle ?? cycles[0]?.cycle ?? null;
  const cyclesCol = h`<div class="newgame-col newgame-cycles">
<div class="label">${CHROME.cycles}</div>
${raw(sourceToggle(source))}
<div class="cycle-list">${raw(cycles.map(g => cycleRow(g, cycle)).join(""))}</div>
</div>`;

  const group = groupByCycle(p.index?.scenarios ?? [], source).find(g => g.cycle === cycle);
  const scenarios = group?.scenarios ?? [];
  const scenariosCol = h`<div class="newgame-col newgame-scenarios">
<div class="label">${CHROME.scenarios}</div>
<div class="scenario-list">${raw(scenarios.map(scenarioRow).join(""))}</div>
</div>`;

  return h`<main class="pane newgame"><div class="newgame-grid">${raw(playersCol)}${raw(cyclesCol)}${raw(scenariosCol)}</div></main>`;
}
