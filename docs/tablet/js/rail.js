// The left column: three read-only status zones (PLAYERS / QUEST / STAGING)
// plus the log block pinned to the bottom. Pure string builder like every
// other tablet render function - no document/window, so tests/test_tablet.py
// can drive it under node. No chips or buttons in this milestone: every
// value here is status (design spec, "The left column") - the "Edit >"
// chips arrive with the sheets in milestone 3, "Open >" with the log screen
// in milestone 4.
import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { zone } from "./primitives.js";
import { fmtMs } from "../../js/gamestate.js";
import { VIEW_LABELS } from "../../js/viewcopy.js";
import { icon } from "../../js/icons_svg.js";

// Stat icon colours, from design/stat-system.md (cited in the task-4 brief):
// player threat red with a charcoal shadow, enemy/staging threat black with
// a light edge, willpower gold, progress green with a brown shadow. Literal
// rgb() strings, not CSS custom properties - an SVG fill="" attribute in a
// string builder can't read var(--x).
const THREAT_RED = "rgb(247,101,62)";
const THREAT_RED_SHADOW = "rgb(7,5,3)";
const THREAT_BLACK = "rgb(0,0,0)";
const THREAT_BLACK_EDGE = "rgb(96,86,54)";
const WILLPOWER_GOLD = "rgb(214,180,110)";
const TRAIL_GREEN = "rgb(136,168,92)";
const TRAIL_BROWN = "rgb(104,70,34)";

// One PLAYERS cell: label (gold + flag glyph for the first player), threat,
// a 3px bar that turns bar-danger inside 10 of elimination, then a row with
// willpower commit and engaged enemies (dim at 0).
function renderPlayerCell(game, p, i) {
  const isFirst = i === game.first_player;
  const danger = p.threat >= p.elimination - 10;
  // Sub-fragments built with h`` come back as plain strings (h returns a
  // string, not a Raw), so every one of them needs raw() at the point it is
  // re-interpolated into the outer template - otherwise the outer h``
  // re-escapes the already-escaped markup.
  const label = isFirst ? h`${raw('<span class="flag">&#9873;</span>')}P${i + 1}` : h`P${i + 1}`;
  const elim = p.eliminated ? h`<div class="player-elim">${CHROME.eliminated}</div>` : "";
  return h`<div class="${cx("player-cell", p.eliminated && "is-eliminated")}">
<div class="${cx("player-label", isFirst && "is-first")}">${raw(label)}</div>
<div class="player-threat"><span class="num num-36">${p.threat}</span>${raw(icon("THREAT", 28, THREAT_RED, THREAT_RED_SHADOW))}</div>
<div class="${cx("bar", danger && "bar-danger")}"></div>
<div class="player-stats">
<span class="stat">${raw(icon("WILLPOWER", 20, WILLPOWER_GOLD))}<span class="num num-26">${p.commit}</span></span>
<span class="${cx("stat", p.engaged === 0 && "is-dim")}">${raw(icon("THREAT", 20, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-26">${p.engaged}</span></span>
</div>${raw(elim)}</div>`;
}

function renderPlayersZone(game) {
  const cells = game.players.map((p, i) => renderPlayerCell(game, p, i)).join("");
  return zone({
    name: CHROME.players,
    icon: icon("THREAT", 22, THREAT_RED, THREAT_RED_SHADOW),
    edge: "gold",
    ground: "card",
    body: h`<div class="player-grid">${raw(cells)}</div>`,
  });
}

// The stage pill: "Stage {questLabel}", progress/points, and the stage's
// own name when the preloaded catalog data has one (a bare game in tests
// does not, so this line is omitted rather than shown blank).
function renderStagePill(game) {
  const name = game.stages[game.stage_idx]?.cards?.[game.card_idx]?.name;
  const nameRow = name ? h`<p class="body pill-name">${name}</p>` : "";
  return h`<div class="pill">
<div class="pill-head"><span class="label">Stage ${game.questLabel()}</span></div>
<div class="pill-stat">${raw(icon("TRAIL", 18, TRAIL_GREEN, TRAIL_BROWN))}<span class="num num-26">${game.quest.progress}</span><span class="pill-sep">/</span><span class="num num-26">${game.quest.points}</span></div>
${raw(nameRow)}</div>`;
}

// The active location's pill, or a dashed "no active location" slot - there
// is at most one shown here even though the model holds a list (five
// printed cards allow two active at once; that gets its own row in the
// milestone-3 quest editor, not the rail).
function renderLocationPill(game) {
  const loc = game.active_locations[0];
  if (!loc) return h`<div class="pill pill-dashed"><p class="body secondary">${CHROME.noLocation}</p></div>`;
  return h`<div class="pill">
<p class="body pill-name">${loc.name ?? "Location"}</p>
<div class="pill-stat">${raw(icon("TRAIL", 18, TRAIL_GREEN, TRAIL_BROWN))}<span class="num num-26">${loc.progress}</span><span class="pill-sep">/</span><span class="num num-26">${loc.points}</span></div>
</div>`;
}

// Side quests get their own pills in milestone 3; for now this is always
// the dashed "+ side quest" affordance, per the task-4 brief.
function renderSideQuestSlot() {
  return h`<div class="pill pill-dashed"><p class="body secondary">${CHROME.sideQuest}</p></div>`;
}

function renderQuestZone(game) {
  const body = renderStagePill(game) + renderLocationPill(game) + renderSideQuestSlot();
  return zone({
    name: CHROME.quest,
    icon: icon("TRAIL", 22, TRAIL_GREEN, TRAIL_BROWN),
    edge: "green",
    ground: "card",
    body,
  });
}

// A compact staging pill: icon + one number, no caption - "each num-34 with
// the black helm" per the brief. threat/enemies/locations share the one
// icon; there is no separate mask for enemy- or location-count, and the
// zone header already says what section this is.
function renderStagingPill(value) {
  return h`<div class="pill pill-compact">${raw(icon("THREAT", 26, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-34">${value}</span></div>`;
}

function renderStagingZone(game) {
  const body = renderStagingPill(game.staging) + renderStagingPill(game.staging_enemies) + renderStagingPill(game.staging_locations);
  return zone({
    name: CHROME.staging,
    icon: icon("THREAT", 22, THREAT_BLACK, THREAT_BLACK_EDGE),
    edge: "outline",
    ground: "well",
    body: h`<div class="staging-row">${raw(body)}</div>`,
  });
}

// Last five log entries, then a prompt row naming the current view. `t` is
// null in tests (no clock wired up) - render an empty time cell then rather
// than fmtMs(null).
function renderLogBlock(game) {
  const rows = game.log.slice(-5).map(e => {
    const time = typeof e.t === "number" ? fmtMs(e.t) : "";
    return h`<div class="log-row"><span class="log-time">${time}</span><span class="log-text">${e.text}</span></div>`;
  }).join("");
  const prompt = VIEW_LABELS[game.view] ?? game.view;
  return h`<div class="log-block">
<div class="label">${CHROME.log}</div>
${raw(rows)}
<div class="log-prompt">&#9654; ${prompt}</div>
</div>`;
}

export function renderRail(game, ui) {
  return h`<aside class="column">${raw(renderPlayersZone(game))}${raw(renderQuestZone(game))}${raw(renderStagingZone(game))}${raw(renderLogBlock(game))}</aside>`;
}
