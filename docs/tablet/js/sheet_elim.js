// The elimination sheet (Task 3): auto-opened by actions.js's afterTap the
// instant a player's threat crosses their elimination level (see app.js and
// actions.js's dispatch() for the elim_confirm/elim_avert/elim_lvl/
// elim_setlvl acts, which mirror EliminationModal.onButton in
// docs/js/screens.js exactly, log lines included). Its copy differs from
// the twin's canvas wording (this sheet titles itself "P{n} reaches
// {level}", not "eliminated?"), but the rule underneath is the same one the
// twin encodes and the only rules claim either UI makes: a player whose
// threat is at or above their elimination level is eliminated (Rules
// Reference, "Player Elimination" - review finding M7: that glossary entry
// carries no section number; "7.4" formerly cited here is this repo's own
// phases.py step LABEL ("7.2-7.4 Ready cards, raise threat, pass P1 token",
// id "7.R") for the unrelated Refresh-phase "pass P1 token" step). That
// citation lives here, in the source, not on screen - see CLAUDE.md's iron
// rule 4.
import { h, raw, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta, chip } from "./primitives.js";

function step(act, arg, label) {
  return h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${label}</button>`;
}

export function renderElimSheet(game, ui) {
  const { i, level } = ui.sheet;
  const p = game.players[i];
  // The title and the avert preview both read p.elimination (the player's
  // real, committed level), never the stepper's own draft `level` - exactly
  // how the twin's draw() reads p.elimination for both, while only the
  // stepper's own numeral shows `this.newLevel` (EliminationModal, above).
  // Otherwise nudging −/+ without tapping Set would silently make Avert's
  // preview lie about what avertElimination() is about to do.
  const avertedTo = Math.max(0, p.elimination - 5);
  return h`<h1 class="display">${fmt(CHROME.elimTitle, i + 1, p.elimination)}</h1>
<div class="esheet-choices">
<div class="esheet-choice">
${raw(cta({ act: "elim_confirm", label: CHROME.elimEliminate, tone: "no", grow: false }))}
<p class="body secondary">${CHROME.elimEliminateBody}</p>
${raw(chip({ act: "open_rules", arg: "term:Player Elimination", label: CHROME.elimRulesChip, tone: "tan" }))}
</div>
<div class="esheet-choice">
${raw(cta({ act: "elim_avert", label: CHROME.elimAvert, tone: "plain", grow: false }))}
<p class="body secondary">${fmt(CHROME.elimAvertBody, avertedTo)}</p>
</div>
<div class="esheet-choice">
<p class="body secondary">${CHROME.elimLevelQuestion}</p>
<div class="esheet-lvl">
${raw(step("elim_lvl", "-5", "−5"))}
${raw(step("elim_lvl", "-1", "−1"))}
<span class="esheet-lvl-val"><span class="num num-40">${level}</span></span>
${raw(step("elim_lvl", "1", "+1"))}
${raw(step("elim_lvl", "5", "+5"))}
${raw(cta({ act: "elim_setlvl", label: CHROME.elimSet, tone: "ok", grow: false }))}
</div>
</div>
</div>`;
}
