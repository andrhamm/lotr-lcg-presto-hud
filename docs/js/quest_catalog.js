// Quest catalog: cycle/source grouping over the M4-A card-data index, for
// the quest-picker screens (Pick Cycle / Choose Scenario) — M4-B, Task 3.
//
// groupByCycle/cyclesFor are pure and mirror quest_catalog.py's host-tested
// logic verbatim (sanity-checked with a node one-liner, not a test file —
// the host tests live on the Python twin per project convention). loadIndex/
// loadScenario are thin fetch wrappers and are NOT host-tested.

// Verified product/cycle order (see docs/superpowers/plans/
// 2026-07-24-quest-picker-bcore.md Task-2 findings — includes the "Ered
// Mithrin" cycle the original brief omitted). Cycle names not in this list
// sort immediately before "Other" (see cycleRank) rather than being dropped.
export const CYCLE_ORDER = [
  "Core Set", "Shadows of Mirkwood", "The Dwarrowdelf", "Against the Shadow",
  "The Ring-maker", "The Angmar Awakened", "The Dream-chaser", "The Haradrim",
  "Ered Mithrin", "The Vengeance of Mordor", "Hobbit Saga", "LotR Saga",
  "Standalone/PoD", "Other",
];

// Sort key: CYCLE_ORDER position. A cycle name absent from the list
// (shouldn't happen given build_card_data.py's own "Other" fallback, but
// kept defensive) ranks just before "Other" rather than falling off the end.
function cycleRank(cycle) {
  const i = CYCLE_ORDER.indexOf(cycle);
  return i === -1 ? CYCLE_ORDER.indexOf("Other") - 0.5 : i;
}

// Plain ordinal string compare (not localeCompare) so tie-breaks match
// Python's default str sort exactly between the two twins.
function byName(a, b) {
  const an = a.name ?? "", bn = b.name ?? "";
  return an < bn ? -1 : an > bn ? 1 : 0;
}

// The group's display date: the earliest non-null releaseDate among its
// scenarios (YYYY-MM strings compare lexicographically = chronologically),
// or null if every scenario's releaseDate is null (true for all scenarios
// as of Task 2 — B-data is expected to fill these in).
function earliestDate(scenarios) {
  const dates = scenarios.map(s => s.releaseDate).filter(Boolean);
  if (dates.length === 0) return null;
  return dates.reduce((a, b) => (a < b ? a : b));
}

// Group `scenarios` (index.json scenarios[] entries) by cycle for one picker
// source ("official"/"alep"), for the Pick Cycle / Choose Scenario screens.
//
// - Keeps only playable quests (stageCount > 0), excluding kind=="nightmare"
//   and non-quest sets (encounter, campaign).
// - Groups ordered by CYCLE_ORDER (stable: ties keep first-seen order).
// - Scenarios within a group ordered by `name`.
//
// Returns [{cycle, date, scenarios: [entry, ...]}].
export function groupByCycle(scenarios, source) {
  const groups = new Map();
  for (const scn of scenarios) {
    if (scn.source !== source || scn.kind === "nightmare" || (scn.stageCount ?? 0) <= 0) continue;
    const cycle = scn.cycle ?? "Other";
    if (!groups.has(cycle)) groups.set(cycle, []);
    groups.get(cycle).push(scn);
  }

  return [...groups.keys()]
    .sort((a, b) => cycleRank(a) - cycleRank(b))
    .map(cycle => {
      const scns = [...groups.get(cycle)].sort(byName);
      return { cycle, date: earliestDate(scns), scenarios: scns };
    });
}

// [{cycle, date, count}] for the Pick Cycle screen — same filtering/order as
// groupByCycle, over a whole loaded index.json object (as returned by
// loadIndex()).
export function cyclesFor(index, source) {
  return groupByCycle(index.scenarios ?? [], source)
    .map(g => ({ cycle: g.cycle, date: g.date, count: g.scenarios.length }));
}

// Read the whole catalog index. Thin wrapper, not host-tested.
export async function loadIndex() {
  return (await fetch("data/index.json")).json();
}

// Read one scenario's full stage/card data. Thin wrapper, not host-tested.
export async function loadScenario(slug) {
  return (await fetch("data/scenarios/" + slug + ".json")).json();
}
