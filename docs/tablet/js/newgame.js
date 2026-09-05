// The new-game / picker screen (Task 6): pick a player count, a starting
// threat per player, and a scenario from the official quest catalog - or
// resume a save already on disk. Pure string builder like every other
// tablet render function - no document/window, so tests/test_tablet.py can
// drive it under node. app.js owns every catalog fetch and the async
// new_game/ng_players/ng_threat/pick_scenario acts; this module only reads
// what it is handed via `ui.picker = { index, players, threats, hasSave,
// error }` and never touches storage or the network itself.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, counter } from "./primitives.js";
import { CYCLE_ORDER } from "../../js/quest_catalog.js";
import { icon } from "../../js/icons_svg.js";
import { THREAT_RED, THREAT_SHADOW } from "./palette.js";

// Mirrors quest_catalog.js's own (unexported) cycleRank: a cycle absent from
// CYCLE_ORDER sorts just before "Other" rather than falling off the end.
function cycleRank(cycle) {
  const i = CYCLE_ORDER.indexOf(cycle);
  return i === -1 ? CYCLE_ORDER.indexOf("Other") - 0.5 : i;
}

// Plain ordinal compare, not localeCompare - same reasoning as
// quest_catalog.js's byName (twin-stable sort).
function byOrderThenName(a, b) {
  if ((a.order == null) !== (b.order == null)) return a.order == null ? 1 : -1;
  if ((a.order ?? 0) !== (b.order ?? 0)) return (a.order ?? 0) - (b.order ?? 0);
  const an = a.name ?? "", bn = b.name ?? "";
  return an < bn ? -1 : an > bn ? 1 : 0;
}

// Quest-kind, official-source rows grouped by cycle (CYCLE_ORDER order) and
// sorted by play order then name within each group - the shape
// quest_catalog.js's groupByCycle produces for the twin's picker screens,
// but filtered on `kind` directly rather than `stageCount`: a "quest" row in
// the real catalog always carries at least one stage (build_card_data.py
// only stamps kind "quest" when a Quest card is present, and a scenario with
// one has a non-empty stages list), and filtering this way also reads
// correctly against a minimal/synthetic index that never set stageCount at
// all - groupByCycle's own `stageCount > 0` gate would silently drop such
// rows instead.
function scenarioGroups(index) {
  const scenarios = (index?.scenarios ?? [])
    .filter(s => s.kind === "quest" && (s.source ?? "official") === "official"
      && !(s.name ?? "").endsWith(" - Nightmare"));
  const groups = new Map();
  for (const scn of scenarios) {
    const cycle = scn.cycle ?? "Other";
    if (!groups.has(cycle)) groups.set(cycle, []);
    groups.get(cycle).push(scn);
  }
  return [...groups.keys()]
    .sort((a, b) => cycleRank(a) - cycleRank(b))
    .map(cycle => ({ cycle, scenarios: [...groups.get(cycle)].sort(byOrderThenName) }));
}

// One row: a button that starts the game (data-act="pick_scenario", arg the
// slug app.js hands to db.bundle()). A scenario name is a name a player
// reads - BODY (scale 2), sentence case as printed, never the chip's
// ALL-CAPS LABEL treatment - with the pack line under it at the body
// secondary tier. Scenario names and pack names are catalog text, not
// ours - h`` escapes both (names can carry an apostrophe, e.g. "The
// Steward's Fear").
function scenarioRow(scn) {
  return h`<button type="button" class="scenario-row" data-act="pick_scenario" data-arg="${scn.slug}">
<span class="body">${scn.name ?? ""}</span>
<span class="body secondary">${scn.pack ?? ""}</span>
</button>`;
}

function scenarioGroup(g) {
  const rows = g.scenarios.map(scenarioRow).join("");
  return h`<div class="scenario-group"><div class="label">${g.cycle}</div><div class="scenario-list">${raw(rows)}</div></div>`;
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

export function renderNewGame(ui) {
  const p = ui.picker ?? {};
  const players = p.players ?? 2;
  const threats = p.threats ?? Array(players).fill(25);
  const resumeChip = p.hasSave
    ? raw(chip({ act: "resume", label: CHROME.resume, tone: "gold" }))
    : "";
  const catalog = p.error
    ? h`<div class="well"><p class="body">${p.error}</p></div>`
    : scenarioGroups(p.index).map(scenarioGroup).join("");
  return h`<main class="pane newgame">
<div class="newgame-head"><h1 class="display">${CHROME.newGame}</h1>${resumeChip}</div>
<div class="newgame-section"><div class="label">${CHROME.players}</div>${raw(playerChips(players))}${raw(threatCounters(threats))}</div>
<div class="newgame-section"><div class="label">${CHROME.scenario}</div>${raw(catalog)}</div>
</main>`;
}
