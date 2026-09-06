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
import { h, raw, fmt, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { setIcon } from "./seticon.js";
import { cardImage } from "./cardimage.js";
import { stagePointsShape } from "./xshape.js";
import { branchName } from "./resolve_step.js";
import { frontFace } from "./cards.js";
import { notesAt } from "./notes.js";
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

// The heading names WHAT YOU ARE LOOKING AT, which is not always the
// scenario: on a stage it is that stage. There used to be two DISPLAY
// headings on a stage view - the scenario's and the stage card's - so the
// biggest text on screen never changed as you navigated, and the thing you
// had actually selected was the smaller of the two.
//
// The scenario is a breadcrumb above it, at LABEL, together with the dense
// metadata that was already there: it is still worth naming (the in-game
// reference has no list to read it off) but it is context, not the subject.
// Each piece is dropped when the catalog has nothing for it rather than
// leaving a stranded separator.
function header(name, entry, stageCount) {
  const stagesLabel = stageCount
    ? (stageCount === 1 ? CHROME.stagesCountOne : fmt(CHROME.stagesCount, stageCount))
    : "";
  // The pack is dropped when the cycle already contains it ("Core Set" inside
  // "Core Set (Mirkwood Paths)") - printing both is how the breadcrumb this
  // replaces came to be four items long with two of them the same words.
  const cycle = entry.cycle ?? "";
  const pack = entry.pack && !cycle.includes(entry.pack) ? entry.pack : "";
  const meta = [pack, cycle, stagesLabel].filter(Boolean).join(" · ");
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
      prefix, id: c.id, image: c.image, name: c.name, faces: c.faces,
      caption: cardCaption(g.key, c),
    })).join("");
    return h`<div class="ov-type"><div class="label">${CHROME.cardTypes[g.key]}</div>
<div class="ov-cards">${raw(figures)}</div></div>`;
  }).join("");
  return h`<section class="ov-section"><div class="label">${CHROME.cards}</div>
<div class="ov-types">${raw(blocks)}</div></section>`;
}

// The same groups the Notes sheet lists, drawn by the same renderer
// (sheet_notes.js's renderNotesGroup) - General first, then each stage in
// numeric order, each carrying its own Source link. Nothing at all for a
// scenario tips.json never distilled (122 of ~350), which is the same
// degrade the phase pane's notes panel makes.
// The tips, in FIXED SLOTS. Same set, same order, every time - a player
// learns once where pacing advice lives and then always looks there, which
// only works if an empty slot is drawn as empty rather than dropped. That is
// the whole reason this is not just a list.
//
// Tips are strings in tips.json today and every one of them lands in `notes`;
// notes.js's slotted() also accepts {kind, text}, so the classification pass
// can land scenario by scenario without a flag day here.
function slotRows(slots) {
  return slots.map(s => {
    const body = s.items.length
      ? s.items.map(t => h`<li class="body">${t}</li>`).join("")
      : h`<li class="body is-empty">${CHROME.tipSlotEmpty}</li>`;
    return h`<div class="${cx("tipslot", !s.items.length && "is-empty")}">
<span class="label">${CHROME.tipSlots[s.kind]}</span>
<ul>${raw(body)}</ul></div>`;
  }).join("");
}

// `stage` is null for the scenario's general tips, or the stage number.
function tipsSection(ui, slug, stage) {
  const at = notesAt(ui.tips, slug ?? ui.scenarioSlug, stage);
  if (!at) return "";
  const name = at.source?.name ?? "";
  const url = at.source?.url ?? "";
  const link = url
    ? h`<a class="chip chip-tan" href="${url}" target="_blank" rel="noopener">${CHROME.source} · ${name} ›</a>`
    : (name ? h`<span class="label">${CHROME.source} · ${name}</span>` : "");
  return h`<section class="ov-section"><div class="label">${CHROME.notes}</div>
<div class="tipslots">${raw(slotRows(at.slots))}</div>${raw(link)}</section>`;
}

// The whole-screen host has exactly one way out, because it now has exactly
// one caller: the in-game reference (open_overview, always read-only). It
// used to double as the pre-game step between the picker and setup, with a
// Back and a Begin setup - that job belongs to the chooser now, which embeds
// renderScenarioDetail() directly and brings its own Continue.
// One stage, in full: each alternative card, each of its faces, with the
// printed text as written. A branch stage (39 in the catalog) shows every
// alternative - which one the quest deck turns up is not knowable here, and
// naming only the first would be a claim.
//
// Faces are labelled by their printed side. The A side is story/setup and the
// B side carries the quest points (CLAUDE.md: quest cards are two-sided, and
// the flip happens at every stage advance), so both are worth reading before
// the game starts - which is the whole reason this screen exists.
function stageFace(face) {
  const label = face.side === "B" ? CHROME.stageSideB
    : (face.side === "A" ? CHROME.stageSideA : "");
  const text = face.text
    ? h`<p class="body">${face.text}</p>`
    : h`<p class="body is-empty">${CHROME.stageFaceBlank}</p>`;
  return h`<div class="stage-face">${label ? raw(h`<div class="label">${label}</div>`) : ""}${raw(text)}</div>`;
}

// A single-card stage does NOT repeat its name here: the heading above says
// "Stage 1 · Flies and Spiders" already, and printing it again immediately
// underneath is the same redundancy the three repeated STAGE blocks were.
// A branch stage does name each block, because there the name identifies
// WHICH of the alternatives you are reading - the heading can only say how
// many there are.
function stageCardBlock(card, named) {
  const faces = (card.faces ?? []).map(stageFace).join("");
  const head = named
    ? h`<header class="stage-card-head"><p class="body strong">${branchName(card)}</p>${raw(stagePoints(card))}</header>`
    : (stagePoints(card) ? h`<header class="stage-card-head">${raw(stagePoints(card))}</header>` : "");
  return h`<article class="stage-card">${raw(head)}${raw(faces)}</article>`;
}

function stageDetail(stage) {
  const cards = stage.cards ?? [];
  const named = cards.length > 1;
  return h`<section class="ov-section">${raw(cards.map(c => stageCardBlock(c, named)).join(""))}</section>`;
}

function footer() {
  return h`<div class="cta-row ov-foot">${raw(cta({ act: "ov_close", label: CHROME.close, tone: "plain" }))}</div>`;
}

// Everything this screen KNOWS about a scenario, with no opinion about where
// it is being shown. Two hosts embed it and there must never be a third
// version of any of it:
//
//   - the scenario chooser (newgame.js), in the detail column beside the
//     drill-in list, with the difficulty ladder live;
//   - the in-game reference the QUEST zone's stage pill opens
//     (open_overview), read-only, at the difficulty the game committed to.
//
// The chooser used to be a separate SCREEN you left the picker for, which is
// what made "the same content" a thing that could drift. It cannot now: the
// chooser and the in-game reference call this one function.
export function renderScenarioDetail(game, ui) {
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

  // Which of the two views this is. The selection lives on the chooser's own
  // picker seat; the in-game reference has no list to select from, so it is
  // always the overview.
  const sel = ui.picker?.stage ?? "overview";
  const stage = sel === "overview" ? null
    : stages.find((st, i) => String(st.stage ?? i + 1) === String(sel));

  if (!stage) {
    // OVERVIEW. What the whole quest is: the one decision (difficulty), what
    // to pull off the shelf, what its cards look like, and the tips that are
    // not about any single stage. NO stage list - that is the left column's
    // job now, and three repeated blocks of it here is what this replaced.
    // No heading here: the app bar above names the subject, and a screen with
    // one subject gets one title. (The chooser's bar is newgame.js's; the
    // in-game reference brings its own - renderOverview below.)
    return h`<div class="ov-grid">
${raw(difficultySection(ov, entry, data, difficulty))}
${raw(setsSection(sets))}
${raw(tipsSection(ui, ov.slug, null))}
${raw(cardsSection(cardGroups(data, name), ui.imagePrefix))}</div>`;
  }

  // A STAGE. Its own printed text is the authority on what it does, so that
  // is what the view is built around - the card's words, not a paraphrase of
  // them (CLAUDE.md iron rule 4). Its tips sit beside it, and only its: a
  // stage's advice is only findable if it is not mixed in with every other
  // stage's.
  //
  // There are deliberately no per-stage DECK statistics. The encounter deck
  // is one deck for the whole game - it is not partitioned by stage - so any
  // "this stage's enemies" figure would be the scenario's figure wearing a
  // label that claims more than the data says. Deck-wide counts belong to the
  // overview.
  const n = stage.stage ?? sel;
  return h`<div class="ov-grid">
${raw(stageDetail(stage))}
${raw(tipsSection(ui, ov.slug, n))}</div>`;
}

// The whole-screen host: the read-only reference opened mid-game. The
// chooser's host is newgame.js, which embeds the same detail beside its
// list rather than replacing the screen with it.
export function renderOverview(game, ui) {
  const ov = ui.overview ?? {};
  const entry = ov.entry ?? {};
  const name = entry.name ?? ov.bundle?.scenario?.name ?? game?.scenario?.name ?? "";
  const stages = ov.bundle?.stages ?? [];
  // This host has no app bar - it is a reference screen opened over the game,
  // not a step in a flow - so the heading lives here rather than in a band.
  // It is the ONE title on this screen, same rule as the chooser's.
  const head = header(name, entry, entry.stageCount ?? stages.length);
  return h`<main class="pane overview">${raw(head)}${raw(renderScenarioDetail(game, ui))}${raw(footer())}</main>`;
}
