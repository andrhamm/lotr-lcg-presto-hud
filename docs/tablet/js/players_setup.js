// Step 2 of setup: how many are playing, and what each one starts on.
//
// This was a column in the old three-column picker - first on screen,
// competing with the quest list, and answered before the player had decided
// anything. It is a step of its own now, last, immediately before setup
// begins: the point at which "who is at the table" is actually known.
//
// The acts are the picker's own, unchanged (acts_newgame.js's ng_players /
// ng_threat±) and still writing ui.picker, so nothing about how a game is
// started moved - only where the controls are shown.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, counter, cta } from "./primitives.js";
import { setupHead } from "./setup_head.js";
import { icon } from "../../js/icons_svg.js";
import { THREAT_RED, THREAT_SHADOW } from "./palette.js";

function playerChips(count) {
  const chips = [1, 2, 3, 4].map(n => chip({
    act: "ng_players", arg: n, label: String(n), tone: n === count ? "gold" : "tan",
    extraClass: "chip-square",
  })).join("");
  return h`<div class="player-chips">${raw(chips)}</div>`;
}

function threatCounters(threats) {
  // Plain template, not h`` - counter() escapes `label` itself (see
  // primitives.js); pre-escaping here would double-escape it.
  const cells = threats.map((t, i) => counter({
    label: h`P${i + 1} ${CHROME.threat}`,
    icon: icon("THREAT", 34, THREAT_RED, THREAT_SHADOW),
    value: t, act: "ng_threat", arg: i,
  })).join("");
  return h`<div class="threat-row">${raw(cells)}</div>`;
}

export function renderPlayersSetup(ui) {
  const p = ui.picker ?? {};
  const players = p.players ?? 2;
  const threats = p.threats ?? Array(players).fill(25);
  const head = setupHead({
    step: 2, title: CHROME.choosePlayersTitle, hint: CHROME.choosePlayersHint,
    back: "go_scenario",
  });
  // The quest chosen in step 1, named here rather than left behind: this is
  // the screen that starts the game, and "which quest am I about to start?"
  // must not need a trip back to find out.
  const quest = ui.overview?.entry?.name ?? ui.overview?.bundle?.scenario?.name ?? "";
  const questLine = quest
    ? h`<section class="setup-block"><div class="label">${CHROME.scenario}</div><p class="body">${quest}</p></section>`
    : "";

  return h`<main class="pane setup setup-players">${raw(head)}
<div class="setup-body">
${raw(questLine)}
<section class="setup-block"><div class="label">${CHROME.players}</div>${raw(playerChips(players))}</section>
<section class="setup-block"><div class="label">${CHROME.startingThreat}</div>${raw(threatCounters(threats))}</section>
</div>
<div class="cta-row">${raw(cta({ act: "begin_setup", label: CHROME.beginSetup, tone: "ok" }))}</div>
</main>`;
}
