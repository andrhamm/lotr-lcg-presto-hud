# Tablet milestone 4 — Log and rewind — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The tablet exposes the replay cursor in three places — the strip's ticks and transport, the log block's "Open ›" Game Log screen, and that screen's "Rewind to selected line" — and the log tells the truth about history: undone lines grey out, and the next edit drops them.

**Architecture:** Two small model changes land in **both twins** first (a delta remembers the view and round it landed on; truncating the redo future also truncates the log rows it orphans, with a tombstone the log fold understands). The tablet then adds one acts module for the transport (`acts_transport.js`), one for the log screen (`acts_log.js`), a pure renderer per surface (`screen_log.js`, `sheet_export.js`), and a pure filter module (`logfilter.js`). `app.js` remains the only file that touches the DOM or a browser API (scroll-to-bottom, clipboard).

**Tech Stack:** ES modules (`docs/js/`, `docs/tablet/js/`), MicroPython-compatible Python (`gamestate.py`), pytest driving node (`tests/test_tablet*.py`).

**Spec:** `docs/superpowers/specs/2026-09-05-tablet-client-design.md` — sections "The strip", "The left column" (log block), "Modals and full screens" (Game Log row), "Rewind", "Testing".

## Global Constraints

- **Web first, then firmware, in lockstep** (CLAUDE.md iron rule 1): every model change here lands in `docs/js/gamestate.js` AND `gamestate.py` in the same task, with a parity test.
- Generated files (`docs/js/{phases,icons,metrics,viewcopy,xtargets,icons_svg}.js`) are never hand-edited.
- `python3 -m pytest tests/` stays green (2468 at plan time); `tests/test_tablet_tokens.py` and `tests/test_no_stray_io.py` are part of it.
- **No DOM/browser API outside `docs/tablet/js/app.js`**; no `fetch`/`localStorage` outside `docs/js/db.js` (`test_no_stray_io.py` walks `docs/tablet/`).
- Pure renderers return strings via `h`` `/`raw()` from `dom.js`; a fragment built with `h`` ` interpolated into another `h`` ` goes through `raw(...)`; never pass an HTML entity through an interpolation (use the Unicode character).
- Design system: anything read as a sentence, a name or an option is BODY (18px, class `body`); LABEL (13px ALL-CAPS) is chrome and dense tabular metadata only; sizes on the 34/20/18/13 scale (numerals allowlist `num-26/34/36`); every tap target ≥ 44px; `tests/test_tablet_tokens.py` gates button classes by name.
- Never ship an unverified rules claim. This milestone adds NO sentence about how the game works — the explainer copy is about the app (rewinding, greyed lines, edits), nothing else.
- The common round stays at 20 taps (`test_the_common_round_costs_at_most_20_taps`); nothing here is on that path.
- Acts handlers never call `beginAction`/`addDelta`; `perform()` brackets every tap. A cursor move returns `true` from `dispatch` (re-render + record) while `addDelta` records nothing (`_replay_moved` guard) — that is the existing contract, keep it.
- Log strings and copy the twin already ships are reused verbatim (imports from `docs/js/viewcopy.js`), never re-worded in `copy.js`.

## Rulings made while planning (the spec is silent or optimistic)

- **R1 — "Nothing new in the model" is not quite true.** A tick tap needs to know which delta entered a view; the log needs to know which rows an edit orphaned. Both twins get: `_delta_metadata.view`/`.round`, `deltaIndexForView(round, view)`, and log truncation with a `{op:"lt", lo, hi}` tombstone in the log store. Cost if wrong: a few lines in two files plus one fold rule.
- **R2 — What "an edit truncates them" means:** rows whose `delta_i` lies in the discarded redo future are removed from `game.log` at the moment `addDelta` truncates `deltas`. Known limitation, documented in code: a keyed tally row re-tallied inside the undone stretch is removed with it even though its earlier value survives in the kept state (its `delta_i` was restamped). The log is advisory; the tracker never blocks.
- **R3 — Strip transport = four controls** (⏮ first, ◀ undo, ▶ redo, ⏭ last) in the strip's round block; round-granularity (◀◀ ▶▶) lives on the Game Log screen only. The strip is 96px tall; six 44px buttons would starve the segments.
- **R4 — Ticks are the one un-bevelled tap target.** A 44px-tall transparent button wraps each tick that has a rewind target; the glyph stays the same size. The Game Log's side panel explains rewinding, which covers discoverability.
- **R5 — Game Log order is terminal order:** oldest at the top, newest at the bottom, scrolled to the bottom on open (the twin reverses; the spec says terminal).
- **R6 — Filters are text predicates over our own log strings** (`logfilter.js`), not new categories on `logEvent` — no both-twins churn across ~40 call sites. A test drives the model and asserts each real line lands in the right filter, so a reworded string fails loudly.
- **R7 — Export = a sheet with the log as plain text in a read-only textarea plus a Copy chip**; `app.js` performs the clipboard write (browser API). No download link (viewer sandboxes block them).
- **R8 — While the Game Log is open, `afterTap` does not auto-open sheets;** closing the screen runs it once, so a rewind that lands on a pending resolution opens the resolution sheet then, not under the log.

---

### Task 1: Delta metadata and log truncation (both twins)

**Files:**
- Modify: `docs/js/gamestate.js` (`foldLog` ~232, `addDelta` ~1613, add `deltaIndexForView` after `canRedo` ~1666)
- Modify: `gamestate.py` (`fold_log` ~289, `add_delta` ~1922, add `delta_index_for_view` after `can_redo`)
- Test: `tests/test_replay_metadata.py` (new), `tests/test_twin_parity.py` (one new parity test)

**Interfaces:**
- Produces (JS): `game.deltas[i]._delta_metadata = {unix_ms, log_messages, view, round}`; `game.deltaIndexForView(round, view) → number` (first matching delta index, else `-1`); `foldLog(records)` understands `{op:"lt", lo, hi}`; `game.takeLogAppends()` may now yield that op record.
- Produces (Py): `_delta_metadata` dict with `"view"`, `"round"`; `delta_index_for_view(round, view)`; `fold_log` understands `{"op": "lt", "lo": .., "hi": ..}`.
- Consumers: Task 2 (`deltaIndexForView`), Task 3 (greyed rows use `e.delta_i > game.replay_step`; dropped rows simply vanish), `db.js`/`db.py` need no change — they already persist whatever `takeLogAppends()` yields and fold on load.

- [ ] **Step 1: Failing tests (Python, drives both twins)**

```python
# tests/test_replay_metadata.py
"""A delta remembers the view and round it landed on, and truncating the redo
future truncates the log rows it orphaned (with a tombstone the fold applies).
Both twins."""
import json, os, shutil, subprocess, sys, tempfile
import pytest
from gamestate import GameState, fold_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _tap(g, fn):
    snap = g.begin_action()
    fn()
    return g.add_delta(snap)


def _two_view_game():
    g = GameState(2)
    g.view = "resource"
    _tap(g, lambda: g.set_staging(1))                 # delta 0, view resource
    _tap(g, lambda: g.advance_view())                 # delta 1, lands on planning
    _tap(g, lambda: g.set_staging(2))                 # delta 2, view planning
    return g


def test_delta_metadata_carries_view_and_round():
    g = _two_view_game()
    md = [d["_delta_metadata"] for d in g.deltas]
    assert [m["view"] for m in md] == ["resource", "planning", "planning"]
    assert all(m["round"] == g.round for m in md)


def test_delta_index_for_view_is_the_entry_delta_or_minus_one():
    g = _two_view_game()
    assert g.delta_index_for_view(g.round, "planning") == 1
    assert g.delta_index_for_view(g.round, "resource") == 0
    assert g.delta_index_for_view(g.round, "combat_shadow") == -1
    assert g.delta_index_for_view(g.round + 1, "planning") == -1


def test_an_edit_after_undo_drops_the_orphaned_rows_and_tombstones_them():
    g = _two_view_game()
    g.take_log_appends()                               # clear the queue
    orphan = [e for e in g.log if e.get("delta_i") == 2]
    assert orphan and orphan[0]["text"] == "Staging area threat 2"
    assert g.undo()                                    # back to delta 1
    _tap(g, lambda: g.set_willpower(3))                # truncates the future
    assert all(e.get("delta_i") != 2 or e["text"] != "Staging area threat 2"
               for e in g.log if "delta_i" in e and e["delta_i"] <= g.replay_step)
    assert not any(e["text"] == "Staging area threat 2" for e in g.log)
    ops = [r for r in g.take_log_appends() if r.get("op") == "lt"]
    assert len(ops) == 1
    assert ops[0]["lo"] == orphan[0]["seq"] == ops[0]["hi"]


def test_fold_log_applies_the_tombstone():
    rows = [{"seq": 1, "round": 1, "step": "1.1", "text": "a"},
            {"seq": 2, "round": 1, "step": "1.1", "text": "b"},
            {"seq": 3, "round": 1, "step": "1.1", "text": "c"},
            {"op": "lt", "lo": 2, "hi": 2},
            {"seq": 4, "round": 1, "step": "1.1", "text": "d"}]
    assert [e["text"] for e in fold_log(rows)] == ["a", "c", "d"]


def test_fold_reproduces_the_live_log_after_undo_and_edit():
    g = _two_view_game()
    appends = list(g.take_log_appends())
    g.undo()
    _tap(g, lambda: g.set_willpower(3))
    appends += g.take_log_appends()
    assert fold_log(appends) == g.log


def test_undo_alone_keeps_the_rows_and_writes_no_tombstone():
    g = _two_view_game()
    g.take_log_appends()
    g.undo()
    assert any(e["text"] == "Staging area threat 2" for e in g.log)
    assert not any(r.get("op") == "lt" for r in g.take_log_appends())
```

Parity probe appended to `tests/test_twin_parity.py` (copy the file's existing node-staging helper; do not write a second one):

```python
def test_delta_metadata_and_log_truncation_match_the_twin():
    js = _node("""
import { GameState, foldLog } from "./gamestate.js";
const g = new GameState(2); g.view = "resource";
const tap = fn => { const s = g.beginAction(); fn(); return g.addDelta(s); };
tap(() => g.setStaging(1)); tap(() => g.advanceView()); tap(() => g.setStaging(2));
const views = g.deltas.map(d => d._delta_metadata.view);
const idx = [g.deltaIndexForView(g.round, "planning"), g.deltaIndexForView(g.round, "resource"), g.deltaIndexForView(g.round, "combat_shadow")];
let appends = g.takeLogAppends();
g.undo(); tap(() => g.setWillpower(3));
appends = appends.concat(g.takeLogAppends());
console.log(JSON.stringify({ views, idx,
  folded: foldLog(appends).map(e => e.text), live: g.log.map(e => e.text),
  ops: appends.filter(r => r.op === "lt").length }));
""")
    g = GameState(2); g.view = "resource"
    def tap(fn):
        s = g.begin_action(); fn(); return g.add_delta(s)
    tap(lambda: g.set_staging(1)); tap(lambda: g.advance_view()); tap(lambda: g.set_staging(2))
    assert js["views"] == [d["_delta_metadata"]["view"] for d in g.deltas]
    assert js["idx"] == [g.delta_index_for_view(g.round, v) for v in ("planning", "resource", "combat_shadow")]
    appends = list(g.take_log_appends()); g.undo(); tap(lambda: g.set_willpower(3))
    appends += g.take_log_appends()
    assert js["live"] == [e["text"] for e in g.log]
    assert js["folded"] == js["live"] == [e["text"] for e in fold_log(appends)]
    assert js["ops"] == 1
```

- [ ] **Step 2: Run, expect failures** — `python3 -m pytest tests/test_replay_metadata.py tests/test_twin_parity.py -q` → `AttributeError: delta_index_for_view` / KeyError `view`.

- [ ] **Step 3: JS implementation**

In `addDelta`, replace the metadata line and the truncation block:

```js
    d._delta_metadata = { unix_ms: this._now(), log_messages: this.messages,
                          view: this.view, round: this.round };
    // A fresh action after an undo discards the redo future. The journal
    // cannot un-append, so record the truncation instead - and the log rows
    // that future produced go with it (design spec, "Rewind": later entries
    // stay greyed until an edit truncates them). Rows are contiguous in seq:
    // kept deltas' rows < the orphaned rows < this action's own rows (which
    // have no delta_i yet), so one [lo, hi] range names them all. Known
    // limitation: a keyed tally row re-tallied inside the undone stretch had
    // its delta_i restamped there and is dropped too, though its earlier value
    // survives in the kept state. The log is advisory.
    if (this.replay_step + 1 < this.deltas.length) {
      this._replay_appends.push({ op: "t", to: this.replay_step + 1 });
      this._truncateLog(this.replay_step);
    }
```

Add the helper and the lookup beside `canRedo`:

```js
  // Drop log rows produced by deltas past `keep` (the redo future an edit
  // just discarded) and journal the same cut for foldLog.
  _truncateLog(keep) {
    const gone = this.log.filter(e => typeof e.delta_i === "number" && e.delta_i > keep);
    if (!gone.length) return;
    const lo = Math.min(...gone.map(e => e.seq)), hi = Math.max(...gone.map(e => e.seq));
    this.log = this.log.filter(e => !(typeof e.delta_i === "number" && e.delta_i > keep));
    this._log_appends.push({ op: "lt", lo, hi });
  }

  // The delta whose tap first landed on `view` in `round` - the strip's tick
  // target - or -1 when no recorded tap did (a future or skipped step, or a
  // history written before deltas carried a view).
  deltaIndexForView(round, view) {
    return this.deltas.findIndex(d => d._delta_metadata?.round === round
                                   && d._delta_metadata?.view === view);
  }
```

In `foldLog`, before the `prev` logic:

```js
    if (r.op === "lt") {
      const keep = out.filter(e => !(e.seq >= r.lo && e.seq <= r.hi));
      out.length = 0; out.push(...keep);
      continue;
    }
```

Check `applyDelta` skips `_delta_metadata` (it already does for `unix_ms`/`log_messages` — same key). Check `loadLog` in `db.js` uses `foldLog` (it does, line ~141) and that `Session.record` needs no change (it pushes whatever `takeLogAppends` yields).

- [ ] **Step 4: Python implementation** — mirror exactly: in `add_delta`, `d["_delta_metadata"] = {"unix_ms": ..., "log_messages": ..., "view": self.view, "round": self.round}`; inside the `if self.replay_step + 1 < len(self.deltas):` block call `self._truncate_log(self.replay_step)`; add:

```python
    def _truncate_log(self, keep):
        gone = [e for e in self.log if isinstance(e.get("delta_i"), int) and e["delta_i"] > keep]
        if not gone:
            return
        lo = min(e["seq"] for e in gone)
        hi = max(e["seq"] for e in gone)
        self.log = [e for e in self.log
                    if not (isinstance(e.get("delta_i"), int) and e["delta_i"] > keep)]
        self._log_appends.append({"op": "lt", "lo": lo, "hi": hi})

    def delta_index_for_view(self, round_n, view):
        for i, d in enumerate(self.deltas):
            md = d.get("_delta_metadata") or {}
            if md.get("round") == round_n and md.get("view") == view:
                return i
        return -1
```

and in `fold_log`, first thing in the loop: `if r.get("op") == "lt": out = [e for e in out if not (r["lo"] <= e.get("seq", -1) <= r["hi"])]; continue`. Check `db.py`'s log store reader tolerates a record without `seq`/`text` (it should — it feeds `fold_log` blindly; if any code path reads `rec["text"]` before folding, guard it). Check `ui/` screens that read `game.log` do not assume every record has `text` — they read `game.log`, which never holds an op record (only the store does).

- [ ] **Step 5: Run everything** — `python3 -m pytest tests/ -q` green (2468 + 7). Commit:

```bash
git add docs/js/gamestate.js gamestate.py tests/test_replay_metadata.py tests/test_twin_parity.py
git -c commit.gpgsign=false commit -m "feat(model): deltas remember their view; an edit after undo truncates the log rows it orphaned (both twins)"
```

---

### Task 2: Strip transport and tick taps

**Files:**
- Create: `docs/tablet/js/acts_transport.js`
- Modify: `docs/tablet/js/actions.js` (register handler; `afterTap` R8 guard), `docs/tablet/js/strip.js` (transport block, tick buttons), `docs/tablet/js/copy.js`, `docs/tablet/style.css`
- Test: `tests/test_tablet.py` (new tests), `tests/test_tablet_tokens.py` (`tbtn`, `tick-btn` join the height gate)

**Interfaces:**
- Consumes: `game.canUndo()/canRedo()/stepThrough({size, direction|index})/deltaIndexForView(round, view)/replay_step/deltas`.
- Produces acts: `rw_first`, `rw_undo`, `rw_redo`, `rw_last`, `rw_round_back`, `rw_round_fwd`, `rw_index` (arg: delta index), `rw_tick` (arg: view id). All return the boolean `stepThrough` returns. Every successful move resets `ui.alloc = null; ui.placed = false;` and, unless `ui.screen === "log"`, `ui.sheet = null`.
- `afterTap(game, ui)` returns early when `ui.screen === "log"` (R8).

- [ ] **Step 1: Failing tests** (append to `tests/test_tablet.py`, using its `node()`):

```python
def test_transport_acts_move_the_cursor_without_recording_a_delta():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "advance", ""); perform(g, ui, "stg+", "");
const n0 = g.deltas.length;
const undo = perform(g, ui, "rw_undo", "");
const after = { step: g.replay_step, staging: g.staging, n: g.deltas.length };
const redo = perform(g, ui, "rw_redo", "");
const first = perform(g, ui, "rw_first", "");
const atFirst = { step: g.replay_step, view: g.view, staging: g.staging };
const last = perform(g, ui, "rw_last", "");
const noop = perform(g, ui, "rw_redo", "");
console.log(JSON.stringify({ n0, undo, after, redo, first, atFirst, last, noop, n1: g.deltas.length, step: g.replay_step }));
""")
    assert js["n0"] == 3 and js["n1"] == 3           # no cursor move became a delta
    assert js["undo"] is True and js["after"] == {"step": 1, "staging": 1, "n": 3}
    assert js["redo"] is True and js["first"] is True
    assert js["atFirst"] == {"step": -1, "view": "resource", "staging": 0}
    assert js["last"] is True and js["step"] == 2 and js["noop"] is False


def test_a_tick_tap_rewinds_to_the_entry_of_that_view_this_round():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { renderStrip } from "./strip.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "advance", ""); perform(g, ui, "stg+", ""); perform(g, ui, "stg+", "");
const before = renderStrip(g, ui);
const moved = perform(g, ui, "rw_tick", "planning");
const inert = perform(g, ui, "rw_tick", "combat_shadow");
console.log(JSON.stringify({ moved, inert, step: g.replay_step, staging: g.staging, view: g.view,
  planningIsButton: /data-act="rw_tick" data-arg="planning"/.test(before),
  futureIsNotButton: !/data-act="rw_tick" data-arg="combat_shadow"/.test(before),
  transport: ["rw_first","rw_undo","rw_redo","rw_last"].every(a => before.includes(`data-act="${a}"`)),
  readout: /Step 3\\/3/.test(before) }));
""")
    assert js["moved"] is True and js["inert"] is False
    assert js == {**js, "step": 0, "staging": 0, "view": "planning"}
    assert js["planningIsButton"] and js["futureIsNotButton"] and js["transport"] and js["readout"]
```

- [ ] **Step 2: Run, expect failure** (`rw_undo` unknown → `perform` returns false).

- [ ] **Step 3: `acts_transport.js`**

```js
// The replay cursor's three doors on the play screen: the strip's transport,
// its tick taps, and (Task 3) the Game Log's "Rewind to selected line" -
// every one of them is GameState.stepThrough() under a different arg. A
// cursor move is not an action: addDelta() sees _replay_moved and records
// nothing, but dispatch still returns true so app.js re-renders and
// Session.record() journals the {op:"s"} cursor write (Divergence D3).
export function handle(game, ui, act, arg) {
  let moved;
  if (act === "rw_first") moved = game.stepThrough({ size: "index", index: -1 });
  else if (act === "rw_last") moved = game.stepThrough({ size: "index", index: game.deltas.length - 1 });
  else if (act === "rw_undo") moved = game.stepThrough({ size: "single", direction: "undo" });
  else if (act === "rw_redo") moved = game.stepThrough({ size: "single", direction: "redo" });
  else if (act === "rw_round_back") moved = game.stepThrough({ size: "round", direction: "undo" });
  else if (act === "rw_round_fwd") moved = game.stepThrough({ size: "round", direction: "redo" });
  else if (act === "rw_index") {
    const i = Number.parseInt(arg, 10);
    moved = Number.isInteger(i) && i >= -1 && i < game.deltas.length
      && game.stepThrough({ size: "index", index: i });
  } else if (act === "rw_tick") {
    const i = game.deltaIndexForView(game.round, arg);
    moved = i >= 0 && game.stepThrough({ size: "index", index: i });
  } else return null;
  if (moved) {
    // Whatever the allocator/sheet was showing described a state that is
    // no longer the live one.
    ui.alloc = null; ui.placed = false;
    if (ui.screen !== "log") ui.sheet = null;
  }
  return !!moved;
}
```

Register in `actions.js` HANDLERS (before `playActs` is fine — no act name overlaps; keep `rw_` unique). Add the R8 guard as the first line of `afterTap`: `if (ui.screen === "log") return;`.

- [ ] **Step 4: `strip.js`** — in the round block, after the round number row, a `.transport` row:

```js
const tbtn = (act, glyph, on, title) => on
  ? h`<button type="button" class="tbtn" data-act="${act}" title="${title}">${glyph}</button>`
  : h`<span class="tbtn is-off" title="${title}">${glyph}</span>`;
// ...
const canB = game.canUndo(), canF = game.canRedo();
const transport = h`<div class="transport">${raw(tbtn("rw_first", "⏮", canB, CHROME.rwFirst))}${raw(tbtn("rw_undo", "◀", canB, CHROME.rwUndo))}${raw(tbtn("rw_redo", "▶", canF, CHROME.rwRedo))}${raw(tbtn("rw_last", "⏭", canF, CHROME.rwLast))}</div>
<div class="label transport-readout">${fmt(CHROME.stepOf, game.replay_step + 1, game.deltas.length)}</div>`;
```

(`fmt` = the `%s` substitution helper already used by `sheet_resolve.js`; import it from where it lives, or add `fmt` to `dom.js` if it is local — one home only.) In `renderTick`, when `game.deltaIndexForView(game.round, v) >= 0`, wrap the framework/window tick markup in `<button type="button" class="tick-btn" data-act="rw_tick" data-arg="${v}" title="${label}">…</button>`; otherwise emit the plain span as today. `renderTick` needs `game` — thread it through `renderSeg`.

Copy (`copy.js`, no duplicate keys): `rwFirst: "First"`, `rwUndo: "Back one tap"`, `rwRedo: "Forward one tap"`, `rwLast: "Latest"`, `rwRoundBack: "Back one round"`, `rwRoundFwd: "Forward one round"`, `stepOf: "Step %s/%s"`.

CSS: `.transport { display:flex; gap:6px; } .tbtn { min-width:44px; height:44px; ... bevel like .chip ... } .tbtn.is-off { opacity:.4; box-shadow:none; } .tick-btn { height:44px; min-width:28px; padding:0 3px; background:transparent; border:0; display:inline-flex; align-items:center; justify-content:center; } .tick-btn:active .tick { outline:2px solid var(--gold); }`. Extend `_button_heights_of` in `tests/test_tablet_tokens.py` to `(chip|cta|step|scenario-row|step-sm|tbtn|tick-btn)`. Sizes: the readout is LABEL (chrome); glyphs 20px.

- [ ] **Step 5: Run** `python3 -m pytest tests/test_tablet.py tests/test_tablet_tokens.py -q`, then the full suite. Commit — `feat(tablet): the strip's transport and tick taps move the replay head`.

---

### Task 3: The log block's "Open ›" and the Game Log screen

**Files:**
- Create: `docs/tablet/js/logfilter.js`, `docs/tablet/js/screen_log.js`, `docs/tablet/js/sheet_export.js`, `docs/tablet/js/acts_log.js`
- Modify: `docs/tablet/js/rail.js` (log block: "Open ›" chip, greyed rows), `docs/tablet/js/layout.js` (`ui.screen === "log"`), `docs/tablet/js/actions.js` (register `acts_log.js`; `newUi` gains `log: {filter:"all", sel:null}`), `docs/tablet/js/sheets.js` (`export` kind), `docs/tablet/js/app.js` (`copy_log` clipboard; scroll the row list after render), `docs/tablet/js/copy.js`, `docs/tablet/style.css`
- Test: `tests/test_tablet.py`

**Interfaces:**
- `logfilter.js`: `export const FILTERS = ["all","threat","quest","phases","skips"]`; `export function matches(filter, entry) → boolean`; `export function logText(game) → string` (one line per row: `R{round}.{step}  {m:ss}  {text}`, undone rows prefixed `~ `).
- `acts_log.js` acts: `open_log` (`ui.screen="log"; ui.log = {filter:"all", sel:null}`), `log_close` (`ui.screen="play"`; then `afterTap(game, ui)` — import it), `log_filter` (arg ∈ FILTERS; `sel=null`), `log_sel` (arg = row `seq`; toggles), `log_rewind` (selected row's `delta_i` → `rw_index` semantics via `game.stepThrough({size:"index", index})`; returns false when the selection has no valid target), `export_log` (`ui.sheet = {kind:"export"}`). UI-only acts return `true` (they change what renders).
- `screen_log.js`: `export function renderLogScreen(game, ui) → string`.
- Rows: a row is **undone** when `typeof e.delta_i === "number" && e.delta_i > game.replay_step` (class `is-undone`); **rewindable** when `0 <= e.delta_i < game.deltas.length`; **selected** when `ui.log.sel === e.seq`.

- [ ] **Step 1: Failing tests** (append to `tests/test_tablet.py`):

```python
def test_log_filters_sort_real_log_lines():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { matches } from "./logfilter.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "advance", "");                    // Phase: Planning? (phase change logs)
perform(g, ui, "stg+", "");                       // Staging area threat 1
perform(g, ui, "all_thr", "1");                   // All players threat +1
g.setWillpower(4); g.setStaging(0);
const byFilter = {};
for (const f of ["all","threat","quest","phases","skips"]) byFilter[f] = g.log.filter(e => matches(f, e)).map(e => e.text);
console.log(JSON.stringify(byFilter));
""")
    assert any(t.startswith("All players threat") for t in js["threat"])
    assert any(t.startswith("Staging area threat") for t in js["threat"])
    assert all(t.startswith("Phase:") for t in js["phases"]) and js["phases"]
    assert js["skips"] == []
    assert len(js["all"]) >= len(js["threat"])


def test_log_screen_greys_undone_rows_selects_and_rewinds():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform, afterTap } from "./actions.js";
import { layout } from "./layout.js";
import { renderRail } from "./rail.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "stg+", ""); perform(g, ui, "advance", "");
const rail = renderRail(g, ui);
perform(g, ui, "open_log", "");
const opened = layout(g, ui);
perform(g, ui, "rw_undo", "");
const afterUndo = layout(g, ui);
const target = g.log.find(e => e.delta_i === 0);
perform(g, ui, "log_sel", String(target.seq));
const selected = layout(g, ui);
const rewound = perform(g, ui, "log_rewind", "");
perform(g, ui, "log_close", "");
console.log(JSON.stringify({
  openChip: /data-act="open_log"/.test(rail),
  isLogScreen: /class="logscreen"/.test(opened) && !/class="strip"/.test(opened),
  filters: ["all","threat","quest","phases","skips"].every(f => opened.includes(`data-arg="${f}"`)),
  transport6: ["rw_first","rw_round_back","rw_undo","rw_redo","rw_round_fwd","rw_last"].every(a => opened.includes(`data-act="${a}"`)),
  undoneCount: (afterUndo.match(/is-undone/g) || []).length,
  rewindOff: /class="cta[^"]*is-off[^"]*"[^>]*data-act="log_rewind"/.test(afterUndo) || !/data-act="log_rewind"/.test(afterUndo),
  rewindOn: /data-act="log_rewind"/.test(selected) && /is-sel/.test(selected),
  rewound, step: g.replay_step, staging: g.staging, screen: ui.screen,
  sidePanel: /class="log-side"/.test(opened), export: /data-act="export_log"/.test(opened),
}));
""")
    assert js["openChip"] and js["isLogScreen"] and js["filters"] and js["transport6"]
    assert js["undoneCount"] >= 1                     # the advance's row(s) greyed after one undo
    assert js["rewindOff"] and js["rewindOn"]
    assert js["rewound"] is True and js["step"] == 0 and js["staging"] == 1
    assert js["screen"] == "play" and js["sidePanel"] and js["export"]


def test_export_sheet_carries_the_log_as_plain_text():
    js = node("""
import { GameState } from "../../js/gamestate.js";
import { newUi, perform } from "./actions.js";
import { layout } from "./layout.js";
import { logText } from "./logfilter.js";
const g = new GameState(2); g.view = "resource"; const ui = newUi();
perform(g, ui, "stg+", ""); perform(g, ui, "open_log", ""); perform(g, ui, "export_log", "");
const html = layout(g, ui);
console.log(JSON.stringify({ text: logText(g), hasTextarea: /<textarea[^>]*readonly/.test(html),
  hasCopy: /data-act="copy_log"/.test(html), inHtml: html.includes("Staging area threat 1") }));
""")
    assert "Staging area threat 1" in js["text"] and js["text"].startswith("R1.")
    assert js["hasTextarea"] and js["hasCopy"] and js["inHtml"]
```

- [ ] **Step 2: Run, expect failures.**

- [ ] **Step 3: `logfilter.js`**

```js
// Filters over our own log strings (gamestate.js is the only author), and
// the plain-text export. Text predicates, not new logEvent categories -
// ruling R6 in the plan; test_log_filters_sort_real_log_lines drives the
// model so a reworded line fails here rather than silently leaving a filter.
import { fmtMs } from "../../js/gamestate.js";
export const FILTERS = ["all", "threat", "quest", "phases", "skips"];
const RE = {
  threat: /threat|elimination/i,
  quest: /quest|progress|location|stage|explored|travel|advance/i,
  skips: /^Skipped /,
};
export function matches(filter, e) {
  if (filter === "all") return true;
  if (filter === "phases") return (e.cat ?? "move") === "phase";
  return RE[filter]?.test(e.text) ?? false;
}
export function logText(game) {
  return game.log.map(e => {
    const undone = typeof e.delta_i === "number" && e.delta_i > game.replay_step;
    const t = typeof e.t === "number" ? fmtMs(e.t) : "";
    return `${undone ? "~ " : ""}R${e.round}.${e.step}  ${t}  ${e.text}`;
  }).join("\n");
}
```

- [ ] **Step 4: `screen_log.js`** — structure (all strings via `h`` `; lists `.map(...).join("")` then `raw()`):

```
<section class="logscreen">
  <header class="log-head"> <h1 class="display">Game log</h1> <chip log_close "Close ›" tone plain height 44> </header>
  <div class="log-main">
    <div class="filter-row"> for f in FILTERS: chip({act:"log_filter", arg:f, label:CHROME.filters[f], tone: f===ui.log.filter ? "gold" : "tan"}) </div>
    <ol class="log-rows"> for e in game.log.filter(matches(ui.log.filter)):
       <li class="log-line [is-undone] [is-sel]"> (button when rewindable: data-act="log_sel" data-arg=seq; else a div)
          <span class="label log-stamp">R{round}.{step}</span><span class="label log-time">{m:ss}</span><span class="body log-msg">{text}</span>
    </ol>
    <footer class="log-foot">
      <div class="transport"> six tbtn: rw_first ⏮, rw_round_back ◀◀, rw_undo ◀, rw_redo ▶, rw_round_fwd ▶▶, rw_last ⏭ (on/off by canUndo/canRedo) </div>
      <span class="label transport-readout">Step n/N</span>
      cta({act:"log_rewind", label: CHROME.rewindTo, tone:"gold"}) — rendered as an is-off span (no data-act) unless the selected row is rewindable
      chip({act:"export_log", label: CHROME.exportLog, tone:"tan"})
    </footer>
  </div>
  <aside class="log-side">
    <h2 class="label">Rewinding</h2>
    <p class="body">{CHROME.rewindExplain1}</p><p class="body">{CHROME.rewindExplain2}</p><p class="body">{CHROME.rewindExplain3}</p>
    <h2 class="label">Rounds</h2>
    <ol class="round-list"> one <li class="body"> per round present in game.log: "Round {r} · {lines} lines · {m:ss}–{m:ss}" (first/last t of that round; omit the time span when t is null) </ol>
  </aside>
</section>
```

Copy (our own words, about the app only): `gameLog: "Game log"`, `close: "Close"` (reuse if present), `filters: {all:"All", threat:"Threat", quest:"Quest", phases:"Phases", skips:"Skips"}`, `rewindTo: "Rewind to selected line"`, `exportLog: "Export"`, `copyLog: "Copy"`, `rewinding: "Rewinding"`, `rounds: "Rounds"`, `rewindExplain1: "Rewinding puts the tracker back to the moment after an earlier tap. Nothing is deleted yet."`, `rewindExplain2: "Lines after that moment stay in the log, greyed, and Forward brings them back."`, `rewindExplain3: "The next edit you make from a rewound position drops the greyed lines for good."`, `roundLine: "Round %s · %s lines"`. Share the `tbtn` helper with `strip.js` by moving it to `primitives.js` (`transportButton({act, glyph, on, title})`).

`sheet_export.js`: header "Export", `<textarea class="export-text body" readonly rows="16">${logText(game)}</textarea>`, footer: `chip copy_log "Copy"` + `cta sheet_close "Done"`. Register `export` in `sheets.js`.

`acts_log.js`: as in Interfaces. `layout.js`: `if (ui.screen === "log") return h`<div class="app">${raw(renderLogScreen(game, ui))}${raw(renderSheet(game, ui))}</div>`;`. `rail.js` log block: header row becomes `<div class="log-head-row"><span class="label">Game log</span>${chip({act:"open_log", label:"Open ›", tone:"tan", height:30})}</div>`; rows get `is-undone` when undone. `app.js`: handle `copy_log` before `perform` (`navigator.clipboard?.writeText(logText(game))`, ignore rejection, no re-render needed); after `render()`, if `ui.screen === "log"`, scroll `.log-rows` to the selected `.is-sel` element or to the bottom. `newUi()` gains `log: { filter: "all", sel: null }`.

CSS: `.logscreen { display:grid; grid-template-columns: 1fr 360px; height:100%; }`, `.log-rows { overflow-y:auto; }`, `.log-line { min-height:44px; display:grid; grid-template-columns: 72px 56px 1fr; gap:10px; align-items:center; padding: 0 12px; }`, `button.log-line` bevelled like `.scenario-row`; `.is-undone { opacity:.45; }`, `.is-sel { box-shadow: inset 0 0 0 2px var(--gold); }`, `.log-side { border-left:1px solid var(--border); padding:16px; overflow-y:auto; }`, `.export-text { width:100%; font: 18px/1.35 var(--sans); color: var(--tan); background: var(--well); }`. Add `log-line` to the token gate's button classes.

- [ ] **Step 5: Run** the tablet tests, tokens, then the full suite. Commit — `feat(tablet): the Game Log screen - filters, transport, rewind to a line, export`.

---

### Task 4: Persistence of the cursor across a reload, and the walk stays at 20

**Files:** modify `tests/test_tablet.py` only.

- [ ] **Step 1: Test** — drive `perform` through three taps, `rw_undo`, then serialize `game.replayToDict()` + fold `takeReplayAppends()` via `foldReplay` (import from gamestate.js) and assert `[deltas.length, replay_step] == [3, 1]` — the cursor write reached the journal without a delta. Assert `test_the_common_round_costs_at_most_20_taps` still passes unchanged (no edit; run it).
- [ ] **Step 2: Run; commit** — `test(tablet): a rewind survives the journal round-trip`.

---

## Done when

- `python3 -m pytest tests/` green (2468 + Task 1's 7 + Task 2's 2 + Task 3's 3 + Task 4's 1).
- In the browser at 1366×1024: the strip shows ⏮ ◀ ▶ ⏭ and `Step n/N`; ◀ greys the last log line in the rail and lights ▶; tapping a done tick lands on that step's entry; "Open ›" opens the Game Log scrolled to the bottom; a filter chip narrows the list; tapping a line then "Rewind to selected line" moves the head and the strip's playhead when closed; an edit after a rewind drops the greyed lines; Export shows the text and Copy works; reload restores the rewound cursor (`Step n/N` unchanged).
- `rules/README.md` untouched (no rules text in this milestone); TODO cards added for the twin's `_drawReveal` "0 qp" (from milestone 3) and for `sideQuests()` printed text (from milestone 3) if not already filed.
