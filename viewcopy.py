"""Every player-facing string on the play screen, in one place.

This module is the single source of truth for play-screen copy. `docs/js/
viewcopy.js` is GENERATED from it by `tools/gen_web_data.py`, the same way
`phases.js` / `icons.js` / `metrics.js` are, so a copy change is one edit
rather than two hand-edited literals that nothing compares.

That mattered: before this existed, `ACTION_WINDOW_TIPS` and `COMBAT_FLOW`
had landed in the firmware with no JS counterpart at all, and the whole test
suite stayed green. No test compared the twins, because there was nothing to
compare them against.

## Rules for everything in here

Enforced mechanically by `tests/test_viewcopy.py`; the reasoning lives in
`docs/superpowers/specs/2026-07-25-design-system.md`.

- **ASCII only.** `tests/fake_hardware.py`'s `BITMAP8_W` silently measures an
  unknown glyph as 4px, so a curly quote or an arrow passes every test and
  renders as garbage on the device.
- **No spaced dash.** Use two sentences. A trailing clause is where vague copy
  hides.
- **Third person.** The Presto sits between four players, so "your threat" has
  no referent. Use RR's own vocabulary: *the active player* (one player acting
  alone), *each player* (everyone, in player order), *the first player* (token
  holder), *the players* (the table as a group).
- **Bold trigger words are reserved.** `Action`, `Forced`, `Response`,
  `When Revealed`, `Travel`, `Surge`, `Doomed` name printed card abilities.
  Never use one to describe a framework step.
- **Never name a mechanic the copy cannot afford to define.** Say what the
  player does instead.

## Provenance

Every rules claim traces to the Rules Reference, parsed into `research/rules/`
and searchable as the qmd collection `lotr-lcg-rules`:

    qmd query "when does archery damage resolve" -c lotr-lcg-rules

`docs/superpowers/plans/2026-07-28-view-copy-inventory.md` carries the
citation for each line and the reasoning behind the wording.
"""

# --------------------------------------------------------------------------
# View names. Rendered under the NEXT PHASE kicker, so each must measure
# <= 332px at DISPLAY - tests/test_screen_play.py enforces it over every value.
# --------------------------------------------------------------------------
VIEW_LABELS = {
    "setup_game": "Setup",
    "quest_setup": "Quest Setup",
    "resource": "Resource",
    "planning": "Planning",
    "quest_sailing": "Questing: Sailing",
    "quest_commit": "Questing: Commit",
    "quest_staging": "Questing: Staging",
    "quest_resolution": "Questing: Resolution",
    "travel": "Travel",
    "enc_optional": "Encounter: Opt. Engage",
    "enc_checks": "Encounter: Checks",
    "combat_shadow": "Combat: Shadow Cards",
    "combat_enemy": "Combat: Enemy Attacks",
    "combat_player": "Combat: Player Attacks",
    "refresh": "Refresh",
    "round_end": "End of Round",
}

# Window views. These never appear in a CTA - a phase view's button names the
# next PHASE, and the window's own button does too - so they are not bound by
# the 332px CTA span. They are used by the log and by view_for_step fallbacks.
for _pv in ("resource", "quest_commit", "quest_staging", "quest_resolution",
            "travel", "enc_optional", "enc_checks", "refresh"):
    VIEW_LABELS["aw_" + _pv] = "Action Window: " + VIEW_LABELS[_pv]

# --------------------------------------------------------------------------
# Setup. The real confusion is the ORDER of effects during quest setup:
# resolve 1A's Setup text in printed order, keywords on setup reveals DO
# resolve, then flip 1A -> 1B.
# --------------------------------------------------------------------------
SETUP_TIP = [
    "Draw 6 cards. One mulligan, and the second hand must be kept.",
    "Resolve stage 1A Setup text in printed order.",
    "Keywords on setup reveals (Surge/Doomed) do resolve.",
    "Then flip 1A to 1B and begin.",
]

# --------------------------------------------------------------------------
# The red "this happens anyway" band. Keyed by view.
# --------------------------------------------------------------------------
PHASE_FRAMEWORK = {
    "round_end": "Resolve any \"at the end of the round\" effects. Anything "
                 "lasting \"until the end of the round\" expires now.",
    "resource": "Each hero gains a resource and each player draws a card, "
                "all at the same time. (1 each normally.)",
    "planning": "In player order, play allies and attachments from "
                "hand - the only step that allows it.",
    "enc_checks": "Not optional. In player order, each player engages the "
                  "staging enemy with the highest engagement cost at or below "
                  "their threat. This repeats until no enemy in staging can "
                  "engage anyone.",
    "combat_shadow": "In player order, deal 1 facedown shadow card to each of "
                     "that player's engaged enemies, highest engagement cost "
                     "first. If the encounter deck runs out, those enemies "
                     "get none this round.",
    "combat_enemy": "Choose an enemy -> exhaust a defender (optional) -> shadow effect -> damage, one at a time.",
    "combat_player": "Choose an enemy -> exhaust attackers -> total ATK -> damage, one enemy at a time.",
    "refresh": "Simultaneously ready all exhausted cards. Pass the first "
               "player token clockwise. The tracker already raised each "
               "player's threat and passed the token.",
}

# The green "your window to act" section. Three phases get their action-window
# guidance HERE rather than on a dedicated screen, because upstream does not
# describe them as a discrete window following the step: Planning is "player
# actions throughout", and both combat halves are "player actions after each
# combat substep". A single after-the-step screen would misdescribe all three.
PHASE_WINDOW = {
    "planning": "This whole phase is your window - actions may be taken "
                "throughout it, not only at the end. Once you pass on playing "
                "allies you cannot return to it this turn.",
    "quest_commit": "In player order, exhaust characters to commit them and "
                    "add their willpower. They stay committed for the whole "
                    "phase and do not ready at resolution.",
    "enc_optional": "In player order, each player may engage 1 enemy in the "
                    "staging area. Engagement cost is ignored here, so a "
                    "player can engage an enemy far above their threat.",
    "enc_checks": "Responses.",
    "combat_shadow": "Responses.",
    "combat_enemy": "A window opens after each substep of every enemy attack, "
                    "not once at the end.",
    "combat_player": "A window opens after each substep of every attack you "
                     "make. The last one ends the combat phase.",
    "refresh": "Responses.",
}

PHASE_CAPTION = {
    "enc_optional": "Your threat decides which enemies can engage you next.",
    "enc_checks": "In player order, repeating until no enemy in staging can engage anyone.",
    "combat_enemy": "In player order; each player resolves all their enemies before the next. Undefended: all damage to one of your heroes.",
    "combat_player": "In player order; each player makes all their attacks before the next. 1 attack per engaged enemy, and attacking is optional.",
}

# Sailing-only addendum, appended to the framework band when game.sailing.
SHIP_NOTES = {
    "combat_enemy": "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
    "combat_player": "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
}

# --------------------------------------------------------------------------
# Combat loop diagram: (caption, note, [rung labels]). Combat is a loop, so it
# gets a flow diagram rather than a prose arrow-chain - the chain could carry
# the order but not the repetition, and the windows sit INSIDE the loop.
# --------------------------------------------------------------------------
COMBAT_FLOW = {
    "combat_enemy": ("Repeat for each engaged enemy, in player order.",
                     "Undefended: all damage hits one hero.",
                     ["Choose an enemy",
                      "Declare a defender (optional)",
                      "Reveal the shadow card",
                      "Deal damage"]),
    "combat_player": ("Repeat for each attack you make.",
                      "Optional; 1 attack per engaged enemy.",
                      ["Choose an enemy",
                       "Declare attackers",
                       "Total attack vs defence",
                       "Deal damage"]),
}

# --------------------------------------------------------------------------
# Per-window copy, keyed by the view whose step the window FOLLOWS.
# --------------------------------------------------------------------------
ACTION_WINDOW_TIPS = {
    "resource": [
        "Resources are gained and cards are drawn.",
        "Anything played here happens before the planning phase begins.",
    ],
    "quest_commit": [
        "Characters are committed. The encounter deck has not been revealed.",
        "This is the last window before staging.",
    ],
    "quest_staging": [
        "Both totals are set.",
        "Change them now - the comparison happens next and fixes the result.",
    ],
    "quest_resolution": [
        "Progress has been placed.",
        "The travel opportunity comes next.",
    ],
    "travel": [
        "The travel opportunity has passed.",
        "\"Travel Action:\" abilities work only during this phase.",
    ],
    "enc_optional": [
        "Optional engagement is over.",
        "Forced engagement checks run next.",
    ],
    "enc_checks": [
        "Engagements are settled.",
        "The combat phase begins next.",
    ],
    "refresh": [
        "Cards are readied and threat has already gone up.",
        "Reducing threat now cannot undo an elimination that already "
        "happened.",
    ],
}

# --------------------------------------------------------------------------
# Per-view prose that sits outside the framework/window bands.
# --------------------------------------------------------------------------
STAGING = {
    # The deck-empty reshuffle (RR 3.3) was cut from this band, not forgotten:
    # a third sentence pushed the staging view's content past the nav rule.
    # Saying less is the design system's answer to running out of room.
    "framework": "1 encounter card per player, one at a time. Resolve keywords "
                 "and When Revealed effects.",
    "window": "Responses to the reveal.",
    "short": "one at a time / resolve each When Revealed",
}

TRAVEL = {
    "blocked": "A location is already active, so there is no travel this phase.",
    "open": "Travel to one location in the staging area. It is optional: the "
            "players decide as a group, and the first player has the final say.",
    "btn_travel": "Travel to location",
    "btn_replace": "Replace location (card effect)",
}

# Quest resolution. The same three outcomes are phrased in the toast, in the
# resolution card, and in the log - keep them consistent.
OUTCOME = {
    "toast_success": "Quested successfully! +%d progress",
    "toast_fail": "Quest failed. +%d threat to all",
    "toast_tie": "A tie. No progress, no threat.",
    "card_fail": "Quest failed. ",
    "card_tie": "A tie. ",
    "fail_line2_pre": "Each player's ",
    "fail_line2_post": "rose by %d.",
    "tie_line2": "Neither successful nor unsuccessful.",
    "alloc_caption": "Location fills first, then the quest",
    "alloc_header": "Place %d progress",
    "alloc_unplaced": "Unplaced (discarded)",
}

SAILING = {
    "no_keyword": "No Sailing keyword on this quest.",
    "enable_hint": "Enable it if the stage says Sailing.",
}

QUEST_SETUP = {
    "none": "No setup instructions for this stage.",
    "banner": "QUEST SETUP - resolve now",
    "flip": "Flip to Side B  ->  %d qp",
}

CONFIRM = {
    "all": "All players confirmed",
    "partial": "Confirm all commits (%d/%d)",
}

TOTALS = {
    "willpower": "Questing for",
    "staging": "Staging area",
    "willpower_modal": "Questing willpower total",
    "staging_modal": "Staging area threat",
}

REFRESH = {
    "preview_caption": "current -> projected",
}
