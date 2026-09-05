// The players sheet (milestone 3): one screen for every player, no tabs -
// design spec point 7. Opened from the rail's PLAYERS "Edit ›" chip
// (rail.js), closed by "Done" or the scrim. Every edit here goes through
// actions.js's dispatch() (the "thr"/"commit"/"eng±"/"all_thr" acts), which
// logs verbatim what the web twin's PlayersDetailModal logs
// (docs/js/screens.js) - see actions.js for the exact strings.
import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { icon } from "../../js/icons_svg.js";
import {
  THREAT_RED, THREAT_SHADOW, THREAT_BLACK, THREAT_BLACK_EDGE, WILLPOWER_GOLD,
} from "./palette.js";

function step(act, arg, label) {
  return h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${label}</button>`;
}

// Everyone-at-once row: "All −1 / +1 / +2" - design spec's Players-sheet
// header, and the tablet's answer to a Doomed keyword (raise every living
// player's threat with one tap instead of one per player).
function renderEveryoneRow() {
  const c = (arg, label) => chip({ act: "all_thr", arg, label: `${CHROME.all} ${label}`, tone: "tan" });
  return h`<div class="psheet-everyone">${raw(c("-1", "−1"))}${raw(c("1", "+1"))}${raw(c("2", "+2"))}</div>`;
}

// One player's threat block: −5 −1 [threat helm 48] +1 +5, per the
// players-sheet brief.
function renderThreatBlock(i, threat) {
  return h`<div class="psheet-threat">
${raw(step("thr", `${i}:-5`, "−5"))}
${raw(step("thr", `${i}:-1`, "−1"))}
<span class="psheet-val">${raw(icon("THREAT", 48, THREAT_RED, THREAT_SHADOW))}<span class="num num-48">${threat}</span></span>
${raw(step("thr", `${i}:1`, "+1"))}
${raw(step("thr", `${i}:5`, "+5"))}
</div>`;
}

// Committed willpower: − [sun 36] +.
function renderWillBlock(i, commit) {
  return h`<div class="psheet-will">
${raw(step("commit", `${i}:-1`, "−"))}
<span class="psheet-val">${raw(icon("WILLPOWER", 36, WILLPOWER_GOLD))}<span class="num num-36">${commit}</span></span>
${raw(step("commit", `${i}:1`, "+"))}
</div>`;
}

// Engaged enemies: − [black helm 36] + - reuses milestone 2's eng±, whose
// arg is the bare player index (no "i:n" pair, unlike thr/commit above).
function renderEngBlock(i, engaged) {
  return h`<div class="psheet-eng">
${raw(step("eng-", `${i}`, "−"))}
<span class="psheet-val">${raw(icon("THREAT", 36, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-36">${engaged}</span></span>
${raw(step("eng+", `${i}`, "+"))}
</div>`;
}

function renderPlayerRow(p, i) {
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
<span class="${cx("body", "secondary", danger && "is-danger")}">${dist} to ${p.elimination}</span>
</div>
${raw(renderThreatBlock(i, p.threat))}
${raw(renderWillBlock(i, p.commit))}
${raw(renderEngBlock(i, p.engaged))}
</div>`;
}

export function renderPlayersSheet(game, ui) {
  const rows = game.players.map((p, i) => renderPlayerRow(p, i)).join("");
  return h`<h1 class="display">${CHROME.players} · ${CHROME.elimAt} ${game.elimination_threat}</h1>
${raw(renderEveryoneRow())}
<div class="psheet-list">${raw(rows)}</div>
<p class="body secondary">${CHROME.playersSheetFooter}</p>
<div class="cta-row">${raw(cta({ act: "sheet_close", label: CHROME.done }))}</div>`;
}
