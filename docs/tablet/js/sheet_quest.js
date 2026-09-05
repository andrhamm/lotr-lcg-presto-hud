// The quest sheet (Task 4): the main quest, every active location and every
// side quest, folded into one progress editor - the tablet's answer to
// QuestingProgressModal + LocationConfigModal + QuestConfigModal
// (docs/js/screens.js). Read those classes' onButton for the exact log
// strings this mirrors; actions.js is where every stepper/action below
// actually dispatches. Opened by the rail's QUEST zone "Edit ›" chip
// (open_quest, rail.js); "Done" (quest_done) closes it and flags the guided
// resolution flow (Task 7's sheet) exactly like the twin's own close does.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { faceOf } from "./cards.js";
import { icon } from "../../js/icons_svg.js";
import { boardTracking } from "../../js/gamestate.js";
import {
  labelFor, autoFor, resolve, AUTO_ENEMIES, AUTO_STAGING_LOCATIONS,
} from "../../js/xtargets.js";
import { TRAIL_GREEN, TRAIL_BROWN, THREAT_BLACK, THREAT_BLACK_EDGE } from "./palette.js";

function step(act, arg, label) {
  return h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${label}</button>`;
}

// One labelled stepper row: an icon-badged value between a -/+ pair - the
// same shape sheet_staging.js's row() uses, shared here across the quest,
// every location and every side quest instead of one screen's three fixed
// rows. `before`/`after` are pre-rendered button html, or "" for a read-only
// row (the printed-X value the tracker answers - no stepper to put there).
function row(iconSvg, label, value, before, after) {
  return h`<div class="qsheet-row">
<span class="body qsheet-label">${label}</span>
<div class="qsheet-controls">${raw(before)}
<span class="qsheet-val">${raw(iconSvg)}<span class="num num-34">${value}</span></span>
${raw(after)}</div>
</div>`;
}

const trailIcon = () => icon("TRAIL", 28, TRAIL_GREEN, TRAIL_BROWN);
// Location/side-quest threat is a staging quantity, not a player's own - the
// black-with-light-edge treatment palette.js documents for exactly that
// (design/stat-system.md's stat-colour rules), not the player-threat red.
const threatIcon = () => icon("THREAT", 28, THREAT_BLACK, THREAT_BLACK_EDGE);

// QuestConfigModal (docs/js/screens.js) shows its points stepper for every
// mode except "condition" (no printed target - the card's own advance
// sentence covers that stage instead, milestone 5) and "formula" (X-driven;
// stepping the pre-resolution printed 0 would invite "fixing" a number the
// card never printed). Undefined mode is a manual/custom game, which has
// always been freely editable.
export function questShowsPointsStepper(game) {
  const mode = game.quest.mode;
  return mode !== "condition" && mode !== "formula";
}

// Whether a location's printed X is answered by a tracked value (no
// stepper) or needs the player to supply a count via lX± - mirrors
// LocationConfigModal's threatShape exactly: the three always-on auto
// targets (players/stage/highestThreat) are never gated, but
// AUTO_ENEMIES/AUTO_STAGING_LOCATIONS only count as "auto" when this client
// actually tracks the board (boardTracking()) - otherwise the player
// supplies the count exactly like an untracked target does.
export function xIsAuto(threatX) {
  const auto = autoFor(threatX?.target);
  if (!auto) return false;
  const trackerBacked = auto === AUTO_ENEMIES || auto === AUTO_STAGING_LOCATIONS;
  return !trackerBacked || boardTracking();
}

function renderQuestGroup(game) {
  const card = game.stages[game.stage_idx]?.cards?.[game.card_idx];
  const face = faceOf(card, game.quest.side);
  const nameLine = face?.name ? h`<p class="body secondary">${face.name}</p>` : "";
  // A condition stage (flipToB's "condition" mode, ~137 of ~400 stage cards)
  // has no printed target to count toward - actions.js's qP±/qPts± both
  // no-op for it, so nothing here offers a stepper that would silently do
  // nothing on tap. The card's own advance sentence takes the row instead,
  // same as QuestingProgressModal's "cond" branch (docs/js/screens.js).
  const cond = game.quest.mode === "condition";
  let body;
  if (cond) {
    body = h`<p class="body secondary">${game.quest.advance || CHROME.questConditionFallback}</p>`;
  } else {
    const progressRow = row(trailIcon(), CHROME.progress, game.quest.progress,
      step("qP-", "", "−"), step("qP+", "", "+"));
    const ptsRow = questShowsPointsStepper(game)
      ? row(trailIcon(), CHROME.questPoints, game.quest.points,
          step("qPts-", "", "−"), step("qPts+", "", "+"))
      : "";
    body = progressRow + ptsRow;
  }
  return h`<div class="qsheet-group">
<div class="qsheet-name"><span class="body">${CHROME.stage} ${game.questLabel()}</span>${raw(nameLine)}</div>
${raw(body)}
</div>`;
}

// Prefer the catalog name; fall back the way pane.js's allocator rows and
// the twin's own QuestingProgressModal._items() do - "Location" for the
// first seat, "Location N" for any seat after it.
function locationName(loc, i) {
  return loc.name ?? (i === 0 ? CHROME.location : `${CHROME.location} ${i + 1}`);
}

// The threat block, in whichever shape the card calls for - read-only when a
// tracked value answers it, otherwise that same read-only value PLUS a
// labelled count stepper the player dials in by looking at the table (see
// xIsAuto above). An ordinary printed number gets a plain editable stepper.
function renderLocationThreat(game, loc, i) {
  if (loc.threatKind === "x" && loc.threatX) {
    const resolved = resolve(loc.threatX, { count: loc.threatCount, ...game.xContext() });
    const shown = resolved === null ? "–" : String(resolved);
    const valueRow = row(threatIcon(), CHROME.threat, shown, "", "");
    if (xIsAuto(loc.threatX)) return valueRow;
    const label = labelFor(loc.threatX.target) ?? CHROME.threat;
    const countRow = row("", label, loc.threatCount ?? 0,
      step("lX-", `${i}`, "−"), step("lX+", `${i}`, "+"));
    return valueRow + countRow;
  }
  return row(threatIcon(), CHROME.threat, loc.threat ?? 0,
    step("lThr-", `${i}`, "−"), step("lThr+", `${i}`, "+"));
}

function renderLocationGroup(game, loc, i) {
  const progressRow = row(trailIcon(), CHROME.progress, loc.progress,
    step("lP-", `${i}`, "−"), step("lP+", `${i}`, "+"));
  const ptsRow = row(trailIcon(), CHROME.questPoints, loc.points,
    step("lPts-", `${i}`, "−"), step("lPts+", `${i}`, "+"));
  const threatRow = renderLocationThreat(game, loc, i);
  // Explored / Back to staging / Replace - the twin's three named ways a
  // location leaves (LocationConfigModal), minus "Remove" (that one has no
  // tablet equivalent yet - nothing here drops a location with no record of
  // where its threat should go).
  const actions = h`<div class="qsheet-actions">
${raw(chip({ act: "lExplored", arg: `${i}`, label: CHROME.explored, tone: "tan" }))}
${raw(chip({ act: "lToStaging", arg: `${i}`, label: CHROME.toStaging, tone: "tan" }))}
${raw(chip({ act: "lReplace", arg: `${i}`, label: CHROME.replace, tone: "tan" }))}
</div>`;
  return h`<div class="qsheet-group">
<div class="qsheet-name"><span class="body">${locationName(loc, i)}</span></div>
${raw(progressRow)}${raw(ptsRow)}${raw(threatRow)}${raw(actions)}
</div>`;
}

function sideQuestName(sq, i) {
  return sq.name ?? `${CHROME.sideQuestLabel} ${i + 1}`;
}

function renderSideQuestGroup(sq, i) {
  const progressRow = row(trailIcon(), CHROME.progress, sq.progress,
    step("sP-", `${i}`, "−"), step("sP+", `${i}`, "+"));
  const ptsRow = row(trailIcon(), CHROME.questPoints, sq.points,
    step("sPts-", `${i}`, "−"), step("sPts+", `${i}`, "+"));
  const actions = h`<div class="qsheet-actions">${raw(chip({ act: "sRemove", arg: `${i}`, label: CHROME.remove, tone: "tan" }))}</div>`;
  return h`<div class="qsheet-group">
<div class="qsheet-name"><span class="body">${sideQuestName(sq, i)}</span></div>
${raw(progressRow)}${raw(ptsRow)}${raw(actions)}
</div>`;
}

export function renderQuestSheet(game, ui) {
  const locs = game.active_locations;
  const sqs = game.side_quests;
  const locSection = locs.length
    ? h`<div class="label qsheet-section">${CHROME.activeLocations}</div>${raw(locs.map((l, i) => renderLocationGroup(game, l, i)).join(""))}`
    : h`<p class="body secondary">${CHROME.noLocation}</p>`;
  const sqSection = sqs.length
    ? h`<div class="label qsheet-section">${CHROME.sideQuestsHeader}</div>${raw(sqs.map((s, i) => renderSideQuestGroup(s, i)).join(""))}`
    : "";
  // The pickers these open are Tasks 5 (locations) and 6 (side quests) - the
  // chips render now (per the task-4 brief) but ui.sheet's "locpick"/
  // "sqpick" kinds have no entry in sheets.js's RENDERERS yet, so tapping
  // either shows nothing until that lands (renderSheet's documented
  // fallback for a kind it does not recognise). Neither dispatches in
  // actions.js yet either - that wiring is those tasks' job, same as
  // open_quest sat inert in rail.js until this one.
  const addRow = h`<div class="qsheet-add">
${raw(chip({ act: "open_locpick", label: CHROME.addLocation, tone: "tan" }))}
${raw(chip({ act: "open_sqpick", label: CHROME.sideQuest, tone: "tan" }))}
</div>`;
  return h`<h1 class="display">${CHROME.quest}</h1>
<div class="qsheet-list">
${raw(renderQuestGroup(game))}
${raw(locSection)}
${raw(sqSection)}
</div>
${raw(addRow)}
<div class="cta-row">${raw(cta({ act: "quest_done", label: CHROME.done }))}</div>`;
}
