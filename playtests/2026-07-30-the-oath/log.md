# The Oath - solo playtest log

Append-only. Generated from `log.jsonl`; do not hand-edit.


## Setup

**001** `setup` *init* - Seeded RNG with 1045977623. Player deck 50 cards, encounter pool 33 cards; both shuffled.

```json
{"player_deck": 50, "encounter_deck": 33, "starting_threat": 29, "heroes": ["Aragorn", "\u00c9owyn", "D\u00fanhere"]}
```

**002** `setup` *note* - Setup: New game, 1 player, threat 29 (Aragorn 12 + Eowyn 9 + Dunhere 8). Scenario picked via Official > Core Set (Mirkwood Paths) > 4. The Oath.

**003** `setup` *note* - UX/DATA: picker row 5 reads 'The Caves of Nibin-Dum'. docs/data/index.json holds BOTH 'The Caves of Nibin-Dum' (pack: Two-Player Limited Edition Starter) and 'The Caves of Nibin-Dum' with the correct u-circumflex (pack: Dark of Mirkwood). The dedupe picked the diacritic-stripped twin. Not a font limitation - the correct spelling is in the same index. Dark of Mirkwood rulebook spells it Nibin-dum with lowercase d and u-circumflex.

**004** `setup` *note* - UX/DATA: picker row 2 reads 'Journey Down the Anduin' (pack: Core Set). index.json also has 'Journey Along the Anduin' (pack: Revised Core Set) at the same cycle order 1. FFG's own books use both spellings (3x Down, 1x Along in research/rules/), so either is defensible - but the cycle is the Revised-Core-era Mirkwood Paths, so the Revised Core naming is the more consistent pick. Same class of duplicate-across-printings bug as Nibin-Dum. Also present upstream: 'Escape from Dol Goldur' (Revised Core Set row) is a typo for Guldur.

**005** `setup` *note* - UX BUG: Scenario Options subtitle renders 'Two-Player Limited Edition Starter - tap ..'. docs/js/screens_other.js:973 composes `${pack} - tap to change` and then truncateText()s the composite to 400px, so a long pack name consumes the line and the affordance verb is what gets amputated. The adjacent comment calls it 'an affordance a player reads, not chrome'. Violates CLAUDE.md 3b (running out of room is not a reason to degrade text). Fix: truncate the pack, keep the instruction whole - 'Two-Player Limited Ed... - tap to change' - or drop the instruction to its own line.

**006** `setup` *note* - DATA BUG (upstream DragnCards, surfaced verbatim by the UI): The Oath + The Goblins card text contains transcription errors the HUD renders as authoritative. Misspellings: 'Gret Spider' (Great Spider text), 'vitory display' (stage 2B), 'Goblintown Savengers' (Goblintown Scavengers text), 'discrad' (Wild Wargs), 'Shuffle of the encounter deck' (stage 1A). Backticks used as apostrophes and rendered as stray ticks on screen: 'Goblins` secret lair' (3B), 'player`s deck', 'Savengers`', and the whole Caught in a Web reminder wrapped in backticks. Also pre-Revised gendered wording ('his hand', 'with him', 'one of his heroes', 'he controls') that FFG degendered in the Revised Core Set printings. CLAUDE.md rule 4 says prefer the card's own printed text over a paraphrase - that policy is right, but it assumes the compiled text IS the printed text. Suggest a lint pass over docs/data card text (spellcheck + backtick-to-apostrophe) with a small committed errata-overlay, since docs/data is regenerated and cannot be hand-edited.

**007** `setup` *note* - NIT (debatable, not filing as a bug): the Quest Cards modal prints '9 pts' in the Stage 1A header. Quest points are printed on side B only; 1B itself correctly explains 'This side prints no game text. It carries the stage's quest points.' Reading the header as a stage-level summary ('stage 1 is worth 9') makes it defensible.

**008** `setup` *draw* - Setup step 5: draw starting hand of six.

```json
{"drawn": ["The Galadhrim's Greeting", "Gandalf", "The Galadhrim's Greeting", "Celebr\u00edan's Stone", "Celebr\u00edan's Stone", "Steward of Gondor"], "hand_size": 6, "deck_left": 44}
```

**009** `setup` *note* - Mulligan decision: KEEP. Hand = Steward of Gondor, Celebrian's Stone x2, The Galadhrim's Greeting x2, Gandalf. Downside: zero round-1 plays (all Leadership cards cost 2, Aragorn generates 1/round; Greeting costs 3 Spirit vs 2 available). Upside: Steward on Aragorn R2 is the deck's engine; Celebrian's Stone gives Aragorn a Spirit icon, bridging Leadership economy into the two Spirit heroes; 2x Greeting answers the true-solo failure mode of this quest (threat-out at 50 while grinding 27 total quest points across 3 stages). Plan: Dunhere is the scenario answer - he can target staging-area enemies when attacking alone at +1 attack (3 total), and this encounter set is built on unreachable engagement costs (Goblin Sniper 48, Goblin Troop 35, Great Spider 34).

**010** `setup` *search_encounter* - Setup step 7 (stage 1A, After the Raid): search encounter deck for 1 copy of The Eaves of Mirkwood, add to the staging area.

```json
{"found": "The Eaves of Mirkwood", "deck_left": 32}
```

**011** `setup` *search_encounter* - Setup step 7: search encounter deck for Goblin Troop, set aside out of play.

```json
{"found": "Goblin Troop", "deck_left": 31}
```

**012** `setup` *shuffle_encounter* - Setup step 7: shuffle the encounter deck after the searches.

**013** `setup-done` *patch* - Flip stage 1A to 1B. Quest points 9. Game ready to begin.


## Round 1

**014** `1.R` *patch* - Round 1 begins. Resource phase 1.2: add 1 resource to each hero's pool.

**015** `1.R` *draw* - Resource phase 1.3: each player draws 1 card.

```json
{"drawn": ["Guard of the Citadel"], "hand_size": 7, "deck_left": 43}
```

**016** `2.P` *patch* - Planning 2.P: no plays possible. Aragorn holds 1 Leadership (Steward/Stone/Guard all cost 2); Eowyn+Dunhere hold 1 Spirit each (Galadhrim's Greeting costs 3); Gandalf costs 5 vs 3 total. Deliberately NOT spending Aragorn's resource so Steward of Gondor lands round 2.

**017** `2.P` *note* - UX FINDING: 'Questing: Commit' shows '+3 reveal estimate'. gamestate.js:198 / gamestate.py:407 hardcode STAGING_HIGH_PER_PLAYER = 3, so the number is identical for every scenario ever played. For The Oath the true single-card high end is 4 (Spider Den), and three cards break the model entirely: Tangled Grove's threat is X = number of locations in staging; Driven by Shadow gives EVERY enemy and location in staging +1 threat until end of phase, so the spike is staging-wide not per-card; Goblins are Upon You! puts a Goblin into play engaged. The catalog already carries what is needed - docs/data has threatKind:'x' and threatX.target:'locations_in_staging' parsed out per card, and the Scenario Options screen already knows the exact encounter sets in play. A scenario-aware high end (max printed threat across the pool, with an 'X' marker when an X-threat or staging-wide modifier is live) would make this number actually informative. Right now it is a constant wearing the costume of a calculation - and the commit stepper next to it is the single decision this screen exists to support.

**018** `2.P` *note* - UX BUG (solo): after committing 6 willpower with the 'Questing for' stepper, the player pill in the header changes from '0' to '?'. Cause: setWillpower() marks willpower_detached = (total != sum of per-player commits) (gamestate.js:367, gamestate.py set_willpower), and screen_play.js:90 renders '?' when detached. The reasoning is sound for 2-4 players - a typed total genuinely loses the breakdown - but in a SOLO game the total IS that one player's commit, so there is nothing to be uncertain about. The app shows a question mark for a number the player just entered, in the one pill they would check to confirm it. Fix: when there is exactly one living player, have setWillpower write through to players[0].commit and leave detached false. Present in BOTH implementations, so the fix has to land in gamestate.js and gamestate.py to keep the twins in lockstep.

**019** `3.2` *patch* - Quest 3.2 commit: Aragorn (2 WP) + Eowyn (4 WP) committed and exhausted = 6 WP. Dunhere held ready deliberately - Spiders of Mirkwood gets +1 attack per exhausted character I control, so committing all three would hand it a 5-attack undefended swing that kills Eowyn (3hp) or Dunhere (4hp). Also NOT spending Aragorn's resource to ready him (his Response), because that resource is earmarked for Steward of Gondor next round.

**020** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card per player (1 player).

```json
{"revealed": ["Forest Gate"], "deck_left": 30}
```

**021** `3.2` *note* - PROCESS SLIP (mine, harmless here): revealed Forest Gate before passing the action window that precedes staging (RR 3.2 window -> 3.3 reveal). No decision was affected - I held 1 Leadership and 2 Spirit resources and the cheapest playable card was 2 Leadership - but knowing the reveal early is information the player should not have. Reveals happen after the window from here on.

**022** `3.2` *note* - UX AUDIT - CONTRAST: PASSES, retracting my earlier suspicion. Computed WCAG 2.x contrast for every pen in pal (docs/js/ui.js) against all 7 background roles. Every text colour clears 4.5:1 AA normal-text on bg/card/well: tan 10.09, gold 9.84, ok_fg 9.78, amber 8.58, muted 7.76, green 7.23, red 6.38, dim 6.33, no_fg 6.12, purple 5.75, slate 5.51 (all vs bg). Worst text case is dim/red on btn_ok at 4.38-4.41, a rounding error off AA and fine at the DISPLAY sizes used there. Only sub-3.0 entry is 'border' (1.62 on bg) which is a 1px rule, not text - WCAG does not apply to decorative separators. The tiny LABEL-scale metadata I flinched at (cycle release dates, TARGET/WAS/PLACE/GOAL headers) is a type-SIZE judgement call, not a contrast defect. Palette is well constructed.

**023** `3.4` *patch* - Quest 3.4 resolution: 6 willpower vs 4 staging threat = 2 progress. No active location, so all 2 go to the quest. Quest 1B now 2/9.

**024** `3.4` *note* - UX BUG (misleads at a decision point): the Travel location picker renders Tangled Grove with threat '0'. Its printed threat is X, where 'X is the number of locations in the staging area'. docs/data already carries this: threatKind:'x' and threatX:{target:'locations_in_staging', text:'the number of locations in the staging area'}. Rendering the absent numeric threat as 0 makes Tangled Grove read as the SAFEST location in the list, when it is the one that scales with the board - and it also charges 'each player must discard 1 random card from his hand to travel here', which the picker does not surface either. This is the second place the parsed threatX field is ignored (the other is stagingRevealEstimate). Suggested fix: render 'X' in the threat pill for threatKind=='x' and expose threatX.text on tap. Same root cause, one fix.

**025** `4.2` *patch* - Travel 4.2: travel to Forest Gate. It leaves the staging area and becomes the active location, so staging threat drops 4 -> 2 (only Eaves of Mirkwood remains). Chose Forest Gate over Eaves (2qp) because both shed the same 2 staging threat, but Forest Gate pays 'Response: After you travel to Forest Gate, the first player draws 2 cards' - and with zero allies on the board, cards are worth more than the 2 extra quest progress Eaves would have overflowed.

**026** `4.2` *draw* - Forest Gate travel Response: the first player draws 2 cards.

```json
{"drawn": ["A Test of Will", "Hasty Stroke"], "hand_size": 9, "deck_left": 41}
```

**027** `7.R` *patch* - Refresh 7.R: ready all characters, threat +1 (29 -> 30). Encounter and Combat were no-ops - the only card in staging was Eaves of Mirkwood (a location), so there was nothing to engage and nothing to attack.

**028** `7.R` *note* - LEDGER FORMAT CHANGE at seq 28: state_after now stores bulk zones (deck, hand, discard, encounter_deck, encounter_discard, set_aside, victory_display) as card-NAME lists instead of full card records. Full printed text is identical per copy and already lives in docs/data, so repeating it every action cost ~32KB/entry (864KB by seq 27, ~10MB projected for a full game). Zones with per-copy mutable state (staging, engaged, allies, active_location) are still stored whole. Entries 1-27 are untouched - the log stays append-only, nothing was rewritten.


## Round 2

**029** `1.R` *patch* - Round 2 resource phase 1.2: +1 resource to each hero.

**030** `1.R` *draw* - Resource 1.3: draw 1 card.

```json
{"drawn": ["Longbeard Orc Slayer"], "hand_size": 10, "deck_left": 40}
```

**031** `2.P` *patch* - Planning 2.P: (1) play Steward of Gondor on Aragorn for 2 Leadership - Aragorn 2->0. (2) immediately exhaust Steward for its Action, +2 to Aragorn's pool - 0->2. (3) play Celebrian's Stone on Aragorn for 2 - 2->0. Aragorn is now 4 willpower and, crucially, has a Spirit resource icon, so Steward's 2/round can pay for the deck's whole Spirit half (Galadhrim's Greeting, A Test of Will, Hasty Stroke, Northern Tracker, Unexpected Courage, Stand and Fight). Chose the Stone over Guard of the Citadel: +2 permanent willpower and a second sphere beats a 1-willpower 2hp body while there are zero enemies on the board. Cost: Aragorn has 0 resources, so he cannot use his own ready-after-questing Response this round.

**032** `2.P` *patch* - CORRECTION (harness bug, not a play): the patch at seq 31 used remove-by-name, which deleted BOTH copies of Celebrian's Stone from hand when only one was played. Restoring the second copy. Hand goes 7 -> 8. engine.py's remove op now pops a single index instead of filtering on title; see the comment there. Nothing rewritten - seq 31 stands as logged and this entry corrects it.

**033** `3.2` *patch* - Quest 3.2 commit: Aragorn (2 base + 2 from Celebrian's Stone = 4 WP) + Eowyn (4 WP) = 8 committed. Dunhere held ready again - his 1 willpower is negligible and he is the only answer to this set's unreachable-engagement enemies (Goblin Sniper 48, Goblin Troop 35, Great Spider 34) via his attack-alone-into-staging ability.

**034** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 2). Holding A Test of Will (1 Spirit) and Hasty Stroke (1 Spirit) for a When Revealed / shadow worth cancelling - Eowyn and Dunhere have 2 Spirit each.

```json
{"revealed": ["Goblintown Scavengers"], "deck_left": 29}
```

**035** `3.2` *mill* - Goblintown Scavengers When Revealed: discard the top card of each player's deck; its printed cost is added to Scavengers' threat until end of phase. Declined to cancel with A Test of Will - a one-phase threat bump plus a single mill is not worth the deck's only answer to Goblins are Upon You! (uncancellable anyway) and Eyes in the Dark.

```json
{"discarded": [{"name": "Northern Tracker", "cost": "4"}], "deck_left": 39}
```

**036** `3.4` *patch* - Quest 3.4: 8 willpower vs 7 staging (Eaves 2 + Scavengers 1+4) = 1 progress, placed on the active location. Forest Gate 1/4, quest still 2/9. Scavengers' threat reverts to 1 at end of phase.

**037** `5.3` *patch* - Encounter 5.3 engagement checks: Goblintown Scavengers engagement cost 12 <= threat 30, so it engages. Staging drops to Eaves of Mirkwood only (2 threat). Declined to play The Galadhrim's Greeting in the encounter action window - 30->24 still clears Scavengers' cost of 12, so the 6 threat buys nothing here and is worth more later near the 50 elimination line.

**038** `5.3` *reveal* - Combat 6.2: deal 1 shadow card to Goblintown Scavengers (only engaged enemy). Plan: take the attack UNDEFENDED, assigning 1 damage to Aragorn (5hp), keeping Dunhere ready to attack for 2. RR 6.4.3 requires undefended damage go to a single hero and defence does not absorb it. Defending with Dunhere takes 0 damage but leaves Scavengers at full 3hp; this line puts it on 1hp so Dunhere finishes it next round.

```json
{"revealed": ["Spiders of Mirkwood"], "deck_left": 28}
```

**039** `6.6` *patch* - Combat 6.4: shadow card revealed = Spiders of Mirkwood, which prints no Shadow effect, so the attack is unmodified. Scavengers attacks undefended for 1; damage assigned to Aragorn (5hp -> 4). Shadow card to the encounter discard. Combat 6.6: Dunhere attacks Scavengers - no staging-attack bonus because Scavengers is engaged, not in staging - 2 attack vs 0 defence = 2 damage. Scavengers 3hp -> 1hp, survives. Dunhere exhausts.

**040** `7.R` *patch* - Refresh 7.R: ready all characters, threat 30 -> 31.

**041** `7.R` *note* - UX FINDING (strongest of the session): the Game Log records keystrokes, not decisions. Measured from the app's own saved state after 2 rounds: 73 entries total - 24 'Phase: X', 14 'Action window: X', and of the 35 remaining 'substantive' ones, 21 are stepper-tick spam. Committing 8 willpower writes EIGHT lines ('Players committed 1 willpower', '...2 willpower', ... '...8 willpower'); setting staging to 7 wrote five ('Staging threat 2 -> 3', '3 -> 4', ... '6 -> 7'). Every single tap of a + stepper is its own log row. Game-meaningful entries across two entire rounds: about 11 of 73, roughly 15 percent. Extrapolated to a 15-round game that is ~550 rows hiding ~80 facts, across ~40 pages of the 7-per-page log view. This is the README's marquee feature ('keeps a timestamped log of the whole game') and it is ~85 percent noise - 'when did Goblin Trail first appear?' is unanswerable by scrolling. Fix has an obvious hook: setWillpower/setStaging already exist as setters specifically so changes reach the log (their own comments say so), so coalesce there - write the SETTLED value on view advance or after an idle beat, not every increment. Secondary: 'Action window: Encounter Opt. Engage' and 'Phase: Encounter Opt. Engage' are logged as two rows for one step; and phase transitions in general belong behind a verbose toggle in Settings, since they are identical every round and carry no game state. Genuinely good, keep it: the per-round summary line 'Round 1 ended: 22m43s, P1 +1, quest +2'.


## Round 3

**042** `1.R` *patch* - Round 3 resource 1.2: +1 to each hero. Aragorn also exhausts Steward of Gondor for +2, so 1+2 = 3 Leadership (and Spirit-payable via Celebrian's Stone). Eowyn 3 Spirit, Dunhere 3 Spirit. 9 resources total.

**043** `1.R` *draw* - Resource 1.3: draw 1.

```json
{"drawn": ["Celebr\u00edan's Stone"], "hand_size": 9, "deck_left": 38}
```

**044** `2.P` *patch* - Planning 2.P: play Gandalf for 5, paid Eowyn 3 + Dunhere 2 - deliberately NOT from Aragorn, so his 3 Leadership stays free for a second play. Gandalf is 4/4/4/4 and is discarded at end of round.

**045** `2.P` *draw* - Gandalf Response (choose 1): draw 3 cards. Chose draw over 'reduce threat by 5' (I hold 2x Galadhrim's Greeting for threat, -12 available) and over 'deal 4 damage to 1 enemy' (only enemy in play is Goblintown Scavengers on 1hp, which Dunhere kills for free). Board development is the binding constraint - zero allies after 2 rounds.

```json
{"drawn": ["Sneak Attack", "Stand and Fight", "Guard of the Citadel"], "hand_size": 11, "deck_left": 35}
```

**046** `2.P` *patch* - Planning 2.P cont: play Celebrian's Stone on EOWYN for 2 of Aragorn's 3 Leadership. Eowyn 4 -> 6 willpower. Chose this over Guard of the Citadel (1 WP body) because +2 permanent willpower on the main quester compounds, and over Sneak Attack + Guard because Sneak Attack is worth far more held for a future Gandalf (1 resource for draw-3 / 4 damage / -5 threat). Aragorn keeps 1 Leadership, which funds his own Response: after committing to the quest, spend 1 resource to ready him - so he quests for 4 AND stays available to defend.

**047** `3.2` *patch* - Quest 3.2: commit Aragorn (4 WP), Eowyn (6 WP with Stone), Gandalf (4 WP) = 14 willpower. Aragorn Response: spend his last resource to ready him - he stays COMMITTED (his willpower still counts) but is untapped for combat. Dunhere held ready to finish Goblintown Scavengers (1hp left).

**048** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 3).

```json
{"revealed": ["Goblin Trail"], "deck_left": 27}
```

**049** `3.4` *patch* - Quest 3.4: 14 willpower vs 5 staging (Eaves 2 + Goblin Trail 3) = 9 progress. Forest Gate 1/4 +3 = explored and leaves play; overflow 6 to the quest. Stage 1B now 8/9 - one progress from advancing. Goblin Trail added to staging: it is MANDATORY for this scenario (stage 2B cannot be defeated unless a copy is in the victory display) and exploring it is progress-neutral (6 in, 6 straight back out onto the current quest) so the plan is to take it DURING stage 2, not now.

**050** `4.2` *patch* - Travel 4.2: travel to The Eaves of Mirkwood (2qp). Staging 5 -> 3 (Goblin Trail only). Accepted cost: Eaves reads 'While The Eaves of Mirkwood is the active location, encounter card effects cannot be canceled', so A Test of Will and Hasty Stroke are dead for one round. Took it because Eaves is only 2 quest points, clears next round, and permanently sheds 2 staging threat before the 12-point stage 2 grind. Risk is the 2 copies of Eyes in the Dark in ~27 cards.

**051** `4.2` *reveal* - Combat 6.2: deal 1 shadow card to Goblintown Scavengers (only engaged enemy).

```json
{"revealed": ["Goblin Runners"], "deck_left": 26}
```

**052** `6.6` *patch* - Combat: shadow card = Goblin Runners, no Shadow effect printed. 6.4 Aragorn defends Goblintown Scavengers - 2 defence vs 1 attack = 0 damage - and exhausts. 6.6 Dunhere attacks Scavengers, 2 attack vs 0 defence = 2 damage, total 4 on a 3hp enemy: DESTROYED, to the encounter discard. Board clear of enemies.


## Round 4

**053** `1.R` *patch* - Refresh 7.R: ready all, threat 31 -> 32. End of round: Gandalf discarded from play per his own text. Round 4 resource 1.2: Aragorn 1 + Steward exhaust 2 = 3 Leadership; Eowyn 1 Spirit; Dunhere 1 + 1 carried = 2 Spirit.

**054** `1.R` *draw* - Resource 1.3: draw 1.

```json
{"drawn": ["Sneak Attack"], "hand_size": 11, "deck_left": 34}
```

**055** `2.P` *patch* - Planning 2.P: play Guard of the Citadel for 2 of Aragorn's 3 Leadership (1/1/0/2). Held both Sneak Attacks for a future Gandalf - 2 Gandalfs and 2 Sneak Attacks remain in the deck and that combo is 1 resource for draw-3 / 4 damage / -5 threat. Aragorn keeps 1 Leadership for his ready Response.

**056** `3.2` *patch* - Quest 3.2: commit Aragorn (4) + Eowyn (6) = 10 willpower. Aragorn spends his last resource on his Response to ready. Dunhere AND Guard of the Citadel both held ready as defenders - 10 is already enough to clear Eaves (2) and put the 1 needed on the quest even against a 4-threat reveal.

**057** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 4). Note: cancels are OFF - The Eaves of Mirkwood is the active location.

```json
{"revealed": ["Goblin Runners"], "deck_left": 25}
```

**058** `3.2` *reveal* - Surge on Goblin Runners: reveal an additional encounter card. (Surge is a keyword, not a When Revealed, so A Test of Will could not have stopped it even if Eaves were not suppressing cancels.)

```json
{"revealed": ["Abandoned Camp"], "deck_left": 24}
```

**059** `3.4` *patch* - Quest 3.4: 10 willpower vs 6 staging = 4 progress. Eaves of Mirkwood 0/2 +2 = EXPLORED and leaves play (cancels come back on). Overflow 1 to the quest = 9/9 -> STAGE 1 DEFEATED. The 4th point of progress is discarded, not carried - RR p.22, and the HUD surfaces it as 'Unplaced (discarded) 1' in red, which is a nice touch. Staging: Goblin Trail 3 + Goblin Runners 1 + Abandoned Camp 2.

**060** `3.4` *note* - UX BUG - HIGHEST SEVERITY OF THE SESSION. Advancing to stage 2 (Mirkwood Forest), the STAGE ADVANCE - RESOLVE NOW panel printed 'No setup instructions for this stage.' That is wrong. The Oath stage 2 carries: 'When Revealed: Each player searches the encounter deck and discard pile for a Forest location and adds it to the staging area. Shuffle the encounter deck. This stage cannot be defeated unless at least 1 copy of Goblin Trail is in the victory display.' A player trusting the HUD skips a mandatory staging addition AND never learns the stage's gating condition - they would grind 12 progress onto stage 2 and be unable to advance with no explanation on screen. CAUSE: docs/js/screens.js:1705, 'const raw = st.face_a.text;' - the panel reads side A only. The Oath's stage 2 text lives on the B face in the compiled data. MEASURED BLAST RADIUS across docs/data: 75 of 514 quest stage cards in 154 scenarios have text on side B and nothing on side A, so all 75 print 'No setup instructions for this stage'. Examples, all mandatory board changes: Flies and Spiders stage 2 ('Reveal stage 3 and create a separate staging area'), Conflict at the Carrock stage 2 ('Place the unique Troll cards previously set aside into the staging area'), Flight to the Ford stage 2 ('Add Ford of Bruinen and The Witch-king to the staging area'), A Shadow of the Past stage 2 ('search the encounter deck and discard pile for a Black Rider'), Escape from Dol Guldur stages 2 and 3. SECOND DEFECT, same function: maxLines = 5 with lines.slice(0, maxLines) and no overflow affordance - 147 of 514 stages have side-A text over 260 chars, up to 630 (The Brandywine Pursuit stage 3), so that text is silently cut. Violates CLAUDE.md 3b, which names the [...] more affordance the quest card modal already implements correctly. FIX: concatenate both faces' text for the resolve-now panel (or prefer A, fall back to B), and page/scroll rather than slice. Both twins - screens.js and the ui/ Python equivalent.

**061** `3.4` *patch* - Stage 2 (Mirkwood Forest, 12qp) revealed and flipped to 2B. Resolving its When Revealed MANUALLY because the HUD said there was none: 'Each player searches the encounter deck and discard pile for a Forest location and adds it to the staging area. Shuffle the encounter deck.' Chose The Eaves of Mirkwood from the encounter discard - joint-lowest threat (2) of every Forest location available and the cheapest to clear at only 2 quest points. Rejected Forest Gate (2 threat but 4qp), Tangled Grove (threat X = locations in staging, which would be 3), Spider Den (4 threat), and a second Goblin Trail (3 threat, redundant - one is already in staging). Staging is now Goblin Trail 3 + Abandoned Camp 2 + Eaves 2 + Goblin Runners 1 = 8.

**062** `3.4` *shuffle_encounter* - Stage 2B When Revealed: shuffle the encounter deck after the search.

**063** `4.2` *patch* - Travel 4.2: travel to Goblin Trail (0/6). Chose it over Eaves (2qp) and Abandoned Camp (3qp) because it is the largest single staging threat (3), it is MANDATORY for stage 2's gate, and exploring it is progress-neutral - 6 in, 6 refunded onto the current quest - so the only real cost is tempo. True staging drops 8 -> 5 (Eaves 2 + Abandoned Camp 2 + Goblin Runners 1). NOTE: the HUD's staging counter reads 3, not 5, because I could not enter the +2 for the Eaves that stage 2B's When Revealed added - the staging stepper only exists on the two questing screens, and 2B resolved during the travel/resolution window. Correcting it on next round's commit screen.

**064** `4.2` *reveal* - Goblin Trail Travel cost: reveal the top card of the encounter deck to travel here.

```json
{"revealed": ["Goblin Sniper"], "deck_left": 23}
```

**065** `5.3` *patch* - Goblin Trail travel reveal = Goblin Sniper to staging (48 engagement, so it will never engage me; 'Forced: If Goblin Sniper is in the staging area at the end of the combat phase, each player deals 1 point of damage to 1 character he controls' - a recurring tax). Encounter 5.3: Goblin Runners engages (20 <= 32). Staging = Eaves 2 + Abandoned Camp 2 + Goblin Sniper 2 = 6.

**066** `5.3` *reveal* - Combat 6.2: deal 1 shadow card to Goblin Runners (the only ENGAGED enemy - Goblin Sniper is in staging and gets none).

```json
{"revealed": ["Spider Den"], "deck_left": 22}
```

**067** `6.6` *patch* - Combat: shadow = Spider Den, no Shadow effect. 6.4 Goblin Runners attacks; CHUMP-DEFEND with Guard of the Citadel (0 defence, 2hp) - takes 3, destroyed. Deliberate: defending with Aragorn would cost only 1 damage but exhausts him, and then Dunhere has to help kill Runners, which breaks his 'attacks alone' condition and leaves Goblin Sniper alive as a permanent 2 staging threat plus 1 damage every combat phase. Spending a 2-cost ally to clear the whole board is the better trade. 6.6 Aragorn attacks Goblin Runners: 3 vs 1 defence = 2 damage, DESTROYED. Dunhere attacks ALONE into the staging area against Goblin Sniper: 2+1 = 3 vs 0 defence = 3 damage, DESTROYED - so its end-of-combat-phase Forced damage never triggers. Board clear of enemies. Staging = Eaves 2 + Abandoned Camp 2 = 4.


## Round 5

**068** `1.R` *patch* - Refresh 7.R: ready all, threat 32 -> 33. Round 5 resource: Aragorn 1 + Steward 2 = 3 Leadership, Eowyn 2 Spirit, Dunhere 3 Spirit.

**069** `1.R` *draw* - Resource 1.3: draw 1.

```json
{"drawn": ["Dwarven Tomb"], "hand_size": 11, "deck_left": 33}
```

**070** `2.P` *patch* - Planning 2.P: play Guard of the Citadel for 2 (Aragorn keeps 1 Leadership for his ready Response). Commit Aragorn 4 + Eowyn 6 + Guard 1 = 11 willpower, then ready Aragorn. Dunhere held. This leaves TWO defenders (Aragorn 2 def / 4hp, Dunhere 1 def / 4hp) which specifically covers the worst reveal left in the deck: Spiders of Mirkwood gets +1 attack per exhausted character I control, so with 3 committed it swings for 5 - Aragorn defends and survives on 1hp; nobody ready and it kills a hero outright. Deck census: of 33 cards, only Goblintown Scavengers (12), Spiders of Mirkwood (18) and Wild Wargs (28) can engage at threat 33; Great Spider x2 (34) and Goblin Sniper (48) cannot.

**071** `3.2` *patch* - Quest 3.2: 11 willpower committed; Aragorn readied with his last resource.

**072** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 5).

```json
{"revealed": ["Eyes in the Dark"], "deck_left": 21}
```

**073** `3.2` *patch* - Quest 3.3 reveal = Eyes in the Dark (Doomed 1; When Revealed: each player chooses - raise threat by 1 per questing character, or discard a questing character). Played A TEST OF WILL for 1 Spirit from Eowyn to cancel the When Revealed. I had 3 questing characters, so the choice was +3 threat or losing Guard of the Citadel. Doomed 1 STILL resolves - RR line 361, 'Doomed X is a keyword ability', which is not a When Revealed effect (the app's own setup tip agrees: 'Keywords on setup reveals (Surge/Doomed) do resolve'). Net threat 33 -> 34 instead of 37. Treachery goes to the encounter discard and contributes no staging threat, so staging stays 4.

**074** `3.2` *note* - UX BUG - DATA LOSS, and it upgrades the earlier '?' finding from cosmetic to severe. Reproduction, exactly as played: during the quest phase (step 3.3) with 11 willpower committed via the 'Questing for' stepper, I tapped the player pill to raise threat by 1 for Eyes in the Dark's Doomed keyword, pressed +, pressed DONE. Observed: threat 33 -> 34 correctly, and committed willpower 11 -> 0, silently. MECHANISM: the commit steppers call setWillpower(), which sets the TOTAL and flags willpower_detached because it never writes through to players[0].commit (gamestate.js:367). The Players modal edits per-player values and on close recomputes the total from those per-player commits - which are still 0. So the detached total is destroyed. This is not a corner case: Doomed, Caught in a Web, quest-failure threat and every threat-raising treachery all push a player to open that modal MID-QUEST-PHASE, which is exactly when a willpower total is live. The player then advances to resolution and the app computes progress from 0 willpower. In a solo game there is no reason for the two to ever diverge. FIX (same one as the '?' finding): when there is exactly one living player, setWillpower writes through to players[0].commit and leaves detached false. For multiplayer, the Players modal must not clobber a detached total on close. Both twins.

**075** `3.3` *patch* - Re-entering the 11 willpower the HUD dropped.

**076** `3.3` *note* - UX NIT: the Questing: Resolution screen's +/- steppers only redistribute the progress earned from willpower; they clamp at that total. Correct as a distribution UI, but it means card effects that PLACE progress outside the quest maths have no home here - Goblin Trail's 'When Goblin Trail leaves play as an explored location, place 6 progress on the current quest', Snowbourn Scout's entry Response, Northern Tracker's commit Response. The + sits there fully drawn and does nothing when the allocation is exhausted (a dead affordance), and nothing points to the Progress modal, which is where those adjustments actually belong. Suggest either disabling/dimming the stepper at the cap, or a one-line 'card effect? adjust in Progress' link.

**077** `3.4` *patch* - Quest 3.4: 11 willpower vs 4 staging = 7 progress. Goblin Trail 0/6 +6 = EXPLORED. Overflow 1 to quest 2B. Goblin Trail leaves play as an explored location: (a) its Response places 6 MORE progress on the current quest, and (b) it carries Victory 3 so it goes to the VICTORY DISPLAY - which satisfies stage 2B's gate, 'This stage cannot be defeated unless at least 1 copy of Goblin Trail is in the victory display'. Quest 2B = 0 + 1 + 6 = 7/12. Staging = Abandoned Camp 2 + Eaves 2 = 4.

**078** `4.2` *patch* - Travel 4.2: travel to The Eaves of Mirkwood (0/2). Staging 4 -> 2 (Abandoned Camp only). Its cancel-suppression clause costs nothing this round - A Test of Will was just spent and only Hasty Stroke remains in hand. No enemies in play, so Encounter and Combat are empty.


## Round 6

**079** `2.P` *patch* - Refresh: ready all, threat 34 -> 35. Round 6 resource: Aragorn 3 Leadership (1 + Steward 2), Eowyn 2 Spirit, Dunhere 4 Spirit. Planning: Celebrian's Stone on DUNHERE for 2 Leadership - he goes 1 -> 3 willpower - leaving Aragorn 1 for his ready Response. Commit all three: Aragorn 4 + Eowyn 6 + Dunhere 3 = 13, then ready Aragorn so there is still a 2-defence body. 13 beats staging 2 + any single reveal in the deck (max printed threat is Spider Den at 4), so Eaves (2qp) explores and at least 5 reaches quest 2B at 7/12 = stage 2 done this round.

**080** `2.P` *draw* - Resource 1.3: draw 1.

```json
{"drawn": ["A Test of Will"], "hand_size": 9, "deck_left": 32}
```

**081** `3.2` *patch* - Quest 3.2: 13 willpower committed, Aragorn readied with his last resource. Drew a second A Test of Will but it is DEAD this round - The Eaves of Mirkwood is the active location and its text reads 'While The Eaves of Mirkwood is the active location, encounter card effects cannot be canceled'. That is the price I knowingly paid to travel there.

**082** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 6). Cancels suppressed by active Eaves.

```json
{"revealed": ["Caught in a Web"], "deck_left": 20}
```

**083** `3.2` *patch* - Quest 3.3 reveal = Caught in a Web. Uncancellable here (Eaves active). Attaches as a Condition to one of my heroes: 'Attached hero does not ready during the refresh phase unless you pay 2 resources from that hero's pool.' Attached to DUNHERE. Reasoning: Eowyn is 6 of my 13 willpower so losing her ready is crippling; Aragorn nets 3 Leadership a round via Steward but that pool IS my entire ally economy and I need bodies to kill the 6hp/3-defence Goblin Troop in stage 3; Dunhere has 4 Spirit banked (two readies' worth), gains 1 a round, and contributes the least willpower at 3. Note it does NOT go to the encounter discard - it stays in play as an attachment. Staging unchanged at 2.

**084** `3.4` *patch* - Quest 3.4: 13 willpower vs 2 staging = 11 progress. Eaves of Mirkwood 0/2 +2 = EXPLORED. Overflow 5 to quest 2B: 7 + 5 = 12/12 -> STAGE 2 DEFEATED (the Goblin Trail gate was already satisfied in round 5). 4 progress discarded as overflow. Cancels come back online now that Eaves has left play.

**085** `3.4` *patch* - STAGE 3 revealed: The Rearguard, 6qp. 3A When Revealed resolved: added the set-aside Goblin Troop to the staging area (solo, so the 'each other player searches for a Goblin' clause does nothing). 3B: 'This stage cannot be defeated while Goblin Troop is in play. When this stage is defeated... the players win the game.' NOTE FOR THE BUG REPORT: this stage's text is on side A and the HUD rendered it correctly - which confirms the round-4 failure was specifically B-side-only text, not stage advances in general. Staging = Abandoned Camp 2 + Goblin Troop 3 = 5. WIN PLAN: Goblin Troop is 5 attack / 3 defence / 6hp at engagement 35 and my threat is exactly 35, so it engages on the next check unless I duck under. Two attacks of Aragorn 3 and Dunhere 2 do ZERO (each attack is reduced by 3 defence separately), so it dies only to one big combined attack or to direct damage: Sneak Attack (1 Leadership) -> Gandalf -> his Response 'deal 4 damage to 1 enemy in play' bypasses defence entirely, and Longbeard Orc Slayer's entry deals 1 to each Orc enemy in play. I hold 2 Sneak Attacks; 2 Gandalfs remain in the deck.

**086** `3.4` *mill* - Abandoned Camp Response: after travelling here, the first player discards the top card of their deck; if it is any ally, put it into play.

```json
{"discarded": [{"name": "Northern Tracker", "cost": "4"}], "deck_left": 31}
```

**087** `4.2` *patch* - Travel 4.2: travel to Abandoned Camp (0/3). Its Response hit NORTHERN TRACKER off the top of my deck - an ally, so it comes into play FREE (normally 4 Spirit). 1/2/2/3 with 'Response: After Northern Tracker commits to a quest, place 1 progress token on each location in the staging area.' Big swing: it is board presence, a 2-defence defender, and 2 more attack toward the 9 I need to one-shot Goblin Troop.

**088** `4.2` *reveal* - Abandoned Camp Travel cost: discard the top card of the encounter deck; if it is an enemy, add it to the staging area.

```json
{"revealed": ["Spider Den"], "deck_left": 19}
```

**089** `5.2` *patch* - Abandoned Camp travel cost discarded Spider Den - a LOCATION, and the effect only adds enemies to staging, so it is simply discarded. Staging = Goblin Troop 3 only. Encounter action window 5.2: play THE GALADHRIM'S GREETING for 3 Spirit (Dunhere 3 of his 4) - 'reduce one player's threat by 6'. Threat 35 -> 29. This is the whole plan: Goblin Troop's engagement cost is 35, so at 29 it will NOT engage on the check and instead sits in staging as 3 threat while I build a board. Optional engagement ignores engagement cost (RR 5.2), so I get to choose the round I fight it - on my terms, with enough attackers to one-shot 6hp through 3 defence.

**090** `5.2` *note* - MISPLAY (mine): I paid The Galadhrim's Greeting's 3 Spirit entirely from Dunhere (4 -> 1) when I should have paid Eowyn 2 + Dunhere 1. Dunhere carries Caught in a Web, which requires 2 resources FROM HIS OWN POOL at refresh to ready him. With 1 left he cannot pay, so he stays exhausted through round 7 - costing 3 willpower and 2 attack. Eowyn's Spirit was equally able to pay and she has no such condition. Logging rather than quietly re-allocating: no new information arrived between the decision and noticing it, so changing it now would be revising a choice after seeing its consequence.

**091** `7.R` *patch* - Encounter 5.3 checks: threat 29 < Goblin Troop's 35, so it does NOT engage - it stays in staging. Nothing engaged, so combat is empty. Refresh 7.R: threat 29 -> 30; Aragorn, Eowyn and Northern Tracker ready; DUNHERE STAYS EXHAUSTED - Caught in a Web demands 2 resources from his pool and he has 1.


## Round 7

**092** `3.2` *patch* - Round 7 resource: Aragorn 3 Leadership, Eowyn 3 Spirit, Dunhere 2 Spirit (still exhausted). Planning: no plays - Longbeard Orc Slayer costs 4 Leadership and Aragorn only makes 3 a round, so I bank. Quest 3.2: commit Aragorn 4 + Eowyn 6 + Northern Tracker 1 = 11, then ready Aragorn for 1 Leadership so a 2-defence defender remains (Goblintown Scavengers 12, Spiders of Mirkwood 18 and Wild Wargs 28 can all still engage at threat 30). 2 Leadership banked toward Longbeard next round.

**093** `3.2` *draw* - Resource 1.3: draw 1.

```json
{"drawn": ["For Gondor!"], "hand_size": 9, "deck_left": 30}
```

**094** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 7).

```json
{"revealed": ["Goblins are Upon You!"], "deck_left": 18}
```

**095** `3.3` *patch* - Quest 3.3 reveal = Goblins are Upon You! - 'Each player must search the encounter deck and discard pile for a Goblin enemy and put it into play, engaged with him. Then, shuffle the encounter deck. (This effect cannot be canceled.)' Chose GOBLIN SNIPER. Reasoning: 0 defence and 2hp makes it the cheapest kill available (Northern Tracker alone does it), and taking it from the deck permanently removes the single worst card in this set for a solo player - at 48 engagement it can never be engaged normally, so in staging it just deals 1 damage to a character every combat phase forever. Engaged, its Forced ability (which requires it to be IN THE STAGING AREA) is switched off entirely. Rejected Goblintown Scavengers (1 attack but 3hp) and Goblin Runners (3 attack, 1 defence). Goblin Troop's '+1 attack and +1 defence to each other Goblin engaged with you' does NOT apply - Goblin Troop is in staging, not engaged.

**096** `3.3` *shuffle_encounter* - Goblins are Upon You!: shuffle the encounter deck after the search.

**097** `3.4` *patch* - Quest 3.4: 11 willpower vs 3 staging (Goblin Troop) = 8 progress. Abandoned Camp 0/3 +3 = EXPLORED. Overflow 5 to quest 3B = 5/6 - one short, and irrelevant until Goblin Troop dies ('This stage cannot be defeated while Goblin Troop is in play'). Travel: no locations in staging, so no travel. Encounter: Goblin Troop 35 > threat 30, stays in staging; declined optional engagement - I cannot kill it yet.

**098** `3.4` *reveal* - Combat 6.2: deal 1 shadow card to Goblin Sniper (the only engaged enemy).

```json
{"revealed": ["Goblintown Scavengers"], "deck_left": 17}
```


## Round 8

**099** `1.R` *patch* - Combat: shadow = Goblintown Scavengers, no Shadow effect. Goblin Sniper attacks; Aragorn defends, 2 attack vs 2 defence = 0 damage. No player attacks - Aragorn is the only ready character and defending exhausted him. Left the Sniper alive on purpose: taking it undefended for 2 to free Aragorn's swing is a bad trade when Longbeard Orc Slayer's entry ('deal 1 damage to each Orc enemy in play') will drop it to 1hp next round for free. Goblin Sniper's Forced ping does NOT fire - it requires the Sniper to be in the STAGING AREA and it is engaged. Refresh: threat 30 -> 31; Dunhere pays 2 from his pool for Caught in a Web and readies (0 left).

**100** `1.R` *draw* - Round 8 resource 1.3: draw 1.

```json
{"drawn": ["Beorn"], "hand_size": 10, "deck_left": 29}
```

**101** `3.2` *patch* - Round 8 planning: play LONGBEARD ORC SLAYER for 4 of Aragorn's 5 Leadership. 'Response: After Longbeard Orc Slayer enters play, deal 1 damage to each Orc enemy in play' - both Goblin Troop (Goblin. Orc.) and Goblin Sniper (Goblin. Orc.) take 1. Goblin Troop 6 -> 5hp, Goblin Sniper 2 -> 1hp. 1 Leadership held back for Sneak Attack in the combat phase. Quest 3.2: commit EOWYN ALONE (6 willpower) - everyone else stays ready for the kill turn.

**102** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 8).

```json
{"revealed": ["Obsidian Arrows"], "deck_left": 16}
```

**103** `3.2` *patch* - Quest 3.3 reveal = Obsidian Arrows (When Revealed: deal 2 damage to a character you control). Cancels are live again - no Eaves in play - so played A TEST OF WILL for 1 Spirit from Eowyn. Cheap insurance: this is the kill turn and I need Beorn, Aragorn, Dunhere, Northern Tracker and Longbeard all alive and swinging. Treachery to the encounter discard, no staging threat, so staging stays 3.

**104** `3.2` *note* - CONSEQUENCE OF THE SIDE-B BUG, observed live. Quest 3B hit 6/6 while Goblin Troop was still alive in the staging area. The HUD showed 'Quest 3B cleared / That was the final stage!' and offered 'Declare Victory'. The printed card forbids this: stage 3B reads 'This stage cannot be defeated while Goblin Troop is in play.' That sentence is on side B - the same face screens.js:1705 never reads - so the app never displayed the gate at any point in the game, and then offered a win the rules do not allow. FAIRNESS: this is NOT a false-victory bug on its own, because the app hedges properly with a second, red button - 'Not yet - keep playing'. That is genuinely good design for a manual tracker: it asks rather than presuming, and it is the right shape for every 'cannot be defeated while X' quest. The defect is purely that the player is given no reason to press it. Fix the face_a-only read and this screen becomes correct: the gate text would have been on screen at the stage advance, and ideally repeated here as the caption for the 'Not yet' button. Chose 'Not yet - keep playing'.

**105** `5.2` *patch* - Quest 3.4: 6 willpower vs 3 staging = 3 progress; quest 3B 5 -> 6/6, 2 discarded. Stage NOT defeated - Goblin Troop is in play. Chose 'Not yet - keep playing'. UX nit: that choice does not dismiss the modal and gives no acknowledgement; both buttons stay on screen and you must also press DONE, so the tap reads as a no-op. Encounter 5.2 OPTIONAL ENGAGEMENT: engage GOBLIN TROOP. Engagement cost has no bearing here (RR 5.2), which is the entire reason its 35 cost never mattered - I picked the round. Staging 3 -> 0.

**106** `5.2` *reveal* - Combat 6.2: deal 1 shadow card to EACH engaged enemy, highest engagement cost first (RR 6.2) - Goblin Sniper (48) then Goblin Troop (35).

```json
{"revealed": ["Spiders of Mirkwood", "Driven by Shadow"], "deck_left": 14}
```

**107** `6.6` *patch* - COMBAT, round 8 - the kill turn. Shadow cards: Goblin Sniper got Spiders of Mirkwood, Goblin Troop got Driven by Shadow; NEITHER prints a 'Shadow:' line, so both are blank (a shadow card applies only its Shadow text, not its normal card text). 6.3 Play SNEAK ATTACK for Aragorn's last Leadership, putting BEORN into play from hand - Sneak Attack ignores cost and sphere, which is the only way a 6-cost Tactics ally reaches the table in a Leadership/Spirit deck. Deliberately did NOT trigger Beorn's +5 attack: untriggered, Sneak Attack returns him to HAND at end of phase; triggered, he shuffles into the deck. He is here purely as a 3-defence 6hp wall so every attacker stays free. 6.4 ENEMY ATTACKS: Goblin Troop attacks, Beorn defends, 5 attack vs 3 defence = 2 damage (Beorn 6 -> 4). Goblin Sniper attacks UNDEFENDED, 2 damage assigned to Dunhere (4 -> 2hp) - undefended damage does not exhaust, so he still swings. 6.6 PLAYER ATTACKS: attack 1 vs GOBLIN TROOP with Aragorn 3 + Dunhere 2 + Northern Tracker 2 + Longbeard Orc Slayer 2 = 9, minus 3 defence = 6 damage against 5 remaining hp - GOBLIN TROOP DESTROYED. Attack 2 vs GOBLIN SNIPER with Guard of the Citadel alone, 1 attack vs 0 defence = 1 damage against 1 remaining hp - DESTROYED. Board completely clear. Stage 3B's gate is now satisfied.


## Round 9

**108** `3.2` *patch* - Refresh: threat 31 -> 32. Beorn returned to HAND (Sneak Attack, untriggered). Dunhere stays EXHAUSTED again - Caught in a Web wants 2 from his pool and he had 1. Round 9 resource: Aragorn 3 Leadership, Eowyn 4 Spirit, Dunhere 2 Spirit. Staging is EMPTY. Quest 3.2: commit Aragorn 4 + Eowyn 6 + Northern Tracker 1 + Guard of the Citadel 1 = 12 willpower against 0 staging plus one reveal. Goblin Troop is dead, so stage 3B's gate is open and any progress placed defeats the stage.

**109** `3.2` *draw* - Resource 1.3: draw 1.

```json
{"drawn": ["Stand and Fight"], "hand_size": 9, "deck_left": 28}
```

**110** `3.2` *patch* - CORRECTION (mine): hand held two copies of Beorn. Sneak Attack puts an ally into play FROM HAND, so Beorn should have been removed from the hand list in round 8; he then returned to hand at end of phase. I never removed him, then appended him again on his return, duplicating a card the deck only has one of. Removing the extra. Hand 9 -> 8.

**111** `3.2` *reveal* - Quest 3.3: reveal 1 encounter card (round 9).

```json
{"revealed": ["Goblin Sniper"], "deck_left": 13}
```

**112** `3.2` *note* - CORRECTION (mine, real rules impact): full zone audit found THREE Goblin Snipers - 2 in the encounter discard plus the one just revealed - against 2 in the encounter set. Cause: at round 7, Goblins are Upon You! made me 'search the encounter deck and discard pile for a Goblin enemy and put it into play'. I appended Goblin Sniper to the engaged zone but never REMOVED it from the encounter deck, so the deck has carried a phantom copy since. Effect: the encounter deck has been 1 card too large for rounds 7-9, very slightly diluting every reveal. It never produced an illegal board state before now because the phantom was not drawn until this reveal. Fix: discard the phantom and reveal a genuine replacement. Every other card in the set reconciles exactly against the 33-card pool (Caught in a Web correctly accounted for as an attachment on Dunhere, Goblin Trail in the victory display).

**113** `3.2` *reveal* - Quest 3.3 RE-REVEAL after removing the phantom Goblin Sniper.

```json
{"revealed": ["Surprising Speed"], "deck_left": 12}
```

**114** `3.2` *patch* - Quest 3.3 reveal = Surprising Speed. 'Each player returns 1 enemy engaged with him to the staging area. If no enemy was returned to the staging area this way, Surprising Speed gains surge and doomed 1.' My board is clear of engaged enemies, so no enemy returns and it gains BOTH keywords: doomed 1 (threat 32 -> 33) and surge (reveal another card). No A Test of Will in hand, so no cancel available - and doomed/surge are keywords anyway, which A Test of Will does not touch (RR line 361).

**115** `3.2` *reveal* - Surge from Surprising Speed: reveal an additional encounter card.

```json
{"revealed": ["Wild Wargs"], "deck_left": 11}
```

**116** `3.3` *patch* - Surge reveal = Wild Wargs (2 threat, 28 engagement, 2/1/3) added to the staging area. Staging = 2. It would engage at threat 33, but the QUEST phase resolves before the encounter phase, so it never gets the chance.

**117** `VICTORY` *patch* - VICTORY. Stage 3B 'The Rearguard' defeated in round 9 - 6/6 progress with Goblin Troop destroyed, satisfying 'This stage cannot be defeated while Goblin Troop is in play'. Card text: 'When this stage is defeated, the heroes discover the trail to the Goblins' secret lair and the players win the game.' Final: threat 33 of 50, all three heroes alive (Aragorn 4/5, Eowyn 3/3, Dunhere 2/4), allies Northern Tracker / Longbeard Orc Slayer / Guard of the Citadel in play, Goblin Trail in the victory display for 3 victory points. NOTE ON THE ROUTE: because the quest already sat at 6/6, the resolution screen placed 0 progress and did not re-fire the cleared trigger. The way back was the Progress modal, whose DONE button turns into a green RESOLVE when the quest is full - that re-opened the victory prompt. Good affordance, and it means declining victory once is recoverable.

**118** `VICTORY` *note* - FINAL SCORE, per the official system (Learn to Play p.31 'Scoring'; lower is better): final threat 33 + threat cost of destroyed heroes 0 + damage on surviving heroes 3 (Aragorn 1, Eowyn 0, Dunhere 2) + 10 per completed round (9 x 10 = 90) - victory points 3 (Goblin Trail) = 123. ENHANCEMENT for the victory screen: it reports Rounds, Duration and P1 threat, which is three of the five inputs to the official score, but not the score itself. It cannot compute the other two - hero damage and victory points are board state a manual tracker does not hold - but it could ask for them on this screen (two steppers) and print the total, which is the number players actually compare between runs. Also worth showing: the scenario name, which appears nowhere on the victory screen.

**119** `VICTORY` *note* - THREAT DISCREPANCY at game end: the HUD's victory screen reports P1 threat 32; the true value is 33. I raised threat in the app for Eyes in the Dark's Doomed 1 in round 5, but never entered the Doomed 1 from Surprising Speed in round 9 - by then the quest phase was resolving and opening the Players modal mid-quest-phase is precisely the action that silently wipes committed willpower (see the data-loss finding). My omission, not the app's, but the data-loss bug is what made me avoid the control.
