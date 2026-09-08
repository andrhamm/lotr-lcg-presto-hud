// The left column: three read-only status zones (PLAYERS / QUEST / STAGING)
// plus the log block pinned to the bottom. Pure string builder like every
// other tablet render function - no document/window, so tests/test_tablet.py
// can drive it under node. Every value here is status (design spec, "The
// left column") - the one tap target per zone is its header's "Edit ›" chip
// (milestone 3), opening the players/quest/staging sheet; "Open ›" arrives
// with the log screen in milestone 4.
import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { glyph } from "./glyphs.js";
import { chip, zone } from "./primitives.js";
import { isUndone } from "./logfilter.js";
import { faceOf } from "./cards.js";
import { fmtMs } from "../../js/gamestate.js";
import { VIEW_LABELS } from "../../js/viewcopy.js";
import { icon } from "../../js/icons_svg.js";
import { scenarioIcon } from "./seticon.js";
import {
  THREAT_RED, THREAT_SHADOW, THREAT_BLACK, THREAT_BLACK_EDGE,
  WILLPOWER_GOLD, TRAIL_GREEN, TRAIL_BROWN,
} from "./palette.js";

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
  // The first-player marker. It was a literal U+2691 and the log prompt below
  // a U+25B6 - both of which iOS is free to render from its colour emoji face
  // rather than from the UI type. Drawn, like the rest of this client's
  // chrome (glyphs.js).
  const label = isFirst ? h`${raw(h`<span class="flag">${raw(glyph("flag", 16))}</span>`)}P${i + 1}` : h`P${i + 1}`;
  const elim = p.eliminated ? h`<div class="player-elim">${CHROME.eliminated}</div>` : "";
  return h`<div class="${cx("player-cell", p.eliminated && "is-eliminated")}">
<div class="${cx("player-label", isFirst && "is-first")}">${raw(label)}</div>
<div class="player-threat"><span class="num num-36">${p.threat}</span>${raw(icon("THREAT", 28, THREAT_RED, THREAT_SHADOW))}</div>
<div class="${cx("bar", danger && "bar-danger")}"></div>
<div class="player-stats">
<span class="stat">${raw(icon("WILLPOWER", 20, WILLPOWER_GOLD))}<span class="num num-26">${p.commit}</span></span>
<span class="${cx("stat", p.engaged === 0 && "is-dim")}">${raw(icon("THREAT", 20, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-26">${p.engaged}</span></span>
</div>${raw(elim)}</div>`;
}

// Every zone's header chip: same act/label pair shape, just the act differs
// (open_players/open_quest/open_staging) - task-2 brief's Rail interface
// line. height:30 (not the usual 44) because this is a header nav chip
// inside the strip-height-constrained rail, not a sheet's own tap target.
const editChip = act => chip({ act, label: h`${CHROME.edit} ›`, tone: "tan", height: 30 });

function renderPlayersZone(game) {
  const cells = game.players.map((p, i) => renderPlayerCell(game, p, i)).join("");
  return zone({
    name: CHROME.players,
    icon: icon("THREAT", 22, THREAT_RED, THREAT_SHADOW),
    edge: "gold",
    ground: "card",
    body: h`<div class="player-grid">${raw(cells)}</div>`,
    chip: editChip("open_players"),
  });
}

// The stage pill: "Stage {questLabel}", progress/points, and the name of
// whichever face the quest is currently showing (A or B - see cards.js) when
// the preloaded catalog data has one (a bare game in tests does not, so this
// line is omitted rather than shown blank). Catalog cards are
// `{ faces: [...] }`, not `{ name }` at the top level.
//
// The scenario's own set icon (Task 5, seticon.js's scenarioIcon) goes
// before the "Stage n" label - `game.scenario?.name` rather than the stage
// card's own name, since that is the one name this app can turn into an
// icon slug at all (a scenario is usually also the encounter set its own
// quest cards belong to; a bare/manual game with no preloaded scenario has
// no name to try, so the icon is omitted rather than guessing).
function renderStagePill(game) {
  const card = game.stages[game.stage_idx]?.cards?.[game.card_idx];
  const name = faceOf(card, game.quest.side)?.name;
  // Milestone 6 (Task 3): with a real scenario loaded that name is also the
  // way back to the Scenario overview - the difficulty, the sets to gather,
  // the stages and the cards, read-only. A bare/manual game has no scenario
  // to open (and no seated bundle either, which is what open_overview
  // declines on), so there it stays the plain line it has always been.
  const nameRow = !name ? ""
    : game.scenario?.slug
      ? h`<button type="button" class="body pill-name pill-name-btn" data-act="open_overview">${name}</button>`
      : h`<p class="body pill-name">${name}</p>`;
  const stageIcon = scenarioIcon(game, 20);
  return h`<div class="pill">
<div class="pill-head">${raw(stageIcon)}<span class="label">${CHROME.stage} ${game.questLabel()}</span></div>
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
<p class="body pill-name">${loc.name ?? CHROME.location}</p>
<div class="pill-stat">${raw(icon("TRAIL", 18, TRAIL_GREEN, TRAIL_BROWN))}<span class="num num-26">${loc.progress}</span><span class="pill-sep">/</span><span class="num num-26">${loc.points}</span></div>
</div>`;
}

// Side quests do not get their own rail pills - that is unscoped for now,
// not a milestone-3 promise this comment used to make. The rail's own row is
// always this fixed dashed "+ side quest" affordance (per the task-4 brief);
// the quest sheet (sheet_quest.js) is what actually lists every side quest.
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
    chip: editChip("open_quest"),
  });
}

// A compact staging pill: a label caption stacked over a row of icon + one
// number - "each num-34 with the black helm" per the brief, plus the caption
// a controller ruling added so the three pills (Threat/Enemies/Locations) are
// named rather than left to a shared icon to disambiguate. threat/enemies/
// locations share the one icon; there is no separate mask for enemy- or
// location-count, and the caption is what tells them apart now. Stacked
// (caption on top, icon+number below) rather than one row, so the caption
// never collides with the icon in the 324px column - see .pill-compact and
// .staging-grid in style.css.
function renderStagingPill(caption, value, mark = "") {
  return h`<div class="pill pill-compact">
<span class="label">${caption}</span>
<div class="pill-stat">${raw(mark)}<span class="num num-34">${value}</span></div>
</div>`;
}

function renderStagingZone(game) {
  // The helm is on THREAT only. All three pills used to wear it, so a "3"
  // under LOCATIONS was drawn beside the threat mark - reading as "threat 3"
  // for a number that counts locations. There is no enemy or location mask
  // in the icon set, and the honest answer to that is no mark, not the wrong
  // one; the caption above each number is what names it.
  const body = renderStagingPill(CHROME.threat, game.staging,
      icon("THREAT", 20, THREAT_BLACK, THREAT_BLACK_EDGE))
    + renderStagingPill(CHROME.enemies, game.staging_enemies)
    + renderStagingPill(CHROME.locations, game.staging_locations);
  return zone({
    name: CHROME.staging,
    icon: icon("THREAT", 22, THREAT_BLACK, THREAT_BLACK_EDGE),
    edge: "outline",
    ground: "well",
    body: h`<div class="staging-grid">${raw(body)}</div>`,
    chip: editChip("open_staging"),
  });
}

// Last four log entries, then a prompt row naming the current view. `t` is
// null in tests (no clock wired up) - render an empty time cell then rather
// than fmtMs(null). Four, not five: bumping .log-text/.log-time off the
// 13px floor (finding 5) grew each row, and the rail's fixed-height zones
// above leave no room in the 1024px-tall viewport for a fifth. The header is
// a row now (milestone 4): the block's name plus "Open ›", the one way into
// the Game Log screen - same 30px header-nav chip as every zone's "Edit ›",
// in a 44px row that carries the tap-target floor for it.
//
// A row whose delta the cursor has stepped back past is greyed here exactly
// as it is on the log screen - one predicate, logfilter.js's isUndone: the
// rail shows the last four lines, and after an undo some of them describe a
// state the game is no longer in.
//
// Four rows are always RENDERED; the CSS decides how many are seen. The rows
// sit in their own container that clips from the top (.log-rows-clip), so on
// a crowded rail - three players, an eliminated one, a stage name and an
// active location - the oldest line is what goes, never the prompt row.
function renderLogBlock(game) {
  const rows = game.log.slice(-4).map(e => {
    const time = typeof e.t === "number" ? fmtMs(e.t) : "";
    return h`<div class="${cx("log-row", isUndone(game, e) && "is-undone")}"><span class="log-time">${time}</span><span class="log-text">${e.text}</span></div>`;
  }).join("");
  const prompt = VIEW_LABELS[game.view] ?? game.view;
  const openChip = chip({ act: "open_log", label: h`${CHROME.open} ›`, tone: "tan", height: 30 });
  return h`<div class="log-block">
<div class="log-head-row"><span class="label">${CHROME.log}</span>${raw(openChip)}</div>
<div class="log-rows-clip">${raw(rows)}</div>
<div class="log-prompt">${raw(glyph("next", 14))} ${prompt}</div>
</div>`;
}

export function renderRail(game, ui) {
  return h`<aside class="column">${raw(renderPlayersZone(game))}${raw(renderQuestZone(game))}${raw(renderStagingZone(game))}${raw(renderLogBlock(game))}</aside>`;
}
