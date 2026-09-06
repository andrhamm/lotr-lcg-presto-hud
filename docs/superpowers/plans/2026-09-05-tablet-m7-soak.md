# Tablet milestone 7 — Soak — Checklist

> **For agentic workers:** this milestone is a human play session on the real iPad. Nothing here is executed by subagents; the checklist is what the session records, and the findings become TODO cards (Ideas column) or a fix plan.

**Goal:** One real game of *LOTR: The Card Game* tracked on the iPad Pro 12.9" with the tablet client, the way the Presto had one — measuring what the specs could only estimate.

**Spec:** `docs/superpowers/specs/2026-09-05-tablet-client-design.md` — "Risks and open questions" (opaque-response quota, the PDF URL), "Tap economy", "Persistence".

## Before the session (main session, not a worker)

- [ ] Merge the tablet branch into `main` and push (the user's call — Pages deploys from `main`; see `.github/workflows/pages.yml`, which builds the card data, the icon pack, and — when `tools/data/rules.SOURCE.txt` carries a `url=` — `docs/data/rules_text.json`).
- [ ] If the Rules Reference PDF is on hand, fill `sha256=` in `tools/data/rules.SOURCE.txt` and build the corpus + artifact locally (`rules/README.md`); without a `url=` the deployed site ships no `rules_text.json` and the Rules modal shows the summary and the rulebook link only.
- [ ] Open `https://andrhamm.com/lotr-lcg-presto-hud/tablet/` on the iPad in Safari, landscape; "Add to Home Screen" so the shell runs full-screen and the service worker's caches persist.
- [ ] Confirm in Safari's Develop menu (Mac tethered) that `lotr-tablet-shell-v1` and `lotr-tablet-images-v1` exist after "Begin setup".

## During the game — record these

| What | How | Spec's estimate to check |
|---|---|---|
| Tap latency | feel; if anything lags, note the tap and the round | RAM-only taps, background journal |
| The common round | count taps on a round with no enemies engaged | ≤ 20 |
| Skip landing | after the combat skip, is the view the last relevant window? | 6.P |
| Rail at 3–4 players with an eliminated player, a stage name and an active location | does the log block still show its prompt row? | never clipped (M4 fix) |
| The strip at 1366 with all ticks | any wrap that hides the playhead? | 96px, no overflow |
| Undo/rewind under play | rewind three taps in the Game Log, edit, confirm the greyed lines drop | M4 |
| Card images | do the picker thumbnails appear on first open (prefetch) and after airplane mode (cache)? | prefetch ~40 cards on Begin setup |
| **Opaque-response quota** | Safari → Settings → Websites data for the origin after the game; note MB used vs images cached | spec Risk: unmeasured; cap is 400 entries |
| Rules chips | tap three "Rules §n ›" chips mid-game — does the modal open in one tap and close in one? | M5 |
| Notes | Source link opens the article in Safari and the game survives coming back | M5 |
| Reload mid-game | pull down to reload at round 3: does the game resume at the same step with the same `Step n/N`? | journal round-trip |

## After the session

- [ ] Write the numbers into `docs/superpowers/specs/2026-09-05-tablet-client-design.md` "Risks" (quota measured → set `IMAGE_CACHE_MAX` accordingly in `docs/tablet/sw.js`).
- [ ] Every friction point becomes an Ideas card in `TODO.md` with the round it happened in.
- [ ] Anything that blocked play becomes a fix plan (`docs/superpowers/plans/`), executed the same way as milestones 1–6.
