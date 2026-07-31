"""What X counts, as an enum - so nothing has to parse prose at runtime.

54 location/stage stats print a literal X instead of a number. Each one's card
says what X is, in its own words, and those words were distilled into
tools/data/*_distilled.json. But a sentence is only good for SHOWING; to draw a
control and compute a value the app needs to know two things separately:

    what to count      -> the stepper's label
    what to do with it -> the number on screen

Both come from an enum assigned once per card, not from re-reading the
sentence. 43 distinct sentences collapse to the 26 targets below, because most
of the difference is phrasing: "the number of characters controlled by the
first player" and "the number of characters the first player controls" are the
same question, and "1 more than" and "1 plus" are the same arithmetic.

Arithmetic is two integers rather than a third enum:

    value = mul * count + add

which covers every observed shape - a bare count (1,0), "1 more than" (1,1),
"twice" (2,0), "N per player" (N,0) and "2, plus 2 for each" (2,2).

`auto` names the tracked value that answers the question without asking the
player. Only three of the 26 have one, and they are the three the HUD already
models: how many players there are, which stage the main quest is on, and the
highest player threat. The other 23 are board state the HUD does not see, so
the player supplies the count and the app does the arithmetic - they never do
it in their head, and the count survives to next round when it changes by one.

Pure data, no imports: runs under MicroPython on the device and CPython for
host tests, same posture as phases.py / viewcopy.py.
"""

# auto values the game state can answer directly
AUTO_PLAYERS = "players"
AUTO_STAGE = "stage"
AUTO_HIGHEST_THREAT = "highest_threat"

# enum -> {label: the stepper's label, auto: tracked source or None}
#
# `label` is what the player reads above the stepper, so it is sentence case
# and names the thing to count, not the stat being computed: the row already
# says "Threat".
TARGETS = {
    # -- answerable from state we already track -----------------------------
    "players": {"label": "Players", "auto": AUTO_PLAYERS},
    "stage_number": {"label": "Main quest stage", "auto": AUTO_STAGE},
    "highest_threat": {"label": "Highest player threat",
                       "auto": AUTO_HIGHEST_THREAT},

    # -- in play -----------------------------------------------------------
    "enemies_in_play": {"label": "Enemies in play", "auto": None},
    # ASCII, not "Nazgul" with a circumflex: these labels are drawn with
    # bitmap8, whose glyph table has no accented characters, and an unknown
    # glyph measures 4px - so a diacritic passes every layout test and only
    # breaks on the device. See test_copy_is_ascii_only.
    "nazgul_in_play": {"label": "Nazgul enemies in play", "auto": None},
    "dark_locations_in_play": {"label": "Dark locations in play", "auto": None},
    "quest_cards_in_play": {"label": "Quest cards in play", "auto": None},
    "allies_in_play": {"label": "Ally cards in play", "auto": None},
    "characters_in_play": {"label": "Characters in play", "auto": None},
    "damaged_characters": {"label": "Damaged characters", "auto": None},

    # -- staging area ------------------------------------------------------
    "locations_in_staging": {"label": "Locations in staging", "auto": None},
    "snow_in_staging": {"label": "Snow cards in staging", "auto": None},
    "ally_cost_in_staging": {"label": "Total ally cost in staging",
                             "auto": None},

    # -- a particular player -----------------------------------------------
    "first_player_characters": {"label": "First player's characters",
                                "auto": None},
    "first_player_hand": {"label": "Cards in first player's hand",
                          "auto": None},
    "heroes_questing": {"label": "Heroes committed to the quest",
                        "auto": None},
    "allies_most": {"label": "Allies of the player with the most",
                    "auto": None},
    "allies_breelanders": {"label": "Bree-landers player's allies",
                           "auto": None},

    # -- objectives the players control -------------------------------------
    "clue_objectives": {"label": "Clue objectives controlled", "auto": None},
    "captive_allies": {"label": "Captive objective allies", "auto": None},
    "mount_objectives": {"label": "Mount objectives controlled",
                         "auto": None},
    "locations_controlled": {"label": "Locations controlled", "auto": None},

    # -- the victory display ------------------------------------------------
    "castle_side_quests_victory": {"label": "Castle side quests in victory",
                                   "auto": None},
    "quest_stages_victory": {"label": "Quest stages in victory",
                             "auto": None},

    # -- tokens on a specific card ------------------------------------------
    "resources_on_main_quest": {"label": "Resources on the main quest",
                                "auto": None},
    "resources_here": {"label": "Resource tokens here", "auto": None},
    "progress_on_to_the_tower": {"label": "Progress on To the Tower",
                                 "auto": None},
    "cards_captured_here": {"label": "Cards captured here", "auto": None},
    "highest_wose_archery": {"label": "Highest Wose archery value",
                             "auto": None},
}


def label_for(target):
    """The stepper label, or None for an unknown target."""
    t = TARGETS.get(target)
    return t["label"] if t else None


def auto_for(target):
    """Which tracked value answers this target, or None if the player must."""
    t = TARGETS.get(target)
    return t["auto"] if t else None


def value_of(count, mul=1, add=0):
    """value = mul * count + add, never below zero."""
    return max(0, mul * count + add)


def resolve(spec, count=None, players=1, stage=1, highest_threat=0):
    """The number to put on screen, or None when the player has not supplied a
    count yet.

    `spec` is a card's coded X: {"target", "mul", "add"}. An auto target
    ignores `count` entirely and recomputes from the tracked value, which is
    the whole point of tagging those three separately - "X is 4 per player"
    must follow the player count without anyone touching a stepper.
    """
    if not spec:
        return None
    target = spec.get("target")
    mul = spec.get("mul", 1)
    add = spec.get("add", 0)
    auto = auto_for(target)
    if auto == AUTO_PLAYERS:
        return value_of(players, mul, add)
    if auto == AUTO_STAGE:
        return value_of(stage, mul, add)
    if auto == AUTO_HIGHEST_THREAT:
        return value_of(highest_threat, mul, add)
    if count is None:
        return None
    return value_of(count, mul, add)
