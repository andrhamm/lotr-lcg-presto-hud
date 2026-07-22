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

- [ ] (add ideas here)

## Ready

## In Progress

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
