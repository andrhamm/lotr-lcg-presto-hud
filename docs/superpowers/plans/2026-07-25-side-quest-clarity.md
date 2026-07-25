# Side-Quest Add-Flow Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the side-quest add flow say, in plain terms, what number is being set and when. The picker list gains a "Target" column header and a progress hint in its caption; the "Manual" button opens a dedicated **Target quest points** screen (title + label + live stepper) instead of silently appending a blank `0/0` entry; and the one remaining silent path — the catalog-unavailable fallback in the main loop — is routed through the same modal instead of appending a placeholder with no screen at all.

**Architecture:** No new classes and no data-model changes. `SideQuestPickModal` (both twins) gains a small internal sub-state (`manual`/`manualPts`) that swaps its `draw()` between the existing picker list and a new full-screen "Manual Side Quest" prompt, reusing the app's established `stepper()` + `_footer()`/`footer()` full-screen-prompt pattern — the same one `QuestingProgressModal`'s "Replace location" flow already uses (`ui/modals.py`'s `_draw_loc_pts` / `docs/js/screens.js`'s `_drawLocPts`) — rather than inventing new visual language. The picker list itself gains one column header and a reworded caption. `main.py` / `docs/js/main.js`'s catalog-unavailable fallback drops its silent direct-append branch and always opens `SideQuestPickModal`, which already renders a graceful empty state.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** This is a clarity/polish follow-up to the already-shipped **B-sidequest** picker (`docs/superpowers/plans/2026-07-24-side-quest-picker.md`, part of the M4-B family — see `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md`). The TODO item under diagnosis (`TODO.md` Ideas): *"side quests modal for adding, not clear that we're setting the quest points.. and since the progress is readonly on this screen, its a bit confusing..."*

Diagnosis, from reading the live code and rendering the actual scenes (`python3 tools/preview.py side_quest_pick`, `side_quest_pick_empty`, `questing_progress_modal`):

- **There are two classes with "side quest" in the name; only one is reachable.** `SideQuestsModal` (`ui/modals.py:213`, `docs/js/screens.js:231`) is a simpler +/- stepper editor. A repo-wide grep for `SideQuestsModal(` (an actual instantiation, not the class definition or its lone import) returns **zero hits** anywhere in `ui/`, `docs/js/`, `main.py`, or `docs/js/main.js` — it is imported in `docs/js/screen_play.js:9` and unit-tested in isolation (`tests/test_modals.py:27`), but nothing ever opens it. The user's complaint is about the modal that actually opens today: **`SideQuestPickModal`** (`ui/modals.py:1716`, `docs/js/screens.js:1509`), reached from `QuestingProgressModal`'s "+ Side quest" button via the `pending_side_quest_pick` flag (`main.py:246-266`, `docs/js/main.js:357-379`). `SideQuestsModal` is out of this plan's scope — it is dead code, not a UI the user can reach.

- **On the picker screen (`side_quest_pick` scene), rendered:** title "Add Side Quest"; caption "Pick a side quest, then Add - or enter manually."; each row shows a radio glyph, the quest's name, and — right-aligned, in gold when selected — `"<N> pts"`, with the card's sphere in small dim text underneath. **Nothing on this screen says "target," "quest points," or mentions progress at all.** The only cue that `"8 pts"` means anything in particular is the literal string "pts" — there is no column header, no label tying it to what happens after you tap Add. A player who hasn't already internalized this app's Current/Target data model has no way to tell from this screen alone whether "8 pts" is the quest's current progress, its target, or just flavor text off the card.

- **"the progress is readonly on this screen" does not describe `QuestingProgressModal`** (the Progress-detail modal the picker is opened *from*): rendered there (`questing_progress_modal` scene), the header row explicitly labels two columns, **"Current"** and **"Target"**, and every row — including side quests — draws *both* as full circular `-`/`+` steppers (`ui/modals.py:923-936`, `_val_editor2`; the only difference is Current shows a filled progress ring and Target a dim empty one). Progress is fully editable there. The note's "this screen" therefore refers to the **picker/add screen itself**, where progress has **no representation at all** — not a disabled control, just absent — which reads as "readonly" in the sense that there is nothing to touch, and its absence is never explained, so the one number that *is* shown ("N pts") is ambiguous by contrast.

- **The "Manual" path is the sharpest version of the problem.** Today, tapping "Manual" (`ui/modals.py:1830-1833`, `docs/js/screens.js:1592-1596`) immediately does `game.side_quests.append({"points": 0, "progress": 0})` and closes — zero screens, zero feedback. The player only discovers what happened when a new "Side Quest N" row appears back on Progress-detail already sitting at `0/0`, and has to figure out on their own that the Target `+` stepper is how they now fix it.

- **A related, more extreme instance surfaced during research, outside the modal entirely:** when the side-quest catalog fails to load (`quest_catalog.load_player_side_quests()` returns `[]`), `main.py:255-266` / `docs/js/main.js:367-379` skip `SideQuestPickModal` altogether and directly `append({"points": 4, "progress": 0})` — a silent placeholder with no modal, no button press even required beyond the original "+ Side quest" tap. `SideQuestPickModal` already renders a graceful empty state for `entries == []` (the `side_quest_pick_empty` scene: "No side-quest catalog data available. Use Manual entry below." + a lone Manual button), so this fallback is redundant *and* the worst offender for "not clear we're setting the quest points." It is small to fix (Task 3) and directly serves the same complaint, so it is included.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror; identical layout, ids, and behavior.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter (`tests/test_layout.py`: no text collisions, all touch targets ≥24px in each dimension, everything inside 480×480). Add/extend scenes for every new visual state.
- **Match the vocabulary `QuestingProgressModal` already established** — "Target" and "Current" are its column headers (`ui/modals.py:1004-1006`); reuse "Target" verbatim on the add screen instead of a new synonym, so the same concept reads the same way on both screens.
- **ASCII punctuation only** — hyphen, not em-dash; this file's own comments already document why (`ui/modals.py:1781-1786`: the device's bitmap8 font only covers standard ASCII).
- **No `side_quests` data-model change.** Entries stay `{points, progress, name?}`; this is a presentation-only fix on top of the already-shipped B-sidequest shape.
- **Reuse existing widgets, don't invent new ones:** `stepper()` (`ui/widgets.py:79`, `docs/js/ui.js:90`) and `_footer()`/`footer()` (`ui/modals.py:20`, `docs/js/screens.js:99`) are already imported/defined in the files this plan touches — no new imports needed.
- **Manual-entry target defaults to 4 and clamps to 1-30** — the last known-good manual-entry convention in this codebase (dead `SideQuestsModal`'s own default/clamp, `ui/modals.py:254,258`). *If the user prefers a different default or a wider clamp (matching Progress-detail's own Target field, which clamps 0-99 once a quest exists), that's a one-line constant change in Task 2 — noted at that step.*

## File structure

- `ui/modals.py` / `docs/js/screens.js` — `SideQuestPickModal`: labelled picker list (Task 1) + new manual target-points sub-screen (Task 2).
- `main.py` / `docs/js/main.js` — the `pending_side_quest_pick` consumer: always route through `SideQuestPickModal`, even with an empty catalog (Task 3).
- `tests/scenes.py` — new `side_quest_pick_manual` scene.
- `tests/test_modals.py` — updated + new `SideQuestPickModal` behavior tests.

---

### Task 1: Label the picker list — "Target" column + progress hint

**Files:**
- Modify: `docs/js/screens.js:1538` (inside `SideQuestPickModal.draw`'s `entries.length` branch)
- Modify: `ui/modals.py:1764-1765` (same branch, `SideQuestPickModal.draw`)
- Test: `tests/test_modals.py` (append after line 754, end of file)

**Interfaces:**
- No new methods or state. Pure text-content/layout change inside the existing `draw()`/`draw(self, hw, game, pal)`.

**Exact copy:**
- Caption, replacing `"Pick a side quest, then Add - or enter manually."`: **`"Pick a side quest, then Add - progress starts at 0."`**
- New right-aligned column header, same line, above the per-row `"N pts"` values: **`"Target"`**

Both were measured against this repo's actual bitmap8 metrics (`tests/fake_hardware.measure_bitmap8`) before writing this plan: the caption is 237px wide at scale 1 (fits the 12-456px row easily), the header is 30px wide right-aligned to x=456 (starts at x=426) — an 176px gap separates them, so there is no collision with each other or with any row content below (rows start at y=66; this header line sits at y=46-54).

- [ ] **Step 1: Write the failing test.** Append to `tests/test_modals.py`:

```python
def test_side_quest_pick_labels_target_column_and_progress_hint():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Target" in texts
    assert "Pick a side quest, then Add - progress starts at 0." in texts
```

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest tests/test_modals.py -k target_column -v`
Expected: FAIL — `assert "Target" in texts` (neither string is drawn today).

- [ ] **Step 3: Implement in the web twin first.** In `docs/js/screens.js`, inside `SideQuestPickModal.draw`'s `else` branch (the `entries.length` case), change:

```js
      textLeft(ctx, "Pick a side quest, then Add - or enter manually.", 12, 46, 1, pal.dim);
```

to:

```js
      textLeft(ctx, "Pick a side quest, then Add - progress starts at 0.", 12, 46, 1, pal.dim);
      const tgtW = measureText("Target", 1);
      textLeft(ctx, "Target", 456 - tgtW, 46, 1, pal.dim);
```

- [ ] **Step 4: Mirror in the firmware.** In `ui/modals.py`, the equivalent block, change:

```python
            text_left(d, pal, "Pick a side quest, then Add - or enter manually.",
                      12, 46, 1, pal.dim)
```

to:

```python
            text_left(d, pal, "Pick a side quest, then Add - progress starts at 0.",
                      12, 46, 1, pal.dim)
            tgt_w = d.measure_text("Target", 1)
            text_left(d, pal, "Target", 456 - tgt_w, 46, 1, pal.dim)
```

- [ ] **Step 5: Run the test again.**

Run: `python3 -m pytest tests/test_modals.py -k target_column -v`
Expected: PASS.

- [ ] **Step 6: Render and inspect.** No scene changes needed — `side_quest_pick` already exercises the non-empty-entries branch:

```bash
python3 tools/preview.py side_quest_pick /tmp/sqp_target.png
```

Confirm: "Target" sits top-right, aligned above the "pts" column; the reworded caption doesn't run into it; nothing looks cramped. Also re-render `side_quest_pick_empty` as a smoke check — it uses the other branch and must render byte-for-byte as before.

- [ ] **Step 7: Full suite → green.**

Run: `python3 -m pytest tests/ -q`

- [ ] **Step 8: Commit.**

```bash
git add docs/js/screens.js ui/modals.py tests/test_modals.py
git commit -m "feat(sidequest): label the add-picker's target column and clarify progress starts at 0"
```

---

### Task 2: "Manual" opens a dedicated Target quest points screen

**Files:**
- Modify: `docs/js/screens.js` — `SideQuestPickModal` (constructor, `draw`, `onButton`; new `_drawManual`/`_onManualButton`)
- Modify: `ui/modals.py` — `SideQuestPickModal` (mirror)
- Modify: `tests/test_modals.py:712-732` (the two existing Manual tests — their asserted behavior changes) + append 3 new tests
- Modify: `tests/scenes.py` (new `side_quest_pick_manual` scene, alongside `_side_quest_pick`/`_side_quest_pick_empty` around line 704)

**Interfaces:**
- Produces: `SideQuestPickModal` gains `self.manual` (bool, default `False`) / `this.manual` and `self.manual_pts` (int, default `4`) / `this.manualPts`. New button ids: `("m_pts", -1|1)` / `["m_pts", -1|1]` (stepper), `("cancel",)` / `["cancel"]` (back to the list, no side quest added), `("save",)` / `["save"]` (commit the manual entry). `on_button`/`onButton` returns `"redraw"` for `"manual"`, stepper taps, and `"cancel"`; `"close"` for `"save"` (same as every other commit path in this file).
- Consumes: `stepper(d, pal, buttons, id_minus, id_plus, x, y, value_str, w, h)` / `stepper(ctx, buttons, idMinus, idPlus, x, y, valueStr, w, h)` and `_footer(d, pal, buttons, save_label=...)` / `footer(ctx, buttons, saveLabel)` — both already imported/defined in these files (`ui/modals.py:8-9,20`; `docs/js/screens.js:4-6,99`). Layout numbers copy `_draw_loc_pts`/`_drawLocPts` (`ui/modals.py:1108-1113`, `docs/js/screens.js:873-878`) exactly: title at `(240, 30)` scale 3, label at `(60, 216)` scale 2, stepper at `(250, 200, w=170, h=60)`, footer at the standard `(24/256, 404, 200, 64)` Cancel/Confirm pair — a pattern already proven to pass the layout linter.

**Exact copy:**
- Screen title: **`"Manual Side Quest"`**
- Caption (below the title): **`"Progress starts at 0 - set its target below."`**
- Field label: **`"Target quest points"`**
- Footer confirm button label: **`"Add"`**
- Log line on commit: **`"Side quest added manually: %d pts target (progress view)"`** (was `"Side quest added manually (progress view)"` — now says what got set, closing the same gap as the UI change).

All four strings were measured the same way as Task 1's: title is 243px at scale 3 (centered, fits); caption is 207px at scale 1 (centered at y=70, 16px clear of the title's bottom edge at y=54); label "Target quest points" is 184px at scale 2 starting at x=60, ending at x=244 — 6px clear of the stepper's left edge at x=250 (the original "Quest points" label is 114px in the same slot, so this is the same layout with a longer, still-safe, string).

- [ ] **Step 1: Update the two existing Manual tests, then add three new ones.**

Replace `tests/test_modals.py:712-732` (the two tests currently named `test_side_quest_pick_manual_falls_back_to_blank_entry` and `test_side_quest_pick_empty_entries_renders_and_offers_manual`) with:

```python
def test_side_quest_pick_manual_opens_target_points_screen():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("manual",))) == "redraw"
    assert m.manual is True
    assert game.side_quests == []          # nothing appended yet - just opened the screen
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Manual Side Quest" in texts
    assert "Target quest points" in texts
    assert "4" in texts                    # default target shown in the stepper


def test_side_quest_pick_empty_entries_manual_also_opens_target_points_screen():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.SideQuestPickModal(game, [])
    m.draw(hw, game, pal)          # must not raise
    assert any(b.id[0] == "manual" for b in m.buttons)
    assert not any(b.id[0] == "add" for b in m.buttons)   # nothing to add yet
    assert m.on_button(_find(m, ("manual",))) == "redraw"
    assert m.manual is True
    m.draw(hw, game, pal)          # must not raise with no catalog entries either
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Manual Side Quest" in texts
```

Append at the end of the file (after the current last line, `test_side_quest_pick_null_points_default_to_zero_and_pager_pages`):

```python


def test_side_quest_pick_manual_stepper_adjusts_and_confirms():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.SideQuestPickModal(game, [])
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("manual",)))
    m.draw(hw, game, pal)
    plus = _find(m, ("m_pts", 1))
    assert m.on_button(plus) == "redraw"
    assert m.on_button(plus) == "redraw"
    assert m.on_button(plus) == "redraw"
    assert m.manual_pts == 7               # 4 default + 3 taps
    assert m.on_button(_find(m, ("save",))) == "close"
    assert game.side_quests[-1] == {"points": 7, "progress": 0}


def test_side_quest_pick_manual_cancel_returns_to_list_without_adding():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("manual",)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("cancel",))) == "redraw"
    assert m.manual is False
    assert game.side_quests == []
    m.draw(hw, game, pal)                  # back on the list, still functional
    assert any(b.id[0] == "add" for b in m.buttons)


def test_side_quest_pick_manual_target_clamps_to_1():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.SideQuestPickModal(game, [])
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("manual",)))
    m.draw(hw, game, pal)
    minus = _find(m, ("m_pts", -1))
    for _ in range(10):
        m.on_button(minus)
    assert m.manual_pts == 1               # clamped, never 0 or negative
```

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest tests/test_modals.py -k side_quest_pick_manual -v`
Expected: FAIL — `AttributeError: 'SideQuestPickModal' object has no attribute 'manual'`.

- [ ] **Step 3: Implement the web twin first.** In `docs/js/screens.js`, replace the whole `SideQuestPickModal` class body's constructor/`draw`/`onButton`, and add the two new methods, so the class reads:

```js
export class SideQuestPickModal {
  static PER_PAGE = 6;
  static ROW_H = 44;
  static ROW_STRIDE = 46;
  static LIST_Y0 = 66;
  static NAME_MAX_W = 300;
  static FOOTER_Y = 404;
  static FOOTER_H = 64;

  constructor(game, entries) {
    this.game = game;
    this.entries = entries;
    this.selected = entries.length ? entries[0].id : null;
    this.page = 0;
    this.manual = false;      // true while the dedicated target-points screen is open
    this.manualPts = 4;       // default target for a manually-added side quest
    this.buttons = [];
  }

  _pages() { return Math.max(1, Math.ceil(this.entries.length / SideQuestPickModal.PER_PAGE)); }

  draw(ctx) {
    const { PER_PAGE, ROW_H, ROW_STRIDE, LIST_Y0, NAME_MAX_W, FOOTER_Y, FOOTER_H } = SideQuestPickModal;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.manual) { this._drawManual(ctx); return; }
    modalHeader(ctx, this.game, "Add Side Quest", this.buttons);

    if (!this.entries.length) {
      textCenter(ctx, "No side-quest catalog data available.", 240, 140, 2, pal.dim);
      textCenter(ctx, "Use Manual entry below.", 240, 168, 1, pal.dim);
    } else {
      textLeft(ctx, "Pick a side quest, then Add - progress starts at 0.", 12, 46, 1, pal.dim);
      const tgtW = measureText("Target", 1);
      textLeft(ctx, "Target", 456 - tgtW, 46, 1, pal.dim);
      const pages = this._pages();
      this.page = Math.min(this.page, pages - 1);
      const chunk = this.entries.slice(this.page * PER_PAGE, (this.page + 1) * PER_PAGE);
      let y = LIST_Y0;
      for (const e of chunk) {
        const on = e.id === this.selected;
        if (on) rect(ctx, 8, y, 456, ROW_H, pal.card_hi);
        sqRadio(ctx, 30, y + 22, on);
        const name = truncateText(e.name ?? "", 2, NAME_MAX_W);
        textLeft(ctx, name, 52, y + 13, 2, on ? pal.tan : pal.muted);
        const ptsS = `${e.points ?? 0} pts`;
        const pw = measureText(ptsS, 2);
        textLeft(ctx, ptsS, 456 - pw, y + 4, 2, on ? pal.gold : pal.tan);
        const sphereS = e.sphere || "-";
        const sw = measureText(sphereS, 1);
        textLeft(ctx, sphereS, 456 - sw, y + 26, 1, pal.dim);
        rect(ctx, 8, y + ROW_H, 456, 1, pal.border);
        this.buttons.push(new Button(["row", e.id], 8, y, 456, ROW_H));
        y += ROW_STRIDE;
      }
      if (pages > 1) {
        const up = new Button(["older"], 12, 352, 150, 46);
        const dn = new Button(["newer"], 318, 352, 150, 46);
        bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
        textCenter(ctx, "Up", up.x + 75, up.y + 14, 2, pal.tan);
        bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
        textCenter(ctx, "Down", dn.x + 75, dn.y + 14, 2, pal.tan);
        textCenter(ctx, `${this.page + 1}/${pages}`, 240, 366, 2, pal.muted);
        this.buttons.push(up, dn);
      }
    }

    const manual = new Button(["manual"], 24, FOOTER_Y, 200, FOOTER_H);
    bevel(ctx, manual.x, manual.y, manual.w, manual.h, pal.btn, false, 3);
    textCenter(ctx, "Manual", manual.x + manual.w / 2, manual.y + 20, 2, pal.tan);
    this.buttons.push(manual);

    if (this.entries.length) {
      const add = new Button(["add"], 256, FOOTER_Y, 200, FOOTER_H);
      bevel(ctx, add.x, add.y, add.w, add.h, pal.btn_ok, false, 3);
      textCenter(ctx, "Add", add.x + add.w / 2, add.y + 20, 2, pal.ok_fg);
      this.buttons.push(add);
    }
  }

  _drawManual(ctx) {
    textCenter(ctx, "Manual Side Quest", 240, 30, 3, pal.gold);
    textCenter(ctx, "Progress starts at 0 - set its target below.", 240, 70, 1, pal.dim);
    textLeft(ctx, "Target quest points", 60, 216, 2, pal.tan);
    stepper(ctx, this.buttons, ["m_pts", -1], ["m_pts", 1], 250, 200, String(this.manualPts), 170, 60);
    footer(ctx, this.buttons, "Add");
  }

  onButton(btn) {
    if (this.manual) return this._onManualButton(btn);
    const k = btn.id[0];
    if (k === "close") return "close";
    if (k === "row") { this.selected = btn.id[1]; return "redraw"; }
    if (k === "older") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    if (k === "newer") { this.page = Math.min(this._pages() - 1, this.page + 1); return "redraw"; }
    if (k === "manual") { this.manual = true; return "redraw"; }
    if (k === "add") {
      const e = this.entries.find(x => x.id === this.selected);
      if (e) {
        const pts = e.points ?? 0;
        this.game.side_quests.push({ points: pts, progress: 0, name: e.name });
        this.game.logEvent(`Side quest added: ${e.name} (${pts} pts, progress view)`);
      }
      return "close";
    }
    return null;
  }

  _onManualButton(btn) {
    const k = btn.id[0];
    if (k === "m_pts") {
      this.manualPts = Math.max(1, Math.min(30, this.manualPts + btn.id[1]));
      return "redraw";
    }
    if (k === "cancel") { this.manual = false; return "redraw"; }
    if (k === "save") {
      this.game.side_quests.push({ points: this.manualPts, progress: 0 });
      this.game.logEvent(`Side quest added manually: ${this.manualPts} pts target (progress view)`);
      return "close";
    }
    return null;
  }
}
```

- [ ] **Step 4: Mirror in the firmware.** In `ui/modals.py`, replace `SideQuestPickModal`'s `__init__`, `draw`, `on_button`, and add the two new methods, so the class reads:

```python
class SideQuestPickModal:
    """Picker over the player side-quest catalog (M4-B sidequest, Task 2):
    radio-select list (name / points / sphere), Up/Down pager (mirrors
    ChooseScenarioScreen/PickCycleScreen in ui/screen_quest.py - same row
    stride/pager geometry, same radio glyph), plus Add (commits the
    selection) and Manual (opens a dedicated Target quest points screen,
    side-quest add-flow clarity - see docs/superpowers/plans/
    2026-07-25-side-quest-clarity.md).

    Opened from QuestingProgressModal's "+ Side quest" button via the
    pending_side_quest_pick flag (see main.py's loop) - constructed with the
    already-loaded catalog entries (quest_catalog.side_quests(...) shape:
    {"id","name","points","sphere","pack"}), never reads the catalog itself.

    Empty `entries` (no catalog data) still renders and offers Manual rather
    than raising - defense in depth; the call site now always opens this
    modal regardless of whether entries is empty (Task 3 of the clarity
    plan above)."""

    PER_PAGE = 6
    ROW_H = 44
    ROW_STRIDE = 46
    LIST_Y0 = 66
    NAME_MAX_W = 300
    FOOTER_Y = 404
    FOOTER_H = 64

    def __init__(self, game, entries):
        self.game = game
        self.entries = entries
        self.selected = entries[0]["id"] if entries else None
        self.page = 0
        self.manual = False   # True while the dedicated target-points screen is open
        self.manual_pts = 4   # default target for a manually-added side quest
        self.buttons = []

    def _pages(self):
        return max(1, -(-len(self.entries) // self.PER_PAGE))

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        if self.manual:
            self._draw_manual(d, pal)
            return
        modal_header(d, pal, game, "Add Side Quest", self.buttons)

        if not self.entries:
            text_center(d, pal, "No side-quest catalog data available.", 240, 140, 2, pal.dim)
            text_center(d, pal, "Use Manual entry below.", 240, 168, 1, pal.dim)
        else:
            text_left(d, pal, "Pick a side quest, then Add - progress starts at 0.",
                      12, 46, 1, pal.dim)
            tgt_w = d.measure_text("Target", 1)
            text_left(d, pal, "Target", 456 - tgt_w, 46, 1, pal.dim)
            pages = self._pages()
            self.page = min(self.page, pages - 1)
            chunk = self.entries[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
            y = self.LIST_Y0
            for e in chunk:
                on = e["id"] == self.selected
                if on:
                    d.set_pen(pal.card_hi)
                    d.rectangle(8, y, 456, self.ROW_H)
                _sq_radio(d, pal, 30, y + 22, on)
                name = truncate_text(e.get("name") or "", 2, self.NAME_MAX_W, d.measure_text)
                text_left(d, pal, name, 52, y + 13, 2, pal.tan if on else pal.muted)
                pts_s = "%d pts" % (e.get("points") or 0)
                pw = d.measure_text(pts_s, 2)
                text_left(d, pal, pts_s, 456 - pw, y + 4, 2, pal.gold if on else pal.tan)
                sphere_s = e.get("sphere") or "-"
                sw = d.measure_text(sphere_s, 1)
                text_left(d, pal, sphere_s, 456 - sw, y + 26, 1, pal.dim)
                d.set_pen(pal.border)
                d.rectangle(8, y + self.ROW_H, 456, 1)
                self.buttons.append(Button(("row", e["id"]), 8, y, 456, self.ROW_H))
                y += self.ROW_STRIDE

            if pages > 1:
                up = Button(("older",), 12, 352, 150, 46)
                dn = Button(("newer",), 318, 352, 150, 46)
                bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
                text_center(d, pal, "Up", up.x + 75, up.y + 14, 2, pal.tan)
                bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
                text_center(d, pal, "Down", dn.x + 75, dn.y + 14, 2, pal.tan)
                text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 366, 2, pal.muted)
                self.buttons.append(up)
                self.buttons.append(dn)

        manual = Button(("manual",), 24, self.FOOTER_Y, 200, self.FOOTER_H)
        bevel(d, pal, manual.x, manual.y, manual.w, manual.h, pal.btn, t=3)
        text_center(d, pal, "Manual", manual.x + manual.w / 2, manual.y + 20, 2, pal.tan)
        self.buttons.append(manual)

        if self.entries:
            add = Button(("add",), 256, self.FOOTER_Y, 200, self.FOOTER_H)
            bevel(d, pal, add.x, add.y, add.w, add.h, pal.btn_ok, t=3)
            text_center(d, pal, "Add", add.x + add.w / 2, add.y + 20, 2, pal.ok_fg)
            self.buttons.append(add)

    def _draw_manual(self, d, pal):
        text_center(d, pal, "Manual Side Quest", 240, 30, 3, pal.gold)
        text_center(d, pal, "Progress starts at 0 - set its target below.", 240, 70, 1, pal.dim)
        text_left(d, pal, "Target quest points", 60, 216, 2, pal.tan)
        stepper(d, pal, self.buttons, ("m_pts", -1), ("m_pts", 1), 250, 200,
               str(self.manual_pts), 170, 60)
        _footer(d, pal, self.buttons, save_label="Add")

    def on_button(self, btn):
        if self.manual:
            return self._on_manual_button(btn)
        k = btn.id[0]
        if k == "close":
            return "close"
        if k == "row":
            self.selected = btn.id[1]
            return "redraw"
        if k == "older":
            self.page = max(0, self.page - 1)
            return "redraw"
        if k == "newer":
            self.page = min(self._pages() - 1, self.page + 1)
            return "redraw"
        if k == "manual":
            self.manual = True
            return "redraw"
        if k == "add":
            e = next((x for x in self.entries if x["id"] == self.selected), None)
            if e:
                pts = e.get("points") or 0
                self.game.side_quests.append({"points": pts, "progress": 0,
                                              "name": e.get("name")})
                self.game.log_event("Side quest added: %s (%d pts, progress view)"
                                    % (e.get("name"), pts))
            return "close"
        return None

    def _on_manual_button(self, btn):
        k = btn.id[0]
        if k == "m_pts":
            self.manual_pts = max(1, min(30, self.manual_pts + btn.id[1]))
            return "redraw"
        if k == "cancel":
            self.manual = False
            return "redraw"
        if k == "save":
            self.game.side_quests.append({"points": self.manual_pts, "progress": 0})
            self.game.log_event("Side quest added manually: %d pts target (progress view)"
                                % self.manual_pts)
            return "close"
        return None
```

- [ ] **Step 5: Add the scene.** In `tests/scenes.py`, immediately after `_side_quest_pick_empty` (around line 704) add:

```python
def _side_quest_pick_manual():
    # Manual-entry sub-screen (side-quest add-flow clarity, 2026-07-25):
    # opened via SideQuestPickModal's "Manual" button instead of a blind
    # append - exercises the dedicated Target quest points stepper. Set
    # before the single draw() call, same reason as
    # _questing_progress_modal_loc_pts: FakeDisplay.calls accumulates
    # across draw() calls, so drawing the list first would leave stale text
    # around and produce false-positive collisions.
    from ui.modals import SideQuestPickModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = SideQuestPickModal(g, list(_SIDE_QUEST_SAMPLE))
    m.manual = True
    m.draw(hw, g, pal)
    return hw, m
```

And register it in the `SCENES` dict next to the other two side-quest-pick entries:

```python
    "side_quest_pick_manual": _side_quest_pick_manual,
```

- [ ] **Step 6: Run the tests again.**

Run: `python3 -m pytest tests/test_modals.py -k side_quest_pick -v`
Expected: all PASS, including the two updated tests and the three new ones.

- [ ] **Step 7: Layout lint + render.**

```bash
python3 -m pytest tests/test_layout.py -q
python3 tools/preview.py side_quest_pick_manual /tmp/sqp_manual.png
python3 tools/preview.py side_quest_pick /tmp/sqp_list.png
python3 tools/preview.py side_quest_pick_empty /tmp/sqp_empty.png
```

Confirm on `side_quest_pick_manual`: title, caption, "Target quest points" label, and the `[-][4][+]` stepper are all legible and non-overlapping; Cancel/Add footer matches the app's standard confirm-pair styling. Confirm the other two scenes still render exactly as before (Task 2 only touches the `manual` branch and the constructor/on_button dispatch, not the list-rendering code Task 1 already covered).

- [ ] **Step 8: Browser walkthrough.** Serve `docs/` (build card data first if `docs/data/` is missing: `python3 tools/build_card_data.py`). New Game → any scenario → reach round 1 → Progress detail → "+ Side quest" → confirm the picker shows the new "Target" header/caption from Task 1 → tap **Manual** → confirm "Manual Side Quest" opens with the stepper defaulted to 4 → tap `+` a few times → **Add** → confirm a new side-quest row appears on Progress-detail with the chosen number as its Target and `0` as Current. Then repeat, tapping **Cancel** on the manual screen instead, and confirm it returns to the picker list with nothing added. Report any console errors.

- [ ] **Step 9: Full suite → green.**

Run: `python3 -m pytest tests/ -q`

- [ ] **Step 10: Commit.**

```bash
git add docs/js/screens.js ui/modals.py tests/scenes.py tests/test_modals.py
git commit -m "feat(sidequest): manual add opens an explicit target-points screen"
```

---

### Task 3: Route the catalog-unavailable fallback through the same modal

**Files:**
- Modify: `docs/js/main.js:357-379` (the `pending_side_quest_pick` handler)
- Modify: `main.py:246-266` (same handler)

**Interfaces:**
- Consumes: `SideQuestPickModal(game, entries)` from Task 2 — already handles `entries == []` gracefully (rendered and tested in Task 2/side-quest-picker.md's own coverage).
- No new interfaces produced; this task deletes a branch.

**Note on testing this task:** `main.py`'s run loop (`def main():`) and its JS mirror are the device/browser event loop — nothing in `tests/` imports or exercises `main.py` directly (confirmed: no test file references `import main` or calls into its loop), so there is no pytest seam for this branch today. The reference precedent for entry-point/router wiring in this codebase (`docs/superpowers/plans/2026-07-24-quest-card-modal.md`, Task 2) is a direct edit + explicit browser verification rather than a fabricated unit test, and this task follows the same pattern.

- [ ] **Step 1: Edit the web twin first.** In `docs/js/main.js`, replace:

```js
    // Progress-detail "+ Side quest" tap (SideQuestPickModal entry point):
    // same pending-flag pattern as pending_quest_card above - the picker
    // needs a catalog fetch, which QuestingProgressModal.onButton can't
    // await mid-tap without breaking the modal-replaces-modal invariant, so
    // it flags this instead and the fetch happens here, once modal is null.
    // pending_side_quest_pick is cleared synchronously so a later tick can't
    // re-enter this block while the fetch is in flight. A missing/
    // unreadable catalog (loadPlayerSideQuests() resolves []) skips the
    // picker and keeps today's direct-append behavior instead of showing an
    // empty list.
    if (!modal && active === "play" && game.pending_side_quest_pick) {
      game.pending_side_quest_pick = false;
      loadPlayerSideQuests().then(entries => {
        if (entries.length) {
          modal = new SideQuestPickModal(game, entries);
        } else {
          game.side_quests.push({ points: 4, progress: 0 });
          game.logEvent(`Side quest ${game.side_quests.length} added (progress view)`);
          saveState(game);
        }
        dirty = true;
      });
    }
```

with:

```js
    // Progress-detail "+ Side quest" tap (SideQuestPickModal entry point):
    // same pending-flag pattern as pending_quest_card above - the picker
    // needs a catalog fetch, which QuestingProgressModal.onButton can't
    // await mid-tap without breaking the modal-replaces-modal invariant, so
    // it flags this instead and the fetch happens here, once modal is null.
    // pending_side_quest_pick is cleared synchronously so a later tick can't
    // re-enter this block while the fetch is in flight. A missing/
    // unreadable catalog (loadPlayerSideQuests() resolves []) still opens
    // the picker - its empty-entries state (side-quest add-flow clarity,
    // 2026-07-25) offers Manual entry through the same explicit Target
    // quest points screen instead of silently appending a blind 4pt
    // placeholder with no screen at all.
    if (!modal && active === "play" && game.pending_side_quest_pick) {
      game.pending_side_quest_pick = false;
      loadPlayerSideQuests().then(entries => {
        modal = new SideQuestPickModal(game, entries);
        dirty = true;
      });
    }
```

- [ ] **Step 2: Mirror in the firmware.** In `main.py`, replace:

```python
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
```

with:

```python
        # Progress-detail "+ Side quest" tap (SideQuestPickModal entry
        # point): same pending-flag pattern as pending_quest_card above -
        # the picker needs a catalog read (flash I/O) that
        # QuestingProgressModal.on_button can't do mid-tap without breaking
        # the modal-replaces-modal invariant, so it flags this instead and
        # the read happens here, once modal is None. A missing/unreadable
        # catalog (load_player_side_quests() returns []) still opens the
        # picker - its empty-entries state (side-quest add-flow clarity,
        # 2026-07-25) offers Manual entry through the same explicit Target
        # quest points screen instead of silently appending a blind 4pt
        # placeholder with no screen at all.
        if modal is None and active == "play" and game.pending_side_quest_pick:
            game.pending_side_quest_pick = False
            from ui.modals import SideQuestPickModal
            entries = quest_catalog.load_player_side_quests()
            modal = SideQuestPickModal(game, entries)
            dirty = True
            continue
```

- [ ] **Step 3: Browser walkthrough — both paths.** Normal path: confirm "+ Side quest" still opens the picker with real entries as in Task 2 Step 8. Failure path: temporarily rename `docs/data/players` on disk (e.g. `mv docs/data/players docs/data/players.bak`) so `loadPlayerSideQuests()` resolves `[]`, refresh, reach Progress detail, tap "+ Side quest" — confirm the picker now opens showing "No side-quest catalog data available. Use Manual entry below." (the `side_quest_pick_empty` scene's content) instead of a row silently appearing, and that Manual still leads to the Task 2 target-points screen. Restore the directory afterward (`mv docs/data/players.bak docs/data/players`) and confirm normal play resumes.

- [ ] **Step 4: Full suite → green.**

Run: `python3 -m pytest tests/ -q`

- [ ] **Step 5: Commit.**

```bash
git add docs/js/main.js main.py
git commit -m "feat(sidequest): route the catalog-unavailable fallback through the picker modal"
```

---

## Self-Review

**Spec coverage:**
- *"not clear that we're setting the quest points"* on the catalog-pick path → **Task 1** (the "Target" column header ties the row's `"N pts"` value to the same word `QuestingProgressModal` uses for that exact field).
- Same complaint on the manual path, where previously nothing was shown at all → **Task 2** (a full screen titled "Manual Side Quest" with a "Target quest points" label directly above a live `[-][value][+]` stepper — the value is no longer invisible, it's the whole screen).
- *"the progress is readonly on this screen, its a bit confusing"* → diagnosed in Context as describing the add screen's total absence of a progress control (not `QuestingProgressModal`, where Current/Target are both already editable — verified by rendering `questing_progress_modal`) → addressed by both screens' new copy stating explicitly that progress starts at 0, closing the ambiguity instead of leaving it implicit.
- *"visual distinction between editable and read-only values"* → catalog rows keep their plain (non-stepper) presentation, now labeled "Target" as a read-only preview of what Add will copy in; the Manual screen's value uses this app's one established editable-numeric-field affordance (`stepper()`, the same widget `QuestingProgressModal`'s own Target field and the location-replace flow use) — editable vs. preview-only is visually consistent with the rest of the app rather than a new convention invented for this screen.
- *"whatever affordance makes the add-flow obvious"* → **Task 3** closes the one remaining silent path (catalog load failure) so every "+ Side quest" tap always lands on one consistent, labeled modal — never a row that just appears.
- Explicitly out of scope, with reasons given in Context: the dead `SideQuestsModal` class (confirmed unreachable by a repo-wide grep for real instantiations — not what the user is describing, since they can't reach it); any `side_quests` data-model change (this is presentation-only); `QuestingProgressModal`'s own Current/Target steppers (already correctly editable and distinguished by the diagnosis, not the source of the confusion).

**Placeholder scan:** Tasks 1-2 carry complete test code with concrete assertions and the exact copy strings, measured against this repo's real font metrics before being written down (no "TBD" widths). Task 3's absence of a unit test is explained, not glossed over, and points at the specific precedent (`quest-card-modal.md` Task 2) that already establishes direct-edit-plus-browser-verification as this codebase's pattern for router/entry-point wiring the test suite can't reach.

**Type consistency:** `self.manual`/`this.manual` (bool) and `self.manual_pts`/`this.manualPts` (int, default 4, clamped 1-30) are introduced once in Task 2 and used with those exact names in its own tests, its scene, and Task 3's context. Button id tuples `("m_pts", -1|1)` / `["m_pts", -1|1]`, `("cancel",)` / `["cancel"]`, `("save",)` / `["save"]` match between the Task 2 implementation and its tests in every step. `SideQuestPickModal(game, entries)`'s constructor signature is unchanged from the already-shipped B-sidequest version, so Task 3's call sites need no changes beyond dropping the `if entries:` branch.
