// The resolution sheet (Task 7): the guided walk that runs after progress
// lands - explore the location, flip the stage, pick the fork, advance, or
// declare victory. Mirrors ResolutionModal (docs/js/screens.js) step for
// step; resolve_step.js's deriveResolveStep() is the shared brain, and
// acts_resolve.js is where each button below lands.
//
// It opens itself: actions.js's afterTap seats ui.sheet the instant
// game.pending_resolution is set (placeProgress does that for a catalog
// game, and the quest sheet's Done does it after a manual edit), exactly the
// way main.js's router constructs the modal off the same flag.
//
// Two things the canvas modal has to do that this one does not: fit the text
// (it budgets 7 lines across the two faces and hands truncated text a "more"
// affordance into the card modal - this sheet scrolls, so every face prints
// in full), and paginate. What it does keep is the twin's order of
// precedence and its wording, log lines included.
import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { deriveResolveStep, backOf, branchName } from "./resolve_step.js";

// %s/%d template fill, in order - same helper as pane.js's local fmt().
const fmt = (t, ...a) => { let i = 0; return t.replace(/%[sd]/g, () => a[i++]); };

// One face's printed text under its own caption. BODY, because it is the
// card's own sentences - the caption is the only LABEL here (design system
// rule 3b: ALL-CAPS chrome names the slot, the rules text is prose).
function faceBlock(caption, face) {
  return h`<div class="rsheet-face"><div class="label">${caption}</div>
<p class="body">${face.text || CHROME.noCardText}</p></div>`;
}

// Both faces, because the back is where a stage's rules often live - 75 of
// 514 stage cards print their When Revealed there and nothing on the front.
// A card with only ONE face gets one block: claiming a Side B the catalog
// does not have would be inventing a side of the card (see backOf).
function renderReveal(st) {
  const blocks = faceBlock(CHROME.sideA, st.face_a ?? {})
    + (st.face_b ? faceBlock(CHROME.sideB, st.face_b) : "");
  const name = st.face_a?.name || st.face_b?.name || "";
  return h`<div class="label">${fmt(CHROME.resolveRevealed, st.stage_n)}</div>
<h1 class="display">${name}</h1>
<div class="rsheet-faces">${raw(blocks)}</div>
<div class="cta-row">${raw(cta({ act: "res_flip", label: h`${fmt(CHROME.resolveFlip, st.next_points)}` }))}</div>`;
}

function renderLocation(st) {
  // Rulebook p.15: progress past a location's quest points is not lost, it
  // flows on to the quest card - resolveLocationOverflow() is what does it,
  // and this line says so before the tap rather than after.
  const excess = st.progress - st.points;
  const excessLine = excess > 0
    ? h`<p class="body">${fmt(CHROME.resolveExcess, excess)}</p>` : "";
  return h`<h1 class="display">${CHROME.locationExplored}</h1>
<p class="body">${st.name}</p>
<p class="body secondary">${fmt(CHROME.progressOf, st.progress, st.points)}</p>
${raw(excessLine)}
<div class="cta-row">${raw(cta({ act: "res_location", label: CHROME.resolveContinue }))}</div>`;
}

// One fork alternative: the path's own name and quest points, over the
// card's own printed text. The name comes off the BACK face (branchName -
// the front is the same generic stage title on 23 of the 39 branch stages),
// and the text is the card's own words rather than a paraphrase of them
// (CLAUDE.md rule 4) - all 116 alternative cards in the catalog print some.
// Same two-line pickable-row shape .sqpick-row uses for a side quest.
function branchRow(card, i, picked) {
  const text = backOf(card)?.text;
  const line = text ? h`<span class="body secondary">${text}</span>` : "";
  return h`<button type="button" class="${cx("rsheet-row", picked && "is-selected")}" data-act="res_branch" data-arg="${i}">
<span class="rsheet-row-head"><span class="body">${branchName(card)}</span>
<span class="body secondary">${fmt(CHROME.branchPoints, card.questPoints ?? 0)}</span></span>
${raw(line)}</button>`;
}

function renderBranch(st, sheet) {
  const rows = st.cards.map((c, i) => branchRow(c, i, (sheet.branchPick ?? null) === i)).join("");
  // ALL CAPS both ways: this slot names how the choice gets made and is read
  // as chrome under the title, not as a sentence (the twin's own comment).
  const mode = st.mode === "random" ? CHROME.randomPath : CHROME.firstPlayerChooses;
  const dice = st.mode === "random"
    ? h`<div class="qsheet-add">${raw(chip({ act: "res_random", label: CHROME.randomize, tone: "tan" }))}</div>`
    : "";
  return h`<h1 class="display">${CHROME.choosePath}</h1>
<div class="label">${mode}</div>
<div class="rsheet-branch">${raw(rows)}</div>
${raw(dice)}`;
}

function renderAdvance(st) {
  const warn = st.underfilled ? h`<p class="body no">${CHROME.underfilled}</p>` : "";
  return h`<h1 class="display">${fmt(CHROME.questCleared, st.cleared)}</h1>
${raw(warn)}
<div class="cta-row">${raw(cta({ act: "res_advance", label: h`${fmt(CHROME.revealStage, st.next_stage)}` }))}</div>`;
}

// The final stage's own text, so "Not yet" has a stated reason. The twin
// shipped this prompt with nothing above it but "That was the final stage!",
// and in the 2026-07-30 playtest the HUD offered victory while the stage's
// own back face said it "cannot be defeated while Goblin Troop is in play".
function renderVictory(st) {
  const text = st.face_b?.text ? h`<p class="body">${st.face_b.text}</p>` : "";
  return h`<p class="body secondary">${fmt(CHROME.questCleared, st.cleared)}</p>
<h1 class="display">${CHROME.finalStage}</h1>
${raw(text)}
<div class="cta-row">${raw(cta({ act: "res_victory", label: CHROME.declareVictory, grow: false }))}
${raw(cta({ act: "res_not_yet", label: CHROME.notYet, tone: "plain", grow: false }))}</div>`;
}

function renderSideQuest(st) {
  return h`<h1 class="display">${st.name}</h1>
<p class="body secondary">${fmt(CHROME.progressOf, st.progress, st.points)}</p>
<div class="cta-row">${raw(cta({ act: "res_side_done", label: CHROME.markComplete, grow: false }))}
${raw(cta({ act: "res_side_skip", label: CHROME.leaveAsIs, tone: "plain", grow: false }))}</div>`;
}

// Nothing left. This is the ONLY step that draws res_close - the sheet is
// otherwise left to its own steps, and the scrim's sheet_close is always
// there for a player who wants out early (it's a tracker, not a referee).
function renderDone() {
  return h`<h1 class="display">${CHROME.allResolved}</h1>
<div class="cta-row">${raw(cta({ act: "res_close", label: CHROME.resolveContinue }))}</div>`;
}

export function renderResolveSheet(game, ui) {
  const st = deriveResolveStep(game, ui);
  if (st === null) return renderDone();
  if (st.kind === "reveal") return renderReveal(st);
  if (st.kind === "location") return renderLocation(st);
  if (st.kind === "branch") return renderBranch(st, ui.sheet ?? {});
  if (st.kind === "advance") return renderAdvance(st);
  if (st.kind === "victory") return renderVictory(st);
  return renderSideQuest(st);
}
