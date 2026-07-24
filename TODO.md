---
kanban-plugin: board
tags:
  - kanban
---

# Board

Drop ideas into **Ideas**. Anything in **Ready** is fair game for background
workers. Card protocol lives in [[CLAUDE]] — workers claim cards, move them
across columns, and surface blockers here.

## Ideas

* not in love with the placement or design of the tips... the stats redesign is much more compact than the initial design so the tips can be revamped to use the recovered space more effectively
* side quests modal for adding, not clear that we're setting the quest points.. and since the progress is readonly on this screen, its a bit confusing...
* Choose an appropriate license, fully open source but with care regarding the copyrighted IP
* Contributing.md and section on the README
* Action Window toasts should come up from the bottom, (over the next view's main CTA). Any auto-adjusted value changes (like threat or placed progress) should happen via animation _after_ the next view renders, so its clear what changed
* Game log data should be logged with full timestamp, log view should at least show the basic date and time with each entry. Logs should be latest at the bottom, like a terminal, need ability to scroll up and down and jump to oldest / latest (4 buttons on right side of screen where a scrollbar would normally be expected)
* Feasibility report: could we add audio by taking advantage of the Qwiic port and something like this (with a small speaker(s)) https://www.adafruit.com/product/6258
	* daisy chain qwiic to add haptic feedback driver?
* back button. all stat changes / events are recorded for the given phase. if you click the back button and make a change, the "final" values for that page are adjusted, the next page always bases stat changes relative to the final values from the previous phase. 
* action windows. interstitial screens for action windows. when you advance to the next phase, if there is an action window, you land on the action window view, which has a 3 second timer. when timer reaches 0, automatic movement to the next phase. "perform actions" button dismisses the timer. tip explains action window rules. allows adjusting players/progress zones, which get recorded as having been done in the action window. Next phase primary call to action button. this is a setting that can be disabled, which reverts to the action window toast reminder instead of the interstitial view.
* long term: campaign mode tracking, long term historical game results, stats, sharing
* feasibility report: how could a basic wireless camera be incorporated? low FPS / just occasional snapshots of the board state at the table. something easy to build with raspberry pi / xioa camera, battery just adequate for a single game session. 3d printed enclosure with 1/4-20 mount for gorillapod or similar. communicates with the presto / web app over wifi, images saved.
* RingsDB integration - specify which deck each player is using
* full Github actions CI with playwright integration tests for all UI/UX functionality. Automatic PR coverage report with screenshots of failing issues... at least one of my private GH projects implement this

## Ready

## In Progress

## Blocked

## Done

- [x] **Stats redesign** — two flipped compact zones (Players matrix + Progress zone), circular arc/token primitives, Players + Progress detail views, DONE header convention, staging inline ±, `commit_touched` + `quest_history`
  - notes: spec [[stats-redesign]], plan `design/stats-redesign-plan.md`; web-first + firmware lockstep; 378 host tests green; verified device-faithful via `tools/preview.py`
  - done: squash-merged to `main` locally (one commit)
  - follow-ups: push to remote (scheduled 5:30pm) → GitHub Pages deploy; deploy to Presto
- [x] Dream-chaser Sailing support + stage-completion flow + game-end transition
  - notes: heading on/off-course, wheel + weather glyphs, stage-complete + game-over screens; `SailingModal` is the sailing-test flow (reached from the quest_sailing view)
  - done: web 2e97817; firmware ported (parity work)
- [x] Trim encounter reminders to Archery + Battle/Siege
  - notes: dropped "Discard shadow cards" + "Time counters" (Lost Realm+ mechanic, not in pool)
  - done: web 5cb1608; firmware ported (parity work)
- [x] About page: settings tile + boot disclaimers link + "made with love @andrhamm" credits
  - done: web 5cb1608; firmware `ui/screen_about.py` (parity work)
- [x] Crop boxart source to 480x480; purge unused assets; gitignore icon packs (keep local)
  - done: d83b997
- [x] M1 firmware: guided round, threat/quest tracking, log, LEDs
  - done: shipped to device, 266 host tests
- [x] Web digital twin + GitHub Pages + README
  - done: https://andrhamm.com/lotr-lcg-presto-hud/

%%
Card format (one card = one deliverable):

- [ ] Short imperative title
  - notes: optional context, links, files
  - claim: <worker-id> <date>          (added when work starts)
  - blocked: <concrete reason>         (only while in Blocked)
  - done: <commit sha / URL>           (added when moved to Done)
%%
