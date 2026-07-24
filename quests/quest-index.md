---
title: Quest Index
type: MOC
aliases:
  - quests
  - Quest Index
tags:
  - lotr-lcg/moc
---

# Quest Index

Reference notes on LOTR LCG quests, captured to ground the [[../CLAUDE|Presto HUD]]
companion's quest-aware help. Source: [Vision of the Palantir](https://visionofthepalantir.com/).

## Design review
- [[design-review]] — critique, red/green framework model, aesthetic direction (what was rejected & decided)
- [[stat-system]] — stat colours / icons / layout rules + current implementation
- [[roadmap]] — prototype→beta milestones + artifact links
- [[stats-redesign]] — two-zone Players + Progress layout (M1 build spec)

## Cycles
- [[shadows-of-mirkwood]] — cycle 1 (Core Set + packs)
- [[dream-chaser]] — seafaring cycle ([[sailing-tests|Sailing]])

## Quests captured
| Quest | Cycle | Stages (qp) | Diff |
|---|---|---|---|
| [[passage-through-mirkwood]] | Mirkwood | 8 / 2 / 10 | 1 |
| [[journey-along-the-anduin]] | Mirkwood | 8 / 16 / 0 | ~5 |
| [[escape-from-dol-guldur]] | Mirkwood | 9 / 15 / 7 | ~7 |
| [[flight-of-the-stormcaller]] | Dream-chaser | 8 / 12 / 18 / 24 | ~6 |

## Mechanics
- [[sailing-tests]] — heading, wheels, ships (Dream-chaser)

## Why these matter to the HUD
1. **Quest picker → preload stages + quest points.** Fixed per quest; kills manual entry.
2. **Advancement conditions vary** (progress, combat, objectives) — stage-complete
   flow should allow "condition not yet met."
3. **Threat = engagement risk**; quest enemy engagement costs are the danger dial.
4. **Chase quests** carry a second (enemy) progress track.
5. **Sailing** validated — the HUD's heading model matches the rules.
