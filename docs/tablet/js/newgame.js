// Step 1 of setup: the scenario chooser.
//
// Master/detail, not three columns of lists. The left column is a DRILL-IN -
// cycles, and tapping one replaces the list with that cycle as a clearable
// filter above its own quests - and the right two thirds is the scenario's
// own detail,
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
import { stagePointsShape } from "./xshape.js";
import { branchName } from "./resolve_step.js";

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

// One scenario inside a cycle: its set icon and its name, and nothing else.
// The stage count used to ride along on the right; it is metadata about a
// quest you have not chosen yet, it does not help you choose, and the detail
// beside the list prints it (and the stages themselves) the moment you do.
//
// Selected state is what tells the player which quest the detail on the right
// belongs to - without it the two halves of the screen read as unrelated.
// Scenario names are catalog text, not ours - h`` escapes them (names carry
// apostrophes, e.g. "The Steward's Fear").
function scenarioRow(scn, selected) {
  return h`<button type="button" class="${cx("drill-row", "drill-scenario", scn.slug === selected && "is-selected")}" data-act="pick_scenario" data-arg="${scn.slug}">
${raw(setIcon(scn.name ?? "", 36))}
<span class="body">${scn.name ?? ""}</span>
</button>`;
}

// The list half. Two states, never both.
//
// At the top: the source toggle and every cycle.
//
// Drilled in: the chosen cycle is a FILTER you can see and clear, not a
// heading - CYCLE, the cycle itself on a row with an X, then SCENARIOS and
// the quests inside it. Tapping the row clears the filter and puts the cycle
// list back. (The whole row is the target, not just the glyph: the X says
// what the row does, and a 20px hit area on a table would be a miss waiting
// to happen.)
//
// The source toggle is NOT drawn here. Official/Community chooses which
// catalog the cycle list comes from, and once a cycle is chosen that question
// is already answered - leaving the toggle up offers a control that would
// silently throw away the selection under it.
function drillList(p, cycles, scenarios) {
  if (p.drill !== "scenarios") {
    return h`${raw(sourceToggle(p.source ?? "official"))}
<div class="label">${CHROME.cycles}</div>
<div class="drill-list">${raw(cycles.map(cycleRow).join(""))}</div>`;
  }
  return h`<div class="label">${CHROME.cycleOne}</div>
<button type="button" class="drill-row drill-current" data-act="ng_cycles">
<span class="body">${p.cycle ?? ""}</span>
<span class="drill-x" aria-hidden="true">✕</span>
</button>
<div class="label">${CHROME.scenarios}</div>
<div class="drill-list">${raw(scenarios.map(s => scenarioRow(s, p.slug)).join(""))}</div>`;
}

// The chosen scenario's stages, under the scenario list. Overview is the
// first row and the default, so a scenario that has just loaded shows the
// whole-quest view and every stage is one tap away - rather than the three
// repeated STAGE blocks the middle column used to carry, which is what this
// section replaced.
//
// A stage's own points are LABEL metadata beside its name, and a stage that
// advances on a condition prints no number at all (never a 0 - xshape.js's
// stagePointsShape carries the reasoning; ~137 of ~400 stage cards are this
// kind). `stages` here is the bundle's, so this list is exactly what the
// detail can draw.
function stageRow(label, name, meta, arg, selected) {
  return h`<button type="button" class="${cx("drill-row", "stage-row", selected && "is-selected")}" data-act="ng_stage" data-arg="${arg}">
${label ? raw(h`<span class="label stage-n">${label}</span>`) : ""}
<span class="body">${name}</span>
${meta ? raw(h`<span class="label">${meta}</span>`) : ""}
</button>`;
}

function stagesSection(stages, selected) {
  const rows = [stageRow(null, CHROME.overview, null, "overview", selected === "overview")];
  stages.forEach((st, i) => {
    const n = st.stage ?? i + 1;
    const card = (st.cards ?? [])[0];
    const shape = card ? stagePointsShape(card) : null;
    const meta = shape === "number"
      ? fmt(CHROME.questPointsShort, card.questPoints) : CHROME.noPoints;
    // A branch stage has several possible cards; the row names the stage, not
    // one of the alternatives, because which one you get is not known here.
    const name = (st.cards ?? []).length > 1
      ? fmt(CHROME.stageAlternatives, (st.cards ?? []).length)
      : (card ? branchName(card) : "");
    rows.push(stageRow(fmt(CHROME.stageShort, n), name, meta, String(n), selected === String(n)));
  });
  return h`<div class="label">${CHROME.stagesHeader}</div>
<div class="drill-list stage-list">${raw(rows.join(""))}</div>`;
}

// The detail half before anything is picked. One sentence, BODY, saying what
// to do - not a description of the screen, and not an empty panel.
function emptyDetail() {
  return h`<div class="detail-empty"><p class="body secondary">${CHROME.chooseScenarioEmpty}</p></div>`;
}

export function renderNewGame(game, ui) {
  const p = ui.picker ?? {};
  const head = setupHead({ step: 1, title: CHROME.chooseScenarioTitle, back: "go_home" });

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

  const stages = picked ? (ui.overview?.bundle?.stages ?? []) : [];
  const stageList = picked ? stagesSection(stages, p.stage ?? "overview") : "";

  return h`<main class="pane setup">${raw(head)}<div class="setup-grid">
<div class="setup-list">${raw(drillList({ ...p, source, cycle }, cycles, scenarios))}${raw(stageList)}</div>
<div class="setup-detail">${raw(detail)}${raw(foot)}</div>
</div></main>`;
}
