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

* Choose an appropriate license, fully open source but with care regarding the copyrighted IP
* Contributing.md and section on the README
* Action Window toasts should come up from the bottom, (over the next view's main CTA). Any auto-adjusted value changes (like threat or placed progress) should happen via animation _after_ the next view renders, so its clear what changed
* Game log data should be logged with full timestamp, log view should at least show the basic date and time with each entry. Logs should be latest at the bottom, like a terminal, need ability to scroll up and down and jump to oldest / latest (4 buttons on right side of screen where a scrollbar would normally be fou)

## Ready

## In Progress

- [ ] About page: settings tile + boot "disclaimers" link, credits + copyright disclaimer
  - notes: link to github.com/andrhamm/lotr-lcg-presto-hud; small black text link under New Game
	  - Clarifying: the disclaimer link leads to the About view, not the github repo. A "made with love by <github icon> @andrhamm" on the About view, links to the repo
  - claim: main-session 2026-07-22
- [ ] Crop boxart source to 480x480; purge unused assets; gitignore icon packs (keep local)
  - claim: main-session 2026-07-22
- [ ] Trim encounter reminders: drop "Discard shadow cards" + "Time counters"
  - notes: Time X = Lost Realm+ mechanic (counters removed each refresh); not in user's pool
  - claim: main-session 2026-07-22
- [ ] Dream-chaser Sailing support + stage-completion flow + game-end transition
  - notes: research sailing tests / heading on-off course; wheel + sunny/stormy icons from pack; stage-complete view (set points + stage); game over when final quest done or all eliminated
  - claim: main-session 2026-07-22

## Blocked

## Done

**Complete**

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
