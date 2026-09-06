// The difficulty ladder, as pure functions (Task 3, milestone 6): which
// options a scenario actually offers, and the one sentence shown under the
// ladder for the option that is selected.
//
// A straight port of ScenarioOptionsScreen's own _scenarioModes() /
// difficultyOptions() / _modeCardText() / _tipMessages() (docs/js/
// screens_other.js) - the canvas twin keeps them as methods on the screen
// because it holds `scenario`/`data`/`difficulty` on itself; a tablet render
// function holds nothing, so they take those three as arguments instead.
// Same rules, one behaviour, and NOT a second copy of the copy: every
// sentence still comes from viewcopy's MODE_TIPS / MODE_TIPS_FALLBACK (the
// one home both twins read, with the citations in viewcopy.py) or from the
// scenario's own printed Mode card. Nothing here writes a sentence about the
// game.
import { MODE_TIPS, MODE_TIPS_FALLBACK } from "../../js/viewcopy.js";

// Easy and Standard always apply: Easy is a general rule (Learn to Play
// p.28 "Modes of Play"), not a per-scenario card. Anything else - Hard,
// Epic Multiplayer - only exists as a printed Mode card on the handful of
// scenarios that ship one (exactly 1 of 349 prints Hard, 3 print Epic
// Multiplayer), so it is offered only when this scenario's catalog entry
// lists it. Nightmare is a rung on the same ladder rather than a second
// toggle, and is per-scenario too (68 of 349 have `hasNightmare`).
const BASE_OPTIONS = ["Easy", "Standard"];

// The index entry's `modes` are the printed card NAMES ("Hard Mode",
// "Standard Game Mode") - the ladder wants the bare label, and the two
// spellings of "no mode at all" are dropped.
function scenarioModes(entry) {
  return (entry?.modes ?? [])
    .map(n => String(n).replace(" Mode", "").replace(" Game", "").trim())
    .filter(l => l && !["standard", "normal"].includes(l.toLowerCase()));
}

export function difficultyOptions(entry) {
  const extra = scenarioModes(entry).filter(m => m.toLowerCase() !== "easy");
  const opts = [...BASE_OPTIONS, ...extra];
  if (entry?.hasNightmare) opts.push("Nightmare");
  return opts;
}

// The printed Mode card's own text, for a scenario that ships one. `data` is
// the bundle's scenario record (db.bundle().scenario), whose `modes` are
// whole cards with faces - the first face carrying text wins, exactly as the
// twin reads it.
function modeCardText(data, label) {
  for (const card of data?.modes ?? []) {
    const name = String(card.name ?? "").replace(" Mode", "").replace(" Game", "").trim();
    if (name !== label) continue;
    for (const face of card.faces ?? []) if (face.text) return face.text;
  }
  return null;
}

// One sentence, or null when there is nothing to say (Standard - the game as
// printed). Order matters and is the twin's:
//   1. Easy/Nightmare are GENERAL rules, so their copy is viewcopy's and
//      applies to any scenario - including one whose catalog entry never
//      loaded (a read-only overview on a resumed game with no index).
//   2. Standard says nothing.
//   3. A mode this scenario does not offer says nothing either - the generic
//      fallback would point the players at a Mode card the quest does not
//      print, which is exactly the invented-rules-claim iron rule 4 forbids.
//   4. Otherwise the card's OWN printed text, and only if the catalog has
//      none, viewcopy's fallback naming the card to go read.
export function modeTip(entry, data, difficulty) {
  if (MODE_TIPS[difficulty]) return MODE_TIPS[difficulty];
  if (difficulty === "Standard") return null;
  if (!difficultyOptions(entry).includes(difficulty)) return null;
  return modeCardText(data, difficulty) ?? MODE_TIPS_FALLBACK.replace(/%s/g, difficulty);
}
