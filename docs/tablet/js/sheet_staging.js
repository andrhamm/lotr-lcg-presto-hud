// The staging editor (milestone 3): threat (±5/±1), enemies (±1), locations
// (±1), then Done. Opened from the rail's STAGING "Edit ›" chip (rail.js).
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta } from "./primitives.js";
import { icon } from "../../js/icons_svg.js";
import { THREAT_BLACK, THREAT_BLACK_EDGE } from "./palette.js";

function step(act, arg, label) {
  return h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${label}</button>`;
}

function row(label, value, before, after) {
  return h`<div class="ssheet-row">
<span class="body ssheet-label">${label}</span>
<div class="ssheet-controls">${raw(before)}
<span class="ssheet-val">${raw(icon("THREAT", 36, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-36">${value}</span></span>
${raw(after)}</div>
</div>`;
}

export function renderStagingSheet(game, ui) {
  const threatRow = row(CHROME.threat, game.staging,
    step("stg5", "-5", "−5") + step("stg-", "", "−1"),
    step("stg+", "", "+1") + step("stg5", "5", "+5"));
  const enemiesRow = row(CHROME.enemies, game.staging_enemies,
    step("stgen-", "", "−"), step("stgen+", "", "+"));
  const locationsRow = row(CHROME.locations, game.staging_locations,
    step("stgloc-", "", "−"), step("stgloc+", "", "+"));
  return h`<h1 class="display">${CHROME.staging}</h1>
<div class="ssheet-rows">${raw(threatRow)}${raw(enemiesRow)}${raw(locationsRow)}</div>
<div class="cta-row">${raw(cta({ act: "sheet_close", label: CHROME.done }))}</div>`;
}
