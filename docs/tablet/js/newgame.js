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
import { setIcon, cycleIcon } from "./seticon.js";
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
${raw(cycleIcon(g.cycle, 30))}
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
// The row carries its own state icon on the right, the way the chosen cycle
// carries its ✕:
//
//   selected, not locked   a CHECKMARK - "this is the one" - which locks the
//                          choice and folds the rest of the list away.
//   locked                 an ✕, which unlocks and brings the list back.
//
// Locking is worth having because the list is long (the LotR Saga cycle runs
// to 18) and once you have chosen, every other row is just something in the
// way of the stages below.
//
// The row is a DIV with the act on it, not a <button>, because the icon
// inside it IS a button - nesting them is invalid markup that iOS resolves
// however it likes. app.js delegates on the closest [data-act], so the icon
// takes its own taps and the rest of the row still selects.
function scenarioRow(scn, selected, locked, pinTop) {
  const isSel = scn.slug === selected;
  // The SAME glyph treatment the chosen cycle's ✕ already uses (.drill-x) -
  // it was a chip before, which is a different shape, a different ground and
  // ALL-CAPS letterforms for what is the same kind of control in the same
  // column. One vocabulary: a square gold-edged glyph at the row's right.
  const mark = !isSel ? "" : h`<button type="button" class="drill-x" data-act="${locked ? "ng_unlock" : "ng_lock"}" data-arg="${scn.slug}">${locked ? CHROME.markUnlock : CHROME.markLock}</button>`;
  return h`<div class="${cx("drill-row", "drill-scenario", isSel && "is-selected", isSel && locked && "is-locked")}" data-act="pick_scenario" data-arg="${scn.slug}" role="button"${isSel ? raw(pin(pinTop)) : ""}>
${raw(setIcon(scn.name ?? "", 36))}
<span class="body">${scn.name ?? ""}</span>
${raw(mark)}
</div>`;
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
// The rail pins in a STACK: the CYCLE header, then the chosen cycle, then the
// SCENARIOS header, then the chosen scenario - each parking under the one
// above it rather than all of them fighting for `top: 0`. So both choices and
// both their headers stay on screen however far you scroll into a long list,
// and STAGES arrives underneath them instead of shoving them off.
//
// The offsets are computed here rather than written into the stylesheet
// because they depend on WHICH pins exist: with no scenario chosen there is
// no third pin, and a hard-coded top would leave a gap where it would have
// been. HEAD_H/ROW_H are style.css's own (.setup-list > .label height, and
// .drill-row's min-height plus the list's row gap).
const HEAD_H = 28;
// The ROW's own height, with no spacing added: the next pin has to sit flush
// against the bottom of the one above it. Counting the gap as well left an
// 8px slot between them where the scrolling list showed through.
const ROW_H = 60;
const pin = top => ` style="top:${top}px"`;

function drillList(p, cycles, scenarios) {
  if (p.drill !== "scenarios") {
    return h`${raw(sourceToggle(p.source ?? "official"))}
<div class="label"${raw(pin(0))}>${CHROME.cycles}</div>
<div class="drill-list">${raw(cycles.map(cycleRow).join(""))}</div>`;
  }
  // While locking, the rows are still drawn - with the class that animates
  // them away - so there is something to animate. app.js flips to the locked
  // state when the animation has run; a list that simply vanished would give
  // the eye nothing to follow from the list to the choice.
  const rows = (p.locked && !p.locking)
    ? scenarios.filter(s => s.slug === p.slug)
    : scenarios;
  // Collapsing bottom-up: the last row goes first and the fold travels
  // upward, so the chosen row is left standing rather than being the only
  // thing that survives a simultaneous disappearance. Delay is capped so a
  // long cycle (the LotR Saga's 18) does not take a second to settle.
  const last = rows.length - 1;
  const list = rows.map((s, i) => {
    const row = scenarioRow(s, p.slug, p.locked, HEAD_H * 2 + ROW_H);
    if (!p.locking || s.slug === p.slug) return row;
    const delay = Math.min((last - i) * 16, 160);
    return h`<div class="rail-fold" style="animation-delay:${delay}ms">${raw(row)}</div>`;
  }).join("");
  return h`<div class="label"${raw(pin(0))}>${CHROME.cycleOne}</div>
<div class="drill-row drill-current" data-act="ng_cycles" role="button"${raw(pin(HEAD_H))}>
${raw(cycleIcon(p.cycle ?? "", 30))}
<span class="body">${p.cycle ?? ""}</span>
<span class="drill-x" aria-hidden="true">✕</span>
</div>
<div class="label"${raw(pin(HEAD_H + ROW_H))}>${CHROME.scenarios}</div>
<div class="${cx("drill-list", p.locking && "is-locking")}">${raw(list)}</div>`;
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
  const top = HEAD_H * 3 + ROW_H * 2;
  return h`<button type="button" class="${cx("drill-row", "stage-row", selected && "is-selected")}" data-act="ng_stage" data-arg="${arg}"${selected ? raw(pin(top)) : ""}>
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
  return h`<div class="label"${raw(pin(HEAD_H * 2 + ROW_H * 2))}>${CHROME.stagesHeader}</div>
<div class="drill-list stage-list">${raw(rows.join(""))}</div>`;
}

// The detail half before anything is picked. One sentence, BODY, saying what
// to do - not a description of the screen, and not an empty panel.
function emptyDetail() {
  return h`<div class="detail-empty"><p class="body secondary">${CHROME.chooseScenarioEmpty}</p></div>`;
}

// What the app bar says on this screen. Before a pick there is nothing to
// name but the task; after it, the scenario is the subject and the stage is a
// chip beside it - never concatenated into the title, so the title element
// stays one thing that changes rather than a string that grows.
//
// The metadata line drops the pack when the cycle already contains it ("Core
// Set" inside "Core Set (Mirkwood Paths)"): the breadcrumb printed both, which
// is how it came to be four items long and two of them the same words.
function barFor(ui, picked, openCycle) {
  // Before a scenario is picked the band still has something true to show: the
  // cycle you are inside.
  if (!picked) return { title: CHROME.chooseScenarioTitle,
                        mark: openCycle ? cycleIcon(openCycle, 56) : null };
  const ov = ui.overview ?? {};
  const entry = ov.entry ?? {};
  const name = entry.name ?? ov.bundle?.scenario?.name ?? "";
  const count = entry.stageCount ?? (ov.bundle?.stages ?? []).length;
  const stagesLabel = count
    ? (count === 1 ? CHROME.stagesCountOne : fmt(CHROME.stagesCount, count)) : "";
  const cycle = entry.cycle ?? "";
  const pack = entry.pack && !cycle.includes(entry.pack) ? entry.pack : "";
  return {
    title: name, icon: name,
    meta: [pack, cycle, stagesLabel].filter(Boolean).join(" · "),
  };
}

export function renderNewGame(game, ui) {
  const p = ui.picker ?? {};

  // A catalog that never loaded costs the player the rows, not the screen:
  // the error goes where the quests would have been, and the detail side
  // keeps its own empty state rather than showing the failure twice.
  if (p.error) {
    const head = setupHead({ title: CHROME.chooseScenarioTitle,
                             back: "go_home", backLabel: CHROME.backToHome });
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

  const stages = picked ? (ui.overview?.bundle?.stages ?? []) : [];
  const stageList = picked ? stagesSection(stages, p.stage ?? "overview") : "";
  // Continue lives in the band, not at the foot of the pane. It is the step's
  // forward action, so it belongs with the step's other navigation - and a
  // full-width green bar across the bottom of a reference screen shouted
  // louder than anything it was letting you read.
  //
  // It is drawn whether or not it is armed. A control that appears only once
  // you have done the right thing cannot tell you that the thing exists; a
  // visible, plainly-inert one can. The disabled form carries NO data-act -
  // nothing for the delegation to catch - which is this client's existing
  // convention for an off control (primitives.js's transportButton).
  const head = setupHead({
    back: "go_home", backLabel: CHROME.backToHome, ...barFor(ui, picked, p.drill === "scenarios" ? cycle : null),
    // The aside is the step's forward action and NOTHING else. A stage chip
    // lived here briefly and was wrong twice over: the rail's STAGES list
    // already shows which stage is selected, and putting it beside Continue
    // implied the choice was part of what Continue starts - which it never
    // is. A game always begins at stage 1; the stage selection is a reading
    // position in the detail pane, not a setup decision.
    aside: picked
      ? cta({ act: "go_players", label: h`${CHROME.continueToPlayers}`, tone: "ok", grow: false })
      : h`<span class="cta cta-ok is-off">${CHROME.continueToPlayers}</span>`,
  });

  return h`<main class="pane setup">${raw(head)}<div class="setup-grid">
<div class="setup-list">${raw(drillList({ ...p, source, cycle }, cycles, scenarios))}${raw(stageList)}</div>
<div class="setup-detail">${raw(detail)}</div>
</div></main>`;
}
