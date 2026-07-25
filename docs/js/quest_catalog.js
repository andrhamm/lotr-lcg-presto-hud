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
    if (scn.source !== source || scn.kind === "nightmare" || (scn.stageCount ?? 0) <= 0
        || (scn.name ?? "").endsWith(" - Nightmare")) continue;
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

// Flatten every pack's cards.sideQuest into a name-sorted list of
// {id, name, points, sphere, pack} for the side-quest picker (M4-B
// sidequest, Task 1). Mirrors quest_catalog.py's side_quests() verbatim
// (sanity-checked with a node one-liner, not a test file, per this file's
// existing convention - see the header comment). `playerDb` is an array of
// loaded pack objects (players/<pack>.json shape) or an object of them
// keyed by slug; either is accepted.
//
// `points` is the first non-null questPoints across the card's faces, else
// 0 - 2 of the 14 known player side quests are variable "X" quests with
// every face's questPoints null (Protect the Innocent, Rally the West);
// those show 0 here and the player edits the real value once seated.
export function sideQuests(playerDb) {
  const packs = Array.isArray(playerDb) ? playerDb : Object.values(playerDb ?? {});
  const out = [];
  for (const pack of packs) {
    const packName = pack.pack ?? "";
    const cards = pack.cards?.sideQuest ?? [];
    for (const card of cards) {
      let points = 0;
      for (const face of card.faces ?? []) {
        if (face.questPoints !== null && face.questPoints !== undefined) {
          points = face.questPoints;
          break;
        }
      }
      out.push({ id: card.id, name: card.name, points, sphere: card.sphere, pack: packName });
    }
  }
  return out.sort(byName);
}

// Read every pack listed in players/index.json (a bare JSON array of
// {slug, name, cardCount}, per build_card_data.py's emit()) and flatten via
// sideQuests(). Thin fetch wrapper, not host-tested - on ANY failure (data/
// not built yet, a missing/corrupt pack, ...) returns [] so the side-quest
// picker's caller falls back to today's manual "+ Side quest" entry rather
// than erroring (per the plan's Global Constraints: catalog data is
// optional at runtime).
export async function loadPlayerSideQuests() {
  try {
    const index = await (await fetch("data/players/index.json")).json();
    const packs = await Promise.all(
      index.map(entry => fetch("data/players/" + entry.slug + ".json").then(r => r.json())));
    return sideQuests(packs);
  } catch (e) {
    console.error("quest catalog: loadPlayerSideQuests failed - falling back to manual entry", e);
    return [];
  }
}

// Icon matcher (M4-B icons, Task 2) - maps a catalog encounterSet slug to a
// rasterized mask from docs/data/icons.json. Mirrors quest_catalog.py's
// normalizeIconKey/iconFor verbatim (sanity-checked with a node one-liner,
// not a test file, per this file's existing convention - see the header
// comment).

const REPEAT_HYPHENS = /-{2,}/g;
const NON_ALNUM_RUN = /[^a-z0-9]+/g;

// A display name (e.g. a "sets to gather" row label) -> the same slug shape
// tools/build_card_data.py's own slugify() produces (mirrored, not
// imported - tools/ is host-only Python build tooling): lowercase, any run
// of non-alphanumerics becomes one hyphen, no leading/trailing hyphen.
// Never throws (falsy input -> "").
//
// "The Steward's Fear" -> "the-steward-s-fear" - the exact "-s-" shape
// normalizeIconKey()'s possessive rule exists to undo.
export function slugify(name) {
  let s = (name ?? "").toString().trim().toLowerCase();
  s = s.replace(NON_ALNUM_RUN, "-");
  return s.replace(/^-+|-+$/g, "");
}

// Fold a catalog encounterSet slug or an icons.json key onto a common form
// so iconFor() can match across the small, mostly-cosmetic differences
// between the two sources (our catalog slugs come from set names; the icon
// pack's come from its own filenames) - apostrophes rendered as
// "-s-"/"-s", a leading "the-" article, doubled hyphens, and
// Nightmare-suffixed variants of an otherwise identical set. Never throws
// (falsy input -> "").
//
// Order matters: nightmare-suffix is dropped before the possessive fix so
// "...-s-nightmare" can't leave a dangling "-s"; "the-" is stripped after,
// so a normalized "the-...-s-..." lines up with a plain "...-..." key.
export function normalizeIconKey(slug) {
  if (!slug) return "";
  let s = slug.toLowerCase();
  if (s.endsWith("-nightmare")) s = s.slice(0, -"-nightmare".length);
  s = s.split("-s-").join("s-");
  if (s.endsWith("-s")) s = s.slice(0, -2) + "s";
  if (s.startsWith("the-")) s = s.slice("the-".length);
  return s.replace(REPEAT_HYPHENS, "-");
}

// The rasterized mask (a [size, [rows...]] pair, see docs/js/icons.js'
// drawIcon) for catalog `slug` out of a loaded `icons` object (loadIcons()'s
// "icons" map), or null if there's no reasonable match - the caller
// (iconSlot()) keeps its placeholder glyph in that case, never a crash or a
// blank hole.
//
// Three tries, cheapest/most-precise first: the exact slug; the normalized
// slug tried as-is against `icons`' (unnormalized) keys; and finally both
// sides normalized, for the cases where each source keeps a different one
// of two forms (e.g. one has a "the-" article the other dropped). Never
// throws - falsy `slug`/`icons` just fall through to null.
export function iconFor(slug, icons) {
  if (!slug || !icons) return null;
  if (slug in icons) return icons[slug];
  const norm = normalizeIconKey(slug);
  if (norm in icons) return icons[norm];
  for (const key of Object.keys(icons)) {
    if (normalizeIconKey(key) === norm) return icons[key];
  }
  return null;
}

// Read the rasterized set/scenario icon masks (tools/build_icons.py's
// docs/data/icons.json "icons" map). Thin fetch wrapper, not host-tested -
// on ANY failure (data/ not built yet, build_icons.py found no SVG pack and
// wrote an empty map, a corrupt file, ...) returns {} so iconFor() always
// misses and every iconSlot() falls back to its placeholder glyph rather
// than erroring (per the plan's Global Constraints: catalog data is
// optional at runtime).
export async function loadIcons() {
  try {
    const data = await (await fetch("data/icons.json")).json();
    return data.icons ?? {};
  } catch (e) {
    console.error("quest catalog: loadIcons failed - icon slots stay placeholders", e);
    return {};
  }
}

// Strategy tips (M4-B tips, Task 2) - mirrors quest_catalog.py's tips_for/
// load_tips verbatim (sanity-checked with a node one-liner, not a test
// file, per this file's existing convention - see the header comment).

// {tips: [...], attribution: {...}} for catalog `slug` at `stage` (a stage
// NUMBER - card.stage, not an index into game.stages - `tips` keys its
// "stages" map by stage number as a string; `stage` may be passed as
// either a number or a string), or null when there is nothing to show
// (unknown slug, or an entry whose general/stages both come up empty for
// this stage) - the modal's Tips button stays in its disabled state in
// that case.
//
// Merges that stage's own notes with the scenario-wide `general` notes,
// stage-specific first (a player mid-stage cares about this stage's
// branch-specific gotchas before the scenario's general threat-watch
// advice). Never throws - a falsy/malformed `tips` (e.g. {} from a
// loadTips() failure) just means every lookup misses.
export function tipsFor(slug, stage, tips) {
  const entry = (tips ?? {})[slug];
  if (!entry) return null;
  const stageTips = (entry.stages ?? {})[String(stage)] ?? [];
  const general = entry.general ?? [];
  const merged = [...stageTips, ...general];
  if (!merged.length) return null;
  return { tips: merged, attribution: entry.attribution ?? {} };
}

// Read the per-scenario strategy tips (tools/build_tips.py's
// docs/data/tips.json "scenarios" map). Thin fetch wrapper, not
// host-tested - on ANY failure (data/ not built yet, tips.json wasn't
// generated this build, a corrupt file, ...) returns {} so tipsFor()
// always misses and the Tips button stays in its disabled state rather
// than erroring (per the plan's Global Constraints: tips are optional at
// runtime).
export async function loadTips() {
  try {
    const data = await (await fetch("data/tips.json")).json();
    return data.scenarios ?? {};
  } catch (e) {
    console.error("quest catalog: loadTips failed - Tips button stays disabled", e);
    return {};
  }
}
