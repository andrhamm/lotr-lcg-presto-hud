// The round's timeline: one segment per phase, one tick per flow view, the
// round's action-window ticks, and the current playhead. It is also the
// client's replay NAVIGATION - every tick a delta actually reached this round
// is a rewind target - which is why there is no separate transport up here
// any more. The Game Log screen keeps its own six-control one, where moving
// by round is the point. Pure string
// builder like every other tablet render function - no document/window, so
// tests/test_tablet.py can drive it under node the way it drives the model.
import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip } from "./primitives.js";
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

  // The Menu sheet's one entry point (milestone 3): new game mid-play. It
  // sits at the RIGHT end of the strip now, with the reload - app-level
  // chrome, in the corner every other screen keeps app-level chrome in. It
  // was crammed against the round number, sharing a 2x2 grid with a replay
  // transport, in the spot the eye reads first.
  const menuChip = chip({ act: "open_menu", label: h`${CHROME.menu}`, tone: "tan", height: 36 });


  // Round on the left, the round's own timeline across the middle, app chrome
  // on the right. The strip IS the navigation: every tick a delta reached is
  // a rewind target (renderTick's rw_tick), so a separate four-button
  // transport beside the round number was a second control for a job the
  // timeline already does - and it was the first thing the eye met.
  // A LEGEND, because a shape nobody can name is decoration. The strip's two
  // marks encode the single most important distinction in a round - what
  // happens anyway, and when you are allowed to act - and until now the only
  // way to learn which was which was to watch the playhead move.
  // "An action ability may only be triggered during an action window" (Rules
  // Reference), which is exactly the thing a tracker exists to teach.
  const legend = h`<div class="legend">
<span class="legend-item"><i class="tick tick-framework is-done"></i>${CHROME.legendFramework}</span>
<span class="legend-item"><i class="tick tick-window is-done"></i>${CHROME.actionWindow}</span>
</div>`;

  return h`<header class="strip">
<div class="round"><div class="round-n"><span class="label">${CHROME.round}</span><span class="num num-40">${game.round}</span></div>${raw(legend)}</div>
<div class="strip-flow">${raw(body)}</div>
<div class="strip-tools">${raw(menuChip)}</div>
</header>`;
}
