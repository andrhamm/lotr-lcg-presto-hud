// The menu sheet (milestone 3): the tablet's only way to abandon the current
// game and start a new one mid-play. Opened from the strip's "Menu ›" chip
// (strip.js). "New game" is confirmed here rather than acted on immediately
// - app.js treats "new_game_confirm" exactly like "new_game" (clears the
// session, shows the picker); "Cancel" just closes the sheet.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta } from "./primitives.js";

export function renderMenuSheet(game, ui) {
  return h`<h1 class="display">${CHROME.menu}</h1>
<p class="body secondary">${CHROME.newGameWarning}</p>
<div class="cta-row">
${raw(cta({ act: "new_game_confirm", label: CHROME.newGame, tone: "no" }))}
${raw(cta({ act: "sheet_close", label: CHROME.cancel, tone: "plain" }))}
</div>`;
}
