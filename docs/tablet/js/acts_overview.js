// The Scenario overview's own acts (Task 3, milestone 6): the difficulty
// ladder, the two ways off the screen, and the way onto it from the rail.
// Every one of them is ui-only - `begin_setup` stays in app.js because it is
// the one that rebinds `game` (and clears the tagged write queue with it).
//
// While ui.screen is "newgame"/"overview" app.js routes acts straight
// through dispatch() rather than perform(): `game` at that moment may still
// be the PREVIOUS, already-finished GameState, and a queued write tagged to
// it would resurrect a save the player just left behind (CLAUDE.md's "the
// queue is tagged with its game object"). open_overview is the exception -
// it is tapped from the play screen, so it rides the normal perform() path
// like every other sheet-opening act, and produces no delta because it
// changes nothing on `game`.
import { difficultyOptions } from "./difficulty.js";

export function handle(game, ui, act, arg) {
  if (act === "ov_difficulty") {
    // Refuse anything this scenario does not actually offer: the ladder is
    // per-scenario (Hard/Epic Multiplayer are printed Mode cards only a
    // handful of quests ship, Nightmare is a separately sold deck 68 of 349
    // have), and a mode set from a stale render would travel all the way
    // into the saved game's `scenario.mode`.
    if (!difficultyOptions(ui.overview?.entry).includes(arg)) return false;
    if (ui.overview.difficulty === arg) return false;
    ui.overview.difficulty = arg;
    return true;
  }
  if (act === "ov_back") {
    // Back to the picker, with its state (source/cycle/players/threats)
    // exactly as the player left it - only pick_scenario writes ui.overview,
    // and a fresh pick overwrites it wholesale, so there is nothing to clean
    // up here. (Moved from acts_newgame.js, which owned it while layout.js
    // still carried a placeholder screen.)
    ui.screen = "newgame";
    return true;
  }
  if (act === "ov_close") {
    // The read-only variant's only way out: back to the game it was opened
    // over. It never touches the game, so there is nothing to confirm.
    ui.screen = "play";
    return true;
  }
  if (act === "open_overview") {
    // The QUEST zone's stage pill (rail.js), mid-game. The bundle was
    // already pinned at pick/boot - db.bundle() is not re-read to open a
    // reference screen - so an overview seat that never arrived (a resumed
    // game whose bundle failed to load) simply declines rather than opening
    // an empty screen.
    if (!ui.overview) return false;
    ui.overview.readonly = true;
    // The game's own mode is the authority once play has started: an undo
    // that rewound past setup, or a save resumed into a fresh boot, must not
    // show the ladder value some earlier pick left in the seat.
    ui.overview.difficulty = game.scenario?.mode ?? ui.overview.difficulty;
    ui.screen = "overview";
    return true;
  }
  return null;
}
