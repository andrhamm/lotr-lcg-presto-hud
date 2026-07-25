"""Scene builders shared by tools/preview.py and the layout lint tests.

Each builder returns (hw, obj) where hw.display.calls holds the draw calls and
obj (screen or modal) exposes .buttons. Covers every wireframe state.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from gamestate import GameState, VIEW_STEP


def _game():
    g = GameState()
    for i, t in enumerate((14, 28, 41, 19)):
        g.adjust_threat(i, t)
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 6}
    g.active_location = {"points": 3, "progress": 2}
    g.side_quests = [{"points": 5, "progress": 3}]
    g.willpower = 11
    g.staging = 7
    return g


def _play(view, mutate=None):
    def build():
        from ui.screen_play import ScreenPlay
        hw = FakeHardware()
        pal = Palette(hw.display)
        g = _game()
        g.view = view
        g.step = VIEW_STEP[view]
        if view == "quest_commit":
            for i, c in enumerate((3, 4, 2, 2)):
                g.set_commit(i, c)
        if view == "quest_resolution":
            g.pending_budget = 4
            g.quest_outcome = "success"
            g.quest_outcome_n = 4
        if mutate:
            mutate(g)
        s = ScreenPlay()
        s.draw(hw, g, pal)
        return hw, s
    return build


def _quest_setup():
    # R0 pre-round-1 phase view: a scenario-preloaded game (Passage Through
    # Mirkwood shape - stage 1, 8 quest points) showing stage 1A's setup text,
    # still to be resolved before the Flip to Side B CTA begins round 1.
    from ui.screen_play import ScreenPlay
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(4, 25)
    g.preload_scenario(
        {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
         "pack": "Core Set", "cycle": "Core Set", "source": "official",
         "kind": "quest", "nightmare": False, "mode": "Standard"},
        [{"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
            "faces": [{"side": "A", "name": "Flies and Spiders",
                       "text": "Search the encounter deck for 1 copy of the Forest "
                               "Spider and 1 copy of the Old Forest Road, add them to "
                               "the staging area, then shuffle the encounter deck."},
                      {"side": "B", "name": "Flies and Spiders", "text": None}]}]}])
    g.view = "quest_setup"
    g.step = VIEW_STEP["quest_setup"]
    s = ScreenPlay()
    s.draw(hw, g, pal)
    return hw, s


def _boot(saved):
    def build():
        from ui.screen_boot import BootScreen
        hw = FakeHardware()
        pal = Palette(hw.display)
        s = BootScreen(saved)
        s.draw(hw, _game(), pal)
        return hw, s
    return build


def _setup(threats, first=0):
    def build():
        from ui.screen_setup import SetupScreen
        hw = FakeHardware()
        pal = Palette(hw.display)
        s = SetupScreen()
        s.threats = list(threats)
        s.first = first
        s.draw(hw, _game(), pal)
        return hw, s
    return build


def _screen(mod, cls, prep=None):
    def build():
        import importlib
        m = importlib.import_module(mod)
        hw = FakeHardware()
        pal = Palette(hw.display)
        g = _game()
        if prep:
            prep(g)
        s = getattr(m, cls)()
        s.draw(hw, g, pal)
        return hw, s
    return build


def _scenario_source():
    from ui.screen_quest import ScenarioSourceScreen
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScenarioSourceScreen()
    s.draw(hw, _game(), pal)
    return hw, s


# Cycle list shaped like quest_catalog.cycles_for(index, "official") output
# ({"cycle","date","count"} entries) — 8 cycles at PickCycleScreen.PER_PAGE=7
# exercises the Log-style pager (page 1/2).
_PICK_CYCLE_SAMPLE = [
    {"cycle": "Core Set", "date": None, "count": 3},
    {"cycle": "Shadows of Mirkwood", "date": None, "count": 6},
    {"cycle": "The Dwarrowdelf", "date": None, "count": 6},
    {"cycle": "Against the Shadow", "date": None, "count": 6},
    {"cycle": "The Ring-maker", "date": None, "count": 6},
    {"cycle": "The Angmar Awakened", "date": None, "count": 6},
    {"cycle": "The Dream-chaser", "date": None, "count": 6},
    {"cycle": "The Haradrim", "date": None, "count": 6},
]


def _pick_cycle():
    from ui.screen_quest import PickCycleScreen
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = PickCycleScreen("official", list(_PICK_CYCLE_SAMPLE))
    s.draw(hw, _game(), pal)
    return hw, s


def _pick_cycle_empty():
    # Community (ALeP) source with zero catalog scenarios (no ALeP data yet)
    # — must render the graceful empty-state placeholder, not a blank list.
    from ui.screen_quest import PickCycleScreen
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = PickCycleScreen("alep", [])
    s.draw(hw, _game(), pal)
    return hw, s


# Scenario list shaped like one group_by_cycle() group's "scenarios" list
# ({"slug","name",...} entries) — 6 scenarios matches Shadows of Mirkwood
# exactly (mock_quest.py's frame_choose sample), so ChooseScenarioScreen.
# PER_PAGE=6 keeps this on a single page (no pager) like the mock.
_CHOOSE_SCENARIO_SAMPLE = [
    {"slug": "the-hunt-for-gollum", "name": "The Hunt for Gollum"},
    {"slug": "conflict-at-the-carrock", "name": "Conflict at the Carrock"},
    {"slug": "a-journey-to-rhosgobel", "name": "A Journey to Rhosgobel"},
    {"slug": "the-hills-of-emyn-muil", "name": "The Hills of Emyn Muil"},
    {"slug": "the-dead-marshes", "name": "The Dead Marshes"},
    {"slug": "return-to-mirkwood", "name": "Return to Mirkwood"},
]


def _choose_scenario():
    from ui.screen_quest import ChooseScenarioScreen
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ChooseScenarioScreen("official", "Shadows of Mirkwood", list(_CHOOSE_SCENARIO_SAMPLE))
    s.draw(hw, _game(), pal)
    return hw, s


# Scenario Options fixture: a real Core Set scenario's index entry + a
# per-scenario-JSON stand-in. "includedSets" is what build_card_data.py
# actually merges in from Hall of Beorn's sets-to-gather enrichment
# (catalog-enrichment plan, Task 3) - and for Passage Through Mirkwood this
# exact 3-set list is the real, verified output (see
# tools/build_hob_enrichment.py's tests + the Task 1 report), so this
# fixture doubles as both a real-data example and (unchanged from before)
# a pixel-parity match for mock_quest.py's frame_options() sample.
_SCENARIO_OPTIONS_ENTRY = {
    "slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
    "pack": "Core Set", "cycle": "Core Set", "source": "official", "kind": "quest",
}
_SCENARIO_OPTIONS_DATA = {
    "slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
    "pack": "Core Set",
    "includedSets": ["Passage Through Mirkwood", "Spiders of Mirkwood", "Dol Guldur Orcs"],
}

# Fallback fixture: a scenario with no "includedSets" at all - either
# enrichment.json wasn't merged for this build, or Hall of Beorn's API had
# no answer for this scenario (both happen - see the Task 1 report; e.g.
# "Temple of Doom" resolved no gather list). ScenarioOptionsScreen._gather_
# sets() must fall back to the scenario's own name alone, same as before
# B-data landed.
_SCENARIO_OPTIONS_DATA_NO_ENRICHMENT = {
    "slug": "the-old-forest", "name": "The Old Forest", "pack": "The Old Forest",
}
_SCENARIO_OPTIONS_ENTRY_NO_ENRICHMENT = {
    "slug": "the-old-forest", "name": "The Old Forest",
    "pack": "The Old Forest", "cycle": "Standalone/PoD", "source": "official", "kind": "quest",
}


def _scenario_options(difficulty="Standard", mode="Normal"):
    def build():
        from ui.screen_quest import ScenarioOptionsScreen
        hw = FakeHardware()
        pal = Palette(hw.display)
        s = ScenarioOptionsScreen(dict(_SCENARIO_OPTIONS_ENTRY), dict(_SCENARIO_OPTIONS_DATA),
                                  difficulty=difficulty, mode=mode)
        s.draw(hw, _game(), pal)
        return hw, s
    return build


def _scenario_options_no_enrichment():
    from ui.screen_quest import ScenarioOptionsScreen
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScenarioOptionsScreen(dict(_SCENARIO_OPTIONS_ENTRY_NO_ENRICHMENT),
                              dict(_SCENARIO_OPTIONS_DATA_NO_ENRICHMENT))
    s.draw(hw, _game(), pal)
    return hw, s


# Real rasterized masks (tools/build_icons.py output, docs/data/icons.json
# - not committed, see CLAUDE.md's Card data section) for the M4-B icons
# Task 3 scene below: just enough real 24-row bitmasks to exercise
# ScenarioOptionsScreen's actual icon-drawing path (icon_slot -> icons.draw)
# rather than only its placeholder-triangle fallback (already covered by
# _scenario_options above). Matches _SCENARIO_OPTIONS_DATA's three
# "includedSets" names exactly, so all four slots (scenario symbol + 3
# gather rows) draw a real symbol.
_ICONS_FIXTURE = {
    "passage-through-mirkwood": [0, 0, 0, 0, 0, 2560, 574496, 967104, 494336, 233088,
                                  651008, 130688, 47552, 14464, 6144, 6144, 6144, 6144,
                                  14336, 15360, 56064, 67584, 0, 0],
    "spiders-of-mirkwood": [0, 0, 0, 0, 0, 1792, 2176, 5104, 13824, 62464, 195584,
                             261888, 523456, 391744, 391424, 389408, 57600, 256, 0,
                             2048, 2048, 0, 0, 0],
    "dol-guldur-orcs": [0, 0, 0, 0, 32256, 65280, 393120, 262112, 262080, 262080,
                         131008, 65088, 48384, 97920, 130944, 65280, 28160, 16896,
                         13824, 15360, 6144, 0, 0, 0],
}


def _scenario_options_icons():
    from ui.screen_quest import ScenarioOptionsScreen
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScenarioOptionsScreen(dict(_SCENARIO_OPTIONS_ENTRY), dict(_SCENARIO_OPTIONS_DATA),
                              icons=dict(_ICONS_FIXTURE))
    s.draw(hw, _game(), pal)
    return hw, s


def _scenario_options_dropdown():
    # The Difficulty dropdown's option-picker modal, opened over the screen
    # (mirrors _led_modal's "build the modal directly and draw it" shape).
    from ui.screen_quest import ScenarioOptionsScreen, OptionListModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScenarioOptionsScreen(dict(_SCENARIO_OPTIONS_ENTRY), dict(_SCENARIO_OPTIONS_DATA))
    m = OptionListModal(s, "difficulty", "Difficulty", ScenarioOptionsScreen.DIFFICULTY_OPTIONS)
    m.draw(hw, _game(), pal)
    return hw, m


def _elim_modal():
    from ui.modals import EliminationModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.adjust_threat(2, 20)  # 41 + 20 -> crosses 50
    m = EliminationModal(g, 2)
    m.draw(hw, g, pal)
    return hw, m


def _led_modal():
    from ui.modals import LedModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = LedModal({"brightness": 70, "scene": "torch"}, g)
    m.draw(hw, g, pal)
    return hw, m


def _commit_modal():
    from ui.modals import CommitModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    for i, c in enumerate((3, 4, 2, 2)):
        g.set_commit(i, c)
    m = CommitModal(g, 2)
    m.state.tap(2)
    m.draw(hw, g, pal)
    return hw, m


def _reminders_modal():
    from ui.modals import RemindersModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.reminders["archery"] = True
    g.reminders["battle"] = True
    m = RemindersModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _counter():
    from ui.modal_counter import CounterModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    m = CounterModal("P1 threat", 14, icon="threat", subtext="Elimination at 50")
    m.state.tap(5)
    m.draw(hw, None, pal)
    return hw, m


def _log_prep(g):
    for i in range(30):
        g.log_event("P%d threat %d -> %d after a fairly long explanation" % ((i % 4) + 1, 20 + i, 21 + i))


def _sailing_on(g):
    g.sailing = True
    g.heading = 2


def _many_side_sailing(g):
    g.sailing = True
    g.heading = 1
    g.side_quests = [{"points": 4, "progress": 1} for _ in range(8)]


def _resolution_fail(g):
    g.quest_outcome = "fail"
    g.quest_outcome_n = 3


def _players_detail_modal():
    from ui.modals import PlayersDetailModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    for i, c in enumerate((3, 4, 2, 2)):
        g.set_commit(i, c)
    m = PlayersDetailModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _players_detail_edit_modal():
    # Inline +-5 pad sub-state (nested modals aren't supported - see
    # PlayersDetailModal's docstring), reached by tapping a token.
    from ui.modals import PlayersDetailModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = PlayersDetailModal(g)
    m._open_edit(1, "willpower")
    m.edit[2].tap(5)
    m.draw(hw, g, pal)
    return hw, m


def _questing_progress_modal():
    from ui.modals import QuestingProgressModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.sailing = True
    g.heading = 1
    g.side_quests = [{"points": 5, "progress": 2}]
    for wp, st in [(16, 12), (14, 14), (22, 11)]:
        g.resolve_quest(wp, st)
    m = QuestingProgressModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _questing_progress_modal_no_location():
    # No active location and no history yet: "+ Add location" row-slot and
    # the chart's empty-state placeholder (guards the div-by-zero column
    # math when quest_history is empty).
    from ui.modals import QuestingProgressModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.active_location = None
    g.side_quests = []
    g.sailing = False
    m = QuestingProgressModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _questing_progress_modal_loc_choose():
    # In-modal location-remove prompt: the 3-way "choose" stage. Set the
    # state before the (single) draw - FakeDisplay.calls accumulates across
    # draw() calls, so drawing the normal view first would leave stale text
    # in hw.display.calls and produce false-positive collisions.
    from ui.modals import QuestingProgressModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = QuestingProgressModal(g)
    m.loc_prompt = {"stage": "choose"}
    m.draw(hw, g, pal)
    return hw, m


def _questing_progress_modal_loc_pts():
    # Location-remove prompt: "Replaced" -> new quest-points sub-stage.
    from ui.modals import QuestingProgressModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = QuestingProgressModal(g)
    m.loc_prompt = {"stage": "pts", "pts": 3}
    m.draw(hw, g, pal)
    return hw, m


def _questing_progress_modal_loc_contrib():
    # Location-remove prompt: "To staging" -> threat-contribution sub-stage.
    from ui.modals import QuestingProgressModal
    from ui.counter import CounterState
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = QuestingProgressModal(g)
    m.loc_prompt = {"stage": "contrib", "state": CounterState(2, 0, 9)}
    m.draw(hw, g, pal)
    return hw, m


def _sailing_modal():
    from ui.modals import SailingModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.sailing = True
    g.heading = 2
    m = SailingModal(g)
    m.v = 1
    m.draw(hw, g, pal)
    return hw, m


def _stage_complete_modal():
    from ui.modals import StageCompleteModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.pending_stage = {"cleared": "2B", "excess": 2}
    m = StageCompleteModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _quest_config_modal():
    from ui.modals import QuestConfigModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.sailing = True
    m = QuestConfigModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _quest_card_modal():
    # A normal (non-branch) stage with real text on both faces (Foundations
    # of Stone stage 1) - exercises wrapped text in both SIDE A and SIDE B
    # blocks at once, plus the CURRENT marker (opens on the game's own stage).
    from ui.modals import QuestCardModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(4, 25)
    g.preload_scenario(
        {"slug": "foundations-of-stone", "name": "Foundations of Stone",
         "pack": "Foundations of Stone", "cycle": "The Dwarrowdelf", "source": "official",
         "kind": "quest", "nightmare": False, "mode": "Standard"},
        [{"stage": 1, "cards": [{"questPoints": 9, "victory": None, "sailing": False,
            "faces": [{"side": "A", "name": "The Dripping Walls",
                       "text": "Setup: Place the Foundations of Stone encounter set "
                               "aside, out of play. The first player attaches Cave "
                               "Torch to a hero of his choice."},
                      {"side": "B", "name": "The Dripping Walls",
                       "text": "When Revealed: Reveal 1 card from the encounter deck "
                               "per player, and add it to the staging area."}]}]}])
    m = QuestCardModal(g)
    m.draw(hw, g, pal)
    return hw, m


# Passage Through Mirkwood's real 3-stage tree (same source _quest_setup uses
# for stage 1) - shared here so the branch scene shows the actual "A Chosen
# Path" -> "Don't Leave the Path!" / "Beorn's Path" split.
_MIRKWOOD_STAGES = [
    {"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "Flies and Spiders",
                   "text": "Setup: Search the encounter deck for 1 copy of the Forest "
                           "Spider and 1 copy of the Old Forest Road, and add them to "
                           "the staging area. Then, shuffle the encounter deck."},
                  {"side": "B", "name": "Flies and Spiders", "text": None}]}]},
    {"stage": 2, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "A Fork in the Road", "text": None},
                  {"side": "B", "name": "A Fork in the Road",
                   "text": "Forced: When you defeat this stage, proceed to one of "
                           "the 2 \"A Chosen Path\" stages, at random."}]}]},
    {"stage": 3, "branch": "random", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "\"Don't Leave the Path!\"",
                    "text": "When Revealed: Each player must search the encounter "
                            "deck and discard pile for 1 Spider card of his choice, "
                            "and add it to the staging area.  The players must find "
                            "and defeat Ungoliant's Spawn to win this game."}]},
        {"questPoints": 10, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Beorn's Path",
                    "text": "Players cannot defeat this stage while Ungoliant's "
                            "Spawn is in play. If players defeat this stage, they "
                            "have won the game."}]}]},
]


def _quest_card_modal_branch():
    # The branch stage (3 of 3): dual differing B-face names, the alt
    # control, and the "no text" placeholder on side A.
    from ui.modals import QuestCardModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(4, 25)
    g.preload_scenario(
        {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
         "pack": "Core Set", "cycle": "Core Set", "source": "official",
         "kind": "quest", "nightmare": False, "mode": "Standard"},
        _MIRKWOOD_STAGES)
    g.stage_idx = 2
    m = QuestCardModal(g)
    m.draw(hw, g, pal)
    return hw, m


# The two longest real quest-stage texts in the entire built dataset (a full
# docs/data/ scan: 441 real stage/card combinations across 349 scenario
# JSONs), both from Attack on Dol Guldur's stage-3 4-way "choice" branch:
# side F "Battle Under the Trees" (916 chars, the single longest) and side D
# "The Tower of Sorcery" (784 chars, the second-longest anywhere). Quoted
# verbatim - not fabricated copy. In the real data these sit on two
# *different* alternative cards, each independently labelled A/B (DragnCards
# assigns sequential physical-card letters across a branch's alternatives -
# alternative 1 is A/B, alternative 2 is C/D, alternative 3 is E/F, etc.), so
# QuestCardModal's side-"A"/side-"B" face lookup only resolves the first
# alternative (C/D, E/F, G/H never match "A"/"B" literally - a pre-existing
# gap in the Task 1 lookup, out of scope here and flagged separately). To
# actually exercise both SIDE A and SIDE B with real long text at once (the
# worst case for the adaptive line budget), this scene combines both real
# texts onto one synthetic card labelled A/B, with differing 2-line names and
# victory + sailing forced on - the least favorable combination of real
# content this modal can ever be asked to lay out, per the same
# stress-testing approach the Task 1 report used for its own layout budget.
_DOL_GULDUR_D_TEXT = (
    "When Revealed: Remove all tokens from the Lieutenant enemy at this stage and "
    "set it aside, out of play. Add the set aside Sorcerer of Dol Guldur to the "
    "staging area, unless it is in a victory display. If Dol Guldur's city strength "
    "is 5 or lower (10 or lower if playing epic multiplayer mode), Sorcerer of Dol "
    "Guldur makes an immediate attack against each player in turn order.Sorcerer of "
    "Dol Guldur gets -1 engagement cost for each progress token on this stage. "
    "Forced: At the end of the round, remove 5 progress from this stage or each "
    "player at each stage discards all but 1 card from his hand. The first player "
    "may remove an additional 5 progress from this stage to choose a player at any "
    "stage. That player searches his deck for a card, adds it to his hand, and "
    "shuffles his deck.")
_DOL_GULDUR_F_TEXT = (
    "When Revealed: Remove all tokens from the Lieutenant enemy at this stage and "
    "set it aside, out of play. Add the set aside Chieftain Morlug to the staging "
    "area, unless it is in a victory display. If Dol Guldur's city strength is 5 or "
    "lower (10 or lower if playing epic multiplayer mode), Chieftain Morlug makes an "
    "immediate attack against each player in turn order.Chieftain Morlug gets -1 "
    "engagement cost for each progress token on this stage. Forced: At the end of "
    "the round, remove 5 progress from this stage or each player at each stage "
    "discards cards from the top of the encounter deck until an enemy is discarded "
    "and puts it into play engaged with him. (If the last card of the encounter "
    "deck is discarded resolving this effect, shuffle the discard pile back into "
    "the encounter deck.) The first player may remove an additional 5 progress from "
    "this stage to choose a non-unique enemy at any stage and destroy it.")
# The real first alternative of the same branch (side A/B genuinely, no
# relabeling needed) - included as cards[1] purely so len(cards) > 1 and the
# BRANCH row actually renders alongside the dual-long-text card above
# (cards[0], still the one displayed by default at card_idx=0). Both faces'
# real text, quoted verbatim.
_DOL_GULDUR_SIEGE_A_TEXT = (
    "When Revealed: Remove all tokens from the Lieutenant enemy at this stage and "
    "set it aside, out of play. Add the set aside Bane of Amon Lanc to the staging "
    "area, unless it is in a victory display. If Dol Guldur's city strength is 5 or "
    "lower (10 or lower if playing epic multiplayer mode), Bane of Amon Lanc makes "
    "an immediate attack against each player in turn order.")
_DOL_GULDUR_SIEGE_B_TEXT = (
    "When Revealed: Remove all tokens from the Lieutenant enemy at this stage and "
    "set it aside, out of play. Add the set aside Bane of Amon Lanc to the staging "
    "area, unless it is in a victory display. If Dol Guldur's city strength is 5 or "
    "lower (10 or lower if playing epic multiplayer mode), Bane of Amon Lanc makes "
    "an immediate attack against each player in turn order.Bane of Amon Lanc gets "
    "-1 engagement cost for each progress token on this stage. Forced: At the end "
    "of the round, remove 5 progress from this stage or increase Dol Guldur's city "
    "strength by 3. The first player may remove an additional 5 progress to reduce "
    "Dol Guldur's city strength by 3.")


def _quest_card_modal_long_text():
    # Worst case for the adaptive line budget (Task 2 / Part C): dual real
    # long texts (916 + 784 chars, see above) on the displayed card,
    # differing 2-line names, a branch row (a real second alternative), and
    # victory + sailing both forced - the layout must still fit with no
    # overflow/collision, trimming both SIDE A and SIDE B down from their
    # natural (9- and 11-line) wraps to fit the budget.
    from ui.modals import QuestCardModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(4, 25)
    g.preload_scenario(
        {"slug": "attack-on-dol-guldur", "name": "Attack on Dol Guldur",
         "pack": "Attack on Dol Guldur", "cycle": "Standalone/PoD", "source": "official",
         "kind": "quest", "nightmare": False, "mode": "Standard"},
        [{"stage": 3, "branch": "choice", "cards": [
            {"questPoints": 0, "victory": 2, "sailing": True,
             "faces": [{"side": "A", "name": "The Tower of Sorcery", "text": _DOL_GULDUR_D_TEXT},
                       {"side": "B", "name": "Battle Under the Trees", "text": _DOL_GULDUR_F_TEXT}]},
            {"questPoints": 0, "victory": None, "sailing": False,
             "faces": [{"side": "A", "name": "The Siege of Dol Guldur",
                        "text": _DOL_GULDUR_SIEGE_A_TEXT},
                       {"side": "B", "name": "The Siege of Dol Guldur",
                        "text": _DOL_GULDUR_SIEGE_B_TEXT}]},
        ]}])
    m = QuestCardModal(g)
    m.draw(hw, g, pal)
    return hw, m


# The 14 real player side quests (M4-B sidequest, Global Constraints -
# verified against docs/data/players/*.json's cards.sideQuest, 2026-07-24).
# Hardcoded here as a fixture only (never as the runtime source - that's
# quest_catalog.side_quests()'s job); exercises the Up/Down pager (14 at
# PER_PAGE=6 -> 3 pages), the "-" sphere fallback (4 entries have sphere
# None), and the null-questPoints -> 0 default (Protect the Innocent, Rally
# the West) all at once.
_SIDE_QUEST_SAMPLE = [
    {"id": "sq1", "name": "Delay the Enemy", "points": 8, "sphere": "Tactics", "pack": "p"},
    {"id": "sq2", "name": "Double Back", "points": 4, "sphere": "Spirit", "pack": "p"},
    {"id": "sq3", "name": "Explore Secret Ways", "points": 6, "sphere": "Lore", "pack": "p"},
    {"id": "sq4", "name": "Fend Off Despair", "points": 8, "sphere": None, "pack": "p"},
    {"id": "sq5", "name": "Gather Information", "points": 4, "sphere": "Neutral", "pack": "p"},
    {"id": "sq6", "name": "Keep Watch", "points": 6, "sphere": "Tactics", "pack": "p"},
    {"id": "sq7", "name": "Loot the Dungeons", "points": 4, "sphere": None, "pack": "p"},
    {"id": "sq8", "name": "Mysterious Omens", "points": 9, "sphere": None, "pack": "p"},
    {"id": "sq9", "name": "Prepare for Battle", "points": 6, "sphere": "Leadership", "pack": "p"},
    {"id": "sq10", "name": "Protect the Innocent", "points": 0, "sphere": None, "pack": "p"},
    {"id": "sq11", "name": "Rally the West", "points": 0, "sphere": "Spirit", "pack": "p"},
    {"id": "sq12", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"},
    {"id": "sq13", "name": "Send for Aid", "points": 6, "sphere": "Leadership", "pack": "p"},
    {"id": "sq14", "name": "The Storm Comes", "points": 5, "sphere": "Neutral", "pack": "p"},
]


def _side_quest_pick():
    from ui.modals import SideQuestPickModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = SideQuestPickModal(g, list(_SIDE_QUEST_SAMPLE))
    m.draw(hw, g, pal)
    return hw, m


def _side_quest_pick_empty():
    # No catalog data (matches load_player_side_quests()'s [] failure
    # fallback shape) - must render gracefully and still offer Manual.
    from ui.modals import SideQuestPickModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = SideQuestPickModal(g, [])
    m.draw(hw, g, pal)
    return hw, m


def _quest_card_modal_tips():
    # Tips view open (M4-B tips): a stage-specific note ranked before the
    # scenario-wide general notes, attribution name + URL visible beneath -
    # same passage-through-mirkwood branch-stage fixture as
    # _quest_card_modal_branch (stage 3 of 3), so this doubles as a visual
    # check that the tips panel replaces the SIDE A/B blocks cleanly without
    # disturbing the header/stat-strip/branch row above it or the
    # button/pager below it. The three "general" strings are the real
    # tools/build_tips.py output for this scenario (see the Task 1 report);
    # "stages" is a synthetic stand-in - the automated build only populates
    # "general" today (see build_tips.py's module docstring).
    from ui.modals import QuestCardModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(4, 25)
    g.preload_scenario(
        {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
         "pack": "Core Set", "cycle": "Core Set", "source": "official",
         "kind": "quest", "nightmare": False, "mode": "Standard"},
        _MIRKWOOD_STAGES)
    g.stage_idx = 2
    tips = {"passage-through-mirkwood": {
        "attribution": {"name": "Vision of the Palantir",
                         "url": "https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/"},
        "general": ["Avoid: bother with easy mode.",
                    "Stay under 40 threat - avoid Hummerhorns.",
                    "Avoid: take undefended attacks."],
        "stages": {"3": ["Beorn's Path cannot be defeated while Ungoliant's Spawn is in play."]},
    }}
    m = QuestCardModal(g, tips=tips)
    m.tips_open = True   # set state directly, not via on_button - a second
                          # draw() on the same FakeHardware would accumulate
                          # both views' text calls into one collision check
    m.draw(hw, g, pal)
    return hw, m


def _quest_card_modal_empty():
    # Custom game: no scenario preloaded, game.stages == [] - the modal must
    # render a graceful placeholder rather than raise.
    from ui.modals import QuestCardModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(2, 25)
    m = QuestCardModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_game(flip=True):
    # Shared base for every ResolutionModal scene below: Passage Through
    # Mirkwood's real 3-stage tree (same _MIRKWOOD_STAGES the QuestCardModal
    # branch/tips scenes above use) - stage 1 "Flies and Spiders" (8qp, real
    # setup text), stage 2 "A Fork in the Road" (2qp, single card - no branch
    # in the way), stage 3 the real random branch ("Don't Leave the Path!"
    # 0qp / "Beorn's Path" 10qp). flip=False leaves stage 1 on side A (pre-
    # round-1), the precondition the "reveal" step scene wants.
    g = GameState(4, 25)
    g.preload_scenario(
        {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
         "pack": "Core Set", "cycle": "Core Set", "source": "official",
         "kind": "quest", "nightmare": False, "mode": "Standard"},
        _MIRKWOOD_STAGES)
    if flip:
        g.flip_to_b()
    return g


def _resolution_reveal():
    # "reveal" step: stage 1A's real setup text (Flies and Spiders) - the
    # same source text the quest_setup scene shows, so this doubles as a
    # visual parity check against ScreenPlay's own scroll-tip look.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game(flip=False)
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_location():
    # "location" step: active location 1 progress over its 2 points - the
    # excess (1) will be credited to the quest card on Continue.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    g.active_location = {"points": 2, "progress": 3}
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_branch():
    # "branch" step: stage 3's real random 2-way split ("Don't Leave the
    # Path!" 0qp / "Beorn's Path" 10qp) - exercises the Randomize button
    # (mode "random") alongside the two picker rows.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    g.stage_idx = 1
    g.quest.update({"stage_n": 2, "side": "B", "points": 2, "progress": 2})
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_advance():
    # "advance" step: stage 1 cleared exactly on target (8/8) -> stage 2
    # ("A Fork in the Road", a single card - no branch step in the way).
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    g.quest["progress"] = 8
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_advance_underfilled():
    # "advance" step reached via force_advance (the quest row's chevron,
    # Task 3) without the numeric target actually met - the underfilled
    # caution banner.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    g.quest["progress"] = 3   # 8 needed
    m = ResolutionModal(g, force_advance=True)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_victory():
    # "victory" step: stage 3 (the final catalogued stage) cleared - no next
    # stage to advance to.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    g.stage_idx = 2
    g.card_idx = 1
    g.quest.update({"stage_n": 3, "side": "B", "points": 10, "progress": 10})
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_side_quest():
    # "side_quest" step: one side quest at target, one still short - only
    # the completed one is offered.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    g.side_quests = [{"points": 4, "progress": 4, "name": "Gather Information"},
                      {"points": 6, "progress": 2, "name": "Scout Ahead"}]
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _resolution_done():
    # None step: nothing over target anywhere - the plain "All resolved"
    # confirmation.
    from ui.modals import ResolutionModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _resolution_game()
    m = ResolutionModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _gameover(result):
    def build():
        from ui.screen_gameover import GameOverScreen
        hw = FakeHardware()
        pal = Palette(hw.display)
        g = _game()
        g.game_over = {"result": result, "round": g.round, "duration": "12m30s"}
        if result == "defeat":
            for p in g.players:
                p.eliminated = True
        s = GameOverScreen()
        s.draw(hw, g, pal)
        return hw, s
    return build


def _about():
    from ui.screen_about import ScreenAbout
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScreenAbout()
    s.draw(hw, _game(), pal)
    return hw, s


SCENES = {
    "boot": _boot({"round": 3, "phase": "Combat (Enemy Attacks)", "saved_at": "2026-07-21 19:04"}),
    "boot_fresh": _boot(None),
    "setup": _setup([25]),
    "setup3": _setup([25, 27, 29], first=1),
    "setup4": _setup([25, 27, 29, 31], first=3),
    "play_setup": _play("setup_game"),
    "play_setup_sailing": _play("setup_game", mutate=_sailing_on),
    "play_resource_planning": _play("resource_planning"),
    "play_quest_sailing": _play("quest_sailing", mutate=_sailing_on),
    "play_quest_commit": _play("quest_commit"),
    "play_quest_commit_sailing": _play("quest_commit", mutate=_sailing_on),
    "play_quest_commit_manyside": _play("quest_commit", mutate=_many_side_sailing),
    "play_quest_staging": _play("quest_staging"),
    "play_quest_resolution": _play("quest_resolution"),
    "play_quest_resolution_fail": _play("quest_resolution", mutate=_resolution_fail),
    "play_travel": _play("travel"),
    "play_travel_none": _play("travel", mutate=lambda g: setattr(g, "active_location", None)),
    "play_enc_optional": _play("enc_optional"),
    "play_enc_checks": _play("enc_checks"),
    "play_combat_shadow": _play("combat_shadow"),
    "play_combat_enemy": _play("combat_enemy"),
    "play_combat_player": _play("combat_player"),
    "play_refresh": _play("refresh"),
    "quest_setup": _quest_setup,
    "scenario_source": _scenario_source,
    "pick_cycle": _pick_cycle,
    "pick_cycle_empty": _pick_cycle_empty,
    "choose_scenario": _choose_scenario,
    "scenario_options_std": _scenario_options("Standard", "Normal"),
    "scenario_options_easy": _scenario_options("Easy", "Normal"),
    "scenario_options_nm": _scenario_options("Standard", "Nightmare"),
    "scenario_options_dropdown": _scenario_options_dropdown,
    "scenario_options_icons": _scenario_options_icons,
    "scenario_options_no_enrichment": _scenario_options_no_enrichment,
    "phases_screen": _screen("ui.screen_phases", "ScreenPhases"),
    "log": _screen("ui.screen_log", "ScreenLog", prep=_log_prep),
    "settings": _screen("ui.screen_settings", "ScreenSettings"),
    "counter": _counter,
    "elim_modal": _elim_modal,
    "commit_modal": _commit_modal,
    "players_detail_modal": _players_detail_modal,
    "players_detail_edit_modal": _players_detail_edit_modal,
    "reminders_modal": _reminders_modal,
    "led_modal": _led_modal,
    "questing_progress_modal": _questing_progress_modal,
    "questing_progress_modal_no_location": _questing_progress_modal_no_location,
    "questing_progress_modal_loc_choose": _questing_progress_modal_loc_choose,
    "questing_progress_modal_loc_pts": _questing_progress_modal_loc_pts,
    "questing_progress_modal_loc_contrib": _questing_progress_modal_loc_contrib,
    "side_quest_pick": _side_quest_pick,
    "side_quest_pick_empty": _side_quest_pick_empty,
    "sailing_modal": _sailing_modal,
    "stage_complete_modal": _stage_complete_modal,
    "resolution_reveal": _resolution_reveal,
    "resolution_location": _resolution_location,
    "resolution_branch": _resolution_branch,
    "resolution_advance": _resolution_advance,
    "resolution_advance_underfilled": _resolution_advance_underfilled,
    "resolution_victory": _resolution_victory,
    "resolution_side_quest": _resolution_side_quest,
    "resolution_done": _resolution_done,
    "quest_config_modal": _quest_config_modal,
    "quest_card_modal": _quest_card_modal,
    "quest_card_modal_branch": _quest_card_modal_branch,
    "quest_card_modal_long_text": _quest_card_modal_long_text,
    "quest_card_modal_tips": _quest_card_modal_tips,
    "quest_card_modal_empty": _quest_card_modal_empty,
    "gameover_victory": _gameover("victory"),
    "gameover_defeat": _gameover("defeat"),
    "about": _about,
}
