// The Rules modal (Task 3, milestone 5): opened by a band's own "Rules §n ›"
// chip (primitives.js's band(), section-wired per view in pane.js) or the
// elimination sheet's own glossary chip (sheet_elim.js). ui.sheet carries
// EITHER a Rules Reference section id (`{kind:"rules", section:"6.2"}`) or a
// glossary term (`{kind:"rules", term:"Player Elimination"}`) - never both.
//
// Four blocks, in order: the official excerpt (verbatim - CLAUDE.md iron
// rule 4, "prefer the card's own printed text over a paraphrase" applies to
// rules text just as much as card text), this tracker's own one-line
// summary (reusing the exact copy the band it was opened from already
// shows - rules_map.js's SECTION_SUMMARY, never re-worded here), an FAQ
// block (always empty today - tools/build_rules_text.py's "faq": [] - kept
// so a future corpus pass has somewhere to land), and Related chips
// (STEP_ORDER prev/next plus the record's own see_also terms).
//
// ui.rules null, or missing the requested id/term entirely, DROPS the
// official excerpt entirely - never a placeholder rules claim, and never a
// heading over an apology for the missing text either. The Timing summary and the Related prev/next chips are both
// static lookups (SECTION_SUMMARY / STEP_ORDER) that don't read `rules` at
// all, so a build shipped without the rulebook artifact still shows this
// tracker's own summary and a way to keep browsing - only the verbatim
// official text is unavailable (Fix round 1: this used to read as "every
// block but the footer degrades", which was never what the code did).
import { h, raw } from "./dom.js";
import { CHROME, rulesPageUrl } from "./copy.js";
import { chip, cta } from "./primitives.js";
import { STEP_ORDER, SECTION_SUMMARY } from "./rules_map.js";

// The Timing block's text - the SAME string pane.js already bands next to
// this section's own chip, resolved once in rules_map.js's SECTION_SUMMARY
// (never duplicated/re-typed here) so the two can never drift apart. null
// for a section rules_map.js has no entry for (a view whose band lives in
// loops.js with no tracker copy of its own, or one only reached via a
// Related chip) - sheet_rules.js just omits the block rather than
// inventing a summary.
function summaryFor(id) {
  return SECTION_SUMMARY[id]?.text ?? null;
}

function relatedSectionChip(id, rules) {
  const rec = rules?.sections?.[id];
  const title = rec && rec.title ? rec.title : null;
  const label = title ? h`§${id} · ${title}` : h`§${id}`;
  return chip({ act: "open_rules", arg: id, label, tone: "tan" });
}

function relatedTermChip(term) {
  return chip({ act: "open_rules", arg: `term:${term}`, label: term, tone: "tan" });
}

export function renderRulesSheet(game, ui) {
  const { section, term } = ui.sheet;
  const rules = ui.rules;
  const rec = section ? (rules?.sections?.[section] ?? null) : (rules?.glossary?.[term] ?? null);

  // The eyebrow names the BOOK, the title names the section. It used to put
  // the section number in both - "RULES REFERENCE · §1.2" over a DISPLAY
  // reading "§1.2" - and then a third time in the summary's own attribution.
  const headerLine = section
    ? h`${CHROME.rulesReference}`
    : h`${CHROME.rulesReference} · ${CHROME.rulesGlossaryHeader}`;
  const title = section
    ? (rec?.title ? h`§${section} · ${rec.title}` : h`§${section}`)
    : (rec?.title ?? term);

  // No official text in this build: no block. It used to draw the heading
  // "Official text" over the sentence "The official text is not in this
  // build." - a heading for content that does not exist, and an apology for
  // it. What the sheet has to say instead is what it does have, which is the
  // block below (headed "This tracker's summary", so nothing can read as
  // official) and the link to the book in the footer.
  const officialBlock = rec
    ? h`<div class="label rules-section">${CHROME.rulesOfficialHeader}</div>
<div class="rules-body">${raw(rec.text.split("\n\n").map(p => h`<p class="body">${p}</p>`).join(""))}</div>`
    : "";

  const summaryText = section ? summaryFor(section) : null;
  // No attribution line under it: the block's own heading is the
  // attribution. It used to carry "Summarised by this tracker from Rules
  // Reference §1.2" as well - which said the same thing as the heading two
  // lines above, and repeated the section number the title already carries.
  const summaryBlock = summaryText
    ? h`<div class="label rules-section">${CHROME.rulesSummaryHeader}</div>
<p class="body">${summaryText}</p>`
    : "";

  // Entries are always [] today (tools/build_rules_text.py never populates
  // this yet) - String(entry) is a placeholder READER for whatever lands
  // here later, not invented content; nothing renders from it until a build
  // actually ships one.
  const faqBlock = rules?.faq?.length
    ? h`<div class="label rules-section">${CHROME.rulesFaqHeader}</div>${raw(rules.faq.map(entry => h`<p class="body">${String(entry)}</p>`).join(""))}`
    : "";

  const idx = section ? STEP_ORDER.indexOf(section) : -1;
  const prevId = idx > 0 ? STEP_ORDER[idx - 1] : null;
  const nextId = idx >= 0 && idx < STEP_ORDER.length - 1 ? STEP_ORDER[idx + 1] : null;
  const seeAlso = rec?.see_also ?? [];
  const relatedChips = [
    prevId ? relatedSectionChip(prevId, rules) : "",
    nextId ? relatedSectionChip(nextId, rules) : "",
    ...seeAlso.map(relatedTermChip),
  ].join("");
  const relatedBlock = (prevId || nextId || seeAlso.length)
    ? h`<div class="label rules-section">${CHROME.rulesRelatedHeader}</div><div class="rules-related">${raw(relatedChips)}</div>`
    : "";

  const pageUrl = rules?.source?.page || rulesPageUrl;
  const footer = h`<div class="cta-row">
<a class="cta cta-plain" href="${pageUrl}" target="_blank" rel="noopener">${CHROME.rulesOpenPdf}</a>
${raw(cta({ act: "sheet_close", label: CHROME.done }))}
</div>`;

  return h`<p class="label">${headerLine}</p>
<h1 class="display">${title}</h1>
${raw(officialBlock)}
${raw(summaryBlock)}
${raw(faqBlock)}
${raw(relatedBlock)}
${raw(footer)}`;
}
