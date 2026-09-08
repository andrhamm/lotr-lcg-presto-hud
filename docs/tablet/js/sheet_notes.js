// The Notes sheet (Task 4, milestone 5): opened by the phase pane's own
// notes panel "More notes ›" chip (acts_notes.js's open_notes, pane.js's
// renderNotesPanel). Lists every tip group notes.js's allNotes() has for
// the current scenario - General first, then each stage in numeric order
// (R9) - each group carrying its own Source link, same shape as the
// panel's own list-plus-link but with no 3-item cap (the sheet scrolls,
// same convention the resolution sheet's card-text blocks already use -
// see style.css's .rsheet-face comment). `Done` just closes: this is a
// reference list, not an editor, so there is nothing else to confirm.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta, sourceCite } from "./primitives.js";
import { allNotes } from "./notes.js";

// Exported because the Scenario overview's Notes section draws the same
// groups (Task 3, milestone 6) - one markup, so the sheet and the overview
// can never drift into two shapes for the same list.
//
// No source link per group: every group in a scenario cites the same article,
// so the sheet printed the identical bar four times. renderNotesSheet prints
// the distinct sources ONCE, at the foot.
export function renderNotesGroup(g) {
  const items = g.items.map(t => h`<li class="body">${t}</li>`).join("");
  return h`<div class="notes-group">
<div class="label">${g.scope}</div>
<ul>${raw(items)}</ul>
</div>`;
}

// Every distinct source across the groups, in the order they first appear -
// a list, because tips.json CAN attribute per stage, and one line in practice
// because no scenario does today.
function cites(groups) {
  const seen = new Set();
  const out = [];
  for (const g of groups) {
    const key = `${g.source?.name ?? ""}|${g.source?.url ?? ""}`;
    if (!g.source?.name || seen.has(key)) continue;
    seen.add(key);
    out.push(sourceCite(g.source));
  }
  return out.length ? h`<div class="cite-row">${raw(out.join(""))}</div>` : "";
}

export function renderNotesSheet(game, ui) {
  const groups = allNotes(ui.tips, ui.scenarioSlug);
  const body = groups.map(renderNotesGroup).join("");
  const footer = h`<div class="cta-row">${raw(cta({ act: "sheet_close", label: CHROME.done }))}</div>`;
  return h`<h1 class="display">${CHROME.notesSheetTitle}</h1>
${raw(body)}
${raw(cites(groups))}
${raw(footer)}`;
}
