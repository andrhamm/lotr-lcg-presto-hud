// The side-quest picker (Task 6): pick a sphere, then a catalog side quest
// inside it, or skip straight to a manual entry - mirrors SideQuestPickModal
// in docs/js/screens.js (_drawSpheres/_drawQuests for the layout,
// onButton/_leave for what each act in acts_sqpick.js does), but as a
// scrollable, paged sheet rather than a fixed 480x480 canvas modal (the
// canvas paginates because it has no scrollbar; this sheet scrolls too, but
// still pages per the design system's own "page it" guidance for a list that
// can run long - CLAUDE.md rule 3b). Opened by the quest sheet's "+ Side
// quest" chip (open_sqpick, sheet_quest.js) via app.js, which loads
// `ui.sideQuests` lazily before seating `ui.sheet` - see app.js's own
// "open_sqpick" case and acts_sqpick.js's module comment.
import { h, raw, cx, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { glyph } from "./glyphs.js";

const NO_SPHERE = CHROME.sqpickNoSphere;
// The five printed spheres in their usual order, then any other catalog
// sphere (alphabetical), then "No sphere" last - SideQuestPickModal's own
// SPHERE_ORDER/spheres(), mirrored exactly so the two twins list spheres the
// same way.
const SPHERE_ORDER = ["Leadership", "Lore", "Spirit", "Tactics", "Neutral"];
// Rows per page - this sheet scrolls (unlike the twin's fixed canvas), so
// this is a "page it" call (CLAUDE.md rule 3b), not a viewport limit.
// Exported so acts_sqpick.js's sqpick_page can clamp to the same page count
// instead of carrying a second copy of this number (review finding 2).
export const PER_PAGE = 8;

function sphereOf(e) { return e.sphere || NO_SPHERE; }

// [sphere, count] pairs in SPHERE_ORDER's fixed order - mirrors
// SideQuestPickModal.spheres() verbatim.
function spheres(entries) {
  const counts = new Map();
  for (const e of entries) {
    const k = sphereOf(e);
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  const out = SPHERE_ORDER.filter(k => counts.has(k)).map(k => [k, counts.get(k)]);
  const rest = [...counts.keys()].filter(k => !SPHERE_ORDER.includes(k) && k !== NO_SPHERE).sort();
  for (const k of rest) out.push([k, counts.get(k)]);
  if (counts.has(NO_SPHERE)) out.push([NO_SPHERE, counts.get(NO_SPHERE)]);
  return out;
}

function inSphere(entries, sphere) { return entries.filter(e => sphereOf(e) === sphere); }

function questCountLabel(n) {
  return n === 1 ? CHROME.sqpickOneQuest : fmt(CHROME.sqpickManyQuests, n);
}

// One sphere row: name (BODY - a name a player reads) with its quest count
// right-aligned as BODY secondary - same shape sheet_locpick.js's locRow
// draws for a location's name + threat/points pair (design system rule 3b:
// a name is never a chip's ALL-CAPS LABEL).
function sphereRow([sphere, count]) {
  return h`<button type="button" class="sqpick-row" data-act="sqpick_sphere" data-arg="${sphere}">
<div class="sqpick-row-head"><span class="body">${sphere}</span><span class="body secondary">${questCountLabel(count)}</span></div>
</button>`;
}

// One side-quest row: name + points on one line, the card's own printed text
// (when the catalog has one) stacked underneath as a second BODY secondary
// line - CLAUDE.md rule 4, "prefer the card's own printed text over a
// paraphrase". There is no selected state: tapping the row adds the quest
// (see renderSqPickSheet), so nothing is ever merely chosen.
function questRow(e) {
  const pts = fmt(CHROME.sqpickPts, e.points ?? 0);
  // No current data path fills `e.text` - docs/js/quest_catalog.js's
  // sideQuests() emits only {id, name, points, sphere, pack} (verified
  // 2026-09-05), so this branch is dead until a follow-up extends
  // sideQuests()/side_quests() in both twins to carry the card's printed
  // text. Kept rather than removed so that follow-up is a data change only.
  const text = e.text ? h`<span class="body secondary">${e.text}</span>` : "";
  return h`<button type="button" class="sqpick-row" data-act="sqpick_row" data-arg="${e.id}">
<div class="sqpick-row-head"><span class="body">${e.name ?? ""}</span><span class="body secondary">${pts}</span></div>
${raw(text)}</button>`;
}

// The chosen sphere: a FILTER you can see and clear, not a heading - the same
// row the scenario chooser gives the chosen cycle (newgame.js: a LABEL, then
// the choice on a gold-edged row carrying an X, the whole row being the
// target). It replaces a "< Spheres" chip that sat in the footer among the
// actions, which put "go back a step" in the row reserved for "leave" and
// "commit".
function sphereCrumb(sphere) {
  return h`<div class="label">${CHROME.sqpickSphere}</div>
<div class="drill-row drill-current" data-act="sqpick_back" role="button">
<span class="body">${sphere}</span>
<span class="drill-x" aria-hidden="true">${raw(glyph("close", 18))}</span>
</div>`;
}

// Prev/Next steppers plus a "page/pages" readout - only drawn once there is
// more than one page, same gate as the twin's own _pager().
function pager(page, pages) {
  if (pages <= 1) return "";
  return h`<div class="sqpick-pager">
${raw(chip({ act: "sqpick_page", arg: "-1", label: CHROME.sqpickPrev, tone: "tan" }))}
<span class="body secondary">${fmt(CHROME.sqpickPage, page + 1, pages)}</span>
${raw(chip({ act: "sqpick_page", arg: "1", label: CHROME.sqpickNext, tone: "tan" }))}
</div>`;
}

function paged(rows, page) {
  const pages = Math.max(1, Math.ceil(rows.length / PER_PAGE));
  const clamped = Math.min(page, pages - 1);
  return { chunk: rows.slice(clamped * PER_PAGE, (clamped + 1) * PER_PAGE), page: clamped, pages };
}

export function renderSqPickSheet(game, ui) {
  const sheet = ui.sheet;
  const entries = ui.sideQuests ?? [];
  const ctas = [];
  let body;
  if (!entries.length) {
    // No catalog data at all - same fallback the location picker shows
    // (LocationPickModal/loadPlayerSideQuests both degrade to [] on any
    // catalog failure), so Manual entry is the only way forward.
    body = h`<p class="body secondary">${CHROME.sqpickEmpty}</p>`;
  } else if (sheet.sphere === null) {
    const { chunk, page, pages } = paged(spheres(entries), sheet.page);
    body = h`<div class="sqpick-list">${raw(chunk.map(sphereRow).join(""))}</div>
${raw(pager(page, pages))}`;
  } else {
    const { chunk, page, pages } = paged(inSphere(entries, sheet.sphere), sheet.page);
    // A ROW IS THE ADD. Picking a quest and then pressing Add is two taps for
    // one decision, and it is what forced the sheet to explain itself in
    // prose ("Lore - pick one, then Add."). The twin needs the confirm - its
    // canvas modal has no way to scroll a list, so a row tap is also how it
    // pages - and it is not reversible there either; here the quest sheet's
    // own remove (sRemove) undoes a mis-tap in one.
    body = h`${raw(sphereCrumb(sheet.sphere))}
<div class="sqpick-list">${raw(chunk.map(questRow).join(""))}</div>
${raw(pager(page, pages))}`;
  }
  // Two ways out, both the same shape - a CTA in the footer. "Manual entry"
  // is always offered, catalog or not (the twin's own footer button never
  // depends on this.entries.length either), and it used to be an ALL-CAPS
  // chip beside a sentence-case CTA: two treatments for two things a player
  // does with the same finality.
  ctas.push(cta({ act: "sqpick_manual", label: CHROME.manualEntry, tone: "plain", grow: false }));
  ctas.push(cta({ act: "sqpick_cancel", label: CHROME.cancel, tone: "plain", grow: false }));
  return h`<h1 class="display">${CHROME.sqpickTitle}</h1>
${raw(body)}
<div class="cta-row cta-row-end">${raw(ctas.join(""))}</div>`;
}
