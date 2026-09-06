// The transport strip: one segment per phase, one tick per flow view, the
// round's action-window ticks, and the current playhead. Pure string
// builder like every other tablet render function - no document/window, so
// tests/test_tablet.py can drive it under node the way it drives the model.
import { h, raw, cx, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, transportButton } from "./primitives.js";
import {
  flowViews, VIEW_STEP, windowAfter, isActionWindow, lastWindowBefore,
  phaseViewOf,
} from "../../js/gamestate.js";
import { VIEW_LABELS } from "../../js/viewcopy.js";
import { PHASES, step } from "../../js/phases.js";

// A flow view that IS its own action window, with no separate aw_ pairing:
// Planning's 2.P (player actions throughout), and Combat's 6.E (enemy
// attacks) and 6.P (player attacks) - phases.js marks all three
// action_window, and gamestate.js's windowAfter() has no "aw_" key for any
// of them, so each draws its own tick as the round's window tick rather than
// pairing with a separate one.
const isOwnWindowView = v => isActionWindow(v) && !windowAfter(v);

const phaseLabel = id => {
  const p = PHASES.find(ph => ph.id === id);
  return p ? p.label : id;
};

// done / current / future for a view at position `idx` in flowViews(),
// relative to the view at `curIdx`.
const stateOf = (idx, curIdx) => {
  if (idx < 0 || curIdx < 0) return "is-future";
  if (idx < curIdx) return "is-done";
  if (idx === curIdx) return "is-current";
  return "is-future";
};

// One flow view's tick, plus (when it has one) the round window that
// follows it. Under "bands" the window is drawn on the view itself, but the
// strip still shows it as a tick of its own - just never named "aw_...":
// only the plain view id ever reaches data-view/title.
//
// The view's own tick is a rewind target exactly when some delta actually
// entered it this round (game.deltaIndexForView) - a future view, or one the
// round skipped past, has nowhere to rewind TO, so it stays the plain span
// it always was. The window tick (`aw`) is never a tap target of its own -
// it pairs with the view that opened it, which is already the button.
function renderTick(game, v, idx, curIdx) {
  const state = stateOf(idx, curIdx);
  const own = isOwnWindowView(v);
  const cls = cx("tick", own ? "tick-window" : "tick-framework", state);
  const label = VIEW_LABELS[v] ?? v;
  const playhead = state === "is-current" ? raw('<i class="playhead"></i>') : "";
  const tick = h`<span class="${cls}" data-view="${v}" title="${label}">${playhead}</span>`;
  const canRewind = game.deltaIndexForView(game.round, v) >= 0;
  let out = canRewind
    ? h`<button type="button" class="tick-btn" data-act="rw_tick" data-arg="${v}" title="${label}">${raw(tick)}</button>`
    : tick;
  const aw = windowAfter(v);
  if (aw) {
    const wstate = idx <= curIdx ? "is-done" : "is-future";
    const wlabel = VIEW_LABELS[aw] ?? label;
    out += h`<span class="${cx("tick", "tick-window", wstate)}" title="${wlabel}"></span>`;
  }
  return out;
}

// One phase segment: its name, its ticks, a log-count badge, and (when a
// promoted skip passes every one of its views) the skippable note.
//
// `offPhase` is the phase of an off-flow view (quest_setup, quest_sailing -
// see renderStrip) standing outside flowViews() entirely, so curIdx is -1 and
// every tick would otherwise render is-future. When this segment IS that
// phase, treat its first tick's index as the current one: is-current picks
// up its playhead and the .seg:has(.tick.is-current) CSS rule golds the
// phase name for free - no separate "current segment" styling needed.
function renderSeg(game, views, seg, curIdx, skipRange, offPhase) {
  const idxs = seg.views.map(v => views.indexOf(v));
  const skippable = !!skipRange && idxs.every(i => i > skipRange.ci && i <= skipRange.li);
  const effectiveCur = (offPhase !== null && seg.phase === offPhase) ? idxs[0] : curIdx;
  const ticks = seg.views.map((v, k) => renderTick(game, v, idxs[k], effectiveCur)).join("");

  const stepIds = new Set(seg.views.map(v => VIEW_STEP[v]));
  const count = game.log.filter(e => e.round === game.round && stepIds.has(e.step)).length;
  const badge = count > 0 ? h`<span class="log-badge">${count}</span>` : "";
  const note = skippable
    ? h`<div class="skip-note">${VIEW_STEP[skipRange.landing]}</div>`
    : "";

  return h`<div data-phase="${seg.phase}" class="${cx("seg", skippable && "is-skippable")}"><div class="phase-name">${phaseLabel(seg.phase)}</div><div class="tick-row">${raw(ticks)}${raw(badge)}</div>${raw(note)}</div>`;
}

// Group flowViews() by step(VIEW_STEP[v]).phase. The views arrive already in
// round order and a phase is never revisited, so consecutive grouping is
// enough - no need to walk PHASES separately to find each one's views.
function segments(views) {
  const segs = [];
  for (const v of views) {
    const phase = step(VIEW_STEP[v]).phase;
    const last = segs[segs.length - 1];
    if (last && last.phase === phase) last.views.push(v);
    else segs.push({ phase, views: [v] });
  }
  return segs;
}

export function renderStrip(game, ui) {
  const views = flowViews();
  const curIdx = views.indexOf(game.view);

  // quest_setup and quest_sailing are off VIEW_ORDER entirely (pre-round
  // setup, and the sailing test - a band drawn instead of a flow view under
  // this client's window policy), so indexOf above is always -1 for them and
  // every tick would render is-future with no playhead at all. Resolve the
  // view's PHASE instead and let renderSeg mark that phase's segment
  // current. quest_setup's phase (Beginning) has no segment before round 1 -
  // offPhase matches nothing, so nothing lights up, which is correct: there
  // is no "current" yet.
  const offPhase = curIdx < 0 ? (step(VIEW_STEP[game.view])?.phase ?? null) : null;

  // A promoted skip highlights every segment made up entirely of views it
  // passes: strictly after the current view, up to and including the
  // landing (lastWindowBefore(skip.to)) - the landing is the view the skip
  // actually lands on, so its segment is skippable too even though the
  // landing itself isn't "passed" in the log-message sense.
  const offer = game.skipOffer();
  let skipRange = null;
  if (offer && offer.promoted) {
    // lastWindowBefore walks the raw VIEW_ORDER, so under "bands" it can hand
    // back an aw_ landing that flowViews() has filtered out. Index its phase
    // view instead - same idiom as GameState.skipTo (gamestate.js, "stay
    // total") - so the highlight never silently disappears via indexOf(-1).
    const landing0 = lastWindowBefore(offer.skip.to);
    const landing = views.includes(landing0) ? landing0 : phaseViewOf(landing0);
    const li = views.indexOf(landing);
    if (curIdx >= 0 && li > curIdx) skipRange = { ci: curIdx, li, landing };
  }

  const body = segments(views)
    .map(seg => renderSeg(game, views, seg, curIdx, skipRange, offPhase))
    .join("");

  // The Menu sheet's one entry point (milestone 3): new game mid-play. Same
  // header-nav chip shape as the rail's "Edit ›" (rail.js), height:30 so it
  // sits beside the round number instead of stacking past the strip's 96px.
  const menuChip = chip({ act: "open_menu", label: h`${CHROME.menu} ›`, tone: "tan", height: 30 });

  // The transport (Task 2, milestone 4): ⏮ ◀ ▶ ⏭ move the replay cursor by
  // index/single-step/round - canUndo()/canRedo() alone decide whether each
  // end is live, exactly like Back/Redo everywhere else in this client.
  // Placed as a second pair of rows in `.round` (style.css turns the block
  // into a 2x2 grid so the four 44px buttons sit beside the round number
  // instead of stacking past the strip's 96px - see the CSS comment there).
  const canB = game.canUndo(), canF = game.canRedo();
  const transport = h`<div class="transport">${raw(transportButton({ act: "rw_first", glyph: "⏮", on: canB, title: CHROME.rwFirst }))}${raw(transportButton({ act: "rw_undo", glyph: "◀", on: canB, title: CHROME.rwUndo }))}${raw(transportButton({ act: "rw_redo", glyph: "▶", on: canF, title: CHROME.rwRedo }))}${raw(transportButton({ act: "rw_last", glyph: "⏭", on: canF, title: CHROME.rwLast }))}</div>
<div class="label transport-readout">${fmt(CHROME.stepOf, game.replay_step + 1, game.deltas.length)}</div>`;

  return h`<header class="strip"><div class="round"><span class="label">${CHROME.round}</span><div class="round-row"><span class="num num-40">${game.round}</span>${raw(menuChip)}</div>${raw(transport)}</div>${raw(body)}</header>`;
}
