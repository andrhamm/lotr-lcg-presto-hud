// The export sheet (milestone 4, Task 3): the whole log as plain text, in a
// readonly <textarea> the player can select by hand, plus a Copy chip that
// puts the same string on the clipboard (app.js owns that - it is the one
// browser API call in the client, and this file stays a pure string builder).
//
// A textarea rather than a <pre>: it is selectable and scrollable with one
// gesture on a touchscreen, and long-pressing it gets the platform's own
// Select All / Share, which is the escape hatch when the clipboard write is
// refused.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { logText } from "./logfilter.js";

export function renderExportSheet(game, ui) {
  return h`<h1 class="display">${CHROME.exportLog}</h1>
<textarea class="export-text body" readonly rows="16">${logText(game)}</textarea>
<div class="cta-row">${raw(chip({ act: "copy_log", label: CHROME.copyLog, tone: "tan" }))}${raw(cta({ act: "sheet_close", label: CHROME.done, tone: "plain" }))}</div>`;
}
