// The page layout: which screen `ui.screen` names, assembled from the strip
// (Task 3), the rail (Task 4) and the phase panes (this task). Pure string
// builder like every other tablet render function - no document/window.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta } from "./primitives.js";
import { renderStrip } from "./strip.js";
import { renderRail } from "./rail.js";
import { renderPane } from "./pane.js";
import { renderNewGame } from "./newgame.js";
import { renderSheet } from "./sheets.js";
import { renderLogScreen } from "./screen_log.js";

// Milestone 6 (Task 2): a placeholder for the Scenario overview - Task 3
// renders the real thing (difficulty ladder, sets, stages, cards, notes).
// This exists only so the picker -> overview -> begin_setup flow is usable
// end-to-end before Task 3 lands, and so this task's own tests can assert
// the screen transition. `ov_back`/`begin_setup` are real acts already
// (acts_newgame.js / app.js) - only the body is a stand-in.
function renderOverviewPlaceholder(ui) {
  const entry = ui.overview?.entry ?? {};
  return h`<main class="pane overview">
<h1 class="display">${entry.name ?? ""}</h1>
<div class="cta-row">${raw(cta({ act: "ov_back", label: CHROME.backToScenarios, tone: "plain" }))}${raw(cta({ act: "begin_setup", label: CHROME.beginSetup, tone: "ok" }))}</div>
</main>`;
}

function renderGameOver(game) {
  const over = game.game_over ?? {};
  const won = over.result === "victory";
  const title = won ? CHROME.victory : CHROME.defeat;
  const round = over.round ?? game.round;
  // over.duration was frozen by setGameOver() the moment the game ended;
  // gameDuration() itself keeps ticking off the live log/clock, so it is
  // only a fallback for an over object that somehow lacks one.
  const duration = over.duration ?? game.gameDuration();
  const label = duration ? h`${CHROME.round} ${round} · ${duration}` : h`${CHROME.round} ${round}`;
  return h`<div class="app"><main class="pane gameover">
<h1 class="display center">${title}</h1>
<p class="label center">${raw(label)}</p>
<div class="cta-row">${raw(cta({ act: "new_game", label: CHROME.newGame }))}</div>
</main></div>`;
}

export function layout(game, ui) {
  if (ui.screen === "gameover") return renderGameOver(game);
  if (ui.screen === "newgame") return h`<div class="app">${raw(renderNewGame(ui))}</div>`;
  if (ui.screen === "overview") return h`<div class="app">${raw(renderOverviewPlaceholder(ui))}</div>`;
  // The Game Log is a whole screen, not an overlay: it replaces the strip,
  // the rail and the pane (it has its own transport and its own log block).
  // The sheet layer still rides on top of it - that is where its export
  // overlay lands.
  if (ui.screen === "log") return h`<div class="app">${raw(renderLogScreen(game, ui))}${raw(renderSheet(game, ui))}</div>`;
  return h`<div class="app">${raw(renderStrip(game, ui))}<div class="body-row">${raw(renderRail(game, ui))}${raw(renderPane(game, ui))}</div>${raw(renderSheet(game, ui))}</div>`;
}
