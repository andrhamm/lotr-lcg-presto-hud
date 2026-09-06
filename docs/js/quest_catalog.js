// Quest catalog: cycle/source grouping over the M4-A card-data index, for
// the quest-picker screens (Pick Cycle / Choose Scenario) — M4-B, Task 3.
//
// groupByCycle/cyclesFor are pure and mirror quest_catalog.py's host-tested
// logic verbatim (sanity-checked with a node one-liner, not a test file —
// the host tests live on the Python twin per project convention). loadIndex/
// loadScenario are thin fetch wrappers and are NOT host-tested.

// The compiled card data lives beside this module's directory (docs/data/),
// not beside the page: the web twin's page is docs/index.html but the
// tablet's is docs/tablet/index.html. Resolving against import.meta.url
// makes both clients fetch docs/data/ regardless of the page they load from.
export const dataUrl = path => new URL("../data/" + path, import.meta.url).href;

// Verified product/cycle order (see docs/superpowers/plans/
// 2026-07-24-quest-picker-bcore.md Task-2 findings — includes the "Ered
// Mithrin" cycle the original brief omitted). Cycle names not in this list
// sort immediately before "Other" (see cycleRank) rather than being dropped.
export const CYCLE_ORDER = [
  "Core Set (Mirkwood Paths)", "Shadows of Mirkwood", "The Dwarrowdelf", "Against the Shadow",
  "The Ring-maker", "The Angmar Awakened", "The Dream-chaser", "The Haradrim",
  "Ered Mithrin", "The Vengeance of Mordor", "Hobbit Saga", "LotR Saga",
  "Standalone/PoD",
  // Fan-made (A Long Extended Party). These only ever appear under the
  // Scenario Source screen's community option - groupByCycle filters on
  // `source` first - so they never interleave with the official cycles
  // above. Order and names come from the DragnCards plugin's own menu
  // files; see tools/alep.py.
  "ALeP - Children of Eorl & Oaths of the Rohirrim",
  "ALeP - The Shire's Reckoning & Fell Summer",
  "ALeP - Print on Demand",
  "ALeP - Other",
  "Other",
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
      // PLAY order, not alphabetical. `order` is the global rank
      // tools/build_scenario_order.py aggregates from Hall of Beorn;
      // alphabetical put the Core Set in the exact reverse of its own
      // sequence (Escape, Journey, Passage). Scenarios the table does not
      // cover have no `order` and fall to the end, by date then name.
      const scns = [...groups.get(cycle)].sort((a, b) =>
        (a.order == null) - (b.order == null)
        || (a.order ?? 0) - (b.order ?? 0)
        || (a.releaseDate || "").localeCompare(b.releaseDate || "")
        || byName(a, b));
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

// Everything the three quest-picker screens need to rebuild themselves from a
// saved game's `scenario` stamp, or null if it cannot be resolved.
//
// A resumed game restores its own state fine, but the picker screens are
// router-held: the boot path built them as empty placeholders and `resume`
// only flipped to the play screen, so backing out of Quest Setup landed on an
// unpopulated Scenario Options and the router bounced the player all the way
// to Scenario Source to pick again. Nothing was missing from the save -
// `scenario` already carries slug/name/pack/cycle/source and the chosen
// `mode` - it was just never read back.
//
// Returns null rather than throwing for every way this can legitimately miss:
// a custom game (no scenario at all), or a slug the current catalog no longer
// has because it was rebuilt without ALeP or with a newer card DB.
export function resumePickerState(index, scenario) {
  if (!scenario?.slug) return null;
  const entry = (index.scenarios ?? []).find(s => s.slug === scenario.slug);
  if (!entry) return null;
  // Prefer the stamp's own source/cycle: they are what the player actually
  // navigated through, and they were captured when the pick was made.
  const source = scenario.source ?? entry.source;
  const cycle = scenario.cycle ?? entry.cycle;
  const group = groupByCycle(index.scenarios ?? [], source)
    .find(g => g.cycle === cycle);
  return {
    entry, source, cycle,
    cycles: cyclesFor(index, source),
    siblings: group?.scenarios ?? [],
    // "mode" is where begin_setup stamps the chosen difficulty; a game saved
    // before that field existed just reads as Standard.
    difficulty: scenario.mode || "Standard",
  };
}

// Read the whole catalog index. Thin wrapper, not host-tested.
export async function loadIndex() {
  return (await fetch(dataUrl("index.json"))).json();
}

// Read one scenario's full stage/card data. Thin wrapper, not host-tested.
export async function loadScenario(slug) {
  return (await fetch(dataUrl("scenarios/" + slug + ".json"))).json();
}

// The card-image URL prefix build_card_data.py pinned alongside the card TSV
// (tools/data/cardDb.SOURCE.txt's `image_prefix=`, task 6/R5) and copied into
// index.json as `imagePrefix`. A card record carries only `image:
// "<id>.jpg"`; this prefix plus that id is the full URL. null for an index
// built before this field existed, or any falsy/missing input - trivial by
// design, mirroring quest_catalog.py's image_prefix() verbatim so both
// twins read the identical key.
export function imagePrefix(index) {
  return index?.imagePrefix ?? null;
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
  // Fast path: the precomputed list the build emits. The scan below is kept
  // only for a data/ deploy predating that file - it fetches all 105 packs,
  // which on the firmware twin's flash meant 1.6 MB and 6.4 SECONDS per tap.
  try {
    return await (await fetch(dataUrl("players/side_quests.json"))).json();
  } catch (e) { /* fall through to the scan */ }
  try {
    const index = await (await fetch(dataUrl("players/index.json"))).json();
    const packs = await Promise.all(
      index.map(entry => fetch(dataUrl("players/" + entry.slug + ".json")).then(r => r.json())));
    return sideQuests(packs);
  } catch (e) {
    console.error("quest catalog: loadPlayerSideQuests failed - falling back to manual entry", e);
    return [];
  }
}

// The scenarios/<slug>.json files that between them hold every location this
// scenario can put into play: its "sets to gather" (the committed Hall of
// Beorn enrichment's includedSets, slugified), or its own slug alone when it
// has no gather list. Mirrors quest_catalog.py's location_set_slugs().
//
// The fallback is not a rare path - the enrichment covers 108 scenarios and
// the rest fall back here, which is exactly why the picker keeps its manual
// stepper (see LocationPickModal).
export function locationSetSlugs(scenario) {
  const scn = scenario ?? {};
  const sets = scn.includedSets ?? [];
  if (sets.length) return sets.map(slugify);
  return scn.slug ? [scn.slug] : [];
}

// Every location `scenario` can put into play, as a name-sorted array of
// {id, name, points, threat, set} (plus `image` where the card has art) for
// the location picker. Mirrors
// quest_catalog.py's locations_for() verbatim - keep the two in lockstep.
//
// The union is load-bearing. A scenario's own scenarios/<slug>.json carries
// only cards whose encounterSet IS that scenario's set, so Passage Through
// Mirkwood's own file holds 2 of its 6 locations - the other 4 live in the
// Dol Guldur Orcs and Spiders of Mirkwood files it gathers. `packs` is an
// object of loaded scenario files keyed by slug; a gather-list name with no
// file (14 of 309 catalog-wide) is skipped rather than throwing, and packs
// NOT in the gather list are ignored.
//
// points/threat are the first non-null questPoints/threat across the card's
// faces, else 0 - 15 catalog locations are variable or condition-explored
// with a null questPoints on every face, and 21 are multi-face. Same rule
// sideQuests() uses for the variable "X" quests.
//
// Deduped by (name, encounterSet). `quantity` is deliberately NOT carried -
// the HUD does not model the encounter deck and must not imply it knows
// what is left in it.
export function locationsFor(scenario, packs) {
  const bySlug = packs ?? {};
  const out = [];
  const seen = new Set();
  for (const slug of locationSetSlugs(scenario)) {
    const pack = bySlug[slug];
    if (!pack) continue;
    for (const card of pack.encounter?.location ?? []) {
      const key = JSON.stringify([card.name, card.encounterSet]);
      if (seen.has(key)) continue;
      seen.add(key);
      // Mirrors quest_catalog.py's locations_for: when no face carries a
      // number the printed value was not one, and `${key}Kind` says which of
      // "x" (the card prints a literal X) / "na" (the stat does not apply) it
      // was, with `${key}X` carrying the CODED definition where the card has
      // one - {text, target, mul, add}, so nothing parses the prose. See
      // xtargets.py. This used to flatten all of it to 0.
      const faces = card.faces ?? [];
      const stat = (name) => {
        const has = (v) => v !== null && v !== undefined;
        const val = faces.find(f => has(f[name]));
        if (val) return { value: val[name] };
        const kind = faces.find(f => f[name + "Kind"]);
        const coded = faces.find(f => f[name + "X"]);
        return { value: 0, kind: kind ? kind[name + "Kind"] : "x",
                 x: coded ? coded[name + "X"] : null };
      };
      const qp = stat("questPoints"), th = stat("threat");
      const entry = { id: card.id, name: card.name, points: qp.value,
                      threat: th.value, set: card.encounterSet };
      // The card-art FILENAME as the build recorded it (tablet task 6:
      // docs/tablet/js/cardimage.js joins it to index.json's imagePrefix).
      // Usually "<id>.jpg", but not always - 24 of 1016 catalog locations
      // print on the BACK of a two-sided card and carry "<id>.B.jpg", and 2
      // carry an absolute Hall of Beorn URL - so the filename is carried
      // rather than rebuilt from the id. Omitted when the card has none, so
      // an entry for a card without art is byte-identical to before.
      if (card.image) entry.image = card.image;
      for (const [s, key] of [[qp, "points"], [th, "threat"]]) {
        if (s.kind) entry[key + "Kind"] = s.kind;
        if (s.x) entry[key + "X"] = s.x;
      }
      out.push(entry);
    }
  }
  return out.sort(byName);
}

// Every card picture `scenario` can put on screen (Task 6b's ruling: Begin
// setup prefetches the scenario's own set AND its gathered sets, not just
// the picker's locations), as a list of {id, image} deduped by id. Mirrors
// quest_catalog.py's card_images_for() verbatim - keep the two in lockstep.
//
// Same union locationsFor() makes and for the same reason - a scenario's own
// scenarios/<slug>.json holds only cards whose encounterSet IS its own set,
// so the rest of the pictures live in the gather list (locationSetSlugs(),
// same fallback to the scenario's own slug when it has no gather list). This
// walks EVERY encounter group (enemy, location, treachery, objectiveAlly,
// ...) rather than just location, because every one of those types can end
// up on screen. `image` is omitted when the card has none, the same rule
// locationsFor() uses, so cardUrl()'s "<id>.jpg" fallback still applies.
export function cardImagesFor(scenario, packs) {
  const bySlug = packs ?? {};
  const out = [];
  const seen = new Set();
  for (const slug of locationSetSlugs(scenario)) {
    const pack = bySlug[slug];
    if (!pack) continue;
    for (const group of Object.values(pack.encounter ?? {})) {
      if (!Array.isArray(group)) continue;
      for (const card of group) {
        if (seen.has(card.id)) continue;
        seen.add(card.id);
        const entry = { id: card.id };
        if (card.image) entry.image = card.image;
        out.push(entry);
      }
    }
  }
  return out;
}

// Fetch scenario `scenario`'s own card file plus every file on its gather
// list, keyed by slug. Shared by loadLocations() and loadScenarioMedia() so
// a bundle() read loads every gathered pack ONCE rather than once per caller.
async function loadGatheredPacks(scenario) {
  const packs = {};
  await Promise.all(locationSetSlugs(scenario).map(setSlug =>
    fetch(dataUrl("scenarios/" + setSlug + ".json"))
      .then(r => r.ok ? r.json() : null)
      .then(pack => { if (pack) packs[setSlug] = pack; })
      .catch(() => {})));
  return packs;
}

// Fetch scenario `slug`'s own card file plus every file on its gather list,
// and flatten via locationsFor(). Thin fetch wrapper, not host-tested - on
// ANY failure (data/ not built yet, an unpicked or uncatalogued quest, a
// corrupt file, ...) returns [] so LocationPickModal opens straight on its
// manual stepper rather than erroring (per the plan's Global Constraints:
// catalog data is optional at runtime). Individual missing set files resolve
// to null and are skipped by locationsFor, so one absent set never costs the
// others.
export async function loadLocations(slug) {
  if (!slug) return [];
  try {
    const scenario = await loadScenario(slug);
    const packs = await loadGatheredPacks(scenario);
    return locationsFor(scenario, packs);
  } catch (e) {
    console.error("quest catalog: loadLocations failed - falling back to manual entry", e);
    return [];
  }
}

// Fetch `scenario`'s own card file plus every file on its gather list ONCE,
// and flatten into both locationsFor() and cardImagesFor() - the pair
// db.bundle() pins together. Takes the already-loaded scenario record
// (bundle() has it in hand) rather than a slug, so this is the one place
// that does NOT re-fetch it. Same failure story as loadLocations(): on ANY
// failure both come back empty so the bundle still assembles rather than
// erroring.
export async function loadScenarioMedia(scenario) {
  try {
    const packs = await loadGatheredPacks(scenario);
    return { locations: locationsFor(scenario, packs), images: cardImagesFor(scenario, packs) };
  } catch (e) {
    console.error("quest catalog: loadScenarioMedia failed - falling back to manual entry", e);
    return { locations: [], images: [] };
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
    const data = await (await fetch(dataUrl("icons.json"))).json();
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
    const data = await (await fetch(dataUrl("tips.json"))).json();
    return data.scenarios ?? {};
  } catch (e) {
    console.error("quest catalog: loadTips failed - Tips button stays disabled", e);
    return {};
  }
}

// Read the parsed Rules Reference excerpts (tools/build_rules_text.py's
// docs/data/rules_text.json - book, sections, glossary, faq). Thin fetch
// wrapper, not host-tested - on ANY failure (data/ not built yet,
// rules_text.json wasn't generated this build, a corrupt file, ...) returns
// null so callers treat rules lookup as unavailable rather than erroring
// (same "optional at runtime" contract as loadTips()).
export async function loadRulesText() {
  try {
    return await (await fetch(dataUrl("rules_text.json"))).json();
  } catch (e) {
    console.error("quest catalog: loadRulesText failed - rules text unavailable", e);
    return null;
  }
}
