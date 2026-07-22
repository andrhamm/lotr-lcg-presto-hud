"""Static turn-sequence data for LOTR LCG.

Transcribed verbatim from the DragnCards LOTR-LCG plugin
(jsons/phases.json, steps.json, labels.json) so the phase/step machine and
action-window markers match rules-accurate play. This module is pure data —
no hardware imports — so it is host-testable.

Source: https://github.com/seastan/dragncards-lotrlcg-plugin
"""

# Per-phase LED color (r, g, b), 0-255. Drives the 7 onboard LEDs.
PHASES = [
    {"id": "Beginning", "label": "Beginning",  "color": (60, 50, 30)},
    {"id": "Resource",  "label": "Resource",   "color": (30, 60, 140)},
    {"id": "Planning",  "label": "Planning",   "color": (20, 120, 90)},
    {"id": "Quest",     "label": "Quest",      "color": (90, 60, 160)},
    {"id": "Travel",    "label": "Travel",     "color": (150, 110, 30)},
    {"id": "Encounter", "label": "Encounter",  "color": (170, 80, 20)},
    {"id": "Combat",    "label": "Combat",     "color": (170, 40, 30)},
    {"id": "Refresh",   "label": "Refresh",    "color": (30, 120, 50)},
    {"id": "End",       "label": "End",        "color": (60, 50, 30)},
]

# Ordered steps. `action_window` is True where the DragnCards label notes an
# opportunity for players to act ("then player actions" / "player actions ...").
STEPS = [
    {"id": "0.0",  "phase": "Beginning", "label": "0.0 Beginning of the round",                        "action_window": False},
    {"id": "1.1",  "phase": "Resource",  "label": "1.1 Beginning of the Resource phase",               "action_window": False},
    {"id": "1.R",  "phase": "Resource",  "label": "1.2-1.3 Gain resources and draw cards",             "action_window": True},
    {"id": "1.4",  "phase": "Resource",  "label": "1.4 End of the Resource phase",                     "action_window": False},
    {"id": "2.1",  "phase": "Planning",  "label": "2.1 Beginning of the Planning phase",               "action_window": False},
    {"id": "2.P",  "phase": "Planning",  "label": "2.2-2.3 Play cards in turn order",                  "action_window": True},
    {"id": "2.4",  "phase": "Planning",  "label": "2.4 End of the Planning phase",                     "action_window": False},
    {"id": "3.1",  "phase": "Quest",     "label": "3.1 Beginning of the Quest phase",                  "action_window": True},
    {"id": "3.2",  "phase": "Quest",     "label": "3.2 Commit characters to the quest",                "action_window": True},
    {"id": "3.3",  "phase": "Quest",     "label": "3.3 Staging",                                       "action_window": True},
    {"id": "3.4",  "phase": "Quest",     "label": "3.4 Quest resolution",                              "action_window": True},
    {"id": "3.5",  "phase": "Quest",     "label": "3.5 End of the Quest phase",                        "action_window": False},
    {"id": "4.1",  "phase": "Travel",    "label": "4.1 Beginning of the Travel phase",                 "action_window": False},
    {"id": "4.2",  "phase": "Travel",    "label": "4.2 Travel opportunity",                            "action_window": True},
    {"id": "4.3",  "phase": "Travel",    "label": "4.3 End of the Travel phase",                       "action_window": False},
    {"id": "5.1",  "phase": "Encounter", "label": "5.1 Beginning of the Encounter phase",              "action_window": False},
    {"id": "5.2",  "phase": "Encounter", "label": "5.2 Optional engagement",                           "action_window": True},
    {"id": "5.3",  "phase": "Encounter", "label": "5.3 Engagement checks",                             "action_window": True},
    {"id": "5.4",  "phase": "Encounter", "label": "5.4 End of the Encounter phase",                    "action_window": False},
    {"id": "6.1",  "phase": "Combat",    "label": "6.1 Beginning of the Combat phase",                 "action_window": False},
    {"id": "6.2",  "phase": "Combat",    "label": "6.2 Deal shadow cards",                             "action_window": False},
    {"id": "6.E",  "phase": "Combat",    "label": "6.3-6.6 Enemy attacks",                             "action_window": True},
    {"id": "6.P",  "phase": "Combat",    "label": "6.7-6.10 Player attacks",                           "action_window": True},
    {"id": "6.11", "phase": "Combat",    "label": "6.11 End of the Combat phase",                      "action_window": False},
    {"id": "7.1",  "phase": "Refresh",   "label": "7.1 Beginning of the Refresh phase",                "action_window": False},
    {"id": "7.R",  "phase": "Refresh",   "label": "7.2-7.4 Ready cards, raise threat, pass P1 token",  "action_window": True},
    {"id": "7.5",  "phase": "Refresh",   "label": "7.5 End of the Refresh phase",                      "action_window": False},
    {"id": "8.0",  "phase": "End",       "label": "8.0 End of the round",                              "action_window": False},
]

STEP_ORDER = [s["id"] for s in STEPS]
_STEP_BY_ID = {s["id"]: s for s in STEPS}
_PHASE_BY_ID = {p["id"]: p for p in PHASES}


def step(step_id):
    """Return the step dict for a step id."""
    return _STEP_BY_ID[step_id]


def phase(phase_id):
    """Return the phase dict for a phase id."""
    return _PHASE_BY_ID[phase_id]


def step_index(step_id):
    """Return the 0-based position of a step in STEP_ORDER."""
    return STEP_ORDER.index(step_id)
