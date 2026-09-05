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
  return h`<div class="app">${raw(renderStrip(game, ui))}<div class="body-row">${raw(renderRail(game, ui))}${raw(renderPane(game, ui))}</div>${raw(renderSheet(game, ui))}</div>`;
}
