// The page layout: which screen `ui.screen` names, assembled from the strip
// (Task 3), the rail (Task 4) and the phase panes (this task). Pure string
// builder like every other tablet render function - no document/window.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta } from "./primitives.js";
import { renderStrip } from "./strip.js";
import { renderRail } from "./rail.js";
import { renderPane } from "./pane.js";
import { renderHome } from "./home.js";
import { renderNewGame } from "./newgame.js";
import { renderPlayersSetup } from "./players_setup.js";
import { renderOverview } from "./overview.js";
import { renderSheet } from "./sheets.js";
import { renderLogScreen } from "./screen_log.js";

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
  // The landing screen (M7): the first thing shown on every launch, save or
  // no save. Nothing else is on it - no strip, no rail - so it is its own
  // branch rather than a pane.
  if (ui.screen === "home") return h`<div class="app">${raw(renderHome(ui))}</div>`;
  // Setup is two steps: the scenario chooser (master/detail - the same
  // scenario detail the in-game route shows, embedded beside a drill-in
  // list), then the players.
  if (ui.screen === "newgame") return h`<div class="app">${raw(renderNewGame(game, ui))}</div>`;
  if (ui.screen === "players") return h`<div class="app">${raw(renderPlayersSetup(ui))}</div>`;
  // The Scenario overview (Task 3, milestone 6) is a whole screen on both of
  // its paths: chosen from the picker before a game exists, and opened
  // read-only from the QUEST zone's stage pill mid-game - overview.js draws
  // both, so `game` travels with `ui` here (a resumed game whose catalog
  // never loaded is where its name comes from).
  if (ui.screen === "overview") return h`<div class="app">${raw(renderOverview(game, ui))}</div>`;
  // The Game Log is a whole screen, not an overlay: it replaces the strip,
  // the rail and the pane (it has its own transport and its own log block).
  // The sheet layer still rides on top of it - that is where its export
  // overlay lands.
  if (ui.screen === "log") return h`<div class="app">${raw(renderLogScreen(game, ui))}${raw(renderSheet(game, ui))}</div>`;
  return h`<div class="app">${raw(renderStrip(game, ui))}<div class="body-row">${raw(renderRail(game, ui))}${raw(renderPane(game, ui))}</div>${raw(renderSheet(game, ui))}</div>`;
}
