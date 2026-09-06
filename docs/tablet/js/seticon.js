// Set icons (Task 5): a small <img> for a named encounter set/expansion,
// pulled from the SVGs tools/build_icons.py exports beside icons.json
// (docs/data/icons/svg/<slug>.svg, commit abfbd80) - the tablet's answer to
// the twin's rasterized icons.json masks (docs/js/icons.js's drawIcon), but
// as a real vector image instead of a bitmap decode, since a browser can
// just load an <img> for free.
//
// The slug is quest_catalog.js's own slugify() applied to the printed SET
// NAME - the one slug rule this client already has, not a second copy of
// tools/build_icons.py's _slug(). The two rules are NOT the same in
// general: _slug() lowercases the pack's own FILENAME (underscores to
// hyphens), while slugify() lowercases the printed NAME and turns every run
// of non-alphanumerics into one hyphen.
//
// So the <img> carries a CHAIN, not a single src: the primary slug, then any
// alternates, and only after the last one 404s does the placeholder glyph
// appear. app.js's one delegated error listener walks it. Two alternates
// exist, and they are different kinds of thing:
//
//   1. THE APOSTROPHE RULE. slugify turns "Sauron's Reach" into
//      "sauron-s-reach"; the pack files it as "saurons-reach". Dropping the
//      apostrophe before slugifying (rather than hyphenating it) recovers 8
//      of the catalog's names - Helm's Deep, Sauron's Reach, Shelob's Lair,
//      The Dream-chaser's Fleet, The King's Quest, The Steward's Fear, The
//      Wizard's Quest, Ulchor's Guard. A rule, so it needs no list.
//
//   2. THE DEFINITE ARTICLE RULE. The catalog drops a leading "The" that the
//      pack keeps: "Crossings of Poros" against the-crossings-of-poros.
//      Recovers 5 - Crossings of Poros, Fords of Isen, Foundations of Stone,
//      Nazgul, Temple of Doom. The same divergence CLAUDE.md already records
//      for the Vision of the Palantir corpus ("VotP prefixes a definite
//      article the catalog omits"), so it is a known trait of these names
//      rather than a coincidence. Tried both ways round; only adding one
//      ever matches today, and dropping one costs nothing to try.
//
//   3. ONE NAME THE PACK SPELLS DIFFERENTLY (below). No rule reaches it, so
//      it is a table, and the table has to earn each entry with a citation.
//
// Everything else the pack simply does not carry (201 of the catalog's 401
// names, nearly all of them "X - Nightmare" variants) and those fall back to
// the placeholder glyph, which is the correct answer for a set with no icon.
//
// Pure string builder like every other tablet render helper: no Image()
// probe, no fetch here - a missing SVG 404s like any other <img>, and
// app.js's one delegated capture-phase `error` listener is what actually
// adds `is-missing` to the wrapper (style.css's `.seticon.is-missing img` /
// `.seticon:not(.is-missing) .seticon-fallback` pair swap the glyph in).
import { h, raw } from "./dom.js";
import { dataUrl, slugify } from "../../js/quest_catalog.js";

// Names the community icon pack files under a different title than the one
// FFG prints. Keyed by OUR slug, valued by the pack's.
//
// "Journey Down the Anduin" is the Core Set's second scenario AND its
// encounter set: Learn to Play, "Journey Down the Anduin ... The Journey Down
// the Anduin encounter deck is built with all the cards from the following
// encounter sets: Journey Down the Anduin, Sauron's Reach, Dol Guldur Orcs,
// and Wilderlands." No card in the compiled catalog carries an encounterSet
// of "Journey Along the Anduin" - that string is a CARD name (a location in
// the scenario's Nightmare set). The pack nevertheless ships the symbol as
// journey-along-the-anduin.svg and has no journey-down-the-anduin.svg, while
// carrying every other Core Set set by its printed name (Passage Through
// Mirkwood, Spiders of Mirkwood, Dol Guldur Orcs, Sauron's Reach,
// Wilderlands, Escape from Dol Guldur) - so the file is this set's symbol
// under a wrong title. That last step is an inference from what the pack
// does and does not contain, not something the rulebook states.
const PACK_ALIASES = {
  "journey-down-the-anduin": "journey-along-the-anduin",
};

// Every slug worth trying for this name, primary first, no duplicates.
export function iconSlugs(name) {
  const primary = slugify(name);
  const out = [primary];
  const alias = PACK_ALIASES[primary];
  if (alias) out.push(alias);
  const push = s => { if (s && !out.includes(s)) out.push(s); };
  // The apostrophe rule: strip them rather than let slugify hyphenate them.
  const noApos = slugify(String(name ?? "").replace(/['\u2019]/g, ""));
  push(noApos);
  // The definite-article rule, applied to each spelling so far - both
  // directions, since the divergence is in the names, not in one pack.
  for (const s of [...out]) {
    push(s.startsWith("the-") ? s.slice(4) : "the-" + s);
  }
  return out;
}

// A CYCLE's own icon. The pack files these as "<name>-cycle.svg" with any
// leading "the" dropped - "The Dwarrowdelf" is dwarrowdelf-cycle.svg,
// "The Vengeance of Mordor" is vengeance-of-mordor-cycle.svg - so the cycle
// name needs its own chain rather than the set one. Verified against the pack:
// this resolves 9 of the catalog's 17 cycles. The 8 it does not are groupings
// this project invented rather than printed cycles (Core Set (Mirkwood Paths),
// the two Sagas, Standalone/PoD and the four ALeP groups), which have no cycle
// symbol to find - they fall back to the placeholder glyph, correctly.
export function cycleIcon(name, px) {
  const base = slugify(name);
  const bare = base.startsWith("the-") ? base.slice(4) : base;
  const chain = [];
  for (const b of [base, bare]) {
    for (const s of [b + "-cycle", b]) if (s && !chain.includes(s)) chain.push(s);
  }
  return iconImg(chain, px);
}

// One <img> carrying a chain of candidates. data-alt is the rest of it,
// comma-separated; app.js's error listener shifts one off and retries before
// giving up on the placeholder glyph.
function iconImg(chain, px) {
  const [primary, ...rest] = chain;
  const src = dataUrl("icons/svg/" + primary + ".svg");
  const alt = rest.map(s => dataUrl("icons/svg/" + s + ".svg")).join(",");
  return h`<span class="seticon" style="width:${px}px;height:${px}px"><img src="${src}" alt="" loading="lazy"${alt ? raw(h` data-alt="${alt}"`) : ""}><i class="seticon-fallback">◆</i></span>`;
}

export function setIcon(name, px) {
  return iconImg(iconSlugs(name), px);
}

// The scenario's own set icon, keyed by `game.scenario?.name` (the one name
// this app can turn into an icon slug at all - a scenario is usually also
// the encounter set its own quest cards belong to). Empty string for a
// bare/manual game with no preloaded scenario, so callers can `raw()` it
// unconditionally instead of repeating the `setName ? setIcon(...) : ""`
// guard - rail.js's stage pill and sheet_quest.js's quest-group header both
// used to carry that exact two-line duplicate.
export function scenarioIcon(game, px) {
  const setName = game.scenario?.name;
  return setName ? setIcon(setName, px) : "";
}
