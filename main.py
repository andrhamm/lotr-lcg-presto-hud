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

STATE_PATH = "/state.json"
PREFS_PATH = "/device.json"
DEFAULT_PREFS = {"brightness": 100, "scene": "phase"}


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
    }
    active = "boot"
    nav_stack = []  # origins to return to when overlay screens (log/settings) close
    modal = None
    dirty = True

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
                if active not in ("boot", "setup"):
                    update_leds(hw, game, prefs, tick)
            hw.update()
            dirty = False

        # torchlight flickers ~5x/sec without needing a redraw
        if prefs["scene"] == "torch" and active not in ("boot", "setup"):
            torch_t += 1
            if torch_t >= 10:  # ~0.2 s at the 0.02 s loop sleep
                torch_t = 0
                tick += 1
                update_leds(hw, game, prefs, tick)

        # a threat change crossed someone's elimination level -> confirm
        if modal is None and active not in ("boot", "setup") \
                and game.pending_elim is not None:
            from ui.modals import EliminationModal
            modal = EliminationModal(game, game.pending_elim)
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
                            elif target in ("settings", "log", "phases"):
                                if active != target:
                                    nav_stack.append(active)
                            else:
                                nav_stack = []  # direct nav resets the trail
                            active = target
                        elif kind == "modal":
                            modal = result[1]
                        elif kind == "boot":
                            if result[1] == "resume":
                                active = "play"
                            else:
                                screens["setup"].has_save = save_exists()
                                active = "setup"
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
