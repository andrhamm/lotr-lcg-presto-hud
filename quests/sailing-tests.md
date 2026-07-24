---
title: Sailing Tests (mechanic)
cycle: Dream-chaser
product: The Grey Havens (deluxe) + Dream-chaser cycle
tags:
  - lotr-lcg/mechanic
  - dream-chaser
  - sailing
source: https://visionofthepalantir.com/2019/01/02/ships-and-sailing-tests/
---

# Sailing Tests

The Dream-chaser cycle's signature mechanic. Validates the HUD's heading/sailing
feature. See [[dream-chaser|Dream-chaser cycle]].

## Heading (4 positions, best → worst)
1. **Sunny** — on-course (best; can't rotate further toward good)
2. **Partially Cloudy** — off-course
3. **Rainy** — off-course
4. **Lightning Bolt** — fully off-course (worst)

Rotates **90° per round**. Players begin on-course.

## The Sailing test — timing + procedure
**When:** at the **beginning of the quest phase**, before committing to the quest.

1. Heading auto-rotates **90° clockwise = one step OFF-course**.
2. First player exhausts **any number of characters** to commit to the test.
   - The **Dream-chaser** ship may always commit and counts as **two** characters.
3. **Discard** that many encounter cards from the encounter deck.
4. Each **wheel/pennant symbol** revealed shifts the heading **one step back toward
   on-course** (counter-clockwise).
5. Recovering Lightning → Sunny needs **3 wheels**.

> [!check] Matches the HUD
> The HUD enters `quest_sailing` (step 3.1) before commit, auto-shifts +1
> off-course on entry, then the Sailing modal takes the wheels found and shifts
> back. HEADINGS = SUN / CLOUD / RAIN / STORM. All correct.

> [!warning] Copy fix for the HUD
> The sailing tip says characters "look at that many cards" — the cards are
> **discarded**. Reword to "…looks at and **discards** that many cards."

## On-course vs off-course
- **On-course (Sunny):** enemy ships are **weaker**, beneficial locations appear,
  and **many quest stages require on-course** to advance.
- **Off-course (Cloudy/Rainy):** encounter cards hit harder.
- **Lightning:** worst effects — e.g. **cannot cancel** encounter effects.

## Ships
**Ship-objectives (yours):** count as characters/allies, have **Sentinel**, can
**only attack ship-enemies**, **cannot defend** regular enemies, take no player
card effects. If destroyed the controller is defeated; **Dream-chaser destroyed =
whole fellowship eliminated**.

**Ship-enemies (Corsairs):** usually **Boarding X** (summon more corsairs), immune
to attachments, **only ship-objectives can defend** them; an **undefended** ship-enemy
attack redirects all damage to your ship (not a hero). Any character may counterattack.

> [!check] HUD ship-combat reminders are accurate
> "Only a ship can defend a ship-enemy; undefended ship attacks must damage a ship
> you control" — confirmed correct.

## Notes
First sailing quest: [[flight-of-the-stormcaller]]. This mechanic is why the HUD
has the HEADING progress card + Sailing modal.
