// The location picker (Task 5): pick a catalog location or enter one
// manually, then travel to it / replace the active seat with it. Mirrors
// LocationPickModal in docs/js/screens.js - _drawList/_drawManual for the
// layout, onButton/_commit for what each act below does - but as a
// scrollable sheet (the twin's version is a fixed 480x480 canvas modal, so
// it paginates PER_PAGE=6; this one never does) and with no "how it
// arrived" toggle: arrival is inferred from `ui.sheet.back` (actions.js),
// not a button the player sets. Opened by the quest sheet's "+ Add
// location" chip (open_locpick, back "quest") and the Travel pane's own
// CTA (back "play") - see actions.js's openLocPick() for the shape both
// share, and pane.js's "travel" case for the CTA.
import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";

// %s/%d template fill, in order - same helper as pane.js's local fmt().
const fmt = (t, ...a) => { let i = 0; return t.replace(/%[sd]/g, () => a[i++]); };

function step(act, arg, label) {
  return h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${label}</button>`;
}

// The seat a "change" would overwrite, or null - mirrors _replacing() in
// docs/js/screens.js exactly (mode "new" never replaces, even with one
// already active - that is how a second seat arrives).
function replacing(game, sheet) {
  if (sheet.mode !== "change") return null;
  return sheet.idx < game.active_locations.length ? game.active_locations[sheet.idx] : null;
}

// Catalog rows grouped by their encounter set, in the order sets first
// appear (locationsFor's own byName sort already orders rows inside each
// set) - same shape newgame.js's scenarioGroups gives cycles, just without
// the extra cycle-rank sort (there is no printed release order for
// encounter sets to sort by).
function groupBySet(entries) {
  const groups = new Map();
  for (const e of entries) {
    const key = e.set ?? "";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  }
  return [...groups.entries()].map(([set, rows]) => ({ set, rows }));
}

// One row: name (BODY - a name a player reads) with its threat/quest-points
// pair right-aligned as BODY secondary, not a chip's ALL-CAPS LABEL - same
// distinction newgame.js's scenario-row draws between a printed name and
// chrome. A card that prints a literal X shows "X", never a 0 it made up
// (locationsFor/quest_catalog.js hands the picker *Kind for exactly this -
// see LocationPickModal's own eThreat/ePoints comment).
function locRow(e, selected) {
  const eThreat = e.threatKind === "x" ? "X" : (e.threat ?? 0);
  const ePoints = e.pointsKind === "x" ? "X" : (e.points ?? 0);
  return h`<button type="button" class="${cx("locpick-row", selected && "is-selected")}" data-act="locpick_row" data-arg="${e.id}">
<span class="body">${e.name ?? ""}</span>
<span class="body secondary">${fmt(CHROME.locpickStats, eThreat, ePoints)}</span>
</button>`;
}

function renderList(game, ui) {
  const sheet = ui.sheet;
  const entries = ui.locations ?? [];
  const loc = replacing(game, sheet);
  const sub = loc
    ? h`<p class="body secondary">${fmt(CHROME.locpickReplacing, loc.progress, loc.points)}</p>`
    : h`<p class="body secondary">${CHROME.locpickPrompt}</p>`;
  const groups = groupBySet(entries).map(({ set, rows }) => h`<div class="locpick-group">
${set ? h`<div class="label">${set}</div>` : ""}
${raw(rows.map(e => locRow(e, e.id === sheet.selected)).join(""))}
</div>`).join("");
  return h`${raw(sub)}<div class="locpick-list">${raw(groups)}</div>`;
}

// The manual stepper pair - 1..30 quest points, 0..9 threat contribution,
// the same clamps as the twin's onButton ("pts"/"ctr" branches). Rows reuse
// .qsheet-row/-controls/-val (style.css) rather than a locpick-prefixed
// duplicate - it is the identical labelled-stepper layout sheet_quest.js's
// own row() draws, just built here with h`` instead of imported (that
// helper is local to sheet_quest.js, not exported).
function renderManual(ui) {
  const m = ui.sheet.manual;
  return h`<div class="locpick-manual">
<div class="qsheet-row">
<span class="body">${CHROME.pickPoints}</span>
<div class="qsheet-controls">${raw(step("locpick_pts", "-1", "−"))}
<span class="qsheet-val"><span class="num num-34">${m.points}</span></span>
${raw(step("locpick_pts", "1", "+"))}</div>
</div>
<div class="qsheet-row">
<span class="body">${CHROME.pickContribution}</span>
<div class="qsheet-controls">${raw(step("locpick_contrib", "-1", "−"))}
<span class="qsheet-val"><span class="num num-34">${m.contrib}</span></span>
${raw(step("locpick_contrib", "1", "+"))}</div>
</div>
<p class="body secondary">${CHROME.contributionNote}</p>
</div>`;
}

export function renderLocPickSheet(game, ui) {
  const sheet = ui.sheet;
  const title = sheet.mode === "new" ? CHROME.locpickTitleNew : CHROME.locpickTitleChange;
  const manual = sheet.manual;
  const body = manual ? renderManual(ui) : renderList(game, ui);
  // "Travel"/"Add" - the confirm CTA must not claim a travel the players
  // never paid for (LocationPickModal's own footer label switch, verbatim).
  const confirmLabel = sheet.back === "play" ? CHROME.travelHere : CHROME.addHere;
  const ctas = [];
  // "Manual entry" only offers a way OUT of the list into the steppers -
  // once there, "Save" replaces it (mirrors the twin's list<->manual
  // step, minus a way back: Cancel is the tablet's one way out of either,
  // see the module comment).
  if (!manual) {
    ctas.push(chip({ act: "locpick_manual", label: CHROME.manualEntry, tone: "tan" }));
    // Needs a selection - LocationPickModal only draws its Travel button
    // once this.selected is set; this mirrors that gate on the render
    // side (dispatch's own locpick_travel case guards it again).
    if (sheet.selected !== null) {
      ctas.push(cta({ act: "locpick_travel", label: confirmLabel, grow: false }));
    }
  } else {
    ctas.push(cta({ act: "locpick_save", label: confirmLabel, grow: false }));
  }
  ctas.push(cta({ act: "locpick_cancel", label: CHROME.cancel, tone: "plain", grow: false }));
  return h`<h1 class="display">${title}</h1>
${raw(body)}
<div class="cta-row">${raw(ctas.join(""))}</div>`;
}
