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
import { cta } from "./primitives.js";
import { logText } from "./logfilter.js";

export function renderExportSheet(game, ui) {
  // The box is as tall as the log, within reason. A fixed 16 rows meant a
  // one-line log sat in a 570px void; the clamp keeps a long one scrollable
  // instead of pushing the sheet past its own max-height.
  const text = logText(game);
  const rows = Math.max(6, Math.min(18, text.split("\n").length));
  return h`<h1 class="display">${CHROME.exportLog}</h1>
<textarea class="export-text body" readonly rows="${rows}">${text}</textarea>
<div class="cta-row cta-row-end">${raw(cta({ act: "copy_log", label: CHROME.copyLog, tone: "plain", grow: false }))}${raw(cta({ act: "sheet_close", label: CHROME.done, grow: false }))}</div>`;
}
