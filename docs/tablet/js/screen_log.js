// The Game Log screen (milestone 4, Task 3): every line the game has written,
// filtered, with the replay transport under it and one row selectable as a
// rewind target. Pure string builder like every other tablet render function -
// no document/window, so tests/test_tablet.py can drive it under node.
//
// Two columns, not a sheet over the play screen: the explainer and the
// per-round index are reference text a player reads WHILE choosing a line,
// and a modal would cover the very rows it is explaining.
import { h, raw, cx, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta, transportButton } from "./primitives.js";
// isUndone/isRewindable live in logfilter.js with the filters - the rail and
// acts_log.js ask the same two questions, and one answer means the button
// this screen offers and the act that answers it can never disagree about
// which rows are targets.
import { FILTERS, matches, isUndone, isRewindable } from "./logfilter.js";
import { fmtMs } from "../../js/gamestate.js";

// One row. Rewindable rows are bevelled <button>s because they are tappable -
// the HUD's one chrome rule (primitives.js); a row with nowhere to rewind to
// is a plain <li> with no bevel and no data-act, so there is nothing for
// app.js's delegation to catch.
function renderRow(game, log, e) {
  const cls = cx("log-line", isUndone(game, e) && "is-undone", log.sel === e.seq && "is-sel");
  const time = typeof e.t === "number" ? fmtMs(e.t) : "";
  const cells = h`<span class="label log-stamp">R${e.round}.${e.step}</span><span class="label log-time">${time}</span><span class="body log-msg">${e.text}</span>`;
  if (!isRewindable(game, e)) return h`<li class="${cls}">${raw(cells)}</li>`;
  return h`<li><button type="button" class="${cls}" data-act="log_sel" data-arg="${e.seq}">${raw(cells)}</button></li>`;
}

// The filter row. Chips, because a filter is chrome naming a slot, not a
// sentence: the current one is gold, the rest tan.
function renderFilters(log) {
  const chips = FILTERS.map(f => chip({
    act: "log_filter", arg: f, label: CHROME.filters[f],
    tone: f === log.filter ? "gold" : "tan", height: 44,
  })).join("");
  return h`<div class="filter-row">${raw(chips)}</div>`;
}

// Six controls, where the strip carries four: the log screen is where a
// player goes to move by ROUND, so ◀◀ / ▶▶ are here and nowhere else. An
// unavailable one drops to the same inert, unbevelled span the strip uses -
// one off state for the whole client (see primitives.js's transportButton).
function renderTransport(game) {
  const back = game.canUndo(), fwd = game.canRedo();
  const b = (act, glyph, on, title) => transportButton({ act, glyph, on, title });
  const controls = b("rw_first", "⏮", back, CHROME.rwFirst)
    + b("rw_round_back", "◀◀", back, CHROME.rwRoundBack)
    + b("rw_undo", "◀", back, CHROME.rwUndo)
    + b("rw_redo", "▶", fwd, CHROME.rwRedo)
    + b("rw_round_fwd", "▶▶", fwd, CHROME.rwRoundFwd)
    + b("rw_last", "⏭", fwd, CHROME.rwLast);
  return h`<div class="transport">${raw(controls)}</div>`;
}

// One entry per round the log touched, with its line count and the wall-clock
// span it covered. `t` is null in tests (no clock wired up) and null for any
// row written before one was - the span is omitted then rather than printed
// as a pair of zeroes. Rounds only ever increase, so consecutive grouping is
// enough (strip.js's segments() groups its phases the same way).
function renderRounds(game) {
  const rounds = [];
  for (const e of game.log) {
    const last = rounds[rounds.length - 1];
    const r = last && last.round === e.round ? last : null;
    if (!r) rounds.push({ round: e.round, n: 1, from: null, to: null });
    else r.n += 1;
    const cur = rounds[rounds.length - 1];
    if (typeof e.t === "number") {
      if (cur.from === null) cur.from = e.t;
      cur.to = e.t;
    }
  }
  const items = rounds.map(r => {
    const span = r.from === null ? "" : h` · ${fmtMs(r.from)}–${fmtMs(r.to)}`;
    const line = r.n === 1 ? fmt(CHROME.roundLineOne, r.round)
                           : fmt(CHROME.roundLine, r.round, r.n);
    return h`<li class="body">${line}${raw(span)}</li>`;
  }).join("");
  return items;
}

function renderSide(game) {
  return h`<aside class="log-side">
<h2 class="label">${CHROME.rewinding}</h2>
<p class="body">${CHROME.rewindExplain1}</p>
<p class="body">${CHROME.rewindExplain2}</p>
<p class="body">${CHROME.rewindExplain3}</p>
<h2 class="label">${CHROME.rounds}</h2>
<ol class="round-list">${raw(renderRounds(game))}</ol>
</aside>`;
}

export function renderLogScreen(game, ui) {
  // newUi() seats ui.log, and open_log re-seats it - this fallback is for a
  // caller that renders the screen without either (a test, a resumed save
  // written by an older build), not a state the app reaches.
  const log = ui.log ?? { filter: "all", sel: null };
  const kept = game.log.filter(e => matches(log.filter, e));
  // A filter that matches nothing renders one sentence rather than a blank
  // column: an empty list and a broken screen look identical otherwise.
  const rows = kept.length
    ? kept.map(e => renderRow(game, log, e)).join("")
    : h`<li><p class="body secondary">${CHROME.logEmptyFilter}</p></li>`;

  // The CTA is live only while the selected row is a rewind target. With no
  // selection it is an inert, unbevelled span carrying no data-act at all -
  // the same "not a tap target" shape transportButton's off case uses on the
  // strip - so a tap on it cannot look like it did something.
  const sel = log.sel === null ? null : game.log.find(e => e.seq === log.sel);
  const rewind = sel && isRewindable(game, sel)
    ? cta({ act: "log_rewind", label: CHROME.rewindTo, tone: "gold", grow: false })
    : h`<span class="cta cta-gold is-off">${CHROME.rewindTo}</span>`;

  const foot = h`<footer class="log-foot">${raw(renderTransport(game))}
<span class="label transport-readout">${fmt(CHROME.stepOf, game.replay_step + 1, game.deltas.length)}</span>
${raw(rewind)}${raw(chip({ act: "export_log", label: CHROME.exportLog, tone: "tan" }))}</footer>`;

  return h`<section class="logscreen">
<header class="log-head"><h1 class="display">${CHROME.log}</h1>${raw(chip({ act: "log_close", label: h`${CHROME.close} ›`, tone: "tan" }))}</header>
<div class="log-main">${raw(renderFilters(log))}
<ol class="log-rows">${raw(rows)}</ol>
${raw(foot)}</div>
${raw(renderSide(game))}</section>`;
}
