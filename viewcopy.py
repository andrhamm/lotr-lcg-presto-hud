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
    "combat_shadow": "In player order, deal 1 facedown shadow card to each of "
                     "that player's engaged enemies, highest engagement cost "
                     "first. If the encounter deck runs out, those enemies "
                     "get none this round.",
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
    "quest_commit": "In player order, exhaust characters to commit them and "
                    "add their willpower. They stay committed for the whole "
                    "phase and do not ready at resolution.",
    "enc_optional": "In player order, each player may engage 1 enemy in the "
                    "staging area. Engagement cost is ignored here, so a "
                    "player can engage an enemy far above their threat.",
    "combat_shadow": "Responses.",
    "refresh": "Responses.",
}

PHASE_CAPTION = {
}


# --------------------------------------------------------------------------
# Combat loop diagram: (caption, note, [rung labels]). Combat is a loop, so it
# gets a flow diagram rather than a prose arrow-chain - the chain could carry
# the order but not the repetition, and the windows sit INSIDE the loop.
# --------------------------------------------------------------------------
# Loop diagrams. Four views are genuinely loops, and each is drawn with the
# same three-part shape: a framing line saying what the whole loop is, the
# diagram, and an optional note.
#
#   intro   leads with "In player order," wherever that governs the loop. It
#           is what tells a reader whether the diagram is one pass or a
#           rotation, so it comes BEFORE the diagram.
#   rungs   (label, opens_a_window, sub_rung_or_None)
#   exit    always "Repeat until <condition>". A question-shaped rung asks
#           the player to work out the answer at the moment they want to be
#           told it.
#   note    one consequence, or None. Padding this slot to match a
#           neighbouring view is how recap sentences got here originally.
#
# opens_a_window renders a purple tick, explained by ONE legend line. It used
# to be an inline ", then actions" on every rung, which cost 128px each and
# ran the longest rungs to 570px against a 480px screen.
#
# Ticks are placed from RR's timing chart, not by symmetry. The enemy flow has
# ACTION WINDOW after every rung INCLUDING the choose step (6.4b); the player
# flow has NONE after 6.8b and its first window follows the ranged option.
# Planning and the engagement checks carry no ticks at all - Planning IS the
# window, and 5.3's window is a screen of its own.
LOOP_FLOW = {
    "planning": {
        # Playing allies and attachments is entirely optional: your window,
        # green. The rotation the intro describes is the shape of that window,
        # not something that happens to you.
        "kind": "window",
        "intro": "In player order, each player becomes the active player once.",
        "rungs": [
            ("Active player plays any number of allies and attachments", False,
             "only the active player may"),
            ("Any player may take one action, or pass", False,
             "in player order, first player first"),
        ],
        "exit": "Repeat until every player has been active",
        # A rule about how the loop works, not advice: framework.
        "note_kind": "framework",
        "note": "Only actions rotate. Responses fire on their own trigger.",
    },
    "enc_checks": {
        # The copy says it outright - "Not optional" - so red.
        "kind": "framework",
        "intro": "Not optional. In player order, each player engages one enemy "
                 "at a time.",
        "rungs": [
            ("First player engages the staging enemy with the highest "
             "engagement cost at or below their threat", False, None),
            ("Each remaining player does the same", False, None),
        ],
        "exit": "Repeat until no enemy in staging can engage anyone",
        # Strategy, not a rule - nothing in RR says this, it is the
        # consequence a player should plan around: tip.
        "note_kind": "tip",
        "note": "Higher threat pulls bigger enemies.",
    },
    "combat_enemy": {
        # Enemies attack whether or not you act: framework, red.
        "kind": "framework",
        # One line by necessity: the two-line version put the note past the
        # nav rule. Both cited facts survive - the player order, and the
        # one-per-enemy cap (6.3: each engaged enemy "will have one
        # opportunity to make an attack").
        "intro": "In player order, one attack per engaged enemy.",
        "rungs": [
            ("Active player chooses an engaged enemy", True, None),
            ("Declare a defender (optional)", True,
             "if none, another player's Sentinel may defend"),
            ("Reveal and resolve the shadow effect", True, None),
            ("Determine combat damage", True, None),
        ],
        "exit": "Repeat until no eligible enemies remain",
        # Trimmed to two lines: a third ran the view past the nav rule. The
        # half that survives is the non-obvious one - defence reduces damage
        # everywhere else in the game, and here it does not.
        #
        # States what the rules do to you, not what to do about it: framework.
        "note_kind": "framework",
        "note": "Undefended: all damage hits one hero, and defence does not "
                "reduce it.",
    },
    "combat_player": {
        # "may attack" - declaring attacks is optional, so green.
        "kind": "window",
        # One line: the standing elimination note below needs two, and the
        # rungs already carry the scope ("1 of their engaged enemies"). The
        # modal "may" is what makes attacking optional, per the copy rules.
        "intro": "In player order, each player may attack.",
        "rungs": [
            ("Active player exhausts characters to attack 1 of their engaged "
             "enemies", False,
             "if every attacker has Ranged, any player's engaged enemy"),
            ("Other players' Ranged may exhaust to join", True, None),
            ("Determine attack strength", True, None),
            ("Determine combat damage", True, None),
        ],
        "exit": "Repeat until no more attacks are declared",
        # The only note here is COMBAT_LAST_CHANCE, which is advice: tip.
        "note_kind": "tip",
        "note": None,
    },
}

LOOP_LEGEND = "= action window opens here"

# Sailing-only third paragraph on the combat flows.
SHIP_FLOW_NOTES = {
    "combat_enemy": "Ships: only a ship can defend a ship-enemy.",
    "combat_player": "Ships attack only ship-enemies.",
}

# --------------------------------------------------------------------------
# Per-window copy, keyed by the view whose step the window FOLLOWS.
# --------------------------------------------------------------------------
ACTION_WINDOW_TIPS = {
    # Every one of these opened by narrating the step the player had just left
    # ("Resources are gained and cards are drawn"). They pressed a button on
    # that exact screen a second ago, so the recap read as though something
    # new had happened. A window screen says what can be done NOW and what
    # closes on leaving; a recap clause survives only where the advice depends
    # on it.
    #
    # Shape: [positional, actionable]. The positional line says
    # "This is the last action window before X" wherever that is the point, so
    # the phrase means the same thing every time it appears.
    #
    # A phase-locked action type is named on the FIRST window of its phase -
    # RR: such abilities "can only be initiated during an action window in the
    # specified phase", which makes them the one thing genuinely lost when a
    # phase ends. Counts are from the compiled card data.
    "resource": [
        # No countdown here: this window closes nothing a player can lose, so
        # inventing urgency would be false. Resource Action: is printed on 1
        # card of 6,037 and is not worth a line.
        "Anything played now happens before the planning phase begins.",
    ],
    "quest_commit": [
        "This is the last action window before staging.",
        "Anything played now resolves before any encounter card is revealed. "
        "\"Quest Action:\" abilities work anywhere in this phase.",
    ],
    "quest_staging": [
        "This is the last action window before quest resolution.",
        "Confirm the tracker matches the board.",
    ],   # plus one CONDITIONAL line - see STAGING_PENDING
    "quest_resolution": [
        "This is the last action window before travel.",
    ],
    "travel": [
        "This is the last action window in the travel phase.",
        "\"Travel Action:\" abilities work only here.",
    ],
    "enc_optional": [
        "This is the last action window before engagement checks.",
        "Lower threat now and fewer enemies can engage. "
        "\"Encounter Action:\" abilities work only in this phase.",
    ],
    "enc_checks": [
        "This is the last action window before combat.",
        "Questers are still exhausted, so ready defenders.",
    ],
    "refresh": [
        # The deliberate exception to the shape: its first line is a PAST
        # fact, because here the door has already shut and the point is that
        # acting now is too late.
        "Last action window of the round. End of round effects resolve after "
        "it.",
        "\"Refresh Action:\" abilities work only here.",
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
    # The caption under the staging stepper. It used to read "+3 reveal
    # estimate", where the 3 was STAGING_HIGH_PER_PLAYER - a constant, so every
    # scenario ever published showed the same number. It is now the worst
    # printed threat in THIS scenario's own gathered pool, computed at build
    # time (index.json's maxCardThreat). A fact the app computed beats a
    # forecast it guessed.
    "estimate": "+%d max per card",
    # ...except a card printing a literal X has no printed maximum, so the
    # number is a floor rather than a ceiling and has to say so. The Oath's
    # Tangled Grove reads "X is the number of locations in the staging area".
    "estimate_x": "+%d max, some print X",
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
    # Learn to Play, setup step 7, near-verbatim: "Perform the 'Setup'
    # instructions presented on the stage '1A' quest card. Then, flip the card
    # to the stage '1B' side. The game is now ready to begin."
    #
    # The framework band, not a text dump. The card's Setup text lives one tap
    # away behind "View quest card", where a player reads it on the card that
    # prints it. This screen says what to DO, which is what a framework band
    # is for everywhere else in the app.
    "resolve": "Perform the Setup instructions on Stage %s, %s.",
    "none": "Stage %s has no Setup instructions.",
    "then_flip": "Then flip the card to its Stage %sB side.",
    "view": "View quest card",
    # "Begin Round 1", not "Flip to Side B". Quest setup happens once per
    # game - it is reached only from the new-game flow - and flip_to_b enters
    # VIEW_ORDER[0] directly, so the resource phase really is immediately
    # after. RR: "After completing these steps, players begin the game
    # starting with the first game round."
    #
    # It is the same label the one-time setup view uses,
    # so both routes into round 1 end with the same button. An ACTION cta:
    # single line, no NEXT PHASE kicker. The flip itself is a table action and
    # is named in the copy above, the same split the refresh view uses.
    "begin": "Begin Round 1",
}

TOTALS = {
    "willpower": "Questing for",
    "staging": "Staging area",
    "willpower_modal": "Questing willpower total",
    "staging_modal": "Staging area threat",
}

REFRESH = {
}


# The staging window's third line, chosen from the pending result. The view
# already computes and shows that result, so the copy reacts to the actual
# game state instead of coaching: three static drafts were rejected in review
# for telling a player something any competent player already knows.
#
# "Without actions," prefixes the lines a player would want to change. A bare
# "P3 is eliminated at 50" reads as a verdict already delivered, which on an
# action-window screen is exactly wrong. The success lines drop the prefix:
# nothing bad is pending, so the fact IS the invitation.
STAGING_PENDING = {
    "fail_elim": "Without actions, %s is eliminated at 50 %s.",
    "fail": "Without actions, each player raises %s by %d.",
    "tie": "Without actions, no progress and no %s. Each +1 %s places 1 %s.",
    # Only true while the stage has room. Past its quest points the extra is
    # DISCARDED (p.22), so the same line would be advising a wasted play.
    "success_room": "Each +1 %s places 1 more %s.",
    "success_full": "%s past %d is discarded.",
}

# Shown on combat_player unconditionally. It CANNOT be conditional: 67 cards
# interact with the refresh threat raise and several replace it outright
# (Nalir raises by 1 per player; Escape From Mount Gram substitutes a
# different number), so a threshold test built on threat_per_round fails
# silently and in the dangerous direction - a player at 44 facing Nalir in a
# four-player game would get no warning at all. An always-on line costs one
# line and never lies.
# One line, because combat_player has room for exactly one. Both halves that
# matter survive: the lever (lower threat) and the stake (refresh eliminates).
COMBAT_LAST_CHANCE = "Lower threat now or refresh may eliminate."

# Progress screen, framework band. The placement ORDER is a rule the player
# acts on, and getting it wrong loses progress: RR p.15 - the active location
# takes progress first, up to its own quest points, and only the remainder goes
# to the quest card. Each resolves the moment it is full, which is why
# exploring a location can advance the quest in the same motion (and why p.22's
# "excess is discarded" applies to the quest, not to the location).
# Shown when the card catalog cannot be read. There is no manual/custom quest
# mode to fall back to: the game is out of print, so the catalog can be
# complete, and a hand-entry escape hatch was a second and worse source of
# truth. An unreadable catalog is a real failure, and on the device it means
# the deploy is missing docs/data.
CATALOG_UNAVAILABLE = ("The scenario catalog could not be read, so there is "
                       "nothing to pick from. On the device this usually "
                       "means the card data was never copied across.")

# A card face that prints no game text. Two-sided quest cards routinely have
# one: side A carries the story and the Setup while side B carries only the
# quest points, or the reverse. Said as what the CARD is, not as what the app
# is missing - the old "no text" read like a failed lookup.
#
# 15 of 505 quest pairs used to hide this behind an upstream defect that
# copied side A's text onto side B (see _unsmear_quest_faces): The Oath's
# stage 1 showed the same paragraph twice rather than admitting 1B is just
# nine quest points.
NO_CARD_TEXT = ("This side prints no game text. It carries the stage's "
                "quest points.")

PROGRESS_PLACEMENT = ("Progress fills the active location first, then the "
                      "current quest. Each resolves the moment it is full, so "
                      "exploring a location can advance the quest in the same "
                      "motion.")
