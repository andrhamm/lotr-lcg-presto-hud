// The players sheet (milestone 3): one screen for every player, no tabs -
// design spec point 7. Opened from the rail's PLAYERS "Edit ›" chip
// (rail.js), closed by "Done" or the scrim. Every edit here goes through
// actions.js's dispatch() (the "thr"/"commit"/"eng±"/"all_thr" acts), which
// logs verbatim what the web twin's PlayersDetailModal logs
// (docs/js/screens.js) - see actions.js for the exact strings.
import { h, raw, cx, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { icon } from "../../js/icons_svg.js";
import {
  THREAT_RED, THREAT_SHADOW, THREAT_BLACK, THREAT_BLACK_EDGE, WILLPOWER_GOLD,
} from "./palette.js";

// A stat column: its NAME, then its controls. The name is drawn on the top
// row only (`head`) and kept as hidden-but-present ink on the rest, so the
// columns are labelled exactly once and every row still lines up.
function block(kind, head, name, controls) {
  const cap = h`<span class="${cx("label", "psheet-cap", !head && "is-ghost")}">${name}</span>`;
  return h`<div class="${cx("psheet-block", kind)}">${raw(cap)}<div class="psheet-controls">${raw(controls)}</div></div>`;
}

function step(act, arg, label) {
  return h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${label}</button>`;
}

// Everyone-at-once row: "All −1 / +1 / +2" - design spec's Players-sheet
// header, and the tablet's answer to a Doomed keyword (raise every living
// player's threat with one tap instead of one per player).
function renderEveryoneRow() {
  const c = (arg, label) => chip({ act: "all_thr", arg, label: h`${CHROME.all} ${label}`, tone: "tan" });
  return h`<div class="psheet-everyone">${raw(c("-1", "−1"))}${raw(c("1", "+1"))}${raw(c("2", "+2"))}</div>`;
}

// One player's threat block: −5 −1 [threat helm 48] +1 +5, per the
// players-sheet brief.
function renderThreatBlock(i, threat, head) {
  return block("psheet-threat", head, CHROME.threat, h`${raw(step("thr", `${i}:-5`, "−5"))}
${raw(step("thr", `${i}:-1`, "−1"))}
<span class="psheet-val">${raw(icon("THREAT", 48, THREAT_RED, THREAT_SHADOW))}<span class="num num-48">${threat}</span></span>
${raw(step("thr", `${i}:1`, "+1"))}
${raw(step("thr", `${i}:5`, "+5"))}`);
}

// Committed willpower: − [sun 36] +.
function renderWillBlock(i, commit, head) {
  return block("psheet-will", head, CHROME.committed, h`${raw(step("commit", `${i}:-1`, "−"))}
<span class="psheet-val">${raw(icon("WILLPOWER", 36, WILLPOWER_GOLD))}<span class="num num-36">${commit}</span></span>
${raw(step("commit", `${i}:1`, "+"))}`);
}

// Engaged enemies: − [black helm 36] + - reuses milestone 2's eng±, whose
// arg is the bare player index (no "i:n" pair, unlike thr/commit above).
function renderEngBlock(i, engaged, head) {
  return block("psheet-eng", head, CHROME.engagedEnemies, h`${raw(step("eng-", `${i}`, "−"))}
<span class="psheet-val">${raw(icon("THREAT", 36, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-36">${engaged}</span></span>
${raw(step("eng+", `${i}`, "+"))}`);
}

function renderPlayerRow(p, i, head) {
  if (p.eliminated) {
    // No steppers on an eliminated player - the twin never lets one edit its
    // own way back into the game from here (elimination is reversed only by
    // a card effect, the elim sheet's "avert" - Task 3).
    return h`<div class="psheet-row psheet-row-elim">
<span class="body psheet-name">P${i + 1}</span>
<span class="player-elim">${CHROME.eliminated}</span>
</div>`;
  }
  const dist = p.elimination - p.threat;
  const danger = dist <= 10;
  return h`<div class="psheet-row">
<div class="psheet-id">
<span class="body psheet-name">P${i + 1}</span>
<span class="${cx("body", "secondary", danger && "is-danger")}">${fmt(CHROME.toElimination, dist, p.elimination)}</span>
</div>
${raw(renderThreatBlock(i, p.threat, head))}
${raw(renderWillBlock(i, p.commit, head))}
${raw(renderEngBlock(i, p.engaged, head))}
</div>`;
}

export function renderPlayersSheet(game, ui) {
  // `head` marks the first row that is NOT eliminated: an eliminated row has
  // no steppers at all, so hanging the column names on it would leave the
  // columns unnamed.
  const headIdx = game.players.findIndex(p => !p.eliminated);
  const rows = game.players.map((p, i) => renderPlayerRow(p, i, i === headIdx)).join("");
  // No game-wide elimination figure in the title (review finding M9): each
  // row already prints its OWN player's distance to elimination
  // ("N to M", above), and elim_setlvl edits that level per player - a
  // single game.elimination_threat here was the wrong number the instant
  // any one row's level was recalibrated away from the default.
  return h`<h1 class="display">${CHROME.players}</h1>
${raw(renderEveryoneRow())}
<div class="psheet-list">${raw(rows)}</div>
<div class="cta-row">${raw(cta({ act: "sheet_close", label: CHROME.done }))}</div>`;
}
