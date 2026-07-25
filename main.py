"""Entry point: boot flow (resume/new), header-nav screens, modal loop, autosave.

Navigation: no tab bar. The header is the nav — tap Round -> Log, tap the
phase name -> Phases, tap Set. -> Settings. Boot offers resume/new; new game
runs the setup screen (players / starting threat / elimination level).
"""

import json
import time

import hardware
import leds
import phases
from gamestate import GameState
from ui.header import VIEW_LABEL
from ui.theme import Palette
from ui.screen_play import ScreenPlay
from ui.screen_phases import ScreenPhases
from ui.screen_log import ScreenLog
from ui.screen_settings import ScreenSettings
from ui.screen_boot import BootScreen
from ui.screen_setup import SetupScreen
from ui.screen_gameover import GameOverScreen
from ui.screen_about import ScreenAbout
from ui.screen_firstrun import FirstRunScreen, LegendScreen
from ui.screen_quest import (ScenarioSourceScreen, PickCycleScreen,
                              ChooseScenarioScreen, ScenarioOptionsScreen)
import quest_catalog

STATE_PATH = "/state.json"
PREFS_PATH = "/device.json"
DEFAULT_PREFS = {"brightness": 100, "scene": "phase"}

# Pre-game screens with no live game to animate: LED/notification/elimination
# per-tick housekeeping (below) is skipped while any of these is active.
PREGAME_ACTIVE = ("boot", "setup", "scenario_source", "pick_cycle",
                  "choose_scenario", "scenario_options", "firstrun", "legend")


def load_prefs():
    try:
        with open(PREFS_PATH) as f:
            d = json.load(f)
        return {"brightness": d.get("brightness", 100),
                "scene": d.get("scene", "phase")}
    except Exception:
        return dict(DEFAULT_PREFS)


def save_prefs(prefs):
    try:
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f)
    except Exception:
        pass


def load_saved():
    """Return (game, meta) or (None, None)."""
    try:
        with open(STATE_PATH) as f:
            d = json.load(f)
        game = GameState.from_dict(d["state"])
        t = d.get("saved_at")
        if t:
            lt = time.localtime(t)
            when = "%04d-%02d-%02d %02d:%02d" % (lt[0], lt[1], lt[2], lt[3], lt[4])
            if lt[0] < 2024:  # RTC not set — wall time unknown
                when = "earlier session"
        else:
            when = "earlier session"
        meta = {"round": game.round,
                "phase": VIEW_LABEL.get(game.view,
                                        phases.step(game.step)["phase"]),
                "saved_at": when}
        return game, meta
    except Exception:
        return None, None


def save_state(game):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump({"saved_at": time.time(), "state": game.to_dict()}, f)
    except Exception:
        pass


def save_exists():
    try:
        import os
        os.stat(STATE_PATH)
        return True
    except Exception:
        return False


def clear_state():
    try:
        import os
        os.remove(STATE_PATH)
    except Exception:
        pass


def press_feedback(hw, pal, b):
    """Video-game button press: invert the bevel edges for ~90 ms."""
    d = hw.display
    t = 2
    d.set_pen(pal.bevel_d)
    d.rectangle(b.x, b.y, b.w, t)
    d.rectangle(b.x, b.y, t, b.h)
    d.set_pen(pal.bevel_l)
    d.rectangle(b.x, b.y + b.h - t, b.w, t)
    d.rectangle(b.x + b.w - t, b.y, t, b.h)
    hw.partial_update(b.x, b.y, b.w, b.h)
    time.sleep(0.09)


def update_leds(hw, game, prefs, tick=0):
    summary = {"step": game.step,
               "players": [{"threat": p.threat, "eliminated": p.eliminated}
                           for p in game.players]}
    leds.apply_scene(hw, prefs["scene"], summary, prefs["brightness"], tick)


def main():
    hw = hardware.Hardware()
    pal = Palette(hw.display)

    saved_game, saved_meta = load_saved()
    game = saved_game if saved_game else GameState()
    clock = getattr(time, "ticks_ms", None) or (lambda: int(time.time() * 1000))
    game.clock = clock
    prefs = load_prefs()

    screens = {
        "play": ScreenPlay(),
        "phases": ScreenPhases(),
        "log": ScreenLog(),
        "settings": ScreenSettings(prefs),
        "boot": BootScreen(saved_meta),
        "setup": SetupScreen(),
        "gameover": GameOverScreen(),
        "about": ScreenAbout(),
        "firstrun": FirstRunScreen(),
        "legend": LegendScreen(),
        "scenario_source": ScenarioSourceScreen(),
        "pick_cycle": PickCycleScreen("official", []),
        "choose_scenario": ChooseScenarioScreen("official", "", []),
        "scenario_options": ScenarioOptionsScreen({}, {}),
    }
    active = "boot"
    nav_stack = []  # origins to return to when overlay screens (log/settings) close
    modal = None
    dirty = True
    catalog_index = None  # cached quest_catalog.load_index() result (fetched once)
    catalog_icons = None  # cached quest_catalog.load_icons() result (fetched once;
                           # load_icons() never raises, so no try/except needed)
    catalog_tips = None    # cached quest_catalog.load_tips() result (M4-B tips;
                            # never raises either - lazily loaded both when entering
                            # the picker AND right before each QuestCardModal is
                            # built, so a resumed game that skipped the picker this
                            # session still gets tips - see the two "if catalog_tips
                            # is None" sites below)

    tick = 0
    torch_t = 0
    prev_view = game.view
    NOTIF_TICKS = 200  # ~4 s at the 0.02 s loop sleep
    notif_t = 0

    while True:
        # reminder notifications fire when the play view changes
        if game.view != prev_view:
            prev_view = game.view
            msgs = [(ic, t, "amber") for ic, t in game.due_notifications()]
            if game.action_window_open():
                msgs.append(("LEADERSHIP", "Action Window", "purple"))
            if msgs:
                screens["play"].notif = msgs
                screens["play"].notif_frac = 1.0
                notif_t = NOTIF_TICKS
                dirty = True
        # a requested toast (e.g. quest-resolution outcome) overrides view notifs
        if screens["play"].toast:
            screens["play"].notif = screens["play"].toast
            screens["play"].notif_frac = 1.0
            notif_t = NOTIF_TICKS
            screens["play"].toast = None
            dirty = True
        if notif_t > 0:
            notif_t -= 1
            play = screens["play"]
            if play.notif is None:
                notif_t = 0  # dismissed by tap
            elif notif_t == 0:
                play.notif = None
                dirty = True
            elif notif_t % 10 == 0 and not dirty and modal is None \
                    and active == "play" and play.notif_pie:
                play.notif_frac = notif_t / NOTIF_TICKS
                cx, cy, r = play.notif_pie
                from ui.screen_play import draw_notif_pie
                draw_notif_pie(hw.display, pal, cx, cy, r, play.notif_frac,
                               play.notif_edge)
                hw.partial_update(cx - r - 2, cy - r - 2, 2 * r + 4, 2 * r + 4)

        if dirty:
            if modal is not None:
                modal.draw(hw, game, pal)
            else:
                screens[active].draw(hw, game, pal)
                if active not in PREGAME_ACTIVE:
                    update_leds(hw, game, prefs, tick)
            hw.update()
            dirty = False

        # torchlight flickers ~5x/sec without needing a redraw
        if prefs["scene"] == "torch" and active not in PREGAME_ACTIVE:
            torch_t += 1
            if torch_t >= 10:  # ~0.2 s at the 0.02 s loop sleep
                torch_t = 0
                tick += 1
                update_leds(hw, game, prefs, tick)

        # a threat change crossed someone's elimination level -> confirm
        if modal is None and active not in PREGAME_ACTIVE \
                and game.pending_elim is not None:
            from ui.modals import EliminationModal
            modal = EliminationModal(game, game.pending_elim)
            dirty = True
            continue

        # Progress-detail quest-row tap (second QuestCardModal entry point):
        # the router replaces one modal at a time, so QuestingProgressModal's
        # on_button closed itself and flagged this instead of returning a
        # modal transition directly - open the card modal now that modal is
        # None.
        if modal is None and active == "play" and game.pending_quest_card:
            from ui.modals import QuestCardModal
            game.pending_quest_card = False
            if catalog_tips is None:
                catalog_tips = quest_catalog.load_tips()
            modal = QuestCardModal(game, tips=catalog_tips)
            dirty = True
            continue

        # Manual progress-edit overflow (QuestingProgressModal close, or the
        # quest row's "Advance" icon): same pending-flag pattern as
        # pending_quest_card above - the modal that detected it had to
        # close first (router holds one modal at a time).
        if modal is None and active == "play" and game.pending_resolution:
            forced = game.pending_resolution == "forced"
            game.pending_resolution = False
            if game.stages:
                from ui.modals import ResolutionModal
                modal = ResolutionModal(game, force_advance=forced)
            else:
                excess = max(0, game.quest["progress"] - game.quest["points"]) \
                    if game.quest["points"] > 0 else 0
                game.pending_stage = {"cleared": game.quest_label(), "excess": excess}
                from ui.modals import StageCompleteModal
                modal = StageCompleteModal(game)
            dirty = True
            continue

        # Progress-detail "+ Side quest" tap (SideQuestPickModal entry
        # point): same pending-flag pattern as pending_quest_card above -
        # the picker needs a catalog read (flash I/O) that
        # QuestingProgressModal.on_button can't do mid-tap without breaking
        # the modal-replaces-modal invariant, so it flags this instead and
        # the read happens here, once modal is None. A missing/unreadable
        # catalog (load_player_side_quests() returns []) skips the picker
        # and keeps today's direct-append behavior instead of showing an
        # empty list.
        if modal is None and active == "play" and game.pending_side_quest_pick:
            game.pending_side_quest_pick = False
            entries = quest_catalog.load_player_side_quests()
            if entries:
                from ui.modals import SideQuestPickModal
                modal = SideQuestPickModal(game, entries)
            else:
                game.side_quests.append({"points": 4, "progress": 0})
                game.log_event("Side quest %d added (progress view)" % len(game.side_quests))
                save_state(game)
            dirty = True
            continue

        # game over: all players eliminated -> defeat (victory is set via the
        # stage-complete modal). Route to the game-over screen from play.
        if modal is None and active == "play" and not game.game_over \
                and game.players and game.all_eliminated():
            game.set_game_over("defeat")
        if modal is None and active == "play" and game.game_over:
            active = "gameover"
            dirty = True
            continue

        hw.poll()
        if hw.clicked:
            x, y = hw.click_x, hw.click_y

            if modal is not None:
                for b in modal.buttons:
                    if b.hit(x, y):
                        press_feedback(hw, pal, b)
                        result = modal.on_button(b)
                        if result == "close":
                            from ui.modals import LedModal
                            if isinstance(modal, LedModal):
                                save_prefs(prefs)
                            else:
                                save_state(game)
                            modal = None
                        elif result == "cancel":
                            modal = None
                        dirty = True
                        break
                time.sleep(0.02)
                continue

            for b in screens[active].buttons:
                if b.hit(x, y):
                    press_feedback(hw, pal, b)
                    result = screens[active].on_button(b, game)
                    if isinstance(result, tuple):
                        kind = result[0]
                        if kind == "goto":
                            target = result[1]
                            if target == "close":
                                target = nav_stack.pop() if nav_stack else "play"
                            elif target in ("settings", "log", "phases",
                                            "firstrun", "legend"):
                                if active != target:
                                    nav_stack.append(active)
                            else:
                                nav_stack = []  # direct nav resets the trail
                            active = target
                        elif kind == "modal":
                            modal = result[1]
                            # Quest Setup button (first QuestCardModal entry
                            # point): screen_play.py builds the modal itself
                            # (it can't await a flash read mid-tap either -
                            # see pending_quest_card above), so tips are
                            # attached here instead of at construction.
                            from ui.modals import QuestCardModal
                            if isinstance(modal, QuestCardModal):
                                if catalog_tips is None:
                                    catalog_tips = quest_catalog.load_tips()
                                modal.tips = catalog_tips
                        elif kind == "boot":
                            if result[1] == "resume":
                                active = "play"
                            elif result[1] == "about":
                                nav_stack.append("boot")
                                active = "about"
                            else:
                                screens["setup"].has_save = save_exists()
                                active = "setup"
                        elif kind == "open_repo":
                            pass  # no browser on the device; link lives in the web twin
                        elif kind == "start_game":
                            threats = result[1]
                            first = result[2] if len(result) > 2 else 0
                            clear_state()
                            game = GameState(player_count=len(threats))
                            for i, t in enumerate(threats):
                                game.players[i].threat = t
                                game.players[i].starting_threat = t
                            game.first_player = first
                            game.clock = clock
                            game.log_event("New game: %d players, threat %s, first P%d"
                                           % (len(threats),
                                              "/".join(str(t) for t in threats),
                                              first + 1))
                            save_state(game)
                            active = "scenario_source"
                        elif kind == "choose_scenario":
                            # Official/Community gate tapped: load (and cache)
                            # the whole catalog index, then show that
                            # source's cycle list. A missing/unreadable
                            # catalog (e.g. no data deploy yet) falls back to
                            # the custom/manual flow rather than crashing the
                            # device loop.
                            source = result[1]
                            try:
                                if catalog_index is None:
                                    catalog_index = quest_catalog.load_index()
                            except Exception as e:
                                print("quest catalog: load_index failed (%r) "
                                      "- falling back to custom quest" % (e,))
                                game.log_event(
                                    "Quest catalog unavailable - continuing "
                                    "with custom/manual setup")
                                game.scenario = None
                                game.view = "setup_game"
                                active = "play"
                                save_state(game)
                            else:
                                if catalog_icons is None:
                                    catalog_icons = quest_catalog.load_icons()
                                if catalog_tips is None:
                                    catalog_tips = quest_catalog.load_tips()
                                cycles = quest_catalog.cycles_for(catalog_index, source)
                                screens["pick_cycle"] = PickCycleScreen(source, cycles)
                                active = "pick_cycle"
                        elif kind == "choose_scenario_list":
                            source, cycle = result[1], result[2]
                            groups = quest_catalog.group_by_cycle(
                                catalog_index.get("scenarios", []), source)
                            group = next((g for g in groups if g["cycle"] == cycle), None)
                            screens["choose_scenario"] = ChooseScenarioScreen(
                                source, cycle, group["scenarios"] if group else [])
                            active = "choose_scenario"
                        elif kind == "goto_pick_cycle":
                            active = "pick_cycle"
                        elif kind == "scenario_chosen":
                            # Load this one scenario's stage/card data. Kept
                            # separate from the load_index() fallback above:
                            # the whole catalog loaded fine to get here, so a
                            # single missing/corrupt scenario file just stays
                            # on the chooser rather than derailing the game.
                            slug = result[1]
                            try:
                                data = quest_catalog.load_scenario(slug)
                            except Exception as e:
                                print("quest catalog: load_scenario(%r) failed "
                                      "(%r) - staying on chooser" % (slug, e))
                            else:
                                entry = next((s for s in catalog_index.get("scenarios", [])
                                             if s["slug"] == slug), None) or {}
                                screens["scenario_options"] = ScenarioOptionsScreen(
                                    entry, data, catalog_icons)
                                active = "scenario_options"
                        elif kind == "begin_setup":
                            # One picker now: Nightmare is a rung on the
                            # difficulty ladder, not a separate Mode.
                            difficulty = result[1]
                            opts = screens["scenario_options"]
                            scn = opts.scenario
                            scenario_meta = {
                                "slug": scn.get("slug"), "name": scn.get("name"),
                                "pack": scn.get("pack"), "cycle": scn.get("cycle"),
                                "source": scn.get("source"), "kind": scn.get("kind"),
                                "nightmare": difficulty == "Nightmare",
                                "mode": difficulty,
                            }
                            stages = opts.data.get("quest", {}).get("stages", [])
                            game.preload_scenario(scenario_meta, stages)
                            game.view = "quest_setup"
                            active = "play"
                            save_state(game)
                        elif kind == "start_custom":
                            game.scenario = None
                            game.view = "setup_game"
                            active = "play"
                        elif kind == "save_quit":
                            save_state(game)
                            _, meta = load_saved()
                            screens["boot"] = BootScreen(meta)
                            nav_stack = []
                            active = "boot"
                        elif kind == "end_game":
                            clear_state()
                            game = GameState()
                            game.clock = clock
                            screens["boot"] = BootScreen(None)
                            nav_stack = []
                            active = "boot"
                    elif result:
                        save_state(game)
                    dirty = True
                    break
        time.sleep(0.02)


main()
