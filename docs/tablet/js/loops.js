// The loop diagram: Planning, the engagement checks, and both combat halves
// (docs/js/viewcopy.js's LOOP_FLOW) share this one widget, same as the
// canvas twin's _loopFlow (docs/js/screen_play.js). Pure string builder like
// every other tablet render function - no document/window.
import { h, raw } from "./dom.js";
import { band } from "./primitives.js";
import { LOOP_LEGEND } from "../../js/viewcopy.js";

// One rung: a numbered gold circle (joined to its neighbours by a 2px
// connector - see .loop-rung::before in style.css), its label and optional
// sub-clause, and - only when this rung is the one that opens an action
// window (rung[1]) - a green 9px dot. The canvas twin marks the same rungs
// with a purple square inline with the text; the tablet's dot sits with the
// rung body instead, since the loop here reads top-to-bottom rather than
// wrapping against a fixed-width column.
function renderRung(n, label, opens, sub) {
  const subLine = sub ? h`<p class="body secondary loop-sub">${sub}</p>` : "";
  const dot = opens ? '<span class="loop-dot"></span>' : "";
  return h`<div class="loop-rung"><span class="loop-num">${n}</span><div class="loop-rung-body"><p class="body">${label}</p>${raw(subLine)}${raw(dot)}</div></div>`;
}

// A LOOP_FLOW entry -> the framing band (banded like every other phase
// view's framing copy - spec.kind is "window" or "framework"), the numbered
// rungs, the "Repeat until ..." exit line (flow.exit already reads as a full
// sentence), the LOOP_LEGEND line (only when some rung opens a window), and
// the closing note banded by its own note_kind ("framework" or "tip" - see
// style.css's .band-tip, added alongside .band-framework/.band-window for
// this).
export function renderLoop(flow) {
  const intro = band({ kind: flow.kind, text: flow.intro });
  const rungs = flow.rungs.map(([label, opens, sub], i) => renderRung(i + 1, label, opens, sub)).join("");
  const ticks = flow.rungs.some(r => r[1]);
  const legend = ticks
    ? h`<p class="body secondary loop-legend"><span class="loop-dot"></span>${LOOP_LEGEND}</p>`
    : "";
  const note = flow.note ? band({ kind: flow.note_kind, text: flow.note }) : "";
  return h`<div class="loop">${raw(intro)}<div class="loop-rungs">${raw(rungs)}</div><p class="body secondary loop-exit">${flow.exit}</p>${raw(legend)}${raw(note)}</div>`;
}
