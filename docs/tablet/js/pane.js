// The phase panes: one view -> one <main class="pane"> per the task-5
// brief's per-view table. Pure string builder like every other tablet
// render function - no document/window, so tests/test_tablet.py can drive
// it under node. Read docs/js/screen_play.js's draw() for how the twin
// assembles the same viewcopy.js keys per view; this mirrors that assembly,
// not the canvas layout.
import { h, raw, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta, counter, band } from "./primitives.js";
import { renderLoop } from "./loops.js";
import { sectionsFor } from "./rules_map.js";
import { notesFor } from "./notes.js";
import { frontFace } from "./cards.js";
import { phaseViewOf, HEADINGS } from "../../js/gamestate.js";
import {
  VIEW_LABELS, ACTION_WINDOW_TIPS, COMBAT_LAST_CHANCE, LOOP_FLOW, OUTCOME,
  PHASE_FRAMEWORK, PHASE_WINDOW, PROGRESS_PLACEMENT, QUEST_SETUP,
  SETUP_TIP, STAGING, TOTALS, TRAVEL,
} from "../../js/viewcopy.js";
import { icon } from "../../js/icons_svg.js";
import {
  THREAT_RED, THREAT_SHADOW, THREAT_BLACK, THREAT_BLACK_EDGE, WILLPOWER_GOLD,
} from "./palette.js";

// The staging window's "without actions" preview: what resolveQuest() WOULD
// do right now. gamestate.questPreview() owns the comparison; this only
// picks the copy.
function questPreviewLine(game) {
  const [outcome, n] = game.questPreview();
  if (outcome === "success") return OUTCOME.toast_success.replace("%d", String(n));
  if (outcome === "fail") return OUTCOME.toast_fail.replace("%d", String(n));
  return OUTCOME.toast_tie;
}

function renderWithoutActions(line) {
  return h`<div class="well"><div class="label">${CHROME.withoutActions}</div><p class="body">${line}</p><p class="body secondary">${PROGRESS_PLACEMENT}</p></div>`;
}

// R0 pre-round-1 phase: stage 1A's setup text to resolve, then the flip that
// begins round 1. A bare game (no scenario, as in the tests) has no
// `stages`, so the card is undefined, frontFace() returns null, and the
// "none" branch renders - same optional-chained lookup rail.js's
// renderStagePill already uses. Catalog cards are `{ faces: [...] }`, not
// `{ name, text }` at the top level, so frontFace(card) (cards.js) is what
// reads the actual A-side name/text - see cards.js for why that is
// positional (faces[0]) rather than a `side === "A"` match.
function renderQuestSetup(game) {
  const tips = SETUP_TIP.map(t => band({ kind: "framework", text: t })).join("");
  const stageN = `${game.quest.stage_n}${game.quest.side}`;
  const card = game.stages[game.stage_idx]?.cards?.[game.card_idx];
  const face = frontFace(card);
  const lead = face?.text
    ? QUEST_SETUP.resolve.replace("%s", stageN).replace("%s", face.name || "")
    : QUEST_SETUP.none.replace("%s", stageN);
  const instr = band({
    kind: "framework", text: lead,
    sub: QUEST_SETUP.then_flip.replace("%s", String(game.quest.stage_n)),
  });
  const well = face?.text ? h`<div class="well"><p class="body">${face.text}</p></div>` : "";
  return { parts: tips + instr + well, cta: cta({ act: "flip_to_b", label: QUEST_SETUP.begin }) };
}

// One allocator step: a live bevelled <button> when it can still do
// something, or - the twin's own convention for a stepper that cannot act
// (docs/js/screen_play.js ~766-780: "must not look like one... no bevel, dim
// glyph, and NOT registered as a target") - a dim, unbevelled <span> with no
// data-act so app.js's click delegation never sees it.
function allocStep(glyph, act, arg, live) {
  return live
    ? h`<button type="button" class="step step-sm" data-act="${act}" data-arg="${arg}">${glyph}</button>`
    : h`<span class="step step-sm step-off">${glyph}</span>`;
}

// One allocator row: label, "was + place / goal", and (unless locked, for an
// active location that fills by the cascade rather than its own stepper) a
// +/- pair targeting the arg allocKey() (actions.js) reads. `used`/`budget`
// gate liveness exactly as the twin's own rows do: "-" is live whenever
// anything is placed anywhere, "+" whenever the shared budget still has
// room - the same global check actions.js's cascade honors, not a per-row
// room check (a row's own cap can still swallow a live-looking tap, same as
// the twin - see docs/js/screen_play.js's "used > 0" / "used < budget").
function allocRow(label, was, add, pts, arg, used, budget) {
  // U+2212, not the "&minus;" entity - allocStep interpolates glyph through
  // h`` , which escapes the "&" a second time into literal "&amp;minus;"
  // text on screen (review finding 7). primitives.js/pane.js's other
  // steppers write "&minus;" straight into template text instead of through
  // an interpolation, which is why they are fine as-is.
  const minus = allocStep("−", "alloc-", arg, used > 0);
  const plus = allocStep("+", "alloc+", arg, used < budget);
  return h`<div class="alloc-row">
<span class="body alloc-label">${label}</span>
<div class="alloc-value">${raw(minus)}<span class="num num-34">${was} + ${add} / ${pts}</span>${raw(plus)}</div>
</div>`;
}

function allocRowLocked(label, was, add, pts) {
  return h`<div class="alloc-row alloc-row-locked">
<span class="body alloc-label">${label}</span>
<span class="num num-34">${was} + ${add} / ${pts}</span>
</div>`;
}

function renderAllocator(game, ui) {
  const a = ui.alloc;
  const used = a.locations.reduce((x, y) => x + y, 0) + a.quest
    + a.side_quests.reduce((x, y) => x + y, 0);
  const discard = game.pending_budget - used;
  const header = OUTCOME.alloc_header.replace("%d", String(game.pending_budget));
  const locRows = game.active_locations.map((loc, i) => allocRowLocked(
    loc.name ?? (i === 0 ? CHROME.location : `${CHROME.location} ${i + 1}`),
    loc.progress, a.locations[i] ?? 0, loc.points,
  )).join("");
  const questRow = allocRow(`${CHROME.quest} ${game.questLabel()}`, game.quest.progress, a.quest, game.quest.points, "quest", used, game.pending_budget);
  const sideRows = game.side_quests.map((sq, i) => allocRow(
    `${CHROME.sideQuestLabel} ${i + 1}`, sq.progress, a.side_quests[i] ?? 0, sq.points, `side:${i}`, used, game.pending_budget,
  )).join("");
  const unplaced = discard > 0
    ? h`<p class="body secondary">${OUTCOME.alloc_unplaced}: ${discard}</p>`
    : "";
  return h`<div class="alloc">
<p class="display">${header}</p>
<p class="body secondary">${OUTCOME.alloc_caption}</p>
${raw(locRows)}${raw(questRow)}${raw(sideRows)}
${raw(unplaced)}
${raw(chip({ act: "alloc_reset", label: CHROME.reset }))}
</div>`;
}

function renderEngagedCell(game, i) {
  const p = game.players[i];
  return h`<div class="eng-cell"><div class="label">P${i + 1}</div><div class="eng-row">
<button type="button" class="step step-sm" data-act="eng-" data-arg="${i}">&minus;</button>
<div class="eng-value">${raw(icon("THREAT", 34, THREAT_BLACK, THREAT_BLACK_EDGE))}<span class="num num-34">${p.engaged}</span></div>
<button type="button" class="step step-sm" data-act="eng+" data-arg="${i}">+</button>
</div></div>`;
}

function renderEncChecksSummary(game) {
  const engaged = game.engagedTotal();
  return h`<div class="well"><div class="label">${CHROME.checksMade}</div><p class="body">${fmt(CHROME.checksSummary, game.staging_enemies, engaged)}</p></div>`;
}

// The skip offer block: the claim always, an amber border when the tracker
// agrees (promoted), and - when it does not - a line naming the actual
// counts so the player can see why. The skip CTA itself is added by the
// common cta-row rule in renderPane, not here.
function renderSkipOffer(offer) {
  const claim = h`<p class="body">${offer.skip.claim}</p>`;
  const counts = !offer.promoted
    ? h`<p class="body secondary">${fmt(CHROME.trackerCounts, offer.engaged, offer.staging_enemies)}</p>`
    : "";
  const cls = offer.promoted ? "well well-amber" : "well";
  return h`<div class="${cls}">${raw(claim)}${raw(counts)}</div>`;
}

// The Notes panel (Task 4, milestone 5): notesFor()'s {scope, items,
// source} rendered verbatim - every line is tips.json's own text, so
// nothing here composes a new sentence about the game (iron rule 4). The
// pipe icon is the twin's own tips-modal glyph (icons_svg.js's ICONS.PIPE);
// gold, matching the panel's own gold left edge (style.css's .notes). The
// Source link is a real <a>, not an app act - it leaves the app, so it gets
// the same a.chip text-decoration override a.cta already needed (Task 3)
// for the identical reason.
function renderNotesPanel(notes) {
  const items = notes.items.map(t => h`<li class="body">${t}</li>`).join("");
  const name = notes.source?.name ?? "";
  const url = notes.source?.url ?? "";
  const sourceLink = h`<a class="chip chip-tan" href="${url}" target="_blank" rel="noopener">${CHROME.source} · ${name} ›</a>`;
  const more = chip({ act: "open_notes", label: h`${CHROME.moreNotes} ›` });
  return h`<aside class="notes"><div class="notes-head">${raw(icon("PIPE", 22, WILLPOWER_GOLD))}<span class="label">${CHROME.notes} · ${notes.scope}</span></div><ul>${raw(items)}</ul><div class="notes-foot">${raw(sourceLink)}${raw(more)}</div></aside>`;
}

// One view -> { parts, cta }. `cta` is null when the common Next/advance
// button applies (see renderPane); non-null replaces it, per the table's
// four views that name their own CTA (quest_setup, quest_staging,
// quest_resolution while allocating, round_end). Back and skip are always
// governed by the common rule (game.canGoBack() / game.skipOffer()) - never
// overridden here, even for those four.
function renderViewParts(view, game, ui) {
  switch (view) {
    case "quest_setup":
      return renderQuestSetup(game);

    case "resource": {
      const [begins, opens] = sectionsFor(view);
      return {
        parts: band({ kind: "framework", text: PHASE_FRAMEWORK.resource, section: begins })
          + band({ kind: "window", text: ACTION_WINDOW_TIPS.resource[0], section: opens }),
        cta: null,
      };
    }

    case "planning":
      return { parts: renderLoop(LOOP_FLOW.planning), cta: null };

    // Entered only with game.sailing on (gamestate.nextView: planning &&
    // sailing -> quest_sailing) - so there is no "no keyword" state to report
    // here; that copy belongs to the sail_toggle affordance the twin shows
    // from *planning* when sailing is off, not this view. Show the heading
    // (headingDesc()'s "term (facing)") as the DISPLAY line, then its degree
    // phrase from the same HEADINGS row in a plain .well underneath - not a
    // green "window" band (there is no action window here to point at) and
    // not the facing word again (headingDesc() already names it: "Off-course
    // (Cloudy)" followed by a well repeating "Cloudy" would just be noise).
    case "quest_sailing": {
      const [, , , degree] = HEADINGS[game.heading];
      // "Sailing test" opens the wheel-count sheet (Task 8, sheet_sailing.js
      // / acts_sailing.js) - a chip alongside the common Next CTA below
      // (cta: null), not a replacement for it, the same way Travel's own
      // chip sits beside Next rather than gating it: a table that finds no
      // wheels this round still has a plain way past this view.
      const testChip = chip({ act: "open_sailing", label: CHROME.sailingTest, tone: "tan" });
      return {
        parts: h`<p class="display">${game.headingDesc()}</p><div class="well"><p class="body">${degree}</p></div>` + testChip,
        cta: null,
      };
    }

    case "quest_commit":
      return {
        // No separate framework band here - the one window band IS the whole
        // view (committing characters), so it names 3.2 (the commit step
        // itself), not 3.1 (the phase's generic "begins" step).
        parts: band({ kind: "window", text: PHASE_WINDOW.quest_commit, sub: ACTION_WINDOW_TIPS.quest_commit.join(" "), section: sectionsFor(view)[1] })
          + counter({ label: TOTALS.willpower, icon: icon("WILLPOWER", 40, WILLPOWER_GOLD), value: game.willpower, act: "wp" }),
        cta: null,
      };

    case "quest_staging": {
      const line = questPreviewLine(game);
      const counters = h`<div class="two-col">${raw(counter({ label: TOTALS.willpower, icon: icon("WILLPOWER", 40, WILLPOWER_GOLD), value: game.willpower, act: "wp" }))}${raw(counter({ label: TOTALS.staging, icon: icon("THREAT", 40, THREAT_BLACK, THREAT_BLACK_EDGE), value: game.staging, act: "stg" }))}</div>`;
      // Staging has one Rules Reference section (3.3) for the whole reveal-
      // and-respond step, so both bands point at the same id.
      const [staging] = sectionsFor(view);
      const parts = band({ kind: "framework", text: STAGING.framework, section: staging })
        + band({ kind: "window", text: STAGING.window, sub: ACTION_WINDOW_TIPS.quest_staging.join(" "), section: staging })
        + counters + renderWithoutActions(line);
      // "Resolve Quest..." is the ONLY forward CTA here - it is what runs
      // resolveQuest() (the "resolve" act). advanceView() from quest_staging
      // hands straight to travel without resolving (gamestate.nextView's
      // "Resolution is entered only by a successful resolve" comment), so a
      // plain Next alongside it would silently skip the fail threat raise /
      // success progress placement. No fallback CTA.
      return { parts, cta: cta({ act: "resolve", label: h`${CHROME.resolveQuestCta}${line}` }) };
    }

    case "quest_resolution": {
      // ui.alloc is seeded by actions.js the moment "resolve" succeeds (and
      // reseeded by app.js on a resume caught mid-allocation) - this render
      // function only ever reads it, never creates it, so the pane stays
      // pure (finding 13).
      if (ui.alloc && !ui.placed) {
        return {
          parts: renderAllocator(game, ui),
          cta: cta({ act: "apply_alloc", label: CHROME.placeProgress }),
        };
      }
      // Compose exactly as the twin's _drawResolution does (screen_play.js):
      // fail is card_fail + fail_line2_pre + the red player-threat icon +
      // fail_line2_post (%d -> quest_outcome_n); tie is card_tie + tie_line2;
      // success names quest_outcome_n progress via toast_success. Always
      // "framework": this reports what resolveQuest() already did to the
      // table (threat raised, progress banked, or nothing), never a "window"
      // hint about something still open to act on.
      let text;
      if (game.quest_outcome === "fail") {
        text = [
          OUTCOME.card_fail, OUTCOME.fail_line2_pre,
          raw(`<span class="icon-inline">${icon("THREAT", 22, THREAT_RED, THREAT_SHADOW)}</span>`),
          OUTCOME.fail_line2_post.replace("%d", String(game.quest_outcome_n)),
        ];
      } else if (game.quest_outcome === "tie") {
        text = [OUTCOME.card_tie, OUTCOME.tie_line2];
      } else {
        text = OUTCOME.toast_success.replace("%d", String(game.quest_outcome_n));
      }
      const [resolved, ends] = sectionsFor(view);
      const parts = band({ kind: "framework", text, section: resolved })
        + band({ kind: "window", text: ACTION_WINDOW_TIPS.quest_resolution[0], section: ends });
      return { parts, cta: null };
    }

    case "travel": {
      const [begins, opportunity, ends] = sectionsFor(view);
      const blocked = game.active_locations.length > 0;
      const fw = blocked
        ? band({ kind: "framework", text: TRAVEL.blocked, section: begins })
        : band({ kind: "window", text: TRAVEL.open, section: opportunity });
      // Travel is optional (TRAVEL.open says so) - its own chip opens the
      // location picker (Task 5) alongside the bands rather than replacing
      // the pane's one shared forward CTA, so a table that chooses not to
      // travel still has a plain Next. arg encodes mode/idx/back for
      // actions.js's open_locpick (idx only matters for "change"; empty
      // reads as 0) - "new::play" when nothing is active yet, "change:0:
      // play" to replace the one seat the rail's own Location pill shows.
      const travelChip = blocked
        ? chip({ act: "open_locpick", arg: "change:0:play", label: TRAVEL.btn_replace, tone: "tan" })
        : chip({ act: "open_locpick", arg: "new::play", label: TRAVEL.btn_travel, tone: "tan" });
      return {
        parts: fw + band({ kind: "window", text: ACTION_WINDOW_TIPS.travel.join(" "), section: ends }) + travelChip,
        cta: null,
      };
    }

    case "enc_optional":
      return {
        // Single band, no separate "phase begins" band - it names 5.2
        // (Optional engagement) itself, not 5.1 (the generic phase start).
        parts: band({ kind: "window", text: PHASE_WINDOW.enc_optional, sub: ACTION_WINDOW_TIPS.enc_optional.join(" "), section: sectionsFor(view)[1] }),
        cta: null,
      };

    case "enc_checks": {
      const offer = game.skipOffer();
      const twoCol = h`<div class="two-col">${raw(renderEncChecksSummary(game))}${offer ? raw(renderSkipOffer(offer)) : ""}</div>`;
      // renderLoop()'s own framework/tip bands (loops.js) are out of this
      // task's scope - only the window band pane.js adds here gets a chip,
      // naming 5.4 (End of the Encounter phase - "last action window before
      // combat", ACTION_WINDOW_TIPS.enc_checks's own framing).
      const parts = renderLoop(LOOP_FLOW.enc_checks)
        + band({ kind: "window", text: ACTION_WINDOW_TIPS.enc_checks.join(" "), section: sectionsFor(view)[1] })
        + twoCol;
      return { parts, cta: null };
    }

    case "combat_shadow": {
      const [begins, deal] = sectionsFor(view);
      return {
        parts: band({ kind: "framework", text: PHASE_FRAMEWORK.combat_shadow, section: begins })
          + band({ kind: "window", text: PHASE_WINDOW.combat_shadow, section: deal }),
        cta: null,
      };
    }

    case "combat_enemy": {
      const cells = game.players.map((_, i) => renderEngagedCell(game, i)).join("");
      return { parts: renderLoop(LOOP_FLOW.combat_enemy) + h`<div class="eng-grid">${raw(cells)}</div>`, cta: null };
    }

    case "combat_player": {
      // renderLoop()'s own window band (loops.js) is out of this task's
      // scope - the tip band pane.js adds here names 6.11 (End of the Combat
      // phase), the closest numbered step to "lower threat now or refresh
      // may eliminate" - refresh, not combat, is where that threat raise and
      // elimination check actually happen.
      const secs = sectionsFor(view);
      return {
        parts: renderLoop(LOOP_FLOW.combat_player) + band({ kind: "tip", text: COMBAT_LAST_CHANCE, section: secs[secs.length - 1] }),
        cta: null,
      };
    }

    case "refresh": {
      const [begins, opens] = sectionsFor(view);
      return {
        parts: band({ kind: "framework", text: PHASE_FRAMEWORK.refresh, section: begins })
          + band({ kind: "window", text: PHASE_WINDOW.refresh, sub: ACTION_WINDOW_TIPS.refresh.join(" "), section: opens }),
        cta: null,
      };
    }

    case "round_end":
      return {
        parts: band({ kind: "framework", text: PHASE_FRAMEWORK.round_end, section: sectionsFor(view)[0] }),
        cta: cta({ act: "endround", label: h`${CHROME.nextPrefix}${VIEW_LABELS.resource} (Round ${game.round + 1})` }),
      };

    default:
      return { parts: "", cta: null };
  }
}

export function renderPane(game, ui) {
  // Under "bands" the tablet never stands on an aw_ view itself, but a
  // cross-client resumed save (the Presto/web twin use window policy
  // "views") can land here on one - render its phase view's pane, since on
  // the tablet the window is a band drawn on that view, not a screen of its
  // own.
  const view = phaseViewOf(game.view);
  const title = view === "round_end" ? `${CHROME.endOfRound}${game.round}` : (VIEW_LABELS[view] ?? view);
  const { parts, cta: customCta } = renderViewParts(view, game, ui);
  const notes = notesFor(ui.tips, ui.scenarioSlug, game.quest?.stage_n);
  const notesHtml = notes ? renderNotesPanel(notes) : "";

  const titleLine = h`${CHROME.round} ${game.round} · ${CHROME.step} ${game.step} · ${CHROME.firstPlayer} P${game.first_player + 1}`;

  const ctaButtons = [];
  // quest_setup's Back leaves the game (there is nothing behind it), so
  // gamestate.prevView() already returns null there and canGoBack() is
  // false - no separate view check needed.
  if (game.canGoBack()) {
    ctaButtons.push(cta({ act: "back", label: CHROME.back, tone: "plain", grow: false }));
  }
  const offer = game.skipOffer();
  if (offer) {
    ctaButtons.push(cta({
      act: "skip", arg: offer.skip.id, label: offer.skip.label,
      tone: offer.promoted ? "skip" : "plain", grow: true,
    }));
  }
  if (customCta) {
    ctaButtons.push(customCta);
  } else {
    const nxt = game.nextPhaseView();
    ctaButtons.push(cta({ act: "advance", label: nxt ? h`${CHROME.nextPrefix}${VIEW_LABELS[nxt]}` : CHROME.next }));
  }

  return h`<main class="pane">
<h1 class="display">${title}</h1>
<p class="label">${raw(titleLine)}</p>
${raw(parts)}
${raw(notesHtml)}
<div class="cta-row">${raw(ctaButtons.join(""))}</div>
</main>`;
}
