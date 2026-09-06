// The sailing test sheet (Task 8) - SailingModal is the twin's canvas
// reference (docs/js/screens.js): a wheel-count stepper draft (ui.sheet.v,
// -3..8, acts_sailing.js's own clamp) that previews what committing it would
// do to the ship's heading before acts_sailing.js's sail_apply actually
// calls game.shiftHeading(). This module only ever reads game.heading /
// headingDesc() - it never mutates, same purity rule every other sheet_*.js
// follows. Copy sheet_elim.js's header/body/footer shape.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta } from "./primitives.js";
import { icon } from "../../js/icons_svg.js";
import { HEADINGS } from "../../js/gamestate.js";
import { WILLPOWER_GOLD } from "./palette.js";

// %s/%d template fill, in order - same helper as sheet_elim.js's own fmt().
const fmt = (t, ...a) => { let i = 0; return t.replace(/%[sd]/g, () => a[i++]); };

// One wheel-count stepper: a live bevelled <button> when the draft can still
// move that way, or - allocStep's live/off convention (pane.js) for a
// stepper that cannot act - a dim, unbevelled <span> with no data-act. The
// glyph is a real Unicode "−" (U+2212), not the "&minus;" HTML entity
// allocStep itself passes - h`` escapes every interpolated value, so an
// entity substituted that way renders as literal text "&minus;" instead of
// a minus sign (reproduced from pane.js and confirmed in a browser during
// this task; every OTHER stepper in the app, e.g. sheet_elim.js's step(),
// already uses the real character for exactly this reason).
function wheelStep(glyph, act, arg, live) {
  return live
    ? h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${glyph}</button>`
    : h`<span class="step step-sm step-off">${glyph}</span>`;
}

// Same "term (facing)" shape as game.headingDesc(), for an arbitrary
// HEADINGS index rather than only the game's own current one - the RESULT
// preview names a heading the game has not committed to yet, so it cannot
// go through headingDesc() itself.
function headingLine(idx) {
  const [term, , facing] = HEADINGS[idx];
  return `${term} (${facing})`;
}

// The sub-line under the stepper - SailingModal.draw()'s three branches
// (found wheels / off-course card effect / nothing), verbatim wording.
// Singular and plural are whole separate CHROME strings, the same way
// sqpickOneQuest/sqpickManyQuests are two keys rather than one template
// with an embedded "s".
function subLine(v) {
  if (v > 1) return { text: fmt(CHROME.sailWheelsFound, v), cls: "body" };
  if (v === 1) return { text: CHROME.sailWheelFound, cls: "body" };
  if (v === -1) return { text: CHROME.sailStepOff, cls: "body no" };
  if (v < -1) return { text: fmt(CHROME.sailStepsOff, -v), cls: "body no" };
  return { text: CHROME.sailNoWheels, cls: "body secondary" };
}

export function renderSailingSheet(game, ui) {
  const { v } = ui.sheet;
  // The RESULT preview clamps to a valid HEADINGS index (0..3) - a
  // different clamp than the draft stepper's own -3..8 (acts_sailing.js),
  // matching SailingModal._result()'s own Math.max(0, Math.min(3, ...)).
  const resultIdx = Math.max(0, Math.min(HEADINGS.length - 1, game.heading - v));
  const sub = subLine(v);
  const wheelIcon = v > 0 ? icon("WHEEL", 34, WILLPOWER_GOLD) : "";
  return h`<h1 class="display">${CHROME.sailingTest}</h1>
<div class="sailsheet-heading">
<div class="label">${CHROME.currentHeading}</div>
<p class="body">${game.headingDesc()}</p>
</div>
<div class="sailsheet-stepper">
${raw(wheelStep("−", "sail_d", "-1", v > -3))}
<span class="sailsheet-val">${raw(wheelIcon)}<span class="num num-48">${v}</span></span>
${raw(wheelStep("+", "sail_d", "1", v < 8))}
</div>
<p class="${sub.cls}">${sub.text}</p>
<div class="sailsheet-heading">
<div class="label">${CHROME.result}</div>
<p class="body">${headingLine(resultIdx)}</p>
</div>
<div class="cta-row">
${raw(cta({ act: "sail_apply", label: CHROME.apply, grow: false }))}
${raw(cta({ act: "sail_cancel", label: CHROME.cancel, tone: "plain", grow: false }))}
</div>`;
}
