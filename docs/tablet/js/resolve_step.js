// The guided resolution flow's one step function (Task 7), ported from
// ResolutionModal._derive() / _questStep() in docs/js/screens.js. Pure: it
// reads `game` plus the sheet's own three fields (forced / branchPick /
// skippedSide) and answers "what do the players have to resolve next?", or
// null when there is nothing left.
//
// It lives in its own module because BOTH sides need the same answer, and a
// second implementation is where the twins drift. The canvas modal keeps
// `this.step` on itself and recomputes it after every button; a tablet sheet
// holds no state beyond ui.sheet, so sheet_resolve.js (render) and
// acts_resolve.js (act) each call this instead - one function, one order of
// precedence: an interrupted flip first, then locations, then the quest,
// then side quests.
import { CHROME } from "./copy.js";
import { faceOf, frontFace } from "./cards.js";

// The twin's backFace() (docs/js/ui.js) returns {} for a single-face card;
// cards.js's faceOf(card, "B") deliberately falls back to faces[0] instead,
// because the quest sheet needs *a* face for a game whose quest.side is "B"
// even on a one-face card. The steps here need the twin's meaning - a card
// with one face has no back - or the reveal step would print the identical
// rules paragraph twice, once under each of its two side captions.
export const backOf = card => ((card?.faces?.length ?? 0) > 1 ? faceOf(card, "B") : null);

// A fork alternative's name, and it is the BACK face's - the same face the
// twin's _drawBranch reads, for a reason the catalog settles: on 23 of the
// 39 branch stages every alternative's FRONT name is identical (Escape from
// Khazad-dum's stage 2 is "Search for an Exit" three times over) and only
// the back tells "Old One Lair" from "A Wrong Turn" from "A Way Up". A row
// named off the front would be three identical rows on more than half the
// forks in the game. Every one of the 116 alternative cards in the catalog
// has a back face, so the front is only a fallback.
export const branchName = card => backOf(card)?.name || frontFace(card)?.name || "";

// Everything the quest card itself can be waiting on. Ported verbatim from
// _questStep(): side A is an unresolved reveal (flip it), side B is either
// the end of the scenario (victory), a fork (branch) or the next stage
// (advance).
function questStep(game, sheet) {
  const g = game;
  if (g.quest.side === "A") {
    const card = g.stages[g.stage_idx].cards[g.card_idx];
    // BOTH faces. The back is not decoration: 75 of 514 stage cards print
    // their When Revealed on the back and nothing on the front, so reading
    // only the front told the player there was nothing to do on cards that
    // add enemies to staging or gate the stage's defeat (the twin's own
    // comment, from the 2026-07-30 playtest of The Oath).
    return { kind: "reveal", stage_n: g.quest.stage_n,
             face_a: frontFace(card), face_b: backOf(card),
             next_points: card.questPoints };
  }
  const nxtIdx = g.stage_idx + 1;
  if (nxtIdx >= g.stages.length) {
    // The final stage's back face carries the win condition, and often a
    // restriction on it ("cannot be defeated while X is in play"). That
    // sentence is the entire reason the victory prompt offers "Not yet", so
    // it travels with the step.
    const final = g.stages[g.stage_idx].cards[g.card_idx];
    return { kind: "victory", cleared: g.questLabel(), face_b: backOf(final) };
  }
  const nxt = g.stages[nxtIdx];
  const pick = sheet.branchPick ?? null;
  if (nxt.cards.length > 1 && pick === null) {
    return { kind: "branch", cards: nxt.cards, mode: nxt.branch ?? "choice" };
  }
  return { kind: "advance", cleared: g.questLabel(), card_idx: pick || 0,
           next_stage: nxt.stage,
           underfilled: g.quest.points > 0 && g.quest.progress < g.quest.points };
}

export function deriveResolveStep(game, ui) {
  const g = game;
  const sheet = ui.sheet ?? {};
  if (g.stages.length && g.quest.side === "A") {
    return questStep(g, sheet);      // finish an interrupted reveal/flip first
  }
  // First seat that is at its points. The guided flow resolves them one at a
  // time, so the next call picks up the next one.
  for (const loc of g.active_locations) {
    if (loc.points > 0 && loc.progress >= loc.points) {
      // The twin's generic fallback here is "Active location"; the tablet
      // already names an unnamed seat "Location" everywhere else it shows
      // one (sheet_quest.js's locationName, pane.js's allocator rows), so
      // this uses that string rather than introducing a second wording for
      // the same nameless seat.
      return { kind: "location", progress: loc.progress, points: loc.points,
               name: loc.name || CHROME.location };
    }
  }
  if ((g.quest.points > 0 && g.quest.progress >= g.quest.points) || sheet.forced) {
    return questStep(g, sheet);
  }
  // Skipped side quests are held by IDENTITY, not index - "Leave as-is" must
  // survive a later splice shifting every index after it (the twin's
  // _skippedSideQuests, same comment).
  const skipped = sheet.skippedSide ?? [];
  for (let i = 0; i < g.side_quests.length; i++) {
    const s = g.side_quests[i];
    if (skipped.some(x => s === x)) continue;
    if (s.points > 0 && s.progress >= s.points) {
      return { kind: "side_quest", idx: i,
               name: s.name || `${CHROME.sideQuestLabel} ${i + 1}`,
               progress: s.progress, points: s.points };
    }
  }
  return null;
}
