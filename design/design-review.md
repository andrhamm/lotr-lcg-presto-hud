---
title: Design Review — findings & direction
type: design-note
tags:
  - lotr-lcg/design
  - prototype-to-beta
related:
  - "[[stat-system]]"
  - "[[roadmap]]"
  - "[[quest-index]]"
---

# Design Review — findings & direction

Living record of the prototype→beta design review so nothing is lost on
compaction. See also [[stat-system]] (concrete rules), [[roadmap]] (plan),
[[quest-index]] (quest data).

## The honest critique (starting point)
- The app is a **dashboard, not a companion** — every screen is the same
  template (header, numbered cards, tip, big button). No hierarchy; gold on
  everything so gold means nothing; the nav CTA borrows the green "confirm"
  colour; dead vertical space; heavy bevels read dated.
- **Click economy:** a normal 4-player round is ~30–40 taps, ~half wasted —
  ~7 do-nothing "Next Phase" taps through passive phases; the commit wizard is
  ~13 taps.
- No answer to the player's real question: **"when can I act?"**
- **Threat is shown as a flat number**, not as risk.
- Combat is untracked yet still costs 4 taps.

## The organizing insight (from the rulebook)
The manual's turn-sequence chart **colour-codes every step**:
- **RED = framework** — mandatory, automatic, no interrupts.
- **GREEN = action window** — any player may play responses/events/abilities.

That is the backbone every phase screen should adopt. Each phase = three zones:
**framework (red)** · **your window (green)** · **the one contextual stat**.

**Threat is the through-line** — the one number the app owns end to end; the
rules make it the engine of danger (it decides which enemies engage you, and it
eliminates you at 50). Show it as *risk*, not a readout.

## Per-phase content spec
| Phase | Framework (red) | Your window (green) | Contextual stat |
|---|---|---|---|
| Planning | — | play allies/attachments — ONLY now | your one window for permanents |
| Quest·Commit | — | commit characters | running willpower total |
| Quest·Staging | reveal 1 card/player | responses | willpower vs staging, live |
| Travel | travel to 1 location | responses | explore active first · travel cost |
| Encounter | enemies engage if cost ≤ threat | optionally engage 1 | your threat = who engages you |
| Combat | choose→defend→shadow→damage | responses each step | first-player-first · 1 hero if undefended |
| Refresh | ready · +1 threat all · pass token | responses | threat after +1 · elimination proximity |

Rules-faithful: keep every phase (knowing the phase matters for card timing);
make each *earn* its screen with tips + the relevant stat. Companion, **not a
replacement** — no heavy data entry beyond what exists without good reason.

## Quest-aware features (from the quest research)
Grounded in [[quest-index]] (Vision of the Palantir + rulebook):
1. **Quest picker preloads** stages + quest-points + **encounter sets to gather**
   (with icon-pack glyphs) — kills manual entry, biggest setup win.
2. **Conditional advancement** — advancing isn't always progress (combat /
   objective conditions). Stage-complete needs a "condition not met" path.
3. **Threat = engagement risk** — surface per-quest warnings (e.g. Hummerhorns
   engage at 40).
4. **Chase quests** carry a second (enemy) progress track.
5. **Quest appendix** — per-quest tips / FAQ / campaign-cards-needed, drawn from
   the rulebook, the blog and the forums into the vault.
6. **Sailing** validated (heading model correct); copy fix: cards are
   *discarded*, not just "looked at".

## Aesthetic direction — what was tried, rejected, decided
User chose a **rethemed overhaul**, but rejected several attempts. Record of the
journey so we don't repeat it:
- ❌ **Parchment + bitmap** (cream panels, oxblood) — "awful": muddy palette,
  boxy, the bitmap font read as a toy.
- ❌ **Three modern dark HTML directions** (Wayfarer / Illuminated / Signalfire)
  — "too modern, don't feel fantasy." **A (Wayfarer) and C (Signalfire) are
  off the table.** Also: HTML mocks with gradients/system fonts **don't render
  on the device** — mockups must be device-faithful (the real 480×480 pipeline).
- ❌ **Gilt-fantasy proto** (leather + ornament + big sunburst/helm) — "loses a
  lot of the good parts of the existing design."

> [!important] The decision
> **Evolve the existing design — do NOT replace it.** Keep its DNA (the current
> dark warm theme, chips, progress cards, bottom bars, tips, CTA). The changes
> are refinements layered on top.
> - **Dark theme** (played mid-game, close range, small 4" screen — not bright).
> - **Leverage the familiar game iconography** (threat helm, willpower sunburst,
>   trail/ranger, sphere marks, encounter-set icons) — the prototype already set
>   that as part of the spirit; keep and amplify it.
> - Mock everything **device-faithfully** (render through the app pipeline).

## Fast input (decided; no tap-and-hold — too finicky on a small device)
- **Inline threat −/+** on chips for micro-adjustments; tapping the value opens
  the full ±5 editor.
- **Set the party willpower total directly** (common case) — per-player commit
  stays available.
- **One-tap "all players +N"** for the many cards that hit everyone.

## Keep
- The **contextual quest/stage tip** (liked) — expand it.

## Process feedback (see memory: use-structured-questions)
- Ask multiple decisions via the **organized AskUserQuestion format**, not prose.
- **Don't ask about imperceptible differences** (the gold-vs-tan value shade was
  a waste — nearly identical; use judgment).
