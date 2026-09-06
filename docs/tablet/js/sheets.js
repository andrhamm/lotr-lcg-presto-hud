// The modal-overlay framework (milestone 3): one scrim + one sheet, drawn
// whenever ui.sheet is set. Pure string builder like every other tablet
// render function - no document/window, so tests/test_tablet.py can drive it
// under node. app.js's click delegation stops a click that lands inside
// `[data-stop]` (the sheet body) from bubbling to the scrim's own
// data-act="sheet_close" - only a tap that lands OUTSIDE the sheet, on the
// scrim itself, or on a `[data-act]` button inside the sheet, does anything.
import { h, raw, cx } from "./dom.js";
import { renderPlayersSheet } from "./sheet_players.js";
import { renderStagingSheet } from "./sheet_staging.js";
import { renderMenuSheet } from "./sheet_menu.js";
import { renderElimSheet } from "./sheet_elim.js";
import { renderQuestSheet } from "./sheet_quest.js";
import { renderLocPickSheet } from "./sheet_locpick.js";
import { renderSqPickSheet } from "./sheet_sqpick.js";
import { renderResolveSheet } from "./sheet_resolve.js";

// Unknown kinds render nothing (not an error): a sheet kind not wired up
// here is a no-op overlay, never a crash.
const RENDERERS = {
  players: renderPlayersSheet,
  staging: renderStagingSheet,
  menu: renderMenuSheet,
  elim: renderElimSheet,
  quest: renderQuestSheet,
  locpick: renderLocPickSheet,
  sqpick: renderSqPickSheet,
  resolve: renderResolveSheet,
};

export function renderSheet(game, ui) {
  if (!ui.sheet) return "";
  const render = RENDERERS[ui.sheet.kind];
  if (!render) return "";
  const body = render(game, ui);
  return h`<div class="scrim" data-act="sheet_close"><section class="${cx("sheet", "sheet-" + ui.sheet.kind)}" data-stop>${raw(body)}</section></div>`;
}
