"""Entry point: boot flow (resume/new), header-nav screens, modal loop, autosave.

Navigation: no tab bar. The header is the nav — tap Round -> Log, tap the
phase name -> Phases, tap Set. -> Settings. Boot offers resume/new; new game
runs the setup screen (players / starting threat / elimination level).
"""

import time

import db as dbmod
import gamestate
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
                              ChooseScenarioScreen, ScenarioOptionsScreen, CatalogUnavailableScreen)
import quest_catalog

# Every path, cache and durability rule lives in db.py - the single place the
# firmware touches storage (enforced by tests/test_no_stray_io.py).
db = dbmod.DataClient()

# Pre-game screens with no live game to animate: LED/elimination per-tick
# housekeeping (below) is skipped while any of these is active.
PREGAME_ACTIVE = ("boot", "setup", "scenario_source", "pick_cycle",
                  "choose_scenario", "scenario_options", "firstrun", "legend")


def _rehydrate_pickers(screens, game, catalog_index, catalog_icons):
    """Rebuild the quest-picker screens from a resumed game's saved scenario.

    The picker screens are router-held, not game state, so a resume left them
    as the empty placeholders the boot path constructed. Everything needed is
    already in the save (`game.scenario` carries slug/source/cycle and the
    chosen `mode`), so this reads it back and rebuilds all three - Scenario
    Options for the scenario itself, and the two list screens behind it so
    backing out further lands on a populated page with the right cycle
    selected, not on an empty list.

    Lazy on purpose, at the first tap that needs a picker rather than during
    resume: reading index.json off flash is the slowest thing the device does,
    and the boot path already defers every catalog read this way (see the
    catalog_tips note above). A resume that never backs out never pays for it.

    Returns the (possibly newly loaded) catalog caches so the caller can keep
    them. Never raises: a failure just leaves the placeholders in place and
    the caller falls back to the source page.
    """
    try:
        if catalog_index is None:
            catalog_index = db.index()
        state = quest_catalog.resume_picker_state(catalog_index, game.scenario)
        if state is None:
            return catalog_index, catalog_icons
        if catalog_icons is None:
            catalog_icons = db.icons()
        data = db.scenario(state["entry"]["slug"])
        screens["pick_cycle"] = PickCycleScreen(state["source"], state["cycles"])
        chooser = ChooseScenarioScreen(state["source"], state["cycle"],
                                       state["siblings"])
        # Land on the scenario the game is actually playing, not the first row.
        chooser.selected = state["entry"]["slug"]
        screens["choose_scenario"] = chooser
        screens["scenario_options"] = ScenarioOptionsScreen(
            state["entry"], data, catalog_icons, state["difficulty"])
    except Exception as e:
        print("resume: could not rebuild the picker screens (%r)" % e)
    return catalog_index, catalog_icons


def _rehydrate_stages(game):
    """Re-read a resumed game's stage tree from the catalog.

    The save carries the scenario's SLUG, not its cards (see
    GameState.to_dict). This is where the assets come back, so a card-data
    correction reaches a game already in progress instead of stopping at the
    save boundary.

    Best-effort by design: a custom game has no scenario, a slug can go
    missing from the catalog, and flash reads fail. Any of those leaves
    whatever from_dict loaded - an old save's embedded copy, or nothing - and
    the game still plays.
    """
    slug = (game.scenario or {}).get("slug")
    if not slug:
        return False
    try:
        data = db.scenario(slug)
        stages = ((data or {}).get("quest") or {}).get("stages") or []
    except Exception:
        return False
    return game.rehydrate_stages(stages)


def load_saved():
    """Return (game, meta) or (None, None). The read itself is db.py's; this
    owns the rehydration and the boot-subtitle formatting."""
    try:
        d = db.session.load_state()
        if d is None:
            return None, None
        game = GameState.from_dict(d["state"])
        # A save with no scenario is from the removed manual/custom mode.
        # There is no view to resume it into, so it is not offered.
        if not (game.scenario or {}).get("slug"):
            return None, None
        _rehydrate_stages(game)
        t = d.get("saved_at")
        if t:
            lt = time.localtime(t)
            # 12-hour with AM/PM, and a 2-digit year: the boot subtitle has a
            # 280px button to live in, and this is a "when did I last play"
            # glance, not a log stamp. Format is duplicated verbatim in
            # docs/js/main.js rather than left to toLocaleString, so both
            # twins read identically.
            hour = lt[3] % 12 or 12
            when = "%d/%d/%02d %d:%02d %s" % (lt[1], lt[2], lt[0] % 100, hour,
                                              lt[4], "AM" if lt[3] < 12 else "PM")
            if lt[0] < 2024:  # RTC not set — wall time unknown
                when = "earlier session"
        else:
            when = "earlier session"
        meta = {"round": game.round, "step": game.step, "saved_at": when}
        return game, meta
    except Exception:
        return None, None


# How long the pressed bevel stays lit. Was 90 ms, chosen when the hold was
# hiding a ~50 ms flash write; with the write off the tap path and the
# repaint down to ~37 ms, 90 ms was most of the felt latency and read as lag
# rather than as feedback. 30 ms still registers as a press.
PRESS_MS = 30
# ticks_ms/ticks_diff are MicroPython-only; the fallbacks keep this importable
# on the host (same guard style as the `clock` binding in main()).
_ticks = getattr(time, "ticks_ms", None) or (lambda: int(time.time() * 1000))
_ticks_diff = getattr(time, "ticks_diff", None) or (lambda a, b: a - b)


def press_begin(hw, pal, b):
    """Video-game button press: invert the bevel edges, and START the press
    clock. Returns the start tick for press_end.

    Split from the old single press_feedback() because those 90 ms were spent
    asleep BEFORE the handler ran, and then the handler's flash write was added
    on top. A durable small write costs ~50 ms on this board (measured, and
    flat regardless of file size), so running the handler INSIDE the press
    window makes it free: the button was going to stay lit that long anyway.
    """
    d = hw.display
    t = 2
    d.set_pen(pal.bevel_d)
    d.rectangle(b.x, b.y, b.w, t)
    d.rectangle(b.x, b.y, t, b.h)
    d.set_pen(pal.bevel_l)
    d.rectangle(b.x, b.y + b.h - t, b.w, t)
    d.rectangle(b.x + b.w - t, b.y, t, b.h)
    hw.partial_update(b.x, b.y, b.w, b.h)
    return _ticks()


def press_end(t0):
    """Hold the pressed bevel for whatever is LEFT of PRESS_MS after the
    handler has already run. Zero if it overran."""
    left = PRESS_MS - _ticks_diff(_ticks(), t0)
    if left > 0:
        time.sleep(left / 1000.0)


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
    if saved_game:
        db.session.load_replay(game)
        db.session.load_log(game)

    # -- the record point ---------------------------------------------------
    # One snapshot before a tap is dispatched, one diff after it settles -
    # mirroring the reference's single process_update call site
    # (game_ui_server.ex). No screen, modal or mutator learns anything about
    # undo.
    #
    # pending[1] guards the handlers that REPLACE `game` (new game, end game):
    # a delta diffed against a snapshot of a different object would be
    # garbage, so those paths record nothing. `game` is read from the
    # enclosing scope, so these see every rebinding below.
    pending = [None, None]        # [snapshot, the game object it came from]

    def begin_action():
        pending[0] = game.begin_action()
        pending[1] = game

    def commit_action():
        # Each of the three stores writes only what this action touched, and
        # each is a no-op when that is nothing. A durable write is ~50 ms flat
        # on this board, so the 90 ms press window has room for about one -
        # which is why none of these may be a whole-file rewrite.
        if pending[0] is not None and pending[1] is game:
            game.add_delta(pending[0])
        pending[0] = pending[1] = None
        db.session.commit(game)

    prefs = db.load_prefs()

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
    catalog_index = None  # db.index() result, held so the screens can share it
    catalog_icons = None  # cached db.icons() result (fetched once;
                           # load_icons() never raises, so no try/except needed)
    catalog_tips = None    # cached db.tips() result (M4-B tips;
                            # never raises either - lazily loaded both when entering
                            # the picker AND right before each QuestCardModal is
                            # built, so a resumed game that skipped the picker this
                            # session still gets tips - see the two "if catalog_tips
                            # is None" sites below)
    catalog_locations = None   # db.locations() result for
                               # the picked scenario (never raises either). Loaded
                               # on the first Travel / "+ Add location" tap and kept
                               # for the game - the picked scenario cannot change
                               # mid-game, and a cold union is several file reads.

    tick = 0
    torch_t = 0
    # A finished game is appended to history once, not on every
    # frame the game-over screen is up. Reset wherever `game` is
    # rebound (new game / end game).
    recorded_game_over = False
    prev_view = game.view

    while True:
        # A view change no longer raises anything: the timed notification
        # overlay and the quest-outcome toast are gone. Contextual, per-stage
        # reminders will live in the phase content areas instead.
        if game.view != prev_view:
            prev_view = game.view

        # Pending-modal resolution runs BEFORE the draw. A modal that wants
        # to hand off to another one closes itself and raises a flag (the
        # router holds one modal at a time), so if these ran after the draw
        # the play screen would paint for one frame in between - a visible
        # flash when you tap "+ Side quest" from the Progress modal.
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
                catalog_tips = db.tips()
            modal = QuestCardModal(game, tips=catalog_tips)
            dirty = True
            continue

        # The Progress modal's History button: a screen, not a modal, so the
        # nav happens here once the modal is gone.
        if modal is None and active == "play" and game.pending_progress_history:
            game.pending_progress_history = False
            active = "log"
            dirty = True
            continue

        # The Progress modal's Quest row: open the quest editor.
        if modal is None and active == "play" and game.pending_quest_config:
            from ui.modals import QuestConfigModal
            game.pending_quest_config = False
            game.pending_progress_detail = True
            modal = QuestConfigModal(game)
            dirty = True
            continue

        # The Progress modal's Location row: open the location's detail sheet.
        # Reopening Progress afterwards is what pending_progress_detail already
        # does for the location picker, so the player lands back where they
        # tapped rather than on the play screen.
        if modal is None and active == "play" and game.pending_location_detail:
            from ui.modals import LocationConfigModal
            game.pending_location_detail = False
            game.pending_progress_detail = True
            modal = LocationConfigModal(game)
            dirty = True
            continue

        # Manual progress-edit overflow (QuestingProgressModal close, or the
        # quest row's "Advance" icon): same pending-flag pattern as
        # pending_quest_card above - the modal that detected it had to
        # close first (router holds one modal at a time).
        if modal is None and active == "play" and game.pending_resolution:
            forced = game.pending_resolution == "forced"
            game.pending_resolution = False
            from ui.modals import ResolutionModal
            modal = ResolutionModal(game, force_advance=forced)
            dirty = True
            continue

        # A side-quest ROW's ">" - the sheet with Done and Remove on it,
        # which is a different modal from the add picker below. Neither twin
        # constructed SideQuestsModal at all before this.
        if modal is None and active == "play" and game.pending_side_quest_detail:
            game.pending_side_quest_detail = False
            from ui.modals import SideQuestsModal
            modal = SideQuestsModal(game)
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
            entries = db.side_quests()
            if entries:
                from ui.modals import SideQuestPickModal
                modal = SideQuestPickModal(game, entries)
            else:
                snap = game.begin_action()
                game.side_quests.append({"points": 4, "progress": 0})
                game.log_event("Side quest %d added (progress view)" % len(game.side_quests))
                game.add_delta(snap)
                db.session.save_state(game)
                db.session.save_log(game)
                db.session.save_replay(game)
            dirty = True
            continue

        # Travel, or the Progress modal's "+ Add location" (LocationPickModal
        # entry points): same pending-flag pattern as pending_side_quest_pick
        # above - the picker needs the scenario's gather-list union read out
        # of flash, which neither ScreenPlay.on_button nor a modal's can do
        # mid-tap. The read is cached for the whole game: the picked scenario
        # cannot change mid-game, and a cold union is several file reads.
        # An empty list (manual game, no /data/ deploy, a quest that gathers
        # no locations) is NOT a fallback here - the modal itself opens
        # straight on its manual stepper, exactly today's behavior.
        if modal is None and active == "play" and game.pending_location_pick:
            req = game.pending_location_pick
            game.pending_location_pick = None
            if catalog_locations is None:
                catalog_locations = db.locations((game.scenario or {}).get("slug"))
            from ui.modals import LocationPickModal
            # `idx` says WHICH seat a "change" replaces - the location
            # sheet's "Replaced" passes its own. Dropping it here sent every
            # replacement to seat 0.
            modal = LocationPickModal(game, mode=req.get("mode", "new"),
                                      entries=catalog_locations,
                                      back=req.get("back", "play"),
                                      idx=req.get("idx", 0))
            dirty = True
            continue

        # Coming back from the side-quest picker or the location picker:
        # reopen the Progress modal you tapped "+ Side quest" / "+ Add
        # location" from, rather than dropping you on the play screen. Same
        # pending-flag pattern as the two above.
        if modal is None and active == "play" and game.pending_progress_detail:
            game.pending_progress_detail = False
            from ui.modals import QuestingProgressModal
            modal = QuestingProgressModal(game)
            dirty = True
            continue


        if dirty and modal is not None and getattr(modal, "dirty_rect", None):
            # A tap that changed exactly one widget repaints that widget alone.
            # Filling is linear in area (5.1 Mpx/s measured), so a 48px token
            # box is 2.4 ms against 45 ms for a full clear, and presenting it
            # is 1.8 ms against 23.6 ms - a stat increment goes ~238 ms -> ~14.
            rect = modal.draw_partial(hw, game, pal)
            if rect:
                hw.partial_update(*rect)
                dirty = False
        if dirty:
            if modal is not None:
                modal.draw(hw, game, pal)
            else:
                screens[active].draw(hw, game, pal)
                if active not in PREGAME_ACTIVE:
                    update_leds(hw, game, prefs, tick)
            hw.update()
            dirty = False
        else:
            # Background persistence. Gameplay writes RAM only; the durable
            # work is drained here, on frames with nothing to draw, so it never
            # lands on a frame the player is waiting for. One bounded unit per
            # call - never a stall.
            db.session.tick(game)

        # torchlight flickers ~5x/sec without needing a redraw
        if prefs["scene"] == "torch" and active not in PREGAME_ACTIVE:
            torch_t += 1
            if torch_t >= 10:  # ~0.2 s at the 0.02 s loop sleep
                torch_t = 0
                tick += 1
                update_leds(hw, game, prefs, tick)

        # a threat change crossed someone's elimination level -> confirm
        # game over: all players eliminated -> defeat (victory is set via the
        # stage-complete modal). Route to the game-over screen from play.
        if modal is None and active == "play" and not game.game_over \
                and game.players and game.all_eliminated():
            game.set_game_over("defeat")
        if modal is None and active == "play" and game.game_over:
            # Record the finished game exactly once, on the transition into the
            # game-over screen. The rollup is bumped with it, so the stats
            # screens never need to scan the history.
            if not recorded_game_over:
                recorded_game_over = True
                db.history.append(game.history_record())
                db.session.flush(game)   # the game is over: make it durable now
            active = "gameover"
            dirty = True
            continue

        hw.poll()
        if hw.clicked:
            x, y = hw.click_x, hw.click_y

            if modal is not None:
                for b in modal.buttons:
                    if b.hit(x, y):
                        press_t0 = press_begin(hw, pal, b)
                        begin_action()
                        result = modal.on_button(b)
                        if result == "close":
                            from ui.modals import LedModal
                            if isinstance(modal, LedModal):
                                db.save_prefs(prefs)
                            else:
                                commit_action()
                            modal = None
                        elif result == "cancel":
                            modal = None
                        press_end(press_t0)
                        dirty = True
                        break
                time.sleep(0.02)
                continue

            for b in screens[active].buttons:
                if b.hit(x, y):
                    press_t0 = press_begin(hw, pal, b)
                    begin_action()
                    result = screens[active].on_button(b, game)
                    if isinstance(result, tuple):
                        kind = result[0]
                        if kind == "goto":
                            target = result[1]
                            if target == "scenario_options" and not (
                                    getattr(screens["scenario_options"],
                                            "scenario", None) or {}).get("slug"):
                                # Resumed straight into the game, so the picker
                                # screens are still the empty placeholders the
                                # boot path built. Rebuild them from the saved
                                # scenario instead of making the player pick
                                # again; only a game with nothing to rebuild
                                # from falls back to the source page.
                                catalog_index, catalog_icons = _rehydrate_pickers(
                                    screens, game, catalog_index, catalog_icons)
                                if not (screens["scenario_options"].scenario
                                        or {}).get("slug"):
                                    target = "scenario_source"
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
                                    catalog_tips = db.tips()
                                modal.tips = catalog_tips
                        elif kind == "boot":
                            if result[1] == "resume":
                                active = "play"
                            elif result[1] == "about":
                                nav_stack.append("boot")
                                active = "about"
                            else:
                                screens["setup"].has_save = db.session.exists()
                                active = "setup"
                        elif kind == "open_repo":
                            pass  # no browser on the device; link lives in the web twin
                        elif kind == "start_game":
                            db.session.flush(game)
                            threats = result[1]
                            first = result[2] if len(result) > 2 else 0
                            db.session.clear()
                            db.session.clear()
                            
                            game = GameState(player_count=len(threats))
                            recorded_game_over = False
                            for i, t in enumerate(threats):
                                game.players[i].threat = t
                                game.players[i].starting_threat = t
                            game.first_player = first
                            game.clock = clock
                            game.log_event("New game: %d players, threat %s, first P%d"
                                           % (len(threats),
                                              "/".join(str(t) for t in threats),
                                              first + 1))
                            db.session.save_state(game)
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
                                    catalog_index = db.index()
                            except Exception as e:
                                # No silent downgrade: there is no manual mode
                                # to fall back to, and on the device this
                                # means docs/data was never deployed - a bug
                                # to see, not to paper over.
                                print("quest catalog: load_index failed (%r)" % (e,))
                                game.log_event("Quest catalog unavailable")
                                screens["catalog_error"] = \
                                    CatalogUnavailableScreen(e)
                                active = "catalog_error"
                            else:
                                if catalog_icons is None:
                                    catalog_icons = db.icons()
                                if catalog_tips is None:
                                    catalog_tips = db.tips()
                                cycles = quest_catalog.cycles_for(catalog_index, source)
                                screens["pick_cycle"] = PickCycleScreen(source, cycles)
                                active = "pick_cycle"
                        elif kind == "choose_scenario_list":
                            source, cycle = result[1], result[2]
                            groups = quest_catalog.group_by_cycle(
                                catalog_index.get("scenarios", []), source)
                            group = next((g for g in groups if g["cycle"] == cycle), None)
                            chooser = ChooseScenarioScreen(
                                source, cycle, group["scenarios"] if group else [])
                            # Land on the scenario the player already has, not
                            # the first row. This handler rebuilds the screen
                            # from scratch, so backing out of Scenario Options
                            # used to silently reset the radio to row 1 - the
                            # picked scenario was still live one screen away.
                            picked = (getattr(screens["scenario_options"],
                                              "scenario", None) or {}).get("slug")
                            if picked and any(sc["slug"] == picked
                                              for sc in chooser.scenarios):
                                chooser.selected = picked
                            screens["choose_scenario"] = chooser
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
                                data = db.scenario(slug)
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
                                # Precomputed by build_card_data over the sets
                                # this scenario actually gathers, so the staging
                                # caption can name a real worst case instead of
                                # a constant. See GameState.staging_reveal_
                                # estimate.
                                "maxCardThreat": scn.get("maxCardThreat"),
                                "hasXThreat": scn.get("hasXThreat"),
                            }
                            stages = opts.data.get("quest", {}).get("stages", [])
                            game.preload_scenario(scenario_meta, stages)
                            game.view = "quest_setup"
                            active = "play"
                            db.session.save_state(game)
                        elif kind == "save_quit":
                            db.session.flush(game)
                            db.session.save_state(game)
                            db.session.save_log(game)
                            db.session.save_replay(game)
                            _, meta = load_saved()
                            screens["boot"] = BootScreen(meta)
                            nav_stack = []
                            active = "boot"
                        elif kind == "end_game":
                            db.session.flush(game)
                            db.session.clear()
                            db.session.clear()
                            
                            game = GameState()
                            recorded_game_over = False
                            game.clock = clock
                            screens["boot"] = BootScreen(None)
                            nav_stack = []
                            active = "boot"
                    elif result:
                        commit_action()
                    press_end(press_t0)
                    dirty = True
                    break
        time.sleep(0.02)


main()
