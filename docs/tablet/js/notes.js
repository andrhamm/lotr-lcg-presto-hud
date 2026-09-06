// Notes panel & sheet (Task 4, milestone 5): the scenario's own strategy
// tips, in this tracker's own words - CLAUDE.md's tips.json precedence
// (the distilled corpus first, quests/*.md callouts only where it is
// silent) already fact-checked every sentence in there; this module just
// picks which of them to show. Pure data lookup only - notesFor()/
// allNotes() never touch the DOM, so pane.js and sheet_notes.js render
// whatever these return, and tests/test_tablet.py can drive both under
// node with a fixture, no build required.
//
// docs/js/quest_catalog.js's loadTips() (line ~437) returns data.scenarios,
// which is the flat map: {"<slug>": { attribution:{name,url}, general:[...],
// stages:{"1":[...], "2":[...]} }}. So this indexes tips[scenarioSlug]
// directly; a scenario tips.json has never heard of (build_tips.py only
// distilled 122 of ~350) is just an absent key, not an error - both functions
// below degrade to "nothing to show" for that case (R9: "a scenario absent
// from tips renders no panel").
import { fmt } from "./dom.js";
import { CHROME } from "./copy.js";

// The panel's own line budget (R9: "at most three") - the sheet has none,
// since it scrolls and is meant to be the full list.
const PANEL_MAX = 3;

// The phase pane's own panel: the CURRENT stage's tips when tips.json has
// any, else the scenario's general tips - R9's first half. Stage tips are
// keyed by the stage number as a plain string (game.quest.stage_n is a
// number; "1"/"2"/... in tips.json), so the lookup coerces before indexing.
// Nothing to show at either scope (an absent scenario, or one whose
// distillation is empty at both) renders no panel at all - never an empty
// shell with a header and no lines.
export function notesFor(tips, scenarioSlug, stage_n) {
  const rec = tips?.[scenarioSlug];
  if (!rec) return null;
  const stageItems = rec.stages?.[String(stage_n)];
  if (stageItems && stageItems.length) {
    return {
      scope: fmt(CHROME.scopeStage, String(stage_n)),
      items: stageItems.slice(0, PANEL_MAX),
      source: rec.attribution,
    };
  }
  const general = rec.general ?? [];
  if (!general.length) return null;
  return { scope: CHROME.scopeGeneral, items: general.slice(0, PANEL_MAX), source: rec.attribution };
}

// THE SLOTS. A player should learn once where pacing advice lives and then
// always look there, which only works if the set and the order never change -
// so this is a fixed list, and an empty slot is DRAWN as empty rather than
// dropped. `notes` is last because it is the catch-all.
export const TIP_SLOTS = ["pacing", "threat", "combat", "watch", "deck", "notes"];

// One tip is either a plain string (every tip in tips.json today) or
// {kind, text} once the classification pass has been over it. Both shapes are
// accepted deliberately: the corpus can be reclassified scenario by scenario
// without a flag day, and an unrecognised kind lands in `notes` rather than
// vanishing.
export function tipSlot(tip) {
  if (typeof tip === "string") return "notes";
  const kind = tip?.kind;
  return TIP_SLOTS.includes(kind) ? kind : "notes";
}

export function tipText(tip) {
  return typeof tip === "string" ? tip : (tip?.text ?? "");
}

// Group one scope's tips into the fixed slots. Returns every slot in order,
// each with its (possibly empty) list - the render decides how to show an
// empty one, this decides nothing.
export function slotted(items) {
  const by = Object.fromEntries(TIP_SLOTS.map(k => [k, []]));
  for (const t of items ?? []) by[tipSlot(t)].push(tipText(t));
  return TIP_SLOTS.map(kind => ({ kind, items: by[kind] }));
}

// One scope's tips, for the scenario detail: `stage` is a number for a stage
// or null for the scenario's general tips. Null when there is nothing at that
// scope at all - the caller draws no panel rather than an empty shell.
export function notesAt(tips, scenarioSlug, stage) {
  const rec = tips?.[scenarioSlug];
  if (!rec) return null;
  const items = stage == null ? (rec.general ?? []) : (rec.stages?.[String(stage)] ?? []);
  if (!items.length) return null;
  return { slots: slotted(items), source: rec.attribution };
}

// The Notes sheet ("More notes ›", acts_notes.js's open_notes): every group
// this scenario has - General first, then each stage in numeric order
// (Object.keys on a stages map carries no ordering guarantee once keys
// exceed single digits, so this sorts explicitly rather than trusting
// insertion order). Every group carries the same attribution - tips.json
// distills one scenario from one spotlight, never a per-stage source - but
// each group repeats its own Source link anyway (R9), since the sheet's
// groups are read independently as the player scrolls.
export function allNotes(tips, scenarioSlug) {
  const rec = tips?.[scenarioSlug];
  if (!rec) return [];
  const groups = [];
  if (rec.general?.length) {
    groups.push({ scope: CHROME.scopeGeneral, items: rec.general, source: rec.attribution });
  }
  const stageKeys = Object.keys(rec.stages ?? {}).map(Number).sort((a, b) => a - b);
  for (const n of stageKeys) {
    const items = rec.stages[String(n)];
    if (items && items.length) {
      groups.push({ scope: fmt(CHROME.scopeStage, String(n)), items, source: rec.attribution });
    }
  }
  return groups;
}
