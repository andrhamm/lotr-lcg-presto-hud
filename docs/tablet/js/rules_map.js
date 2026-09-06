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
import {
  PHASE_FRAMEWORK, PHASE_WINDOW, ACTION_WINDOW_TIPS, LOOP_FLOW, TRAVEL,
  COMBAT_LAST_CHANCE,
} from "../../js/viewcopy.js";

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

// Views whose action-window tips band shows only the FIRST tip line
// (ACTION_WINDOW_TIPS[view][0]) rather than every tip joined with a space -
// resource's "1.4" band and quest_resolution's "3.5", per pane.js's own
// renderViewParts. Every other view that bands ACTION_WINDOW_TIPS joins the
// whole array (a sub-line under a framework/window band, or - travel,
// enc_checks - the band's own main text).
const TIPS_FIRST_ONLY = new Set(["resource", "quest_resolution"]);

// The exact text pane.js already bands for a given (view, kind) pair - Fix
// round 1's fix for the drift the "tips" branch could silently grow: this
// used to be re-derived twice (once in pane.js's own band() call, once in
// sheet_rules.js's summaryFor() by re-reading SUMMARY_SOURCES), and the two
// disagreed for "1.2"/"3.5" - pane.js bands ACTION_WINDOW_TIPS[view][0], but
// the old summaryFor() unconditionally `.join(" ")`ed the whole array, so
// the Timing block showed MORE tips than the band the player actually
// tapped through to get there. Both pane.js's band construction and
// SECTION_SUMMARY below now call this one function, so the two cannot say
// different things again (CLAUDE.md iron rule 4).
export function bandTextFor(view, kind) {
  if (kind === "framework") return PHASE_FRAMEWORK[view] ?? null;
  if (kind === "window") return PHASE_WINDOW[view] ?? null;
  if (kind === "tips") {
    const tips = ACTION_WINDOW_TIPS[view];
    if (tips == null) return null;
    return TIPS_FIRST_ONLY.has(view) ? tips[0] : tips.join(" ");
  }
  return null;
}

// Which text supplies "this tracker's summary" for a given section id - the
// EXACT string pane.js already bands next to that section's own chip, read
// back here by id instead of re-typed, so the sheet and the pane can never
// say two different things about the same rule (CLAUDE.md iron rule 4:
// never re-word a rules claim). Only sections that a pane.js band actually
// names get an entry - a section reachable solely via the sheet's own
// Related prev/next chips (planning's 2.1/2.3/2.4, resource's 1.1/1.3, most
// of combat_enemy and combat_player, plus every id besides the ones below)
// has no tracker copy to show without inventing new prose, so
// sheet_rules.js just omits the Timing block for those rather than ship a
// placeholder.
//
// Most entries resolve through bandTextFor(view, kind) above - a plain
// (view, kind) lookup is enough for every framework/window/tips band that
// pane.js keys off PHASE_FRAMEWORK/PHASE_WINDOW/ACTION_WINDOW_TIPS by view
// name. The rest don't fit that shape and are resolved to a literal value
// instead, imported from the same viewcopy.js module pane.js itself reads,
// so there is still exactly one source of truth:
//   - "4.1"/"4.2" (travel) - pane.js's own first band toggles between
//     TRAVEL.blocked (framework, "4.1 Beginning of the Travel phase") and
//     TRAVEL.open (window, "4.2 Travel opportunity") depending on whether a
//     location is already active. Each id summarises with the copy the band
//     carrying THAT id actually shows (M5 final review: both used to
//     resolve to TRAVEL.open, so tapping the blocked band's own 4.1 chip
//     opened a Timing block describing travel as on offer).
//   - "2.2"/"5.3"/"6.3"/"6.8a" - the four loop views' framing band is built
//     by loops.js's renderLoop() from LOOP_FLOW[view].intro, not by a
//     bandTextFor() lookup, so they read that same field directly. Same
//     no-drift property: the sheet quotes the exact string the loop's own
//     framing band shows.
//   - "6.11" (combat_player) - pane.js's own closing band there is a fixed
//     "tip", COMBAT_LAST_CHANCE, not a per-view PHASE_*/ACTION_WINDOW_TIPS
//     lookup.
//
// Every id a pane.js band actually chips is present here - the render test
// in tests/test_tablet.py asserts that both ways round (every emitted chip
// has an entry; every entry's text appears verbatim on its own view). The
// one numbered step a live band deliberately does NOT chip is "3.4 Quest
// resolution": that band's text is the outcome resolveQuest() just produced,
// a dynamic string, and a Timing summary must quote static copy or nothing.
// `view` names the pane each id's text actually appears on (not read by
// summaryFor() itself - only `text` is - but kept alongside it so a test can
// render that one view and assert the summary shows up verbatim there,
// without hand-maintaining a second id->view table that could itself drift
// from this one).
export const SECTION_SUMMARY = {
  "1.2": { view: "resource", text: bandTextFor("resource", "framework") },
  "1.4": { view: "resource", text: bandTextFor("resource", "tips") },
  "2.2": { view: "planning", text: LOOP_FLOW.planning.intro },
  "3.2": { view: "quest_commit", text: bandTextFor("quest_commit", "window") },
  "3.3": { view: "quest_staging", text: bandTextFor("quest_staging", "tips") },
  "3.5": { view: "quest_resolution", text: bandTextFor("quest_resolution", "tips") },
  "4.1": { view: "travel", text: TRAVEL.blocked },
  "4.2": { view: "travel", text: TRAVEL.open },
  "4.3": { view: "travel", text: bandTextFor("travel", "tips") },
  "5.2": { view: "enc_optional", text: bandTextFor("enc_optional", "window") },
  "5.3": { view: "enc_checks", text: LOOP_FLOW.enc_checks.intro },
  "5.4": { view: "enc_checks", text: bandTextFor("enc_checks", "tips") },
  "6.1": { view: "combat_shadow", text: bandTextFor("combat_shadow", "window") },
  "6.2": { view: "combat_shadow", text: bandTextFor("combat_shadow", "framework") },
  "6.3": { view: "combat_enemy", text: LOOP_FLOW.combat_enemy.intro },
  "6.8a": { view: "combat_player", text: LOOP_FLOW.combat_player.intro },
  "6.11": { view: "combat_player", text: COMBAT_LAST_CHANCE },
  "7.1": { view: "refresh", text: bandTextFor("refresh", "window") },
  "7.2": { view: "refresh", text: bandTextFor("refresh", "framework") },
  "7.5": { view: "round_end", text: bandTextFor("round_end", "framework") },
};
