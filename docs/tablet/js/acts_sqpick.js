// The side-quest picker's own acts (Task 6) - mirrors SideQuestPickModal's
// onButton/_leave (docs/js/screens.js): pick a sphere, then pick a catalog
// row inside it (or skip straight to "Manual entry"). The twin's separate
// "add" confirm is NOT mirrored: on a canvas modal a row tap has to double as
// paging, so the confirm is load-bearing there; here the row tap is the add,
// and the quest sheet's own remove (sRemove) undoes a mis-tap in one. Entries come
// from `ui.sideQuests`, loaded lazily the first time "open_sqpick" fires -
// that needs `await db.sideQuests()`, so app.js handles it directly (the
// same way it already handles "pick_scenario"/"new_game") rather than
// through this synchronous dispatch table; this file only ever sees
// `ui.sideQuests` once app.js has already seated it (or left it `[]` on a
// failed load - the manual path below never depends on it). Split out the
// same way every other sheet's acts are (review finding 6, task-4 fix round
// 1) - one of the per-area handlers dispatch() tries in order, `handle`
// returns null for any act it does not own.
import { CHROME } from "./copy.js";
import { PER_PAGE } from "./sheet_sqpick.js";

// Imported, not a second hardcoded literal - sheet_sqpick.js's own grouping
// keys off the same CHROME string when it builds each row's data-arg, so if
// the two ever drifted, sqpick_sphere's pre-select below would silently stop
// matching the "No sphere" bucket's rows.
const NO_SPHERE = CHROME.sqpickNoSphere;

function sphereOf(e) { return e.sphere || NO_SPHERE; }
function inSphere(entries, sphere) { return entries.filter(e => sphereOf(e) === sphere); }

// Row count for whichever list is on screen - the sphere list (step 1,
// distinct spheres present) or one sphere's quests (step 2). Ordering is
// sheet_sqpick.js's own concern (it draws the fixed sphere order); this only
// needs how many rows sqpick_page is paging through.
function rowCount(ui) {
  const entries = ui.sideQuests ?? [];
  const sphere = ui.sheet.sphere;
  if (sphere === null) return new Set(entries.map(sphereOf)).size;
  return inSphere(entries, sphere).length;
}

export function handle(game, ui, act, arg) {
  if (act === "sqpick_sphere") {
    // Only valid on the sphere-list step - same shape as sqpick_row/
    // sqpick_back's own step guards below, rather than just checking the
    // sheet is a "sqpick" (review finding 6).
    if (ui.sheet?.kind !== "sqpick" || ui.sheet.sphere !== null) return false;
    // No pre-selection to make: there is no selected state on this step any
    // more, because a row tap adds outright.
    ui.sheet.sphere = arg;
    ui.sheet.page = 0;
    return true;
  }
  if (act === "sqpick_back") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "sqpick" || sheet.sphere === null) return false;
    sheet.sphere = null;
    sheet.page = 0;
    return true;
  }
  // The row IS the add - SideQuestPickModal's own onButton "add" branch,
  // verbatim log line, fired from the tap that chose the quest.
  if (act === "sqpick_row") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "sqpick" || sheet.sphere === null) return false;
    const e = (ui.sideQuests ?? []).find(x => x.id === arg);
    if (!e) return false;
    const pts = e.points ?? 0;
    game.side_quests.push({ points: pts, progress: 0, name: e.name });
    game.logEvent(`Side quest added: ${e.name} (${pts} pts, progress view)`);
    ui.sheet = { kind: "quest" };
    return true;
  }
  if (act === "sqpick_page") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "sqpick") return false;
    const pages = Math.max(1, Math.ceil(rowCount(ui) / PER_PAGE));
    const next = Math.max(0, Math.min(pages - 1, sheet.page + Number(arg)));
    if (next === sheet.page) return false;
    sheet.page = next;
    return true;
  }
  if (act === "sqpick_manual") {
    // onButton "manual" branch, verbatim log line - no stepper editor here
    // (unlike the location picker's manual mode): points/progress start at
    // 0 and are dialled in afterward from the quest sheet's own sPts±.
    if (ui.sheet?.kind !== "sqpick") return false;
    game.side_quests.push({ points: 0, progress: 0 });
    game.logEvent("Side quest added manually (progress view)");
    ui.sheet = { kind: "quest" };
    return true;
  }
  if (act === "sqpick_cancel") {
    if (ui.sheet?.kind !== "sqpick") return false;
    ui.sheet = { kind: "quest" };
    return true;
  }
  return null;
}
