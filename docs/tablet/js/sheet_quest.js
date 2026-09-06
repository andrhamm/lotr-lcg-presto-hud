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
import { setIcon } from "./seticon.js";
import { labelFor, resolve } from "../../js/xtargets.js";
import { questShowsPointsStepper, xShape } from "./xshape.js";
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
    // 11 stages state BOTH how they are won and how they are lost -
    // QuestingProgressModal's own "cond" row pairs them the same way
    // (docs/js/screens.js ~1069-1077): showing only the win is showing half
    // the rule (review finding 2, task-4 fix round 1).
    const advanceLine = h`<p class="body secondary">${game.quest.advance || CHROME.questConditionFallback}</p>`;
    const loseLine = game.quest.lose ? h`<p class="body no">${game.quest.lose}</p>` : "";
    body = advanceLine + loseLine;
  } else {
    const progressRow = row(trailIcon(), CHROME.progress, game.quest.progress,
      step("qP-", "", "−"), step("qP+", "", "+"));
    const ptsRow = questShowsPointsStepper(game)
      ? row(trailIcon(), CHROME.questPoints, game.quest.points,
          step("qPts-", "", "−"), step("qPts+", "", "+"))
      : "";
    body = progressRow + ptsRow;
  }
  // The scenario's own set icon (Task 5, seticon.js) before the "Stage n"
  // label - same treatment as rail.js's stage pill, and the same guard:
  // `game.scenario?.name` is the one name this app can turn into an icon
  // slug, omitted for a bare/manual game with no preloaded scenario.
  const setName = game.scenario?.name;
  const stageIcon = setName ? setIcon(setName, 20) : "";
  return h`<div class="qsheet-group">
<div class="qsheet-name"><div class="qsheet-name-head">${raw(stageIcon)}<span class="body">${CHROME.stage} ${game.questLabel()}</span></div>${raw(nameLine)}</div>
${raw(body)}
</div>`;
}

// Prefer the catalog name; fall back the way pane.js's allocator rows and
// the twin's own QuestingProgressModal._items() do - "Location" for the
// first seat, "Location N" for any seat after it.
function locationName(loc, i) {
  return loc.name ?? (i === 0 ? CHROME.location : `${CHROME.location} ${i + 1}`);
}

// The threat block, in whichever shape the card calls for (xShape, xshape.js
// - mirrors LocationConfigModal's own threatShape switch, docs/js/screens.js
// ~1950-2180). Every shape but "plain" carries the card's own X = ... text
// underneath when the catalog has one - CLAUDE.md's rule 4, "prefer the
// card's own printed text over a paraphrase" (review finding 4).
function xFormula(threatX) {
  return threatX.text ? h`<p class="body secondary">X = ${threatX.text}</p>` : "";
}

function renderLocationThreat(game, loc, i) {
  const shape = xShape(loc);
  if (shape === "plain") {
    return row(threatIcon(), CHROME.threat, loc.threat ?? 0,
      step("lThr-", `${i}`, "−"), step("lThr+", `${i}`, "+"));
  }
  if (shape === "blank") {
    // No coded spec at all - a read-only, BLANK slot (never a 0 the card did
    // not print) plus the twin's own line for exactly this case (draw() ~2052
    // in docs/js/screens.js): the card prints X and defines it nowhere this
    // app can read, so acts_quest.js's lThr± stays refused rather than
    // offering a stepper that would just sit there dead (review finding 1).
    const valueRow = row(threatIcon(), CHROME.threat, "", "", "");
    const note = h`<p class="body secondary">${CHROME.xElsewhere}</p>`;
    return valueRow + note;
  }
  if (shape === "bare") {
    // The count IS the value - one stepper labelled by the card's own target,
    // not a value row plus a count row repeating the same number twice
    // (review finding 3).
    const label = labelFor(loc.threatX.target) ?? CHROME.threat;
    const barRow = row(threatIcon(), label, loc.threat ?? 0,
      step("lX-", `${i}`, "−"), step("lX+", `${i}`, "+"));
    return barRow + xFormula(loc.threatX);
  }
  const resolved = resolve(loc.threatX, { count: loc.threatCount, ...game.xContext() });
  const shown = resolved === null ? "–" : String(resolved);
  const valueRow = row(threatIcon(), CHROME.threat, shown, "", "");
  if (shape === "auto") return valueRow + xFormula(loc.threatX);
  // shape === "count": read-only resolved value PLUS a labelled count
  // stepper the player dials in by looking at the table.
  const label = labelFor(loc.threatX.target) ?? CHROME.threat;
  const countRow = row("", label, loc.threatCount ?? 0,
    step("lX-", `${i}`, "−"), step("lX+", `${i}`, "+"));
  return valueRow + countRow + xFormula(loc.threatX);
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
  // "+ Add location" opens the location picker (Task 5 - see
  // sheet_locpick.js/acts_locpick.js). "+ Side quest" opens the side-quest
  // picker (Task 6 - sheets.js's RENDERERS has a "sqpick" entry, and app.js's
  // own "open_sqpick" case seats ui.sheet after loading ui.sideQuests).
  const addRow = h`<div class="qsheet-add">
${raw(chip({ act: "open_locpick", label: CHROME.addLocation, tone: "tan" }))}
${raw(chip({ act: "open_sqpick", label: CHROME.sideQuest, tone: "tan" }))}
</div>`;
  // "Advance anyway" (review finding C1) - the quest row's own way into the
  // guided resolution flow before progress reaches the target, mirroring
  // QuestConfigModal's "force_adv" button (docs/js/screens.js ~2244-2249):
  // gated the same way it is there, on a stage tree existing at all. A
  // custom/manual game (no stages) has no guided flow for this to open, so
  // it keeps editing progress by hand instead.
  const forceCta = game.stages.length
    ? cta({ act: "quest_force", label: CHROME.questForceAdvance, tone: "plain", grow: false })
    : "";
  return h`<h1 class="display">${CHROME.quest}</h1>
<div class="qsheet-list">
${raw(renderQuestGroup(game))}
${raw(locSection)}
${raw(sqSection)}
</div>
${raw(addRow)}
<div class="cta-row">${raw(cta({ act: "quest_done", label: CHROME.done }))}${raw(forceCta)}</div>`;
}
