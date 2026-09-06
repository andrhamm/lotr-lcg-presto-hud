// The Scenario overview (Task 3, milestone 6): the screen between picking a
// scenario and starting the game. Everything the players need before they
// deal a card - which quest this is, how hard they are playing it, which
// encounter sets to pull off the shelf, what the stages are worth, what the
// scenario's own cards look like, and this tracker's notes on it - plus the
// one decision the screen exists to take, the difficulty ladder.
//
// The SAME render is the read-only reference the QUEST zone's stage pill
// opens mid-game (open_overview): a game already under way has committed to
// its difficulty, so the ladder becomes a badge and the footer becomes
// Close. One renderer, not two, because the two would drift.
//
// Pure string builder like every other tablet render module - no document/
// window, no fetch. Everything it draws comes off `ui.overview`
// ({slug, entry, bundle, difficulty, readonly}), seated by app.js on both
// paths (pick_scenario, and boot's resume branch), plus ui.tips/ui.imagePrefix.
//
// Nothing here writes a sentence about the game: the mode tips are
// viewcopy's (difficulty.js), the card and stage text is the catalog's own,
// and the notes are tips.json's already-fact-checked distillation.
import { h, raw, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { setIcon } from "./seticon.js";
import { cardImage } from "./cardimage.js";
import { stagePointsShape } from "./xshape.js";
import { branchName } from "./resolve_step.js";
import { frontFace } from "./cards.js";
import { allNotes } from "./notes.js";
import { renderNotesGroup } from "./sheet_notes.js";
import { difficultyOptions, modeTip } from "./difficulty.js";
import { slugify } from "../../js/quest_catalog.js";

// The seat pick_scenario hands to ui.overview once db.bundle() has resolved,
// and the same one boot() seats for a resumed game (readonly, at the
// difficulty the game was started with). Pure, so tests can build it without
// a live DataClient - pick_scenario itself awaits and cannot be driven under
// node. `entry` is null for a slug the index does not carry (a catalog that
// changed under us, or one that never loaded on the resume path); the render
// degrades to the game's own scenario name rather than refusing to draw.
export function overviewFor(index, slug, bundle, opts = {}) {
  const entry = (index?.scenarios ?? []).find(s => s.slug === slug) ?? null;
  return { slug, entry, bundle, difficulty: opts.difficulty ?? "Standard",
           readonly: opts.readonly ?? false };
}

// What preloadScenario() is given when the players commit (app.js's
// begin_setup). Pure and here rather than inline in app.js so the one thing
// the ladder actually changes about the game - `nightmare`/`mode` - is
// testable without a browser. Every other field is copied off the catalog
// entry unchanged: `maxCardThreat`/`hasXThreat` are what the staging
// estimate reads, and dropping them silently would cost the estimate, not
// crash anything, which is exactly the kind of thing a test should hold.
export function scenarioMetaFor(entry, difficulty) {
  const e = entry ?? {};
  return {
    slug: e.slug, name: e.name, pack: e.pack, cycle: e.cycle,
    source: e.source, kind: e.kind,
    nightmare: difficulty === "Nightmare", mode: difficulty,
    maxCardThreat: e.maxCardThreat, hasXThreat: e.hasXThreat,
  };
}

// -- sections ---------------------------------------------------------

function header(name, entry, stageCount) {
  // pack · cycle · n stages: dense tabular metadata under the name, so
  // LABEL. Each piece is dropped when the catalog has nothing for it (a
  // minimal/synthetic index, or no entry at all) rather than leaving a
  // stranded separator.
  const stagesLabel = stageCount
    ? (stageCount === 1 ? CHROME.stagesCountOne : fmt(CHROME.stagesCount, stageCount))
    : "";
  const meta = [entry.pack, entry.cycle, stagesLabel]
    .filter(Boolean).join(" · ");
  return h`<header class="ov-head">${raw(setIcon(name, 44))}
<div class="ov-head-text"><h1 class="display">${name}</h1><p class="label">${meta}</p></div>
</header>`;
}

function difficultySection(ov, entry, data, difficulty) {
  const tip = modeTip(entry, data, difficulty);
  // At most one sentence, the way the twin's tip panel shows one - it is the
  // selected option's own copy, never a list of every option's.
  const tipLine = tip ? h`<p class="body">${tip}</p>` : "";
  if (ov.readonly) {
    // Nothing to choose mid-game: the difficulty is part of the scenario the
    // players committed to. A badge, not a chip - bevelled means tappable,
    // and this is not.
    return h`<section class="ov-section"><div class="label">${CHROME.difficulty}</div>
<span class="ov-badge label">${difficulty}</span>${raw(tipLine)}</section>`;
  }
  const chips = difficultyOptions(entry).map(opt => chip({
    act: "ov_difficulty", arg: opt, label: h`${opt}`,
    tone: opt === difficulty ? "gold" : "tan",
  })).join("");
  return h`<section class="ov-section"><div class="label">${CHROME.difficulty}</div>
<div class="ov-ladder">${raw(chips)}</div>${raw(tipLine)}</section>`;
}

// Every encounter set this quest draws from, not just its own - the gather
// list build_card_data.py merges from the Hall of Beorn enrichment
// (`includedSets`). Falls back to the scenario's own name when the
// enrichment never covered it (108 of ~350 scenarios are covered; the rest
// land here), exactly as the twin's _gatherSets() does - never an empty
// list, never a crash.
function gatherSets(data, name) {
  return (data.includedSets ?? [name]).filter(Boolean);
}

function setsSection(sets) {
  const rows = sets.map(s =>
    h`<li class="ov-set">${raw(setIcon(s, 28))}<span class="body">${s}</span></li>`).join("");
  return h`<section class="ov-section"><div class="label">${CHROME.setsToGather}</div>
<ul class="ov-sets">${raw(rows)}</ul></section>`;
}

// R7's points cell, via the shared predicate: a real printed target, the
// card's own X sentence, or nothing at all. NEVER a 0 - ~137 of ~400 stage
// cards advance on a condition and print no target, and 48 more have a blank
// upstream field (xshape.js's stagePointsShape carries the full reasoning).
function stagePoints(card) {
  const shape = stagePointsShape(card);
  if (shape === "number") return h`<span class="label">${fmt(CHROME.branchPoints, card.questPoints)}</span>`;
  if (shape === "x" && card.questPointsX?.text) return h`<p class="body">${card.questPointsX.text}</p>`;
  return "";
}

// One stage. A branch stage (39 in the catalog) gets one sub-row per
// alternative, named off the BACK face like every other branch list in this
// client - on 23 of the 39 every alternative's FRONT name is identical, so
// front-named rows would repeat one name three times (resolve_step.js's
// branchName, same function the resolution sheet uses).
function stageRow(st, i) {
  const cards = st.cards ?? [];
  const heading = h`<span class="label">${CHROME.stage} ${st.stage ?? i + 1}</span>`;
  if (cards.length > 1) {
    const alts = cards.map(c =>
      h`<div class="ov-alt"><p class="body">${branchName(c)}</p>${raw(stagePoints(c))}</div>`).join("");
    return h`<div class="ov-stage">${raw(heading)}${raw(alts)}</div>`;
  }
  const card = cards[0];
  if (!card) return h`<div class="ov-stage">${raw(heading)}</div>`;
  return h`<div class="ov-stage">${raw(heading)}<p class="body">${branchName(card)}</p>${raw(stagePoints(card))}</div>`;
}

function stagesSection(stages) {
  const rows = stages.map(stageRow).join("");
  return h`<section class="ov-section"><div class="label">${CHROME.stages}</div>
<div class="ov-stages">${raw(rows)}</div></section>`;
}

// The type headings, in the order a player meets the cards: what fights you,
// where you are, what goes wrong, what you are carrying. Anything else the
// catalog groups separately (objectiveAlly, shipEnemy, treasure, sideQuest)
// falls into one "Other" bucket rather than sprouting a heading per key.
const TYPE_ORDER = ["enemy", "location", "treachery", "objective"];

// R5: the scenario's OWN set, grouped by type. `scenarios/<slug>.json` is
// emitted per encounter group and in today's catalog holds nothing else
// (checked: 0 of 3301 encounter cards across every scenario file carry a
// different set), so this filter is belt-and-braces - but the gather list is
// what the Sets/Shared sets sections are for, and a card from a set the
// players have not opened yet does not belong in "this scenario's cards".
// A card with no `encounterSet` at all is kept rather than dropped.
function cardGroups(data, name) {
  const own = slugify(name);
  const buckets = new Map();
  for (const [key, cards] of Object.entries(data.encounter ?? {})) {
    if (!Array.isArray(cards)) continue;
    const mine = cards.filter(c => !c.encounterSet || slugify(c.encounterSet) === own);
    if (!mine.length) continue;
    const bucket = TYPE_ORDER.includes(key) ? key : "other";
    buckets.set(bucket, [...(buckets.get(bucket) ?? []), ...mine]);
  }
  return [...TYPE_ORDER, "other"].filter(k => buckets.has(k))
    .map(k => ({ key: k, cards: buckets.get(k) }));
}

// The caption under one card: how many copies, then what it prints. The
// words are the game's own - Learn to Play uses "engagement cost", "attack",
// "defense" (US spelling, as FFG prints it) and "Hit Points and Damage"
// (p.20) - and every value is the card's own, read off its printed front
// face. A null field is simply absent from the caption: it means the card
// prints nothing there, and inventing a 0 would be a claim about the card.
function cardCaption(key, card) {
  const face = frontFace(card) ?? {};
  const bits = [];
  if (card.quantity > 0) bits.push(fmt(CHROME.copies, card.quantity));
  const put = (t, v) => { if (v !== null && v !== undefined) bits.push(fmt(t, v)); };
  if (key === "enemy") {
    put(CHROME.stats.engagement, face.engagementCost);
    put(CHROME.stats.threat, face.threat);
    put(CHROME.stats.attack, face.attack);
    put(CHROME.stats.defense, face.defense);
    put(CHROME.stats.hitPoints, face.hitPoints);
  } else if (key === "location") {
    put(CHROME.stats.threat, face.threat);
    put(CHROME.branchPoints, face.questPoints);
  }
  return bits.join(" · ");
}

function cardsSection(groups, prefix) {
  const blocks = groups.map(g => {
    const figures = g.cards.map(c => cardImage({
      prefix, id: c.id, image: c.image, name: c.name,
      caption: cardCaption(g.key, c),
    })).join("");
    return h`<div class="ov-type"><div class="label">${CHROME.cardTypes[g.key]}</div>
<div class="ov-cards">${raw(figures)}</div></div>`;
  }).join("");
  return h`<section class="ov-section"><div class="label">${CHROME.cards}</div>
<div class="ov-types">${raw(blocks)}</div></section>`;
}

// The gather list minus this scenario's own set: the cards that are NOT in
// the Cards grid above, so the players know the grid is not the whole
// encounter deck. Chips by shape only - there is nothing to tap here, so
// they carry no bevel.
function sharedSection(sets, name) {
  const own = slugify(name);
  const others = sets.filter(s => slugify(s) !== own);
  if (!others.length) return "";
  const chips = others.map(s =>
    h`<span class="ov-chip">${raw(setIcon(s, 22))}<span class="body">${s}</span></span>`).join("");
  return h`<section class="ov-section"><div class="label">${CHROME.sharedSets}</div>
<div class="ov-chips">${raw(chips)}</div></section>`;
}

// The same groups the Notes sheet lists, drawn by the same renderer
// (sheet_notes.js's renderNotesGroup) - General first, then each stage in
// numeric order, each carrying its own Source link. Nothing at all for a
// scenario tips.json never distilled (122 of ~350), which is the same
// degrade the phase pane's notes panel makes.
function notesSection(ui, slug) {
  const groups = allNotes(ui.tips, slug ?? ui.scenarioSlug);
  if (!groups.length) return "";
  return h`<section class="ov-section"><div class="label">${CHROME.notes}</div>
${raw(groups.map(renderNotesGroup).join(""))}</section>`;
}

function footer(readonly) {
  if (readonly) {
    return h`<div class="cta-row ov-foot">${raw(cta({ act: "ov_close", label: CHROME.close, tone: "plain" }))}</div>`;
  }
  return h`<div class="cta-row ov-foot">${raw(cta({ act: "ov_back", label: CHROME.backToScenarios, tone: "plain" }))}${raw(cta({ act: "begin_setup", label: CHROME.beginSetup, tone: "ok" }))}</div>`;
}

export function renderOverview(game, ui) {
  const ov = ui.overview ?? {};
  const entry = ov.entry ?? {};
  const data = ov.bundle?.scenario ?? {};
  const stages = ov.bundle?.stages ?? [];
  // Three names for one thing, in falling order of authority: the index
  // entry, the scenario file, and - for a resumed game whose catalog never
  // loaded - the name the save itself carries.
  const name = entry.name ?? data.name ?? game?.scenario?.name ?? "";
  const difficulty = ov.difficulty ?? "Standard";
  const sets = gatherSets(data, name);

  const left = h`<div class="ov-main">${raw(header(name, entry, entry.stageCount ?? stages.length))}
${raw(difficultySection(ov, entry, data, difficulty))}
${raw(setsSection(sets))}
${raw(stagesSection(stages))}
${raw(cardsSection(cardGroups(data, name), ui.imagePrefix))}</div>`;
  const right = h`<div class="ov-side">${raw(sharedSection(sets, name))}${raw(notesSection(ui, ov.slug))}</div>`;
  return h`<main class="pane overview"><div class="ov-grid">${raw(left)}${raw(right)}${raw(footer(ov.readonly))}</div></main>`;
}
