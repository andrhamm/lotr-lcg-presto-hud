---
title: On-device soak protocol
type: design-note
tags:
  - lotr-lcg/design
  - beta
related:
  - "[[roadmap]]"
---

# On-device soak protocol (M5)

The last gate before beta. Everything in this repo is verified on the host —
721 host tests, a layout linter over every scene, and browser walkthroughs of
each flow — but **none of it has ever run on the Presto**. This document is the
procedure that closes that gap.

> [!warning] Not yet run
> No device has been attached during development, so this protocol is written
> but **unexecuted**. Nothing here should be read as "the firmware works on
> hardware"; it is the plan for finding out.

## Pre-flight (host, before touching the device)

All four must pass, in this order:

```bash
python3 -m pytest tests/ -q                 # host tests + layout linter
python3 tools/gen_web_data.py && git diff --exit-code docs/js/phases.js docs/js/icons.js docs/js/metrics.js
python3 tools/build_card_data.py            # catalog (network)
python3 tools/build_icons.py                # set icons (network, pinned)
```

The `gen_web_data.py` step must produce **no diff** — a diff means the
generated web mirrors drifted from `phases.py` / `ui/icons.py`.

## Deploy

Device deploys are **main-session only** (the serial port is single-user, and
the user may be mid-game). Stop any running tethered session first.

```bash
mpremote cp -r docs/data/ :/data/           # catalog + icons + tips (~4 MB)
mpremote cp main.py gamestate.py phases.py quest_catalog.py hardware.py :
mpremote cp -r ui/ :/ui/
```

Then relaunch and **check the output for tracebacks before declaring success**
(per `CLAUDE.md`) — run it in a background task and read the log, don't assume.

## The walkthrough (≥ 3 rounds, 2 players)

Exercise every surface added since the last device deploy:

1. **First run** — the intro should appear on a fresh install; page through all
   three pages, confirm the legend rows render (icons + tokens, not blanks),
   tap Start. Reopen it later via Settings → "How to read this HUD".
2. **New game** → Player Setup → Scenario Source → Official → Core Set →
   **Passage Through Mirkwood**.
3. **Scenario Options** — confirm the three encounter sets list *with icons*,
   switch Difficulty to Easy (tip appears), Mode to Nightmare (tip appears),
   back to Standard/Normal (no tip).
4. **Quest Setup (R0)** — stage 1A setup text renders in the scroll-style tip;
   "View quest card" opens the modal; page all three stages; stage 3 shows the
   branch alternatives; DONE returns. Then **Flip to Side B** → round 1 with
   8 quest points loaded.
5. **Round 1-3**, exercising: inline threat ± (tap left/right halves of a threat
   token), "Confirm all commits", staging ±, quest resolution **both** ways
   (a success and a deliberate failure), travel to a location, add a side quest
   via the picker, the guided resolution flow (push the location over its
   points and confirm it explores and carries the excess), and the Refresh
   projection line.
6. **Log** — open it, use all four scroll buttons, confirm timestamps.

## Power-cycle test

Mid-round, pull power. On reboot the saved game must resume with **identical**
values — photograph the screen before and after and compare field by field.

## Duration and instrumentation

- **≥ 45 minutes** continuous with the display active (a realistic session).
- Record **free RAM at start and end** (`gc.mem_free()`) to catch a slow leak.
  The catalog is read lazily per file, so RAM should be flat between rounds;
  a downward trend is a finding.

## Pass criteria

All must hold:

- [ ] Zero tracebacks in the device output for the whole session.
- [ ] No `MemoryError`, and free RAM at the end within ~10% of the start.
- [ ] State identical across the power cycle.
- [ ] Every screen renders without visual corruption (compare against
      `tools/preview.py` renders of the same scenes).
- [ ] Touch stays responsive at the end — no degradation versus minute one.
- [ ] The catalog loads from flash (icons and sets-to-gather appear); if
      `/data/` is missing the app degrades to the custom-quest path instead of
      crashing.

## What to record

Attach to this document when the soak is run: the device output log, a photo of
each key screen, the start/end RAM figures, and any traceback verbatim. **Any
traceback or leak becomes its own fix task before beta** — do not paper over an
intermittent one.

## Known risks to watch specifically

These are host-verified but hardware-unproven, and are the likeliest failure
points:

- **Flash footprint.** `docs/data/` is ~4 MB (catalog + 251 icons + tips).
  Confirm it fits alongside the firmware and that reads are fast enough not to
  stall the touch loop.
- **The 480×480 full redraw cost.** M2 added phase blocks and a meter; M3
  widened the players zone. Watch for sluggish view transitions.
- **`time.ticks_ms()` wrap** (~12.4 days) in the log's session clock — not a
  realistic session risk, but noted.
- **The RTC is usually unset**, so log timestamps fall back to elapsed time.
  That is expected, not a bug.
