# Action-Window Interstitial Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the guided play flow (`ScreenPlay`) advances into a step that opens a player action window, show a brief full-screen interstitial instead of landing directly on that view: a 3-second auto-continue timer, a rules-accurate tip, the same players/progress zones as every other view (so adjustments can be made right there), a "Perform Actions" button that freezes the timer, and a "Next Phase" primary CTA. A new Settings toggle (default **on**) lets a player revert to today's small toast reminder instead.

**Architecture:** The interstitial is **not** a new modal class — it is transient draw-state owned by `ScreenPlay` itself (`self.action_window` / `this.actionWindow`), exactly like the existing `notif`/`banner`/`toast` fields. This matters for one concrete reason: tapping into the players/progress zones from the interstitial must open `PlayersDetailModal`/`QuestingProgressModal` exactly as it does from every other view, and this codebase's modal router holds **one modal at a time** (a modal cannot open another modal directly — see the `pending_quest_card` hand-off idiom in `main.py`/`main.js`). If the interstitial were itself a modal, diving into a detail editor from it would permanently strand/lose it (no "return to a paused parent modal" support exists). Because `ScreenPlay` is a *screen*, not a modal, opening `PlayersDetailModal` from it is the same zero-friction case every other view already handles — and because the `ScreenPlay` instance is long-lived (stored once in the `screens` dict, never reconstructed), `this.actionWindow` survives the round trip untouched, so closing the detail editor naturally re-shows the interstitial exactly as it was left (same countdown value, same paused/running state).

The main-loop tick (`setInterval(..., 20)` / `while True: ... time.sleep(0.02)`) already detects `game.view` changes and, today, reacts by arming a countdown-dismissed toast (`notif_t`/`notifT`, ~4s). This plan adds a **second, parallel trigger** at the same detection point: when the newly-entered step opens an action window *and* the new setting is on, seed `screens.play.actionWindow` instead of the toast; otherwise (setting off, or no action window) fall through to exactly today's toast code, unchanged.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter. No new dependencies, no changes to `phases.py` (its `action_window` flags are consumed, not modified — no `tools/gen_web_data.py` regen is needed).

**Context:**
- `phases.py` STEPS carries `action_window: bool` per step (transcribed from DragnCards; e.g. `"1.R"`, `"3.2"`, `"4.2"` are `True`, `"6.2"` "Deal shadow cards" is `False`). `GameState.action_window_open()`/`actionWindowOpen()` (`gamestate.py:381-383` / `docs/js/gamestate.js:305`) just returns `phases.step(self.step)["action_window"]`.
- `ScreenPlay.onButton` transitions (`advance` → `game.advanceView()`, `stage_advance` → `game.enterView("quest_resolution")`, `apply_alloc` → `game.enterView("travel")`, `endround` → `game.endRound()`) all update `game.view`/`game.step` **immediately, synchronously, unchanged by this plan**. The interstitial is purely a post-transition UI gate drawn instead of the destination view's normal content for up to 3s — it does not defer or re-trigger any transition. Its own CTA and the timer's expiry do the exact same thing: stop showing the interstitial, which reveals the (already-current) destination view.
- Existing precedent worth reusing verbatim: `main.js`/`main.py`'s `NOTIF_TICKS = 200` (~4s at the 20ms tick) countdown already drives a **pac-man pie** (`drawNotifPie`/`draw_notif_pie`, defined in `docs/js/screens.js` / `ui/screen_play.py`) that auto-dismisses a toast, throttled to redraw only every 10 ticks (~200ms) via `hw.partial_update` on just the pie's bounding box (firmware) or a targeted canvas redraw bypassing the normal `dirty` full-redraw path (web) — this exists specifically because a full-screen redraw every 20ms is not something the firmware loop can afford. This plan's 3s timer (`AW_TICKS = 150`) reuses that exact pie primitive and that exact throttling discipline, just recolored `"purple"` (the established action-window accent — see `pal.purple` "leadership purple" in `ui/theme.py:41-42` and the existing purple "Action Window" toast line).
- **Rules basis for the tip copy** (verified against the rulebook PDF, "Actions" p.22 and the "Turn Sequence" chart p.29-31): *"Actions are always optional, and can be triggered by their controller during any action window... Event cards are actions that are played directly from a player's hand... Some action triggers are preceded by a specific phase... 'Quest Action:' can only be triggered during an action window of the quest phase. Actions without a specified phase can be triggered during any action window throughout the round."* The turn-sequence chart shows a "Player actions" window after nearly every phase step. This backs the three tip lines specified in Task 1 — no other rules claim is made.
- **Pre-existing quirk, preserved as-is (not fixed by this plan):** `GameState.end_round()`/`endRound()` sets `self.step = phases.STEP_ORDER[0]` ("0.0", `action_window: False`) directly rather than routing through `enter_view()`, even though it also sets `self.view = "resource_planning"` (whose own step, `"1.R"`, *is* an action window). Consequently neither today's toast nor this plan's interstitial appears at the start of rounds 2+ — only round 1's entry (via the setup-flip path, which does call `enter_view`) shows it. Do not "fix" this in this plan; it's an existing, separately-scoped state-machine nuance.
- **Pre-existing quirk, also preserved:** jumping via the Phases screen (`ScreenPhases.onButton`'s `"jump"`/`"step"` ids) sets `game.step` directly without touching `game.view`, so it never trips the `game.view !== prevView` detector — no toast today, no interstitial after this plan either.
- `due_notifications()`/`dueNotifications()` (archery/battle reminders) are also gated on `game.view` and today ride the same toast. When the interstitial pre-empts the toast, those reminder lines are folded into the interstitial's tip body instead of being silently dropped (see Task 1).

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror. Identical layout, ids, behavior, and (per the model-field convention already used throughout this codebase for JSON-shaped data — e.g. `pending_quest_card`, `commit_touched` stay snake_case even in the JS files) identical **snake_case** keys for the one new prefs field, `action_window_interstitial`, in both twins. Purely in-memory, non-persisted screen state (`this.actionWindow` / `self.action_window`) instead follows each language's own convention (camelCase JS / snake_case Python), matching `notifFrac`/`notif_frac` etc.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter. Add scenes for the new interstitial states.
- **Touch targets ≥ 24px** each dimension; everything within 480×480; no text collisions (linter-enforced).
- **No `phases.py` / `tools/gen_web_data.py` changes.** `action_window` flags are read-only inputs here.
- **No new persisted `GameState` fields.** The interstitial's state lives on the `ScreenPlay` instance and is never part of `to_dict()`/`toDict()`. Only the prefs dict (already persisted separately, `device.json` / `localStorage`) gains the one new key.
- **The disabled path must be byte-for-byte today's behavior.** When `action_window_interstitial` is `False`, the exact existing toast code runs, unchanged — this plan only *adds* a sibling branch, never edits the toast's own logic.
- **Firmware partial-update discipline:** the passive per-tick countdown must never set the global `dirty` flag (that forces a full 480×480 redraw every 20ms); only `hw.partial_update` on the pie's small bounding box, throttled to every 10 ticks — mirroring `notif_t` exactly.
- **`main.py`/`main.js` are not unit-testable** (no test imports `main`, matching the existing `notif_t`/`NOTIF_TICKS` mechanism, which also has zero test coverage). Verification for Task 3 is a manual browser walkthrough plus careful code-review-against-this-spec; **do not** attempt on-device firmware verification from a worker session — per `CLAUDE.md`, device deploys/testing happen only in the main session.

## File structure

- `gamestate.py` / `docs/js/gamestate.js` — new `ACTION_WINDOW_TIP` copy constant (data only, alongside the existing `SETUP_TIP`).
- `ui/screen_play.py` / `docs/js/screen_play.js` — the interstitial state, drawing, button handling; new exported `AW_TICKS` constant.
- `ui/screen_settings.py` / `docs/js/screens_other.js` — the new toggle row + prefs default.
- `main.py` / `docs/js/main.js` — the trigger branch, countdown tick, `save_prefs` dispatch case.
- `tests/scenes.py` — new scenes; a small `post` hook added to the existing `_play()` builder.
- `tests/test_screen_play.py`, `tests/test_screen_settings.py` — behavior tests.

---

### Task 1: The interstitial itself (`ScreenPlay`, both twins)

**Files:**
- Modify: `gamestate.py`, `docs/js/gamestate.js` (tip copy)
- Modify: `ui/screen_play.py`, `docs/js/screen_play.js` (state, draw, buttons)
- Modify: `tests/scenes.py` (scenes + `_play` hook)
- Modify: `tests/test_screen_play.py` (new tests)

**Interfaces:**
- `ScreenPlay.open_action_window(game, ticks=AW_TICKS)` / `openActionWindow(game, ticks = AW_TICKS)` — seeds `self.action_window` / `this.actionWindow` to `{t, running: True, reminders: due_notifications(), snap: <field snapshot>}`.
- `ScreenPlay.close_action_window(game)` / `closeActionWindow(game)` — diffs the snapshot against current values; if anything changed, appends one `"Action window (<Phase Label>): ..."` log line; always clears the state to `None`/`null`.
- `on_button`/`onButton` ids: `("perform_actions",)` → freezes the countdown (`running = False`), stays open. `("aw_close",)` → calls `close_action_window`, revealing the (already-current) destination view.
- `AW_TICKS = 150` (3000ms / 20ms tick), exported from `ui/screen_play.py` / `docs/js/screen_play.js` for `main.py`/`main.js` to import.

**Layout** (drawn instead of the view's normal content, while `action_window` is set; header, players zone, and progress zone are unchanged from every other view):
- `draw_header`/`drawHeader` as normal (shows the already-current round/phase).
- `_players_zone`/`_playersZone` and `_progress_zone`/`_progressZone` at their usual position (`ZONE_TOP..ZONE_TOP+90`) — **verbatim reuse**, same single big tap targets opening `PlayersDetailModal`/`QuestingProgressModal`. This is what "allows adjusting players/progress zones" means: the exact same editors every other view already offers, nothing new to build.
- At `CONTENT_Y` (150): `"ACTION WINDOW"` label (scale 3, `pal.purple`), and a countdown pie (reusing `draw_notif_pie`/`drawNotifPie`, radius 20, colored `"purple"`) top-right of that row.
- Below it: a `note_panel`/`notePanel` tip using `icons.LEADERSHIP` (ties visually to the existing purple toast), body = `ACTION_WINDOW_TIP` (3 lines) plus any `due_notifications()` text for this view (archery/battle), so nothing that would have shown in today's toast is dropped.
- Below the tip: while `running`, a full-width "Perform Actions" bevel button (52px tall). Once tapped (`running == False`), it's replaced by a static caption ("Adjust players/progress above, then continue.") — the button doesn't need to be tapped twice.
- Bottom: the standard `_cta`/`_cta` at `CTA_Y` (410) labeled `"Next Phase: " + VIEW_LABELS[game.view]` (the already-current view — tapping it or the timer expiring do the identical thing), id `("aw_close",)`. Same styling as every other view's primary CTA (no color override) — it should read as the same kind of control, with the purple title/pie already signaling "this one's different."

- [ ] **Step 1: Add the tip copy.** In `gamestate.py`, right after `SETUP_TIP`:

```python
# Action-window tip (rulebook p.22 "Actions" + p.29-31 turn-sequence chart):
# actions trigger at the controller's discretion during any action window;
# phase-locked triggers (e.g. "Quest Action:") only fire during that phase's
# window.
ACTION_WINDOW_TIP = [
    "Players may act in any order - trigger Action:",
    "abilities on cards in play, or play Event cards.",
    "Phase-specific actions (e.g. \"Quest Action:\") apply now too.",
]
```

  In `docs/js/gamestate.js`, the same list as an export, right after `SETUP_TIP`:

```js
// Action-window tip (rulebook p.22 "Actions" + p.29-31 turn-sequence chart):
// actions trigger at the controller's discretion during any action window;
// phase-locked triggers (e.g. "Quest Action:") only fire during that phase's
// window.
export const ACTION_WINDOW_TIP = [
  "Players may act in any order - trigger Action:",
  "abilities on cards in play, or play Event cards.",
  "Phase-specific actions (e.g. \"Quest Action:\") apply now too.",
];
```

- [ ] **Step 2: Write the failing tests.** Add to `tests/test_screen_play.py` (uses the existing `_setup`/`_find` helpers already in that file):

```python
def test_open_action_window_seeds_state_and_snapshot():
    hw, pal, game, screen = _setup("resource_planning")
    screen.open_action_window(game, 150)
    aw = screen.action_window
    assert aw["t"] == 150 and aw["running"] is True
    assert aw["snap"]["players"][0]["threat"] == game.players[0].threat
    assert aw["snap"]["quest"] == game.quest["progress"]

def test_draw_shows_interstitial_layout_and_keeps_zones():
    hw, pal, game, screen = _setup("resource_planning")
    screen.open_action_window(game, 150)
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "ACTION WINDOW" in texts
    assert any("Next Phase" in t for t in texts)
    ids = [b.id[0] for b in screen.buttons]
    assert "perform_actions" in ids
    assert "aw_close" in ids
    assert "players_detail" in ids       # zones still fully functional
    assert "progress_detail" in ids

def test_perform_actions_freezes_timer_and_view_stays_open():
    hw, pal, game, screen = _setup("resource_planning")
    screen.open_action_window(game, 150)
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("perform_actions",)), game)
    assert result is True
    assert screen.action_window["running"] is False
    screen.draw(hw, game, pal)           # redraws fine, no crash
    assert screen.action_window is not None
    assert not any(b.id[0] == "perform_actions" for b in screen.buttons)  # spent

def test_aw_close_logs_summary_when_adjustments_were_made():
    hw, pal, game, screen = _setup("resource_planning")
    screen.open_action_window(game, 150)
    game.adjust_threat(0, 5)             # simulate an edit via PlayersDetailModal
    game.set_commit(1, 3)
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("aw_close",)), game)
    assert result is True
    assert screen.action_window is None
    lines = [e["text"] for e in game.log]
    assert any("Action window (Resource & Planning)" in t and "P1 threat" in t for t in lines)
    assert any("P2 willpower" in t for t in lines)

def test_aw_close_logs_nothing_when_no_adjustments_made():
    hw, pal, game, screen = _setup("resource_planning")
    screen.open_action_window(game, 150)
    before = len(game.log)
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("aw_close",)), game)
    assert len(game.log) == before

def test_action_window_folds_in_due_reminders():
    hw, pal, game, screen = _setup("quest_commit")
    game.reminders["battle"] = True
    screen.open_action_window(game, 150)
    screen.draw(hw, game, pal)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "Battle/Siege" in texts
```

  Run: `python3 -m pytest tests/test_screen_play.py -q` → fails (`AttributeError: 'ScreenPlay' object has no attribute 'action_window'` / no `open_action_window`).

- [ ] **Step 3: Implement in `ui/screen_play.py`.**
  - Add near the top constants (alongside `MARGIN`/`ZONE_TOP`/`CONTENT_Y`/`CTA_Y`): `AW_TICKS = 150  # 3s at the 0.02s main-loop tick`.
  - Extend the `gamestate` import: `from gamestate import VIEW_ORDER, VIEW_LABELS, SETUP_TIP, ACTION_WINDOW_TIP`.
  - In `ScreenPlay.__init__`, add `self.action_window = None` and `self.action_window_pie = None`.
  - Add the three methods:

```python
    def _aw_snapshot(self, game):
        return {
            "players": [{"threat": p.threat, "commit": p.commit} for p in game.players],
            "quest": game.quest["progress"],
            "loc": game.active_location["progress"] if game.active_location else None,
            "sq": [s["progress"] for s in game.side_quests],
        }

    def open_action_window(self, game, ticks=AW_TICKS):
        self.action_window = {
            "t": ticks,
            "running": True,
            "reminders": game.due_notifications(),
            "snap": self._aw_snapshot(game),
        }

    def close_action_window(self, game):
        aw = self.action_window
        if not aw:
            return
        s = aw["snap"]
        parts = []
        for i, p in enumerate(game.players):
            if p.threat != s["players"][i]["threat"]:
                parts.append("P%d threat %d -> %d" % (i + 1, s["players"][i]["threat"], p.threat))
            if p.commit != s["players"][i]["commit"]:
                parts.append("P%d willpower %d -> %d" % (i + 1, s["players"][i]["commit"], p.commit))
        if game.quest["progress"] != s["quest"]:
            parts.append("quest progress %d -> %d" % (s["quest"], game.quest["progress"]))
        if game.active_location and s["loc"] is not None and game.active_location["progress"] != s["loc"]:
            parts.append("location progress %d -> %d" % (s["loc"], game.active_location["progress"]))
        for i, sq in enumerate(game.side_quests):
            if i < len(s["sq"]) and sq["progress"] != s["sq"][i]:
                parts.append("side quest %d progress %d -> %d" % (i + 1, s["sq"][i], sq["progress"]))
        if parts:
            game.log_event("Action window (%s): %s" % (VIEW_LABELS[game.view], ", ".join(parts)))
        self.action_window = None

    def _draw_action_window(self, d, pal, game):
        aw = self.action_window
        y0 = CONTENT_Y
        text_left(d, pal, "ACTION WINDOW", MARGIN, y0, 3, pal.purple)
        cx, cy, r = 480 - MARGIN - 26, y0 + 16, 20
        self.action_window_pie = (cx, cy, r)
        draw_notif_pie(d, pal, cx, cy, r, aw["t"] / AW_TICKS, "purple")
        body = list(ACTION_WINDOW_TIP) + [t for _ic, t in aw["reminders"]]
        ty = y0 + 40
        th = note_panel(d, pal, MARGIN, ty, 480 - 2 * MARGIN, body, 2, 0, icons.LEADERSHIP)
        by = ty + th + 12
        if aw["running"]:
            pb = Button(("perform_actions",), MARGIN, by, 480 - 2 * MARGIN, 52)
            bevel(d, pal, pb.x, pb.y, pb.w, pb.h, pal.btn)
            text_center(d, pal, "Perform Actions", 240, by + 16, 2, pal.tan)
            self.buttons.append(pb)
        else:
            text_center(d, pal, "Adjust players/progress above, then continue.",
                        240, by + 18, 1, pal.dim)
        self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS[game.view], ("aw_close",))
```

  - In `draw()`, change the first `if view == "quest_setup":` header branch's follow-up from `if view == "setup_game":` to a chain that checks the interstitial first:

```python
        if self.action_window:
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            self._draw_action_window(d, pal, game)
        elif view == "setup_game":
            ...   # (unchanged from here — just retarget the existing `if` to `elif`)
```

  - In `on_button`, right before the final `return None`:

```python
        if k == "perform_actions":
            self.action_window["running"] = False
            return True
        if k == "aw_close":
            self.close_action_window(game)
            return True
        return None
```

- [ ] **Step 4: Mirror in `docs/js/screen_play.js`.** Same structure, JS conventions:
  - `export const AW_TICKS = 150;` near the top constants.
  - Extend the gamestate import: `import { VIEW_ORDER, VIEW_LABELS, SETUP_TIP, ACTION_WINDOW_TIP } from "./gamestate.js";`.
  - Constructor: `this.actionWindow = null; this.actionWindowPie = null;`.
  - `_awSnapshot`, `openActionWindow`, `closeActionWindow`, `_drawActionWindow` methods mirroring the Python above 1:1 (camelCase, template-literal log strings, `Array`/`.map`/`.forEach` instead of comprehensions — e.g. `game.logEvent(\`Action window (${VIEW_LABELS[game.view]}): ${parts.join(", ")}\`)`).
  - `draw()`: `if (this.actionWindow) { this._playersZone(ctx, game); this._progressZone(ctx, game); this._drawActionWindow(ctx, game); } else if (view === "setup_game") { ... }` (retarget the existing `if` to `else if`).
  - `onButton`: add `if (k === "perform_actions") { this.actionWindow.running = false; return true; }` and `if (k === "aw_close") { this.closeActionWindow(game); return true; }` right before the final `return null;`.

- [ ] **Step 5: Add scenes.** In `tests/scenes.py`, give `_play` an optional post-construction hook (runs after `ScreenPlay()` is built, before `.draw()`):

```python
def _play(view, mutate=None, post=None):
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
        if post:
            post(g, s)
        s.draw(hw, g, pal)
        return hw, s
    return build


def _aw_open(g, s):
    s.open_action_window(g, 90)          # mid-countdown look


def _aw_paused(g, s):
    s.open_action_window(g, 150)
    s.action_window["running"] = False


def _aw_with_reminder(g, s):
    g.reminders["battle"] = True
    s.open_action_window(g, 150)
```

  Add to the `SCENES` dict (near the other `play_*` entries):

```python
    "play_action_window": _play("resource_planning", post=_aw_open),
    "play_action_window_paused": _play("quest_commit", post=_aw_paused),
    "play_action_window_reminder": _play("quest_commit", post=_aw_with_reminder),
```

- [ ] **Step 6: Run the new tests, then the full lint.** `python3 -m pytest tests/test_screen_play.py -q` → PASS. `python3 -m pytest tests/test_layout.py -q` → PASS (touch targets ≥24px, no collisions across all three new scenes).

- [ ] **Step 7: Render and inspect.** `python3 tools/preview.py play_action_window /tmp/aw.png`, `python3 tools/preview.py play_action_window_paused /tmp/aw_paused.png`, `python3 tools/preview.py play_action_window_reminder /tmp/aw_reminder.png`. Confirm: the pie sits clear of the "ACTION WINDOW" title, the tip wraps cleanly (with and without the folded-in reminder line), the Perform Actions button / paused caption don't crowd the CTA, and the whole thing reads as clearly related to (not a jarring departure from) every other guided-flow view. Fix any cramped spacing (the coordinates above are a starting point, not final).

- [ ] **Step 8: Full suite → green.** `python3 -m pytest tests/ -q`.

---

### Task 2: Settings toggle + prefs default (both twins)

**Files:**
- Modify: `ui/screen_settings.py`, `docs/js/screens_other.js` (`ScreenSettings`)
- Modify: `tests/test_screen_settings.py`

**Interfaces:**
- Prefs dict gains one key: `action_window_interstitial: bool`, default `True`.
- `ScreenSettings.on_button`/`onButton` gains id `("toggle_action_window",)` → flips `self.prefs["action_window_interstitial"]` / `this.prefs.action_window_interstitial` (prefs is a JSON-serialized bag like `GameState`, so per the Global Constraints lockstep-casing rule the key stays **snake_case in both twins**, not camelCase in JS). Returns `("save_prefs",)` / `["save_prefs"]` (a new tagged result the main loop handles, mirroring the existing `save_quit` pattern — `ScreenSettings` does not call persistence functions itself).

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_screen_settings.py`:

```python
def test_action_window_toggle_row_present_and_defaults_on():
    hw, s = _draw()
    assert s.prefs.get("action_window_interstitial", True) is True
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert any("Action window interstitial" in t for t in texts)
    assert any(b.id == ("toggle_action_window",) for b in s.buttons)

def test_toggle_flips_pref_and_requests_a_prefs_save():
    hw, s = _draw()
    btn = [b for b in s.buttons if b.id == ("toggle_action_window",)][0]
    assert s.on_button(btn, GameState()) == ("save_prefs",)
    assert s.prefs["action_window_interstitial"] is False
    s.draw(hw, GameState(), Palette(hw.display))
    btn2 = [b for b in s.buttons if b.id == ("toggle_action_window",)][0]
    assert s.on_button(btn2, GameState()) == ("save_prefs",)
    assert s.prefs["action_window_interstitial"] is True
```

  Run: `python3 -m pytest tests/test_screen_settings.py -q` → fails (no such button/behavior).

- [ ] **Step 2: Implement in `ui/screen_settings.py`.**
  - Constructor default: `{"brightness": 100, "scene": "phase", "action_window_interstitial": True}`.
  - In `draw()`, right after the End Game button's `self.buttons.append(b)` and before `y += 76` / the `"DEVICE"` section:

```python
        y += 66
        on = self.prefs.get("action_window_interstitial", True)
        tog = Button(("toggle_action_window",), 16, y, 452, 62)
        bevel(d, pal, tog.x, tog.y, tog.w, tog.h, pal.card_hi if on else pal.card, t=2)
        d.set_pen(pal.well)
        d.rectangle(30, y + 17, 28, 28)
        if on:
            d.set_pen(pal.ok_fg)
            d.rectangle(36, y + 23, 16, 16)
        text_left(d, pal, "Action window interstitial", 76, y + 12, 2,
                  pal.tan if on else pal.muted)
        text_left(d, pal, "3s pause to act; off = quick toast instead", 76, y + 38, 1, pal.dim)
        self.buttons.append(tog)
```

  - In `on_button`, add: `if k == "toggle_action_window": self.prefs["action_window_interstitial"] = not self.prefs.get("action_window_interstitial", True); return ("save_prefs",)`.
  - This reuses the exact checkbox-row visual already established by `RemindersModal` (`ui/modals.py`) — same well/fill/geometry — for visual consistency.

- [ ] **Step 3: Mirror in `docs/js/screens_other.js`'s `ScreenSettings`.** Same row, same position (after the End Game button, before the `"DEVICE"` label), same id, same `["save_prefs"]` return. Prefs key stays `action_window_interstitial` (snake_case, per Global Constraints).

- [ ] **Step 4: Tests green.** `python3 -m pytest tests/test_screen_settings.py -q` → PASS. `python3 -m pytest tests/test_layout.py -q` → PASS (the existing `"settings"` scene automatically covers the new row — no new scene needed).

---

### Task 3: Main-loop wiring (trigger, timer, persistence) — both twins

**Files:**
- Modify: `main.py`, `docs/js/main.js`

**Interfaces:**
- Consumes: `ScreenPlay.open_action_window`/`openActionWindow`, `close_action_window`/`closeActionWindow`, `AW_TICKS` from Task 1; `prefs["action_window_interstitial"]` from Task 2.
- No new testable surface (see Global Constraints) — this task is implemented directly from the code below, then verified by walkthrough (Step 3).

- [ ] **Step 1: `main.py`.**
  - Extend the import: `from ui.screen_play import ScreenPlay, draw_notif_pie, AW_TICKS` (check the exact existing import spelling first — today's file has separate `from ui.screen_play import ScreenPlay` plus later a local `from ui.screen_play import draw_notif_pie` inside the notif block; add `AW_TICKS` to whichever of those you keep, or its own line — just make sure `AW_TICKS` is bound before use).
  - `load_prefs()`/`DEFAULT_PREFS`: add `"action_window_interstitial": True` to `DEFAULT_PREFS`, and `"action_window_interstitial": d.get("action_window_interstitial", True)` to the loaded-dict path.
  - Replace the view-change block:

```python
        # reminder notifications fire when the play view changes
        if game.view != prev_view:
            prev_view = game.view
            aw_open = game.action_window_open()
            if aw_open and prefs["action_window_interstitial"] and active == "play" and modal is None:
                screens["play"].open_action_window(game, AW_TICKS)
                dirty = True
            else:
                msgs = [(ic, t, "amber") for ic, t in game.due_notifications()]
                if aw_open:
                    msgs.append(("LEADERSHIP", "Action Window", "purple"))
                if msgs:
                    screens["play"].notif = msgs
                    screens["play"].notif_frac = 1.0
                    notif_t = NOTIF_TICKS
                    dirty = True
```

  - Add `AW_TICKS` isn't a loop-local — it's imported (see above). Add a new countdown block right after the existing `notif_t` block (same indentation level, still before `if dirty:`):

```python
        # action-window interstitial countdown: mirrors the notif_t pie
        # above, but gates a real transition (revealing the already-current
        # view) instead of a cosmetic dismiss. Paused whenever another modal
        # is up (e.g. PlayersDetailModal opened from the interstitial's own
        # players zone) so side-tripping to adjust something never burns
        # down the clock - the ScreenPlay instance survives the round trip,
        # so the interstitial (with whatever time/paused-state it had) is
        # exactly what reappears when that modal closes.
        aw = screens["play"].action_window
        if aw and aw["running"] and modal is None and active == "play":
            aw["t"] -= 1
            if aw["t"] <= 0:
                screens["play"].close_action_window(game)
                save_state(game)
                dirty = True
            elif aw["t"] % 10 == 0 and not dirty and screens["play"].action_window_pie:
                cx, cy, r = screens["play"].action_window_pie
                draw_notif_pie(hw.display, pal, cx, cy, r, aw["t"] / AW_TICKS, "purple")
                hw.partial_update(cx - r - 2, cy - r - 2, 2 * r + 4, 2 * r + 4)
```

  - In the tap-handling section's `elif kind == "goto":` / `"modal"` / ... chain (where `save_quit`, `end_game` etc. are handled as tagged tuple results), add: `elif kind == "save_prefs": save_prefs(prefs)`.

- [ ] **Step 2: `docs/js/main.js`.**
  - Extend the import: `import { ScreenPlay, AW_TICKS } from "./screen_play.js";`.
  - `loadPrefs()`: `return { brightness: d.brightness ?? 100, scene: d.scene ?? "phase", action_window_interstitial: d.action_window_interstitial ?? true };`.
  - Replace the view-change block inside the `setInterval`:

```js
    if (game.view !== prevView) {
      prevView = game.view;
      const awOpen = game.actionWindowOpen();
      if (awOpen && prefs.action_window_interstitial && active === "play" && !modal) {
        screens.play.openActionWindow(game, AW_TICKS);
        dirty = true;
      } else {
        const msgs = game.dueNotifications().map(([ic, t]) => [ic, t, "amber"]);
        if (awOpen) msgs.push(["LEADERSHIP", "Action Window", "purple"]);
        if (msgs.length) {
          screens.play.notif = msgs;
          screens.play.notifFrac = 1.0;
          notifT = NOTIF_TICKS;
          dirty = true;
        }
      }
    }
```

  - Add a new countdown block right after the existing `notifT` block:

```js
    // action-window interstitial countdown: mirrors the notifT pie above,
    // but gates a real transition (revealing the already-current view)
    // instead of a cosmetic dismiss. Paused whenever another modal is up
    // (e.g. PlayersDetailModal opened from the interstitial's own players
    // zone) so side-tripping to adjust something never burns down the
    // clock - the ScreenPlay instance survives the round trip, so the
    // interstitial (with whatever time/paused-state it had) is exactly
    // what reappears when that modal closes.
    const aw = screens.play.actionWindow;
    if (aw && aw.running && !modal && active === "play") {
      aw.t -= 1;
      if (aw.t <= 0) {
        screens.play.closeActionWindow(game);
        saveState(game);
        dirty = true;
      } else if (aw.t % 10 === 0 && !dirty && screens.play.actionWindowPie) {
        const [cx, cy, r] = screens.play.actionWindowPie;
        import("./screens.js").then(m => m.drawNotifPie(ctx, cx, cy, r, aw.t / AW_TICKS, "purple"));
      }
    }
```

  - In `handleResult`'s `if (Array.isArray(result))` chain, add: `} else if (kind === "save_prefs") { savePrefs(prefs); }`.

  **On timer honesty:** both loops tick at a nominal 20ms (`setInterval(..., 20)` / `time.sleep(0.02)`), so `AW_TICKS = 150` targets 3.0s — but neither loop is a hard real-time scheduler. On firmware, a tap mid-countdown adds ~90-110ms via `press_feedback`'s deliberate sleep (identical cost already paid by every other button in the app, including this interstitial's own "Perform Actions"/"Next Phase"), and `hw.poll()` + drawing cost add a small amount per iteration; on the web, `setInterval` drift under load is the browser's own approximation. This is the exact same tolerance the existing ~4s toast countdown already lives with (its own comment says "~4 s", not "4.000s") — this plan does not attempt tighter timing than that established precedent.

- [ ] **Step 3: Manual verification walkthrough (web).** `mcp__Claude_Browser__preview_start` the web twin (or `python3 -m http.server` from `docs/` if no launch config exists), start a game, and walk: Setup → Round 1 (`resource_planning`, an action window) → confirm the interstitial appears, the pie visibly counts down, tapping "Perform Actions" freezes it and swaps the button for the caption, tapping the players zone opens `PlayersDetailModal`, editing a threat value and closing returns to the (still-paused) interstitial, tapping "Next Phase" reveals the normal Resource & Planning screen, and the log (`docs/js/screens_other.js` `ScreenLog` view) shows one `"Action window (Resource & Planning): P# threat X -> Y"` line. Then: Settings → toggle "Action window interstitial" off → advance through another action-window step (e.g. `quest_commit`) → confirm today's small purple toast appears instead, with no interstitial. Toggle back on, reload, confirm the pref persisted. Capture console errors (`read_console_messages`) — must be none introduced by this change.

- [ ] **Step 4: Firmware code review (no device deploy from this session).** Re-read the `main.py` diff against Step 1's block above line-by-line: confirm `dirty` is never set inside the throttled `elif` branch (only inside the `aw["t"] <= 0` branch and the initial open), confirm `hw.partial_update` bounds match `draw_notif_pie`'s drawn region exactly (`cx - r - 2, cy - r - 2, 2r+4, 2r+4`, identical to the existing `notif_t` block), and confirm the `modal is None` guard is present on both the trigger and the countdown decrement. Leave actual device confirmation for the main session, per `CLAUDE.md`.

- [ ] **Step 5: Full suite → green; report.** `python3 -m pytest tests/ -q`.

---

## Self-Review

**Spec coverage:** interstitial appears on advancing into an action-window step (Task 1 draw-branch, Task 3 trigger) → done; 3s timer with automatic continue (Task 1 `AW_TICKS`/countdown state, Task 3 tick loop) → done; "Perform Actions" dismisses/freezes the timer (Task 1 `perform_actions` handler) → done; tip explains action-window rules, rulebook-verified (Task 1 `ACTION_WINDOW_TIP`) → done; adjusting players/progress zones (Task 1 verbatim `_playersZone`/`_progressZone` reuse) → done; adjustments recorded as done in the action window (Task 1 `_aw_snapshot`/`close_action_window` diff-log, modeled directly on `QuestingProgressModal`'s existing close-time diff pattern) → done; "Next Phase" primary CTA (Task 1 `_cta` reuse) → done; a disable setting reverting to today's toast (Task 2 toggle + Task 3's `if/else` that leaves the toast branch byte-for-byte unchanged) → done; a scene + `tools/preview.py` render check (Task 1 Steps 5/7) → done.

**Placeholder scan:** every judgment call is a stated default with rationale, not a TBD: interstitial-as-screen-state vs. a modal class (Architecture paragraph — modal rejected because it would strand the user on a detail-editor round trip); what "Next Phase"/timeout actually does (reveal-already-current-view, not a second transition — Context, 2nd bullet); reminder folding instead of a second overlapping toast (Context, last bullet); pie reuse over a numeric ring (Task 1 Layout — "reusing `draw_notif_pie`"); countdown pause on any open modal (Task 3 code comment, both twins); settings default `True` (Task 2 Interfaces); prefs key casing snake_case-in-both-twins (Global Constraints, justified by existing `pending_quest_card`/`commit_touched` precedent). The two genuinely pre-existing quirks this plan inherits rather than fixes (no interstitial at round-2+ start; no interstitial from a Phases-screen jump) are called out explicitly in Context so they aren't mistaken for bugs introduced here.

**Type consistency:** `action_window`/`actionWindow` is `{t: int, running: bool, reminders: [(icon,text)], snap: {...}}` used identically by `open_action_window`/`close_action_window`/`_draw_action_window` (Task 1) and read (never constructed) by the main-loop countdown (Task 3). `AW_TICKS` is defined once (Task 1, `ui/screen_play.py`/`docs/js/screen_play.js`) and imported everywhere else it's needed (Task 3), never redefined. The `("save_prefs",)`/`["save_prefs"]` tagged result introduced in Task 2 is consumed by exactly the one new dispatch arm added in Task 3, mirroring the pre-existing `save_quit` tagged-result convention already used for the same "screen returns an intent, main performs the side effect" split.
