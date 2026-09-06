// Which Rules Reference section ids each phase view is about - the "Rules
// §n ›" chip pane.js bands into its own view (band()'s `section` prop,
// primitives.js) and the pure lookup the Rules sheet (sheet_rules.js) uses
// for its Related prev/next chips. Hand-mapped rather than derived from
// phases.js's own STEP_ORDER: that file's ids ("1.R", "6.E", "6.P", "7.R")
// each stand for SEVERAL Rules Reference steps folded into one turn-flow
// rung (docs/js/phases.js's own comment on "1.2-1.3 Gain resources and draw
// cards") - a player tapping a chip should land on the actual numbered
// step the book prints, not the flow diagram's grouped rung. quest_setup
// (stage 1A's own Setup text) and quest_sailing (the sailing-test screen)
// are this tracker's own affordances with no Rules Reference section number
// of their own, so they are left out entirely - sectionsFor() returns []
// for them and pane.js gives them no chip (interfaces note).
export const VIEW_SECTIONS = {
  resource: ["1.1", "1.2", "1.3", "1.4"],
  planning: ["2.1", "2.2", "2.3", "2.4"],
  quest_commit: ["3.1", "3.2"],
  quest_staging: ["3.3"],
  quest_resolution: ["3.4", "3.5"],
  travel: ["4.1", "4.2", "4.3"],
  enc_optional: ["5.1", "5.2"],
  enc_checks: ["5.3", "5.4"],
  combat_shadow: ["6.1", "6.2"],
  combat_enemy: ["6.3", "6.4a", "6.4b", "6.4.1", "6.4.2", "6.4.3", "6.4.4", "6.5", "6.6"],
  combat_player: ["6.7", "6.8a", "6.8b", "6.8.1", "6.8.2", "6.8.3", "6.8.4", "6.9", "6.10", "6.11"],
  refresh: ["7.1", "7.2", "7.3", "7.4", "7.5"],
  round_end: ["7.5"],
};

export function sectionsFor(view) {
  return VIEW_SECTIONS[view] ?? [];
}

// Every id above, flattened to book order, for the Rules sheet's own
// Related prev/next chips. A Set() dedupes round_end's "7.5" - it is
// already refresh's own last id, not a second entry naming the same
// section twice.
export const STEP_ORDER = [...new Set(Object.values(VIEW_SECTIONS).flat())];

// Which viewcopy.js object supplies "this tracker's summary" for a given
// section id - the EXACT text pane.js already bands next to that section's
// own chip (see pane.js's renderViewParts), read back here by id instead of
// re-typed, so the sheet and the pane can never say two different things
// about the same rule (CLAUDE.md iron rule 4: never re-word a rules claim).
// Only sections that a pane.js band actually names get an entry - a section
// reachable solely via the sheet's own Related prev/next chips (planning,
// combat_enemy, combat_player, and every id besides the ones below) has no
// tracker copy to show without either reaching into loops.js (out of this
// task's file list) or inventing new prose, so sheet_rules.js just omits
// the Timing block for those rather than ship a placeholder.
export const SECTION_SUMMARY = {
  "1.1": { source: "framework", view: "resource" },
  "1.2": { source: "tips", view: "resource" },
  "3.2": { source: "window", view: "quest_commit" },
  "3.3": { source: "tips", view: "quest_staging" },
  "3.5": { source: "tips", view: "quest_resolution" },
  "4.3": { source: "tips", view: "travel" },
  "5.2": { source: "window", view: "enc_optional" },
  "5.4": { source: "tips", view: "enc_checks" },
  "6.1": { source: "framework", view: "combat_shadow" },
  "6.2": { source: "window", view: "combat_shadow" },
  "7.1": { source: "framework", view: "refresh" },
  "7.2": { source: "window", view: "refresh" },
  "7.5": { source: "framework", view: "round_end" },
};
