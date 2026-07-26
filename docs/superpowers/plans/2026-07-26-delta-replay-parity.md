# Delta Replay — DragnCards architecture parity Implementation Plan

> **STATUS: IMPLEMENTED 2026-07-26.** Both twins, 1136 tests green. Two bugs
> found during the build and fixed with regression tests: history navigation
> was being recorded as an action (caught in the browser, not by tests), and a
> pre-existing `setup_game` overflow the nav rule exposed. Device deploy is
> deliberately NOT done - main-session-only, and the user may be mid-game.

**Goal:** Replace the HUD's absent undo story with DragnCards' delta-replay
architecture, ported at parity: a bidirectional structural-diff log plus a
`replay_step` cursor, giving single-step undo/redo, jump-to-any-point retcon,
and round-granularity stepping — with a `Back` control on the guided round
screen and a full transport on the Log screen.

**Architecture:** Every action snapshots the game to a plain map, lets the
existing mutators run untouched, snapshots again, and stores the recursive
structural diff. Each changed leaf is a two-element `[old, new]` pair, so **one**
`apply_delta` function serves both directions — index 0 undoes, index 1 redoes.
`replay_step` is a cursor into the delta list, not a stack pointer: deltas are
never popped, and a fresh action after an undo truncates the redo future. No
existing mutator learns anything about undo.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the
scene layout linter. No new dependencies in either twin — the diff is ~30 lines
of hand-written code replacing Elixir's `map_diff` package.

---

## The reference, pinned

Read from a shallow clone of **`seastan/DragnCards`** at commit
**`a79716f94dda941ee28258a38486d9902901602b`** (2026-05-22). Every claim below
is cited to a file in that tree. Re-check against that sha, not against
whatever `master` says later.

| Concern | Reference location |
|---|---|
| State + delta container | `backend/lib/dragncards_game/game.ex` — `Game.load/4` returns `%{game: …, deltas: []}` |
| Wrapper shape | `backend/lib/dragncards_game/ui/game_ui.ex` — `GameUI.new/3`, keys `"game"`, `"deltas"`, `"replayStep"` |
| Diff | `game_ui.ex` — `get_delta/2`, `delta/2` |
| Apply (both directions) | `game_ui.ex` — `apply_delta/3`, `apply_delta_list/3` |
| Cursor | `game_ui.ex` — `step/2`, `undo/1`, `redo/1` |
| Multi-step walks | `game_ui.ex` — `apply_deltas_until_index/2`, `apply_deltas_until_round_change/2` |
| Dispatcher | `game_ui.ex` — `step_through/2` (`size` = `"single"` \| `"round"` \| `"index"`) |
| Record point | `game_ui.ex` — `add_delta/2`; sole pipeline call site `ui/game_ui_server.ex` `handle_call({:process_update, …})` |
| Persistence | `backend/lib/dragn/replay.ex` — `Replay` schema: `game_json` (:map) + `deltas` ({:array, :map}); trim in `game.ex` `trim_saved_deltas/2` |
| Log = delta list | `frontend/src/features/engine/hooks/useAllLogMessageDivs.js`, `frontend/src/features/messages/LogMessageDiv.js`, `frontend/src/features/messages/LogButtons.js` |
| Hotkeys | `frontend/src/features/engine/hooks/useDragnHotkeys.js` |

### Reference semantics, precisely

1. **`get_delta(game_old, game_new)`** zeroes `messages` and `fadeText` on the
   old state, then runs `MapDiff.diff/2` and converts the result via `delta/2`.
2. **`delta/2` conversion**, by `:changed` atom:
   - `:equal` → `nil` (key omitted)
   - `:added` → `[":removed", value]`
   - `:removed` → `[value, ":removed"]`
   - `:primitive_change` → `[removed, added]`
   - `:map_change` → recurse; **`"playerUi"` is skipped**
3. **`MapDiff` recurses into maps only.** Verified in
   [the library source](https://github.com/Qqwy/elixir-map_diff/blob/master/lib/map_diff.ex):
   the recursive clause is guarded `when is_map(vala) and is_map(valb)`, and
   everything else falls through to `:primitive_change` with the whole old and
   new values. **A list is therefore atomic** — change one element and the diff
   carries both entire lists.

   This is *why* DragnCards models every collection as an id-keyed map —
   `groupById`, `stackById`, `cardById`, `ruleById`, `messageByTimestamp`,
   `playerData` keyed `"player1"`/`"player2"` (`game.ex:97-114`). Granularity is
   a consequence of the data model, not of the diff. **Porting the diff without
   porting the keyed collections would produce a correct but bloated log** —
   see Task 1.
4. **`apply_delta(map, delta, direction)`** deletes `"_delta_metadata"`, then
   walks: a dict value recurses, otherwise it takes `Enum.at(v, 0)` for `"undo"`
   and `Enum.at(v, 1)` for `"redo"`; a chosen value of `":removed"` deletes the
   key. Guarded by `if is_map(map) and is_map(delta)`, returning `map` unchanged
   otherwise.
5. **`add_delta(gameui, prev_gameui)`** increments `replayStep`, diffs, and on a
   non-nil diff stamps `_delta_metadata = %{unix_ms, log_messages}`, truncates
   `deltas` to `0..prev_replay_step`, and appends.
6. **`undo`** guards `replay_step >= 0`, applies `deltas[replay_step]`,
   decrements. **`redo`** guards `replay_step < count-1`, applies
   `deltas[replay_step+1]`, increments.
7. **The log is the delta list.** There is no separate log array.
   `useAllLogMessageDivs.js:8` maps over `deltas`; `LogMessageDiv.js:41` renders
   `delta._delta_metadata.log_messages`; `LogMessageDiv.js:32` makes each row
   clickable, broadcasting `step_through {size: "index", index: deltaIndex}`.
   `LogButtons.js` renders `⏮ ◀ {replayStep+1}/{numDeltas} ▶ ⏭`.
8. **Persistence is snapshot + deltas**, one row: `game_json` holds the whole
   current game, `deltas` the history. `trim_saved_deltas/2` keeps all deltas
   for supporters and the **last 5** for everyone else.

### Deliberate divergences from the reference

Parity means mirroring the model, its names, and its semantics. It does not mean
copying defects or ignoring our platform. Four departures, each intentional:

- **D1 — `apply_deltas_until_round_change` is fixed.** The reference reads
  `gameui["roundNumber"]` (`game_ui.ex:1017`) and `acc["roundNumber"]`
  (`:1027`), but `roundNumber` lives at `game["roundNumber"]` (`game.ex:92`) —
  the rest of the codebase correctly uses `get_in(state, ["game",
  "roundNumber"])` (`room_channel.ex:136`) and `game["roundNumber"]`
  (`NEXT_STEP.ex:69`). Both reads are `nil`, `nil != nil` is false, so the
  round-change halt never fires and the walk only stops at the ends. Ours reads
  the round out of the snapshot and actually halts on a change.
- **D2 — `add_delta` does not advance the cursor when nothing changed.** The
  reference increments `replayStep` unconditionally and appends only when the
  diff is non-nil, so a no-op action leaves `replay_step == len(deltas)`;
  the next `undo` indexes past the end, hits the `is_map` guard, and is
  silently swallowed. Ours leaves the cursor alone and returns `False`.
- **D3 — `replay_step` is persisted, not recomputed.** The reference sets
  `replayStep => Enum.count(deltas)-1` on load (`game_ui.ex:35`) while
  `game_json` holds whatever the current state was — so saving mid-undo reloads
  with a cursor claiming end-of-history over a state that is several steps back,
  and both undo and redo then misbehave. Ours writes the cursor alongside the
  deltas.
- **D4 — two files, not one row.** `Replay`'s two columns map onto two stores:
  `state.json` ← `game_json` (unchanged shape and write path) and
  `replay.json` ← `deltas` + `replay_step`. Same model, split because the device
  writes to flash rather than Postgres, and folding a whole game's history into
  the every-tap `state.json` write would grow it from ~1.6 KB to ~46 KB per tap.
  The web twin mirrors it with a second `localStorage` key.

### Measured cost

Ported the diff to `GameState` and measured real transitions (2 players,
round 4, played through). Per-delta JSON bytes:

| transition | bytes |
|---|---|
| phase advance (×9) | 60–71 |
| commit willpower (per player) | 92 |
| set staging | 19 |
| resolve, success | 222 |
| place progress | 115 |
| `end_round` | 309 |
| **one full round, 16 transitions** | **1,507** |

A whole 30-round game is **~44 KB** — about what 16 whole-state checkpoints
would cost, and those would buy only ~1.3 rounds of depth. Round-trip verified:
`undo(after) == before` and `redo(before) == after` both hold.

---

## Architecture — our side

**The one adapter.** DragnCards' `game` *is* a map, so it diffs itself.
`GameState` is an object graph, so parity needs a projection at the seam:
`snapshot()` produces the map, `load_snapshot(m)` writes it back. Everything
else — diff, apply, cursor, dispatcher, metadata — is the reference's design
under the reference's names. Making `GameState` hold a dict internally would be
truer parity and would rewrite every screen, modal and test; the projection is
the deliberate boundary.

**Keyed collections.** Because the diff treats lists atomically (reference
semantics #3), the projection converts our lists to index-keyed maps, mirroring
`*ById`:

| live field | projection |
|---|---|
| `players` (list) | `{"0": {...}, "1": {...}}` |
| `side_quests` (list) | `{"0": {...}, …}` |
| `quest_history` (list) | `{"0": {...}, …}` |

Keys are stringified positions, not identities — our collections are
position-addressed everywhere in the UI, and a positional key diffs granularly
for the mutation that actually happens (a field of one entry changing). A
mid-list insertion re-keys the tail and produces a larger delta; that is
correct, just not minimal, and it only occurs when a side quest is removed from
the middle.

**In the projection** (anything a phase can change): `players` (`threat`,
`eliminated`, `commit`, `commit_touched`), `quest`, `active_location`,
`side_quests`, `willpower`, `staging`, `sailing`, `heading`, `pending_budget`,
`pending_stage`, `pending_elim`, `round`, `first_player`, `view`, `step`,
`quest_resolved`, `quest_outcome`, `quest_outcome_n`, `quest_history`,
`stage_idx`, `card_idx`, `game_over`.

`stage_idx`/`card_idx` are included because `clear_and_advance`
(`gamestate.py:560`) and `preload_scenario` (`:483`) both write them.

**Excluded, each mirroring a reference exclusion:**

| excluded | why | reference analogue |
|---|---|---|
| `messages` | drained into `_delta_metadata`, zeroed before diff | `game["messages"]` |
| `log`, `_seq` | append-only session record; Task 5 moves rendering onto deltas | `messages` |
| `clock`, `_round_snap` | injected/derived, not play data | `fadeText` |
| `reminders` | standing preference — undo must not silently retoggle it | `playerUi` |
| `pending_quest_card`, `pending_side_quest_pick`, `pending_progress_detail`, `pending_location_pick`, `pending_resolution` | one-tick router flags, false by the time a delta is recorded | `pendingGuiUpdates` |
| `scenario`, `stages`, `elimination_threat`, `players[].label`/`.starting_threat`/`.threat_per_round`/`.elimination` | set at setup, never mutated by a phase handler | `pluginId`, `layout` |

**The record point.** One choke point per twin, mirroring `process_update`:
`main.py`'s `elif result: save_state(game)` (`main.py:519`) and `main.js`'s
`} else if (result) { saveState(game); }` (`docs/js/main.js:463`). Snapshot
before dispatch, `add_delta` after. No mutator, screen, or modal changes.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the
  firmware mirror. Fields snake_case, methods camelCase in the JS twin —
  matching `gamestate.js` exactly.
- **Reference names are preserved verbatim** (snake_case in Python, camelCase
  methods in JS): `deltas`, `replay_step`/`replayStep`, `get_delta`/`getDelta`,
  `apply_delta`/`applyDelta`, `apply_delta_list`/`applyDeltaList`,
  `undo`, `redo`, `step_through`/`stepThrough`,
  `apply_deltas_until_index`/`applyDeltasUntilIndex`,
  `apply_deltas_until_round_change`/`applyDeltasUntilRoundChange`,
  `add_delta`/`addDelta`, `_delta_metadata`, `":removed"`. Do not rename
  toward local taste — the point is that a reader can hold both codebases open.
  **One forced exception:** the reference's `step/2` becomes
  `step_replay`/`stepReplay`, because `step` is already an instance field (the
  phase step id) in both twins and a method of that name would be shadowed by
  the constructor's assignment.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the
  layout linter. New scenes for every new control.
- **Design system** (`docs/superpowers/specs/2026-07-25-design-system.md`):
  names from `ui/theme.py` / `docs/js/ui.js`, never bare integers. Anything a
  player reads as a sentence, name or option is `BODY` (scale 2); `LABEL`
  (scale 1) is ALL-CAPS chrome and dense tabular metadata only. The transport
  counter (`4/17`) is tabular metadata → `LABEL`. Button labels are `BODY`.
- **Touch targets ≥ 24px** each dimension; everything within 480×480; no text
  collisions (linter-enforced).
- **No new dependencies** in either twin.
- **`MAX_SAVED_DELTAS = 500`** — the plain cap replacing the reference's
  supporter paywall. ~47 KB, ~31 rounds. FIFO from the front, `replay_step`
  shifted by the number dropped.
- No changes to `tools/build_tips.py`, `tests/test_tips.py`, or anything under
  `docs/data/`.

## File structure

- `gamestate.py` / `docs/js/gamestate.js` — the whole delta engine: module-level
  `REMOVED`, `MAX_SAVED_DELTAS`, `get_delta`, `apply_delta`, `apply_delta_list`;
  `GameState` gains `deltas`, `replay_step`, `messages`, `snapshot`,
  `load_snapshot`, `add_delta`, `step_replay`, `undo`, `redo`, `step_through`,
  `apply_deltas_until_index`, `apply_deltas_until_round_change`,
  `can_undo`, `can_redo`, `replay_to_dict`, `replay_from_dict`; `log_event` also
  appends to `messages`.
- `main.py` / `docs/js/main.js` — the record point, and the `replay.json` /
  second-`localStorage`-key read/write.
- `ui/widgets.py` / `docs/js/ui.js` — `arrow_left`/`arrow_right` triangle
  primitives (no new icon mask).
- `ui/screen_play.py` / `docs/js/screen_play.js` — `NAV_W`, `NAV_RULE_Y`,
  `ARROW`, `NAV_PAD`; `_cta` becomes the bottom nav bar and gains `game`; new
  `("back",)` button; the pre-existing `setup_game` overflow fix.
- `tests/test_layout.py` — the rect-crossing check that would have caught that
  overflow.
- `ui/screen_log.py` / `docs/js/screens_other.js` — `PER_PAGE` 13 → 11, the
  transport row, and tap-a-row-to-jump off the `delta_i` stamp.
- `tests/test_delta.py` — new; the diff/apply engine, in isolation.
- `tests/test_gamestate_replay.py` — new; cursor, metadata, trimming, rebase.
- `tests/test_screen_play.py`, `tests/test_screen_log.py`, `tests/scenes.py` —
  additions.

---

### Task 1: The delta engine — `get_delta` / `apply_delta` (both twins)

Pure functions, no `GameState` involvement. Standalone so the trickiest part of
the port is nailed before anything depends on it.

**Files:**
- Modify: `gamestate.py`, `docs/js/gamestate.js`
- Test: `tests/test_delta.py` (new)

**Interfaces:**
- Produces: module-level `REMOVED = ":removed"`; `MAX_SAVED_DELTAS = 500`;
  `get_delta(old, new) -> dict | None` / `getDelta(old, new)`;
  `apply_delta(state, delta, direction) -> dict` / `applyDelta(state, delta, direction)`
  (mutates `state` in place and returns it; `direction` is `"undo"` | `"redo"`);
  `apply_delta_list(state, delta_list, direction)` / `applyDeltaList(...)`.

- [x] **Step 1: Write the failing tests** — create `tests/test_delta.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import get_delta, apply_delta, apply_delta_list, REMOVED


def test_equal_maps_produce_no_delta():
    assert get_delta({"a": 1}, {"a": 1}) is None


def test_primitive_change_is_old_new_pair():
    assert get_delta({"a": 1}, {"a": 2}) == {"a": [1, 2]}


def test_unchanged_keys_are_omitted():
    d = get_delta({"a": 1, "b": 2}, {"a": 1, "b": 3})
    assert d == {"b": [2, 3]}


def test_added_key_uses_removed_sentinel_on_the_left():
    assert get_delta({}, {"a": 5}) == {"a": [REMOVED, 5]}


def test_removed_key_uses_removed_sentinel_on_the_right():
    assert get_delta({"a": 5}, {}) == {"a": [5, REMOVED]}


def test_nested_maps_recurse():
    d = get_delta({"p": {"x": 1, "y": 2}}, {"p": {"x": 1, "y": 9}})
    assert d == {"p": {"y": [2, 9]}}


def test_lists_are_atomic_not_recursed():
    """Parity with MapDiff: the recursive clause is guarded on both values
    being maps, so a list is a primitive and changes wholesale."""
    d = get_delta({"xs": [1, 2, 3]}, {"xs": [1, 2, 4]})
    assert d == {"xs": [[1, 2, 3], [1, 2, 4]]}


def test_map_replaced_by_non_map_is_primitive():
    assert get_delta({"a": {"x": 1}}, {"a": None}) == {"a": [{"x": 1}, None]}


def test_apply_delta_undo_takes_index_zero():
    state = {"a": 2}
    apply_delta(state, {"a": [1, 2]}, "undo")
    assert state == {"a": 1}


def test_apply_delta_redo_takes_index_one():
    state = {"a": 1}
    apply_delta(state, {"a": [1, 2]}, "redo")
    assert state == {"a": 2}


def test_apply_delta_undo_of_an_add_deletes_the_key():
    state = {"a": 5}
    apply_delta(state, {"a": [REMOVED, 5]}, "undo")
    assert state == {}


def test_apply_delta_redo_of_a_removal_deletes_the_key():
    state = {"a": 5}
    apply_delta(state, {"a": [5, REMOVED]}, "redo")
    assert state == {}


def test_apply_delta_recurses_into_nested_maps():
    state = {"p": {"x": 1, "y": 9}}
    apply_delta(state, {"p": {"y": [2, 9]}}, "undo")
    assert state == {"p": {"x": 1, "y": 2}}


def test_apply_delta_ignores_delta_metadata():
    state = {"a": 2}
    apply_delta(state, {"a": [1, 2], "_delta_metadata": {"unix_ms": 1}}, "undo")
    assert state == {"a": 1}


def test_apply_delta_guard_returns_state_when_delta_is_not_a_map():
    state = {"a": 1}
    assert apply_delta(state, None, "undo") is state
    assert state == {"a": 1}


def test_round_trip_undo_then_redo_is_identity():
    old = {"p": {"0": {"threat": 31}}, "view": "quest_staging", "n": 0}
    new = {"p": {"0": {"threat": 33}}, "view": "travel", "n": 2}
    d = get_delta(old, new)
    import copy
    state = copy.deepcopy(new)
    apply_delta(state, d, "undo")
    assert state == old
    apply_delta(state, d, "redo")
    assert state == new


def test_apply_delta_list_walks_in_order():
    state = {"a": 3}
    apply_delta_list(state, [{"a": [2, 3]}, {"a": [1, 2]}], "undo")
    assert state == {"a": 1}
```

- [x] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_delta.py -q`
Expected: FAIL — `ImportError: cannot import name 'get_delta' from 'gamestate'`

- [x] **Step 3: Implement in `gamestate.py`**

Add immediately after the `VIEW_ORDER` / `VIEW_STEP` block, before
`class Player`:

```python
# ---------------------------------------------------------------------------
# Delta replay engine.
#
# Ported at parity from DragnCards (seastan/DragnCards @ a79716f9),
# backend/lib/dragncards_game/ui/game_ui.ex: get_delta/2, delta/2,
# apply_delta/3, apply_delta_list/3. Names and semantics are the reference's;
# see docs/superpowers/plans/2026-07-26-delta-replay-parity.md for the four
# deliberate divergences.
#
# A delta mirrors the shape of the state it describes. Every changed leaf is a
# two-element [old, new] pair, which is what lets ONE apply function serve both
# directions: index 0 undoes, index 1 redoes.
# ---------------------------------------------------------------------------

REMOVED = ":removed"       # sentinel: the key does not exist on this side
MAX_SAVED_DELTAS = 500     # ~47 KB, ~31 rounds. Reference caps at 5 for
                           # non-supporters (game.ex trim_saved_deltas/2);
                           # we have no paywall, just a bound.


def get_delta(old, new):
    """Recursive structural diff. Returns None when nothing changed.

    Parity note: recursion happens only when BOTH sides are dicts. Elixir's
    map_diff has the same guard (`when is_map(vala) and is_map(valb)`), so a
    list is an atomic primitive and changes wholesale. That is why the
    snapshot keys its collections instead of listing them.
    """
    if old == new:
        return None
    if isinstance(old, dict) and isinstance(new, dict):
        out = {}
        for k in old:
            if k not in new:
                out[k] = [old[k], REMOVED]
            else:
                d = get_delta(old[k], new[k])
                if d is not None:
                    out[k] = d
        for k in new:
            if k not in old:
                out[k] = [REMOVED, new[k]]
        return out or None
    return [old, new]


def apply_delta(state, delta, direction):
    """Apply delta to state in place; returns state.

    direction "undo" takes each pair's index 0, "redo" its index 1. A chosen
    value of REMOVED deletes the key. Mirrors the reference's
    `if is_map(map) and is_map(delta)` guard by returning state untouched when
    either side is not a dict.
    """
    if not (isinstance(state, dict) and isinstance(delta, dict)):
        return state
    idx = 0 if direction == "undo" else 1
    for k, v in delta.items():
        if k == "_delta_metadata":
            continue
        if isinstance(v, dict):
            apply_delta(state.get(k), v, direction)
        else:
            val = v[idx]
            if val == REMOVED:
                state.pop(k, None)
            else:
                state[k] = val
    return state


def apply_delta_list(state, delta_list, direction):
    """Fold apply_delta over a list of deltas, in the given order."""
    for d in delta_list:
        apply_delta(state, d, direction)
    return state
```

- [x] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_delta.py -q`
Expected: PASS, 17 tests

- [x] **Step 5: Mirror in `docs/js/gamestate.js`**

Add after the `VIEW_STEP` block, before `class Player`. Exported so the Log
screen and tests can reach them:

```javascript
// ---------------------------------------------------------------------------
// Delta replay engine.
//
// Ported at parity from DragnCards (seastan/DragnCards @ a79716f9),
// backend/lib/dragncards_game/ui/game_ui.ex: get_delta/2, delta/2,
// apply_delta/3, apply_delta_list/3. Mirrors gamestate.py exactly - see
// docs/superpowers/plans/2026-07-26-delta-replay-parity.md.
// ---------------------------------------------------------------------------

export const REMOVED = ":removed";
export const MAX_SAVED_DELTAS = 500;

function isMap(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
  }
  if (isMap(a) && isMap(b)) {
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every(k => k in b && deepEqual(a[k], b[k]));
  }
  return false;
}

export function getDelta(old, cur) {
  if (deepEqual(old, cur)) return null;
  if (isMap(old) && isMap(cur)) {
    const out = {};
    for (const k of Object.keys(old)) {
      if (!(k in cur)) out[k] = [old[k], REMOVED];
      else {
        const d = getDelta(old[k], cur[k]);
        if (d !== null) out[k] = d;
      }
    }
    for (const k of Object.keys(cur)) {
      if (!(k in old)) out[k] = [REMOVED, cur[k]];
    }
    return Object.keys(out).length ? out : null;
  }
  return [old, cur];
}

export function applyDelta(state, delta, direction) {
  if (!isMap(state) || !isMap(delta)) return state;
  const idx = direction === "undo" ? 0 : 1;
  for (const [k, v] of Object.entries(delta)) {
    if (k === "_delta_metadata") continue;
    if (isMap(v)) applyDelta(state[k], v, direction);
    else {
      const val = v[idx];
      if (val === REMOVED) delete state[k];
      else state[k] = val;
    }
  }
  return state;
}

export function applyDeltaList(state, deltaList, direction) {
  for (const d of deltaList) applyDelta(state, d, direction);
  return state;
}
```

Note `isMap` treats arrays as non-maps, which is exactly what makes lists
atomic — matching Elixir's `is_map/1`, under which a list is not a map.
`deepEqual` replaces Python's `==` on nested structures.

- [x] **Step 6: Verify the twins agree**

Run:

```bash
node --input-type=module -e "
import { getDelta, applyDelta, REMOVED } from './docs/js/gamestate.js';
const old = { p: { '0': { threat: 31 } }, view: 'quest_staging', xs: [1,2,3] };
const cur = { p: { '0': { threat: 33 } }, view: 'travel', xs: [1,2,4] };
const d = getDelta(old, cur);
console.log(JSON.stringify(d));
const s = JSON.parse(JSON.stringify(cur));
applyDelta(s, d, 'undo');
console.log('undo==old', JSON.stringify(s) === JSON.stringify(old));
"
```

Expected: the delta prints `{"p":{"0":{"threat":[31,33]}},"view":["quest_staging","travel"],"xs":[[1,2,3],[1,2,4]]}`
and `undo==old true`. Compare against the same input through the Python twin;
the JSON must match key-for-key.

- [x] **Step 7: Commit**

```bash
git add gamestate.py docs/js/gamestate.js tests/test_delta.py
git commit -m "feat(replay): port DragnCards' structural delta engine

get_delta/apply_delta/apply_delta_list at parity with
seastan/DragnCards@a79716f9 backend/lib/dragncards_game/ui/game_ui.ex.
Each changed leaf is an [old, new] pair, so one apply function serves
both directions - index 0 undoes, index 1 redoes.

Lists are atomic, matching Elixir map_diff's is_map/1-guarded recursion
(github.com/Qqwy/elixir-map_diff lib/map_diff.ex). That constraint is why
the reference keys its collections (groupById/cardById) and why our
snapshot will too."
```

---

### Task 2: Snapshot projection + cursor on `GameState` (both twins)

**Files:**
- Modify: `gamestate.py`, `docs/js/gamestate.js`
- Test: `tests/test_gamestate_replay.py` (new)

**Interfaces:**
- Consumes: `get_delta`, `apply_delta`, `REMOVED`, `MAX_SAVED_DELTAS` from Task 1.
- Produces, on `GameState`: fields `deltas` (list), `replay_step` (int, starts
  `-1`), `messages` (list); methods `snapshot() -> dict`,
  `load_snapshot(m) -> None`, `add_delta(prev_snapshot) -> bool`,
  `undo() -> bool`, `redo() -> bool`, `step(direction) -> bool`,
  `step_through(options) -> bool`, `apply_deltas_until_index(target) -> bool`,
  `apply_deltas_until_round_change(direction) -> bool`,
  `can_undo() -> bool`, `can_redo() -> bool`. JS: same fields (snake_case),
  methods `snapshot`, `loadSnapshot`, `addDelta`, `undo`, `redo`,
  `stepReplay`, `stepThrough`, `applyDeltasUntilIndex`,
  `applyDeltasUntilRoundChange`,
  `canUndo`, `canRedo`.

- [x] **Step 1: Write the failing tests** — create `tests/test_gamestate_replay.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import GameState, MAX_SAVED_DELTAS


def _round1(g):
    """Advance a fresh GameState past setup into round 1."""
    g.advance_view()
    return g


def _act(g, fn):
    """Do something, then record the delta - the record point, in miniature."""
    before = g.snapshot()
    fn()
    return g.add_delta(before)


# -- the projection ---------------------------------------------------------

def test_snapshot_keys_collections_as_maps_not_lists():
    g = _round1(GameState(2, 25))
    s = g.snapshot()
    assert isinstance(s["players"], dict)
    assert set(s["players"]) == {"0", "1"}
    assert isinstance(s["side_quests"], dict)
    assert isinstance(s["quest_history"], dict)


def test_snapshot_excludes_transient_and_setup_only_fields():
    g = _round1(GameState(2, 25))
    s = g.snapshot()
    for k in ("log", "messages", "clock", "_round_snap", "reminders",
              "scenario", "stages", "elimination_threat",
              "pending_quest_card", "pending_location_pick"):
        assert k not in s, k


def test_load_snapshot_round_trips():
    g = _round1(GameState(2, 25))
    g.players[0].threat = 31
    g.willpower = 7
    s = g.snapshot()
    g.players[0].threat = 99
    g.willpower = 0
    g.load_snapshot(s)
    assert g.players[0].threat == 31
    assert g.willpower == 7
    assert g.snapshot() == s


def test_load_snapshot_restores_a_cleared_active_location():
    g = _round1(GameState(2, 25))
    g.active_location = {"name": "Old Forest Road", "points": 3, "progress": 1}
    s = g.snapshot()
    g.active_location = None
    g.load_snapshot(s)
    assert g.active_location == {"name": "Old Forest Road", "points": 3, "progress": 1}


def test_load_snapshot_shrinks_and_grows_side_quests():
    g = _round1(GameState(2, 25))
    g.side_quests = [{"name": "A", "points": 4, "progress": 0}]
    s_one = g.snapshot()
    g.side_quests = []
    g.load_snapshot(s_one)
    assert len(g.side_quests) == 1
    g.side_quests = [{"name": "A", "points": 4, "progress": 0},
                     {"name": "B", "points": 8, "progress": 2}]
    g.load_snapshot(s_one)
    assert len(g.side_quests) == 1


# -- cursor mechanics -------------------------------------------------------

def test_fresh_state_cannot_undo_or_redo():
    g = _round1(GameState())
    assert g.replay_step == -1
    assert g.can_undo() is False
    assert g.can_redo() is False
    assert g.undo() is False
    assert g.redo() is False


def test_add_delta_appends_and_advances_the_cursor():
    g = _round1(GameState(2, 25))
    assert _act(g, lambda: g.set_commit(0, 3)) is True
    assert len(g.deltas) == 1
    assert g.replay_step == 0
    assert g.can_undo() is True
    assert g.can_redo() is False


def test_add_delta_is_a_noop_when_nothing_changed():
    """Divergence D2: the reference advances replayStep unconditionally, which
    desyncs the cursor on a no-op action. We leave it alone."""
    g = _round1(GameState(2, 25))
    assert _act(g, lambda: None) is False
    assert g.deltas == []
    assert g.replay_step == -1


def test_undo_restores_and_redo_reapplies():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.willpower == 3
    assert g.undo() is True
    assert g.willpower == 0
    assert g.replay_step == -1
    assert g.redo() is True
    assert g.willpower == 3
    assert g.replay_step == 0


def test_undo_walks_back_through_several_actions():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.enter_view("quest_commit"))
    _act(g, lambda: g.enter_view("quest_staging"))
    assert g.view == "quest_staging"
    assert g.undo() and g.view == "quest_commit"
    assert g.undo() and g.view == "resource_planning"
    assert g.undo() and g.willpower == 0
    assert g.can_undo() is False


def test_a_fresh_action_after_undo_truncates_the_redo_future():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.set_commit(1, 4))
    assert len(g.deltas) == 2
    g.undo()
    assert g.can_redo() is True
    _act(g, lambda: g.set_commit(1, 9))
    assert len(g.deltas) == 2          # the undone delta was replaced
    assert g.can_redo() is False
    assert g.players[1].commit == 9


def test_deltas_carry_metadata_with_the_log_messages_of_their_action():
    g = _round1(GameState(2, 25))
    g.clock = lambda: 1234
    _act(g, lambda: g.enter_view("quest_commit"))
    md = g.deltas[-1]["_delta_metadata"]
    assert md["unix_ms"] == 1234
    assert any("Phase" in m for m in md["log_messages"])


def test_messages_drain_so_the_next_delta_does_not_repeat_them():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.enter_view("quest_commit"))
    first = g.deltas[-1]["_delta_metadata"]["log_messages"]
    _act(g, lambda: g.enter_view("quest_staging"))
    second = g.deltas[-1]["_delta_metadata"]["log_messages"]
    assert first and second and first != second


def test_log_entries_are_stamped_with_their_delta_index():
    """The Log screen needs a jump target per row without matching on text."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.enter_view("quest_commit"))
    _act(g, lambda: g.enter_view("quest_staging"))
    stamped = [e for e in g.log if "delta_i" in e]
    assert [e["delta_i"] for e in stamped] == [0, 1]


def test_undo_does_not_erase_the_log():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.enter_view("quest_commit"))
    n = len(g.log)
    g.undo()
    assert len(g.log) >= n


def test_deltas_are_trimmed_from_the_front_at_the_cap():
    g = _round1(GameState(2, 25))
    for i in range(MAX_SAVED_DELTAS + 10):
        _act(g, lambda i=i: g.adjust_threat(0, 1 if i % 2 == 0 else -1))
    assert len(g.deltas) == MAX_SAVED_DELTAS
    assert g.replay_step == MAX_SAVED_DELTAS - 1


# -- step_through dispatcher ------------------------------------------------

def test_step_through_single_matches_undo():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.step_through({"size": "single", "direction": "undo"}) is True
    assert g.willpower == 0


def test_step_through_index_jumps_backward_to_any_point():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 1))
    _act(g, lambda: g.set_commit(0, 2))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.willpower == 3
    assert g.step_through({"size": "index", "index": 0}) is True
    assert g.replay_step == 0
    assert g.willpower == 1


def test_step_through_index_jumps_forward_again():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 1))
    _act(g, lambda: g.set_commit(0, 2))
    _act(g, lambda: g.set_commit(0, 3))
    g.step_through({"size": "index", "index": 0})
    assert g.step_through({"size": "index", "index": 2}) is True
    assert g.willpower == 3


def test_step_through_index_to_minus_one_rewinds_everything():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 1))
    _act(g, lambda: g.set_commit(0, 2))
    assert g.step_through({"size": "index", "index": -1}) is True
    assert g.replay_step == -1
    assert g.willpower == 0


def test_step_through_round_halts_on_a_round_change():
    """Divergence D1: the reference reads roundNumber off the wrong map, so
    its round walk never halts on a change. Ours reads it from the snapshot."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    g.view = "refresh"
    _act(g, lambda: g.end_round())
    assert g.round == 2
    _act(g, lambda: g.enter_view("quest_commit"))
    _act(g, lambda: g.enter_view("quest_staging"))
    assert g.step_through({"size": "round", "direction": "undo"}) is True
    assert g.round == 1                 # stopped at the boundary, not the start
    assert g.can_undo() is True         # round 1's own deltas are still there


def test_step_through_unknown_size_is_a_noop():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.step_through({"size": "sideways"}) is False
    assert g.willpower == 3


# -- the rebase guarantee, end to end --------------------------------------

def test_resolve_rebases_after_undo_and_edit():
    """The original TODO card: back up from a failed resolve, fix the
    committed willpower, resolve again - the new outcome must be computed
    from the corrected base, not stacked on the old one."""
    g = _round1(GameState(2, 25))
    g.view = "quest_staging"
    g.willpower, g.staging = 0, 5

    before = g.snapshot()
    res = g.resolve_quest(g.willpower, g.staging)
    g.enter_view("quest_resolution")
    g.add_delta(before)
    assert res["outcome"] == "fail"
    assert g.players[0].threat == 30          # 25 + 5 shortfall
    assert len(g.quest_history) == 1

    assert g.undo() is True
    assert g.view == "quest_staging"
    assert g.players[0].threat == 25           # the raise is gone
    assert len(g.quest_history) == 0           # the entry is gone

    g.willpower = 9
    before = g.snapshot()
    res2 = g.resolve_quest(g.willpower, g.staging)
    g.enter_view("quest_resolution")
    g.add_delta(before)
    assert res2["outcome"] == "success"
    assert g.players[0].threat == 25            # NOT 30 - no stacking
    assert len(g.quest_history) == 1            # replaced, not appended
```

- [x] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_gamestate_replay.py -q`
Expected: FAIL — `AttributeError: 'GameState' object has no attribute 'snapshot'`

- [x] **Step 3: Implement the fields in `gamestate.py`**

In `GameState.__init__`, immediately after `self._seq = 0`:

```python
        # -- delta replay (parity: DragnCards gameui["deltas"]/["replayStep"])
        self.deltas = []             # oldest-first; each is a get_delta result
                                     # plus a "_delta_metadata" key
        self.replay_step = -1        # cursor INTO deltas. -1 = before the
                                     # first delta. Not a stack pointer:
                                     # deltas are never popped.
        self.messages = []           # log text produced by the current action,
                                     # drained into the next delta's metadata.
                                     # Mirrors game["messages"].
```

In `log_event`, after the existing `self.log.append({...})`:

```python
        self.messages.append(text)
```

- [x] **Step 4: Implement `snapshot` / `load_snapshot`**

Add a new section just before `# -- persistence`:

```python
    # -- delta replay ------------------------------------------------------
    # The seam between our object graph and the reference's map model.
    # DragnCards' `game` IS a map, so it diffs itself; snapshot()/
    # load_snapshot() are the one adapter parity requires.
    #
    # Collections become index-keyed maps because get_delta recurses into
    # dicts only (see Task 1) - the same reason the reference models
    # everything as groupById/cardById/stackById.

    def snapshot(self):
        """The diffable projection: everything a phase handler can change."""
        return {
            "players": {str(i): {"threat": p.threat,
                                 "eliminated": p.eliminated,
                                 "commit": p.commit,
                                 "commit_touched": p.commit_touched}
                        for i, p in enumerate(self.players)},
            "quest": dict(self.quest),
            "active_location": (dict(self.active_location)
                                if self.active_location else None),
            "side_quests": {str(i): dict(s)
                            for i, s in enumerate(self.side_quests)},
            "quest_history": {str(i): dict(e)
                              for i, e in enumerate(self.quest_history)},
            "willpower": self.willpower,
            "staging": self.staging,
            "sailing": self.sailing,
            "heading": self.heading,
            "pending_budget": self.pending_budget,
            "pending_stage": (dict(self.pending_stage)
                              if self.pending_stage else None),
            "pending_elim": self.pending_elim,
            "round": self.round,
            "first_player": self.first_player,
            "view": self.view,
            "step": self.step,
            "stage_idx": self.stage_idx,
            "card_idx": self.card_idx,
            "quest_resolved": self.quest_resolved,
            "quest_outcome": self.quest_outcome,
            "quest_outcome_n": self.quest_outcome_n,
            "game_over": dict(self.game_over) if self.game_over else None,
        }

    def load_snapshot(self, m):
        """Write a snapshot back onto the live object. Inverse of snapshot()."""
        for i, p in enumerate(self.players):
            pd = m["players"].get(str(i))
            if pd is None:
                continue
            p.threat = pd["threat"]
            p.eliminated = pd["eliminated"]
            p.commit = pd["commit"]
            p.commit_touched = pd["commit_touched"]
        self.quest = dict(m["quest"])
        self.active_location = (dict(m["active_location"])
                                if m["active_location"] else None)
        # keyed maps back to lists, in key order - the keys are positions
        self.side_quests = [dict(m["side_quests"][k])
                            for k in sorted(m["side_quests"], key=int)]
        self.quest_history = [dict(m["quest_history"][k])
                              for k in sorted(m["quest_history"], key=int)]
        self.willpower = m["willpower"]
        self.staging = m["staging"]
        self.sailing = m["sailing"]
        self.heading = m["heading"]
        self.pending_budget = m["pending_budget"]
        self.pending_stage = (dict(m["pending_stage"])
                              if m["pending_stage"] else None)
        self.pending_elim = m["pending_elim"]
        self.round = m["round"]
        self.first_player = m["first_player"]
        self.view = m["view"]
        self.step = m["step"]
        self.stage_idx = m["stage_idx"]
        self.card_idx = m["card_idx"]
        self.quest_resolved = m["quest_resolved"]
        self.quest_outcome = m["quest_outcome"]
        self.quest_outcome_n = m["quest_outcome_n"]
        self.game_over = dict(m["game_over"]) if m["game_over"] else None
```

- [x] **Step 5: Implement `add_delta` and the cursor**

Append to the same section:

```python
    def add_delta(self, prev_snapshot):
        """Record the action that turned prev_snapshot into the current state.

        Parity: game_ui.ex add_delta/2. Returns True when a delta was recorded.

        Divergence D2: the reference advances replayStep before it knows
        whether the diff is non-nil, so a no-op action leaves the cursor one
        past the end and swallows the next undo. We only advance on a real
        delta.
        """
        d = get_delta(prev_snapshot, self.snapshot())
        if d is None:
            self.messages = []
            return False
        d["_delta_metadata"] = {"unix_ms": self._now(),
                                "log_messages": self.messages}
        # A fresh action after an undo discards the redo future. Python's slice
        # handles replay_step == -1 naturally; the reference needs an explicit
        # guard there because Elixir's 0..-1 range means "to the end".
        self.deltas = self.deltas[:self.replay_step + 1]
        self.deltas.append(d)
        self.replay_step = len(self.deltas) - 1
        # Stamp this action's log entries with their delta index, so the Log
        # screen can offer a jump target per row without matching on text.
        # log_event appends to self.log and self.messages together, so the
        # last len(messages) entries are exactly this action's.
        n = len(self.messages)
        if n:
            for e in self.log[-n:]:
                e["delta_i"] = self.replay_step
        self.messages = []
        if len(self.deltas) > MAX_SAVED_DELTAS:
            drop = len(self.deltas) - MAX_SAVED_DELTAS
            self.deltas = self.deltas[drop:]
            self.replay_step -= drop
            for e in self.log:
                if "delta_i" in e:
                    e["delta_i"] -= drop      # may go negative: no longer a target
        return True

    def can_undo(self):
        return self.replay_step >= 0

    def can_redo(self):
        return self.replay_step < len(self.deltas) - 1

    def undo(self):
        """Parity: game_ui.ex undo/1."""
        if not self.can_undo():
            return False
        m = self.snapshot()
        apply_delta(m, self.deltas[self.replay_step], "undo")
        self.load_snapshot(m)
        self.replay_step -= 1
        return True

    def redo(self):
        """Parity: game_ui.ex redo/1."""
        if not self.can_redo():
            return False
        m = self.snapshot()
        apply_delta(m, self.deltas[self.replay_step + 1], "redo")
        self.load_snapshot(m)
        self.replay_step += 1
        return True

    def step(self, direction):
        """Parity: game_ui.ex step/2."""
        if direction == "undo":
            return self.undo()
        if direction == "redo":
            return self.redo()
        return False

    def apply_deltas_until_index(self, target):
        """Walk the cursor to target. Parity: apply_deltas_until_index/2."""
        moved = False
        while self.replay_step > target and self.undo():
            moved = True
        while self.replay_step < target and self.redo():
            moved = True
        return moved

    def apply_deltas_until_round_change(self, direction):
        """Step until the round changes, or we run out.

        Divergence D1: the reference reads roundNumber off the gameui wrapper
        (game_ui.ex:1017, :1027) where the key does not exist, so its halt
        condition compares nil to nil and never fires. We read the live round.
        """
        round_init = self.round
        moved = False
        while self.step(direction):
            moved = True
            if self.round != round_init:
                break
        return moved

    def step_through(self, options):
        """Parity: game_ui.ex step_through/2."""
        size = options.get("size")
        if size == "single":
            return self.step(options.get("direction"))
        if size == "round":
            return self.apply_deltas_until_round_change(options.get("direction"))
        if size == "index":
            return self.apply_deltas_until_index(options.get("index"))
        return False
```

- [x] **Step 6: Run to verify it passes**

Run: `python3 -m pytest tests/test_gamestate_replay.py -q`
Expected: PASS, 22 tests

- [x] **Step 7: Run the full suite for regressions**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — nothing else touches the new fields yet. If `test_log_and_json.py`
fails on an unexpected `messages` attribute, the fix is in that test's expected
key set, not in `snapshot()`.

- [x] **Step 8: Mirror in `docs/js/gamestate.js`**

In the constructor, after `this._seq = 0;`:

```javascript
    // -- delta replay (parity: DragnCards gameui["deltas"]/["replayStep"])
    this.deltas = [];        // oldest-first; get_delta output + _delta_metadata
    this.replay_step = -1;   // cursor INTO deltas, not a stack pointer
    this.messages = [];      // this action's log text, drained into the delta
```

In `logEvent`, after the existing push to `this.log`:

```javascript
    this.messages.push(text);
```

Add the methods, mirroring Task 2 Step 4–5 field-for-field:

```javascript
  // -- delta replay ------------------------------------------------------
  // The seam between our object graph and the reference's map model.
  // Collections become index-keyed maps because getDelta recurses into maps
  // only - the same reason the reference models everything as *ById.

  snapshot() {
    const keyed = xs => Object.fromEntries(xs.map((x, i) => [String(i), { ...x }]));
    return {
      players: Object.fromEntries(this.players.map((p, i) => [String(i), {
        threat: p.threat, eliminated: p.eliminated,
        commit: p.commit, commit_touched: p.commit_touched }])),
      quest: { ...this.quest },
      active_location: this.active_location ? { ...this.active_location } : null,
      side_quests: keyed(this.side_quests),
      quest_history: keyed(this.quest_history),
      willpower: this.willpower,
      staging: this.staging,
      sailing: this.sailing,
      heading: this.heading,
      pending_budget: this.pending_budget,
      pending_stage: this.pending_stage ? { ...this.pending_stage } : null,
      pending_elim: this.pending_elim,
      round: this.round,
      first_player: this.first_player,
      view: this.view,
      step: this.step,
      stage_idx: this.stage_idx,
      card_idx: this.card_idx,
      quest_resolved: this.quest_resolved,
      quest_outcome: this.quest_outcome,
      quest_outcome_n: this.quest_outcome_n,
      game_over: this.game_over ? { ...this.game_over } : null,
    };
  }

  loadSnapshot(m) {
    const unkeyed = o => Object.keys(o).sort((a, b) => a - b).map(k => ({ ...o[k] }));
    this.players.forEach((p, i) => {
      const pd = m.players[String(i)];
      if (!pd) return;
      p.threat = pd.threat;
      p.eliminated = pd.eliminated;
      p.commit = pd.commit;
      p.commit_touched = pd.commit_touched;
    });
    this.quest = { ...m.quest };
    this.active_location = m.active_location ? { ...m.active_location } : null;
    this.side_quests = unkeyed(m.side_quests);
    this.quest_history = unkeyed(m.quest_history);
    this.willpower = m.willpower;
    this.staging = m.staging;
    this.sailing = m.sailing;
    this.heading = m.heading;
    this.pending_budget = m.pending_budget;
    this.pending_stage = m.pending_stage ? { ...m.pending_stage } : null;
    this.pending_elim = m.pending_elim;
    this.round = m.round;
    this.first_player = m.first_player;
    this.view = m.view;
    this.step = m.step;
    this.stage_idx = m.stage_idx;
    this.card_idx = m.card_idx;
    this.quest_resolved = m.quest_resolved;
    this.quest_outcome = m.quest_outcome;
    this.quest_outcome_n = m.quest_outcome_n;
    this.game_over = m.game_over ? { ...m.game_over } : null;
  }

  addDelta(prevSnapshot) {
    const d = getDelta(prevSnapshot, this.snapshot());
    if (d === null) { this.messages = []; return false; }
    d._delta_metadata = { unix_ms: this._now(), log_messages: this.messages };
    this.deltas = this.deltas.slice(0, this.replay_step + 1);
    this.deltas.push(d);
    this.replay_step = this.deltas.length - 1;
    const n = this.messages.length;
    if (n) {
      for (const e of this.log.slice(-n)) e.delta_i = this.replay_step;
    }
    this.messages = [];
    if (this.deltas.length > MAX_SAVED_DELTAS) {
      const drop = this.deltas.length - MAX_SAVED_DELTAS;
      this.deltas = this.deltas.slice(drop);
      this.replay_step -= drop;
      for (const e of this.log) {
        if ("delta_i" in e) e.delta_i -= drop;   // may go negative: not a target
      }
    }
    return true;
  }

  canUndo() { return this.replay_step >= 0; }
  canRedo() { return this.replay_step < this.deltas.length - 1; }

  undo() {
    if (!this.canUndo()) return false;
    const m = this.snapshot();
    applyDelta(m, this.deltas[this.replay_step], "undo");
    this.loadSnapshot(m);
    this.replay_step -= 1;
    return true;
  }

  redo() {
    if (!this.canRedo()) return false;
    const m = this.snapshot();
    applyDelta(m, this.deltas[this.replay_step + 1], "redo");
    this.loadSnapshot(m);
    this.replay_step += 1;
    return true;
  }

  step(direction) {
    if (direction === "undo") return this.undo();
    if (direction === "redo") return this.redo();
    return false;
  }

  applyDeltasUntilIndex(target) {
    let moved = false;
    while (this.replay_step > target && this.undo()) moved = true;
    while (this.replay_step < target && this.redo()) moved = true;
    return moved;
  }

  applyDeltasUntilRoundChange(direction) {
    const roundInit = this.round;
    let moved = false;
    while (this.step(direction)) {
      moved = true;
      if (this.round !== roundInit) break;
    }
    return moved;
  }

  stepThrough(options) {
    const size = options?.size;
    if (size === "single") return this.step(options.direction);
    if (size === "round") return this.applyDeltasUntilRoundChange(options.direction);
    if (size === "index") return this.applyDeltasUntilIndex(options.index);
    return false;
  }
```

Note `GameState.step` is a **method** while `this.step` is also a **field** (the
phase step id, e.g. `"3.3"`). In JS a field assigned in the constructor shadows
the prototype method, so `game.step("undo")` would throw. **Name the JS method
`stepReplay(direction)`** and have `stepThrough` and
`applyDeltasUntilRoundChange` call it; keep Python's `step()` as-is since
Python's `self.step` attribute has the same collision. **Python has the
identical problem** — `self.step = phases.STEP_ORDER[0]` shadows the method.
So: **both twins name it `step_replay` / `stepReplay`**, and the plan's earlier
`step(direction)` references mean that method. Update the Task 2 Step 1 tests
that call `g.step_through(...)` — they are unaffected — and any direct
`g.step("undo")` call, of which there are none in the test file.

- [x] **Step 9: Fix the shadowing in the Python implementation**

Rename in `gamestate.py`: `def step(self, direction)` → `def step_replay(self, direction)`,
and update the two internal callers (`apply_deltas_until_round_change`,
`step_through`). Add to `tests/test_gamestate_replay.py`:

```python
def test_step_field_is_not_shadowed_by_the_replay_method():
    g = _round1(GameState(2, 25))
    assert isinstance(g.step, str)          # the phase step id, e.g. "1.R"
    _act(g, lambda: g.set_commit(0, 3))
    assert g.step_replay("undo") is True
    assert g.willpower == 0
```

Run: `python3 -m pytest tests/test_gamestate_replay.py -q`
Expected: PASS, 23 tests

- [x] **Step 10: Verify the twins agree**

Run:

```bash
node --input-type=module -e "
import { GameState } from './docs/js/gamestate.js';
const g = new GameState(2, 25);
g.advanceView();
const before = g.snapshot();
g.setCommit(0, 3);
console.log('recorded', g.addDelta(before), 'step', g.replay_step);
console.log('wp', g.willpower);
g.undo();
console.log('after undo wp', g.willpower, 'step', g.replay_step);
g.redo();
console.log('after redo wp', g.willpower);
console.log('snapshot players keyed:', JSON.stringify(Object.keys(g.snapshot().players)));
"
```

Expected: `recorded true step 0`, `wp 3`, `after undo wp 0 step -1`,
`after redo wp 3`, `snapshot players keyed: ["0","1"]`. Compare each line
against the Python twin's equivalent.

- [x] **Step 11: Commit**

```bash
git add gamestate.py docs/js/gamestate.js tests/test_gamestate_replay.py
git commit -m "feat(replay): snapshot projection and replay_step cursor

GameState gains deltas/replay_step/messages plus the reference's method
set: snapshot, load_snapshot, add_delta, undo, redo, step_replay,
step_through, apply_deltas_until_index, apply_deltas_until_round_change.

snapshot()/load_snapshot() are the one adapter parity needs, since
DragnCards' `game` is already a map. Collections project to index-keyed
maps because the diff recurses into maps only - the same constraint that
made the reference model everything as groupById/cardById.

Two documented divergences implemented here: add_delta does not advance
the cursor on a no-op (reference desyncs and swallows the next undo), and
the round walk reads the round from the snapshot (reference reads
gameui[\"roundNumber\"], a key that does not exist, so it never halts).

step_replay, not step: `self.step` is already the phase step id in both
twins and would shadow the method."
```

---

### Task 3: The record point and persistence (both twins)

**Files:**
- Modify: `main.py`, `docs/js/main.js`
- Modify: `gamestate.py`, `docs/js/gamestate.js` (`to_dict`/`from_dict` gain nothing —
  see below; the replay file has its own serializer)
- Test: `tests/test_gamestate_replay.py` (additions)

**Interfaces:**
- Consumes: `add_delta`, `snapshot`, `deltas`, `replay_step` from Task 2.
- Produces: `GameState.replay_to_dict() -> dict` / `replayToDict()`;
  `GameState.replay_from_dict(d) -> None` / `replayFromDict(d)`;
  `main.py` `save_replay(game)`, `load_replay(game)`, `clear_replay()`;
  `main.js` `saveReplay(game)`, `loadReplay(game)`, `clearReplay()`;
  `REPLAY_PATH = "/replay.json"` / `REPLAY_KEY`.

- [x] **Step 1: Write the failing tests** — append to `tests/test_gamestate_replay.py`:

```python
def test_replay_to_dict_carries_deltas_and_the_cursor():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.set_commit(1, 4))
    g.undo()
    d = g.replay_to_dict()
    assert d["replay_step"] == 0
    assert len(d["deltas"]) == 2


def test_replay_round_trips_through_json():
    import json
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.enter_view("quest_commit"))
    blob = json.dumps(g.replay_to_dict())

    g2 = _round1(GameState(2, 25))
    g2.load_snapshot(g.snapshot())
    g2.replay_from_dict(json.loads(blob))
    assert g2.replay_step == g.replay_step
    assert g2.deltas == g.deltas
    assert g2.undo() is True
    assert g2.view == "resource_planning"


def test_replay_from_dict_tolerates_a_missing_or_corrupt_file():
    """A bad replay file must cost you undo, never the game."""
    g = _round1(GameState(2, 25))
    g.replay_from_dict(None)
    assert g.deltas == [] and g.replay_step == -1
    g.replay_from_dict({})
    assert g.deltas == [] and g.replay_step == -1
    g.replay_from_dict({"deltas": "not a list", "replay_step": "x"})
    assert g.deltas == [] and g.replay_step == -1


def test_replay_from_dict_clamps_an_out_of_range_cursor():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    g.replay_from_dict({"deltas": g.deltas, "replay_step": 99})
    assert g.replay_step == len(g.deltas) - 1
    g.replay_from_dict({"deltas": g.deltas, "replay_step": -50})
    assert g.replay_step == -1


def test_to_dict_is_unchanged_by_the_replay_feature():
    """Divergence D4: state.json keeps its exact shape and write path."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    d = g.to_dict()
    assert "deltas" not in d
    assert "replay_step" not in d
    assert "messages" not in d
```

- [x] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_gamestate_replay.py -q -k replay_to_dict or replay_round or replay_from or to_dict_is_unchanged`
Expected: FAIL — `AttributeError: 'GameState' object has no attribute 'replay_to_dict'`

- [x] **Step 3: Implement the replay serializer in `gamestate.py`**

Append to the delta-replay section:

```python
    # -- replay persistence ------------------------------------------------
    # Parity: the Replay schema's two columns (backend/lib/dragn/replay.ex) -
    # game_json and deltas. Divergence D4: two stores rather than one row,
    # because the device writes flash, not Postgres, and state.json is
    # rewritten on every tap. to_dict()/from_dict() are untouched.
    #
    # Divergence D3: replay_step is written, not recomputed. The reference
    # derives it as count(deltas)-1 on load while game_json holds whatever the
    # current state was, so saving mid-undo reloads a cursor that claims
    # end-of-history over a state several steps back.

    def replay_to_dict(self):
        return {"deltas": self.deltas, "replay_step": self.replay_step}

    def replay_from_dict(self, d):
        """Load a replay blob. Anything malformed degrades to no history."""
        self.deltas = []
        self.replay_step = -1
        if not isinstance(d, dict):
            return
        ds = d.get("deltas")
        if not isinstance(ds, list) or not all(isinstance(x, dict) for x in ds):
            return
        self.deltas = ds
        rs = d.get("replay_step")
        if not isinstance(rs, int) or isinstance(rs, bool):
            self.replay_step = len(ds) - 1
            return
        self.replay_step = max(-1, min(rs, len(ds) - 1))
```

- [x] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_gamestate_replay.py -q`
Expected: PASS

- [x] **Step 5: Wire the record point in `main.py`**

Next to `STATE_PATH`, add:

```python
REPLAY_PATH = "/replay.json"
```

Next to `save_state`, add the replay-file trio:

```python
def save_replay(game):
    """Persist the delta history. Parity: Replay.deltas. Failure is silent -
    losing undo must never cost you the game."""
    try:
        with open(REPLAY_PATH, "w") as f:
            json.dump(game.replay_to_dict(), f)
    except Exception:
        pass


def load_replay(game):
    try:
        with open(REPLAY_PATH) as f:
            game.replay_from_dict(json.load(f))
    except Exception:
        game.replay_from_dict(None)


def clear_replay():
    try:
        import os
        os.remove(REPLAY_PATH)
    except Exception:
        pass
```

In the button-dispatch tail (`main.py:519`, the `elif result: save_state(game)`
branch), take a snapshot before dispatch and record after. The dispatch site
already holds `result = screen.on_button(b, game)`; wrap it:

```python
                    snap_before = game.snapshot()
                    result = screen.on_button(b, game)
                    ...
                    elif result:
                        game.add_delta(snap_before)
                        save_state(game)
                        save_replay(game)
```

Mirror the same two-line addition at the modal-close `save_state(game)` site,
and add `clear_replay()` beside the existing `clear_state()` in the `end_game`
branch, and `save_replay(game)` beside `save_state(game)` in `save_quit`.
Call `load_replay(game)` immediately after `load_saved()` returns a game.

- [x] **Step 6: Mirror in `docs/js/main.js`**

Next to `STATE_KEY`:

```javascript
const REPLAY_KEY = "lotr_hud_replay";
```

```javascript
function saveReplay(game) {
  try { localStorage.setItem(REPLAY_KEY, JSON.stringify(game.replayToDict())); }
  catch { /* losing undo must never cost the game */ }
}
function loadReplay(game) {
  try { game.replayFromDict(JSON.parse(localStorage.getItem(REPLAY_KEY))); }
  catch { game.replayFromDict(null); }
}
function clearReplay() { localStorage.removeItem(REPLAY_KEY); }
```

Same wrapping at `docs/js/main.js:463` (`} else if (result) { saveState(game); }`)
and the modal-close `saveState(game)` at `:173`, plus `clearReplay()` in
`end_game` and `saveReplay(game)` in `save_quit`.

- [x] **Step 7: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS

- [x] **Step 8: Commit**

```bash
git add gamestate.py docs/js/gamestate.js main.py docs/js/main.js tests/test_gamestate_replay.py
git commit -m "feat(replay): record deltas at the dispatch choke point

One snapshot before screen.on_button, one add_delta after - mirroring the
reference's single process_update call site (game_ui_server.ex). No
mutator, screen, or modal learns anything about undo.

Persistence maps Replay's two columns onto two files rather than one DB
row (divergence D4): state.json keeps its exact shape and every-tap write
path, replay.json carries deltas + replay_step. A missing or corrupt
replay file degrades to no undo history, never to a broken game.

replay_step is written rather than recomputed (divergence D3) - the
reference derives count(deltas)-1 on load, which desyncs the cursor from
game_json whenever a game is saved mid-undo."
```

---

### Task 4: The bottom nav bar on the guided round screen (both twins)

**Approved design** — mockups rendered through the real draw code and signed off
2026-07-26. They live in `docs/screenshots/mockups/` and are the acceptance
target for this task:

| mockup | shows |
|---|---|
| `nav-quest-staging-back.png` | the nav bar with Back present |
| `nav-combat-longest-label.png` | the longest label in the app, `Combat (Player Attacks)` |
| `nav-no-back.png` | no history: left square absent, label does not move |
| `nav-action-cta.png` | a CTA that is an action, not a transition (`End Round`) |
| `setup-overflow-before.png` / `setup-overflow-after.png` | the pre-existing `setup_game` overflow the rule exposed, and the fix |

The full-width CTA button is replaced by a **bottom nav bar**: a 1px rule
dividing the content area from the band, then two identical square arrow
buttons at the outer edges with the destination label between them, outside
both buttons. Three decisions the mockups lock in:

1. **The arrows are identical squares** — `NAV_W = CTA_H`, so square by
   construction. The label sits outside them; that is what keeps them matched.
2. **The label frame is fixed** (x 74…406, centred on 240) whether or not Back
   is drawn, so the text does not jump the moment the first delta is recorded.
3. **Hit areas are deliberately asymmetric.** Forward spans label + arrow
   (74…472) because it is tapped every phase and a 58px target would be a
   regression from today's 464px. Back is its square only, so reaching for the
   label can never undo.

Dropping the `Next: ` prefix takes the longest label from 408px to **330px**,
which fits the 348px span between the squares with 9px either side. **No
short-label table is needed** — every phase keeps its full printed name.

**Files:**
- Modify: `ui/widgets.py`, `docs/js/ui.js` (arrow primitives)
- Modify: `ui/screen_play.py`, `docs/js/screen_play.js`
- Modify: `tests/test_screen_play.py`, `tests/scenes.py`

**Interfaces:**
- Consumes: `can_undo`/`canUndo`, `undo` from Task 2.
- Produces: `arrow_left(d, pal, cx, cy, size, pen, shadow=True)` and
  `arrow_right(...)` in `ui/widgets.py`; `arrowLeft(ctx, cx, cy, size, pen,
  shadow = true)` / `arrowRight(...)` in `docs/js/ui.js`. Module constants in
  both screen files: `NAV_W = CTA_H`, `NAV_RULE_Y = 400`, `ARROW = 22`,
  `NAV_PAD = 8`. `_cta` gains a `game` parameter — Python
  `_cta(self, d, pal, game, label, id, fill=None, fg=None)`, JS
  `_cta(ctx, game, label, id, fill = pal.btn_ok, fg = pal.gold)`. New button id
  `("back",)` / `["back"]`.

- [x] **Step 1: Write the failing tests** — add to `tests/test_screen_play.py`:

```python
def test_nav_rule_is_drawn_full_width():
    from ui.screen_play import NAV_RULE_Y
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    rules = [c for c in hw.display.calls
             if c[0] == "rect" and c[2] == NAV_RULE_Y and c[3] == 480 and c[4] == 1]
    assert len(rules) == 1


def test_back_square_absent_with_no_history():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    assert "back" not in _ids(screen)


def test_back_square_appears_with_history_and_undoes():
    from ui.screen_play import NAV_W, CTA_H, CTA_Y, MARGIN
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    snap = game.snapshot()
    screen.on_button(_find(screen, ("advance",)), game)
    game.add_delta(snap)
    screen.draw(hw, game, pal)
    back = _find(screen, ("back",))
    assert (back.x, back.y, back.w, back.h) == (MARGIN, CTA_Y, NAV_W, CTA_H)
    assert back.w == back.h == CTA_H          # square by construction
    assert screen.on_button(back, game) is True
    assert game.view == "resource_planning"


def test_forward_hit_area_spans_label_and_arrow():
    """The most-tapped control keeps a large target even though only the
    arrow square is drawn as a button."""
    from ui.screen_play import NAV_W, MARGIN, NAV_PAD, CTA_Y, CTA_H
    hw, pal, game, screen = _setup("travel")
    screen.draw(hw, game, pal)
    fwd = _find(screen, ("advance",))
    assert fwd.x == MARGIN + NAV_W + NAV_PAD
    assert fwd.x + fwd.w == 480 - MARGIN
    assert (fwd.y, fwd.h) == (CTA_Y, CTA_H)


def test_label_frame_does_not_move_when_back_appears():
    hw, pal, game, screen = _setup("travel")
    screen.draw(hw, game, pal)
    before = [c[2] for c in hw.display.calls
              if c[0] == "text" and str(c[1]) == "Encounter (Opt. Engage)"]
    snap = game.snapshot()
    game.adjust_threat(0, 1)
    game.add_delta(snap)
    hw.display.calls.clear()
    screen.draw(hw, game, pal)
    after = [c[2] for c in hw.display.calls
             if c[0] == "text" and str(c[1]) == "Encounter (Opt. Engage)"]
    assert before and before == after


def test_phase_advance_uses_a_kicker_and_the_bare_phase_name():
    hw, pal, game, screen = _setup("combat_enemy")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "NEXT PHASE" in texts
    assert "Combat (Player Attacks)" in texts
    assert "Next: Combat (Player Attacks)" not in texts


def test_action_ctas_are_a_single_line_with_no_kicker():
    hw, pal, game, screen = _setup("refresh")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "End Round" in texts
    assert "NEXT PHASE" not in texts


def test_every_label_fits_between_the_nav_squares():
    """Replaces the old full-width ceiling: the label frame is now the
    constraint, and it is the same whether or not Back is drawn."""
    import gamestate
    from ui.screen_play import MARGIN, NAV_W, NAV_PAD
    from ui.theme import DISPLAY
    hw = FakeHardware()
    lx = MARGIN + NAV_W + NAV_PAD
    usable = (480 - MARGIN - NAV_W - NAV_PAD) - lx
    labels = ["Begin Round 1", "End Round", "Confirm all commits",
              "Flip to Side B  ->  10 qp"] + list(gamestate.VIEW_LABELS.values())
    over = [(s, hw.display.measure_text(s, DISPLAY)) for s in labels
            if hw.display.measure_text(s, DISPLAY) > usable]
    assert not over, "nav labels overflow %dpx: %s" % (usable, over)


def test_back_is_a_noop_when_history_is_empty():
    from ui.widgets import Button
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    assert screen.on_button(Button(("back",), 0, 0, 1, 1), game) is None


def test_back_clears_screen_local_allocation_and_banner():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 11, 7
    screen.draw(hw, game, pal)
    snap = game.snapshot()
    screen.on_button(_find(screen, ("stage_advance",)), game)
    game.add_delta(snap)
    screen.draw(hw, game, pal)
    assert screen.alloc is not None
    screen.on_button(_find(screen, ("back",)), game)
    assert screen.alloc is None
    assert screen.banner is None
    assert game.view == "quest_staging"
```

Add to `tests/scenes.py`, beside the other `_*` mutators (~line 338):

```python
def _has_undo_history(g):
    """Two recorded deltas that cancel out, so can_undo() is True while no
    stat on screen differs from the no-history scene - the nav row is then the
    only visual difference between the two mockups."""
    for delta in (1, -1):
        snap = g.snapshot()
        g.adjust_threat(0, delta)
        g.add_delta(snap)
```

and register in `SCENES` (~line 1114):

```python
    "play_quest_staging_can_back": _play("quest_staging", mutate=_has_undo_history),
    "play_combat_player_can_back": _play("combat_enemy", mutate=_has_undo_history),
    "play_travel_can_back": _play("travel", mutate=_has_undo_history),
```

- [x] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_screen_play.py -q -k "nav or back or kicker or fits_between"`
Expected: FAIL — `NAV_RULE_Y` does not exist.

- [x] **Step 3: Add the arrow primitives**

`ui/widgets.py`, above `text_left`:

```python
def _arrow(d, pal, cx, cy, size, pen, left, shadow=True):
    """Solid triangular arrow, drawn with d.triangle - the same device-safe
    primitive draw_notif_pie already uses, so no new icon mask is needed.
    size is the full width and height."""
    h = size // 2
    tip, base = (cx - h, cx + h) if left else (cx + h, cx - h)
    if shadow:
        d.set_pen(pal.shadow)
        d.triangle(tip + 2, cy + 2, base + 2, cy - h + 2, base + 2, cy + h + 2)
    d.set_pen(pen)
    d.triangle(tip, cy, base, cy - h, base, cy + h)


def arrow_left(d, pal, cx, cy, size, pen, shadow=True):
    _arrow(d, pal, cx, cy, size, pen, True, shadow)


def arrow_right(d, pal, cx, cy, size, pen, shadow=True):
    _arrow(d, pal, cx, cy, size, pen, False, shadow)
```

Mirror in `docs/js/ui.js` as `arrowLeft`/`arrowRight`, taking `ctx` in place of
`(d, pal)` per that file's convention, and export both.

- [x] **Step 4: Rebuild `_cta` as the nav bar**

`ui/screen_play.py` — replace `BACK_W`-era constants with:

```python
NAV_W = CTA_H          # back / forward are matching squares, CTA_H on a side
NAV_RULE_Y = 400       # 1px rule dividing the content area from the bottom nav
ARROW = 22             # arrow glyph size inside a nav square
NAV_PAD = 8            # clearance between a nav square and the label between them
```

and add `arrow_left, arrow_right` to the `ui.widgets` import. Replace `_cta`:

```python
    def _cta(self, d, pal, game, label, id, fill=None, fg=None):
        """The bottom nav bar: a 1px rule, then matching square arrow buttons
        at each edge with the destination label between them.

        The label sits OUTSIDE both buttons so the two arrows stay identically
        sized. It is still part of the forward button's hit area, though - that
        control is tapped every phase, so its target spans label + arrow rather
        than the 58px square alone. Back's target is only its square, so a
        mis-reach for the label can never undo.
        """
        d.set_pen(pal.border)
        d.rectangle(0, NAV_RULE_Y, 480, 1)
        fgp = fg if fg is not None else pal.gold
        cy = CTA_Y + CTA_H // 2
        fwd_x = 480 - MARGIN - NAV_W

        if game.can_undo():
            back = Button(("back",), MARGIN, CTA_Y, NAV_W, CTA_H)
            bevel(d, pal, back.x, back.y, back.w, back.h, pal.btn, t=3)
            arrow_left(d, pal, MARGIN + NAV_W // 2, cy, ARROW, pal.tan)
            self.buttons.append(back)

        bevel(d, pal, fwd_x, CTA_Y, NAV_W, CTA_H,
              fill if fill is not None else pal.btn_ok, t=3)
        arrow_right(d, pal, fwd_x + NAV_W // 2, cy, ARROW, fgp)

        # Label centred in the span between the squares - a fixed frame, so the
        # text does not shift when Back appears.
        lx, rx = MARGIN + NAV_W + NAV_PAD, fwd_x - NAV_PAD
        tcx = (lx + rx) // 2
        # Phase advances read as a kicker over the destination; every other CTA
        # ("End Round", "Flip to Side B ...") is a single centred line.
        if label.startswith("Next: "):
            text_center(d, pal, "NEXT PHASE", tcx, CTA_Y + 10, LABEL, pal.muted)
            text_center(d, pal, label[6:], tcx, CTA_Y + 24, DISPLAY, fgp)
        else:
            text_center(d, pal, label, tcx, CTA_Y + 16, DISPLAY, fgp)
        # one hit area: the label span plus the arrow square
        self.buttons.append(Button(id, lx, CTA_Y, 480 - MARGIN - lx, CTA_H))
```

`"NEXT PHASE"` is ALL-CAPS chrome, which is exactly what `LABEL` is for — it
passes `tests/test_typography.py` unaided, no allowlist entry.

Update all 12 `_cta(` call sites to pass `game` third
(`ui/screen_play.py:258, 271, 279, 298, 331, 390, 419, 436, 494, 551, 588, 675`;
re-find with `grep -n "_cta(" ui/screen_play.py`). Every one already has `game`
in scope. **Do not change the label strings** — they stay
`"Next: %s" % VIEW_LABELS[...]`; `_cta` splits the prefix off itself.

Add the button case to `on_button`:

```python
        if b.id == ("back",):
            if not game.undo():
                return None
            # screen-local scratch describes the view we just left
            self.alloc = None
            self.banner = None
            return True
```

- [x] **Step 5: Run to verify it passes**

Run: `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`
Expected: PASS. The old `test_every_cta_label_fits_the_button_at_display_size`
must be **deleted**, not left passing — it measures `"Next: %s"` strings that
are no longer drawn, so it would guard nothing.
`test_every_label_fits_between_the_nav_squares` replaces it.

- [x] **Step 6: Fix the `setup_game` overflow the rule exposes**

This is a **pre-existing bug**, not one this feature introduces: on unmodified
code that view's stack runs to y=412, **2px past the CTA at 410**. The layout
linter never caught it because it compares text, not rectangles. The nav rule
at 400 makes it plainly visible (see
`docs/screenshots/mockups/setup-overflow-before.png`).

Reclaim 20px in the `view == "setup_game"` branch:

```python
            th = note_panel(d, pal, MARGIN, 56, 480 - 2 * MARGIN, SETUP_TIP)
            # This view's two rows are the tallest stack on any play screen and
            # used to run to y=412 - 2px PAST the old CTA at 410, an overlap the
            # layout linter never caught because it compares text, not rects.
            # The nav rule at NAV_RULE_Y makes it visible, so the rows were
            # tightened by 20px total (gap 18->8, rows 48->42 and 38->34) and
            # now end at 392, clearing the rule by 8px. Every target stays
            # >=24px.
            y = 56 + th + 8
            text_left(d, pal, "Stage 1B quest points", MARGIN + 8, y + 13, BODY, pal.tan)
            mn = Button(("qp", -1), 300, y, 52, 42)
            pl = Button(("qp", 1), 412, y, 52, 42)
            for b, s in ((mn, "-"), (pl, "+")):
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                text_center(d, pal, s, b.x + 26, b.y + 9, DISPLAY, pal.tan)
                self.buttons.append(b)
            text_center(d, pal, str(game.quest["points"]), 382, y + 9, DISPLAY, pal.gold)
            sy = y + 44
            text_left(d, pal, "Sailing quest", MARGIN + 8, sy + 9, BODY, pal.tan)
            icons.draw(d, icons.WHEEL, 160, sy + 6, pal.gold if game.sailing else pal.dim)
            sb = Button(("sail_toggle",), 300, sy, 164, 34)
            panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.gold if game.sailing else pal.btn)
            text_center(d, pal, "On" if game.sailing else "Off", sb.x + 82, sb.y + 9, BODY,
                        pal.bg if game.sailing else pal.tan, shadow=False)
            self.buttons.append(sb)
```

Mirror the same numbers in `docs/js/screen_play.js`.

- [x] **Step 7: Teach the layout linter to catch this class of bug**

The linter missed a shipping overlap. Add to `tests/test_layout.py`:

```python
NAV_RULE_SCENES = tuple(s for s in SCENES if s.startswith("play_"))


@pytest.mark.parametrize("scene", NAV_RULE_SCENES)
def test_play_content_clears_the_nav_rule(scene):
    """No drawn rectangle may cross into the bottom nav band. This is the
    check that would have caught setup_game running 2px past its CTA."""
    from ui.screen_play import NAV_RULE_Y
    hw, _ = SCENES[scene]()
    for c in hw.display.calls:
        if c[0] != "rect":
            continue
        _, x, y, w, h = c
        if w >= 480 and y == NAV_RULE_Y:
            continue                      # the rule itself
        if y < NAV_RULE_Y:
            assert y + h <= NAV_RULE_Y, (
                "%s: rect at y=%d h=%d crosses the nav rule at %d"
                % (scene, y, h, NAV_RULE_Y))
```

Run: `python3 -m pytest tests/test_layout.py -q` → PASS for every play scene.

- [x] **Step 8: Render and compare against the approved mockups**

```bash
python3 tools/preview.py play_quest_staging_can_back /tmp/nav1.png
python3 tools/preview.py play_combat_player_can_back /tmp/nav2.png
python3 tools/preview.py play_combat_enemy /tmp/nav3.png
python3 tools/preview.py play_refresh /tmp/nav4.png
python3 tools/preview.py play_setup /tmp/nav5.png
```

Each must match its counterpart in `docs/screenshots/mockups/` — the mockups
were rendered from this exact code path, so any difference is a porting error.

- [x] **Step 9: Mirror in `docs/js/screen_play.js`**

The JS `_cta` (`docs/js/screen_play.js:134`) has the same shape — direct
`new Button(...)`, `bevel`, `textCenter`. Port constant-for-constant:

```javascript
const NAV_W = CTA_H;
const NAV_RULE_Y = 400;
const ARROW = 22;
const NAV_PAD = 8;
```

```javascript
  _cta(ctx, game, label, id, fill = pal.btn_ok, fg = pal.gold) {
    rect(ctx, 0, NAV_RULE_Y, 480, 1, pal.border);
    const cy = CTA_Y + CTA_H / 2;
    const fwdX = 480 - MARGIN - NAV_W;
    if (game.canUndo()) {
      const back = new Button(["back"], MARGIN, CTA_Y, NAV_W, CTA_H);
      bevel(ctx, back.x, back.y, back.w, back.h, pal.btn, false, 3);
      arrowLeft(ctx, MARGIN + NAV_W / 2, cy, ARROW, pal.tan);
      this.buttons.push(back);
    }
    bevel(ctx, fwdX, CTA_Y, NAV_W, CTA_H, fill, false, 3);
    arrowRight(ctx, fwdX + NAV_W / 2, cy, ARROW, fg);
    const lx = MARGIN + NAV_W + NAV_PAD, rx = fwdX - NAV_PAD;
    const tcx = Math.floor((lx + rx) / 2);
    if (label.startsWith("Next: ")) {
      textCenter(ctx, "NEXT PHASE", tcx, CTA_Y + 10, LABEL, pal.muted);
      textCenter(ctx, label.slice(6), tcx, CTA_Y + 24, DISPLAY, fg);
    } else {
      textCenter(ctx, label, tcx, CTA_Y + 16, DISPLAY, fg);
    }
    this.buttons.push(new Button(id, lx, CTA_Y, 480 - MARGIN - lx, CTA_H));
  }
```

and in `onButton`, using this file's id-comparison helper:

```javascript
    if (idEq(b.id, ["back"])) {
      if (!game.undo()) return null;
      this.alloc = null;
      this.banner = null;
      return true;
    }
```

Update every `_cta(` call site to pass `game` second
(`grep -n "_cta(" docs/js/screen_play.js`), and mirror Step 6's `setup_game`
numbers. Use the file's own `rect`/`bevel`/`textCenter` helpers.

- [x] **Step 10: Commit**

```bash
git add ui/widgets.py docs/js/ui.js ui/screen_play.py docs/js/screen_play.js \
        tests/test_screen_play.py tests/test_layout.py tests/scenes.py \
        docs/screenshots/mockups/
git commit -m "feat(play): bottom nav bar with back/forward arrow squares

Replaces the full-width CTA with a rule at y=400 plus matching 58x58
arrow squares at each edge (NAV_W = CTA_H, square by construction) and
the destination label between them, outside both buttons - which is what
keeps the two arrows identically sized.

The label frame is fixed whether or not Back is drawn, so the text does
not jump when the first delta is recorded. Forward's hit area spans
label + arrow because it is tapped every phase; Back's is only its
square, so reaching for the label can never undo.

Dropping the 'Next: ' prefix takes the longest label from 408px to 330px
in a 348px span, so no short-label table is needed and every phase keeps
its full printed name.

Arrows are d.triangle, the primitive draw_notif_pie already uses - no new
icon mask.

Also fixes a PRE-EXISTING setup_game overflow (its stack ran to y=412,
2px past the old CTA at 410) that the rule made visible, and adds the
rect-crossing check to the layout linter that would have caught it.
Mockups approved 2026-07-26, committed under docs/screenshots/mockups/."
```

---

### Task 5: The transport and retcon on the Log screen (both twins)

Parity's payoff: the reference's log **is** the delta list, so every entry is a
jump target. Our log stays its own append-only record (it carries timestamps and
round/step tags the deltas do not), and the transport is added beside it, with
each row that came from a delta made tappable via the `delta_i` stamp Task 2
writes.

**The vertical budget.** `ui/screen_log.py` is 69 lines and already spends the
screen: rows run from `HEADER_H + 10` = 50 in `ROW_H` = 26 steps, `PER_PAGE` = 13
of them, ending at 388; the Older/Newer pager sits at y=420 h=46
(`ui/screen_log.py:49-57`). That leaves a 32px gap — not enough for a 46px
control row. **Drop `PER_PAGE` to 11**, which frees 52px: rows then end at 336,
the transport occupies y=348 h=46, and the pager is untouched at 420 with 26px
of clearance. Paging already exists to reach older entries, so showing two fewer
rows per page costs nothing but a tap.

**Files:**
- Modify: `ui/screen_log.py`, `docs/js/screens_other.js`
- Modify: `tests/test_screen_log.py`, `tests/scenes.py`

**Interfaces:**
- Consumes: `deltas`, `replay_step`, `step_through`, `can_undo`, `can_redo`
  from Task 2, and the `delta_i` key `add_delta` stamps onto log entries.
- Produces: `PER_PAGE = 11` (was 13), `REPLAY_Y = 348`, `REPLAY_H = 46`,
  `REPLAY_BTN_W = 56` module constants; button ids `("replay", "first")`,
  `("replay", "round_back")`, `("replay", "undo")`, `("replay", "redo")`,
  `("replay", "last")`, and `("replay_jump", <delta_index>)`.

- [x] **Step 1: Write the failing tests** — add to `tests/test_screen_log.py`.
  This file has only a `_draw()` helper that builds a fresh `GameState`
  (`tests/test_screen_log.py:12`), so the history-aware helpers are new:

```python
def _draw_with(g):
    """_draw(), but over a caller-supplied game."""
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScreenLog()
    s.draw(hw, g, pal)
    return hw, pal, s


def _history(n=3):
    """A round-1 game with n recorded deltas, each raising P1's threat by 1."""
    g = GameState(2, 25)
    g.advance_view()
    for _ in range(n):
        snap = g.snapshot()
        g.adjust_threat(0, 1)
        g.add_delta(snap)
    return g


def _btn(s, id):
    return [b for b in s.buttons if b.id == id][0]


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_transport_shows_the_cursor_position():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    assert "3/3" in _texts(hw)


def test_transport_undo_moves_the_cursor_and_the_game():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    assert g.players[0].threat == 28
    assert s.on_button(_btn(s, ("replay", "undo")), g) is True
    assert g.replay_step == 1
    assert g.players[0].threat == 27


def test_transport_first_and_last_rewind_and_fast_forward():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    s.on_button(_btn(s, ("replay", "first")), g)
    assert g.replay_step == -1
    assert g.players[0].threat == 25
    hw, pal, s = _draw_with(g)
    s.on_button(_btn(s, ("replay", "last")), g)
    assert g.replay_step == 2
    assert g.players[0].threat == 28


def test_transport_is_a_noop_at_the_ends():
    g = _history(0)
    hw, pal, s = _draw_with(g)
    assert s.on_button(_btn(s, ("replay", "undo")), g) is None
    assert s.on_button(_btn(s, ("replay", "redo")), g) is None


def test_transport_draws_even_with_no_history_so_the_layout_is_stable():
    g = _history(0)
    hw, pal, s = _draw_with(g)
    assert "0/0" in _texts(hw)
    for which in ("first", "round_back", "undo", "redo", "last"):
        assert _btn(s, ("replay", which)) is not None


def test_tapping_a_delta_row_jumps_to_it():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    assert s.on_button(_btn(s, ("replay_jump", 0)), g) is True
    assert g.replay_step == 0
    assert g.players[0].threat == 26


def test_rows_without_a_delta_get_no_jump_button():
    """Setup entries are logged before any delta exists, so they are not
    jump targets."""
    g = _history(2)
    hw, pal, s = _draw_with(g)
    jumps = sorted(b.id[1] for b in s.buttons if b.id[0] == "replay_jump")
    assert jumps == [0, 1]              # not one per log row


def test_round_back_halts_at_the_round_boundary():
    g = GameState(2, 25)
    g.advance_view()
    snap = g.snapshot(); g.adjust_threat(0, 1); g.add_delta(snap)
    g.view = "refresh"
    snap = g.snapshot(); g.end_round(); g.add_delta(snap)
    snap = g.snapshot(); g.enter_view("quest_commit"); g.add_delta(snap)
    assert g.round == 2
    hw, pal, s = _draw_with(g)
    assert s.on_button(_btn(s, ("replay", "round_back")), g) is True
    assert g.round == 1


def test_per_page_shrank_to_make_room_for_the_transport():
    from ui.screen_log import PER_PAGE, REPLAY_Y, ROW_H
    from ui.header import HEADER_H
    assert PER_PAGE == 11
    assert HEADER_H + 10 + PER_PAGE * ROW_H <= REPLAY_Y
```

Add a scene to `tests/scenes.py`. This file builds screen scenes with the
`_screen(mod, cls, prep=None)` factory (`tests/scenes.py:100`), so the scene is
a `prep`. Put it beside `_log_prep` (~line 333):

```python
def _log_replay_prep(g):
    """Log screen mid-history: 6 recorded deltas, cursor two steps back, so
    the transport shows an active redo half and a mid-list position."""
    _log_prep(g)
    for _ in range(6):
        snap = g.snapshot()
        g.adjust_threat(0, 1)
        g.add_delta(snap)
    g.undo()
    g.undo()
```

and register it in `SCENES` beside `"log"` (~line 1168):

```python
    "log_replay": _screen("ui.screen_log", "ScreenLog", prep=_log_replay_prep),
```

- [x] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_screen_log.py -q`
Expected: FAIL — no `("replay", ...)` buttons

- [x] **Step 3: Implement in `ui/screen_log.py`**

Change the module constants (`ui/screen_log.py:9-10`) and add the transport's:

```python
PER_PAGE = 11          # was 13: two rows traded for the transport row below
ROW_H = 26
REPLAY_Y = 348         # rows end at HEADER_H + 10 + 11*26 = 336
REPLAY_H = 46          # same height as the Older/Newer pager
REPLAY_BTN_W = 56
```

Add the transport method. It mirrors `LogButtons.js`'s `⏮ ◀ n/N ▶ ⏭` plus a
round-back control the reference only exposes as a hotkey. The file has no
`_btn`/`_text` helpers — it draws with `bevel` + `text_center` directly, exactly
like its pager:

```python
    def _replay_transport(self, d, pal, game):
        """Cursor transport. Parity: frontend/src/features/messages/
        LogButtons.js - the same five controls and the same n/total readout,
        plus the round-granularity step the reference binds to Shift+Arrow
        (useDragnHotkeys.js) and never gives a button, because the Presto has
        no keyboard.

        Always drawn, even with no history, so the row does not appear and
        disappear under the log and shift the pager."""
        back_on, fwd_on = game.can_undo(), game.can_redo()
        specs = (
            (("replay", "first"),      "|<", 12,  back_on),
            (("replay", "round_back"), "<<", 74,  back_on),
            (("replay", "undo"),       "<",  136, back_on),
            (("replay", "redo"),       ">",  350, fwd_on),
            (("replay", "last"),       ">|", 412, fwd_on),
        )
        for bid, label, x, on in specs:
            b = Button(bid, x, REPLAY_Y, REPLAY_BTN_W, REPLAY_H)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn if on else pal.card)
            text_center(d, pal, label, b.x + REPLAY_BTN_W // 2, REPLAY_Y + 14,
                        BODY, pal.tan if on else pal.dim)
            self.buttons.append(b)
        # Cursor position is dense tabular metadata -> BODY here to match the
        # pager's own "%d/%d" readout two rows down (screen_log.py:55), which
        # a player reads the same way.
        text_center(d, pal, "%d/%d" % (game.replay_step + 1, len(game.deltas)),
                    271, REPLAY_Y + 14, BODY, pal.muted)
```

`271` is the midpoint of the 192..350 gap between the two button groups. The
widest readout, `"123/456"`, is 66px at `BODY`, spanning 238..304 — clear of
both groups.

Call it from `draw`, right after the row loop and before the pager block:

```python
        self._replay_transport(d, pal, game)
```

Make delta-backed rows tappable. Inside the existing `for e in chunk:` loop,
after the row is drawn and before `y += ROW_H`:

```python
            # Rows produced by a recorded action carry a delta_i stamp (see
            # GameState.add_delta) and become jump targets. Setup entries and
            # anything logged outside an action have none, and stay inert.
            di = e.get("delta_i")
            if di is not None and 0 <= di < len(game.deltas):
                self.buttons.append(Button(("replay_jump", di), 12, y,
                                           480 - 24, ROW_H))
```

Handle the new ids in `on_button`, which currently switches on `btn.id[0]`
(`ui/screen_log.py:59-69`) — add before the final `return None`:

```python
        if k == "replay":
            which = btn.id[1]
            if which == "first":
                return game.step_through({"size": "index", "index": -1}) or None
            if which == "last":
                return game.step_through(
                    {"size": "index", "index": len(game.deltas) - 1}) or None
            if which == "round_back":
                return game.step_through(
                    {"size": "round", "direction": "undo"}) or None
            return game.step_through(
                {"size": "single", "direction": which}) or None
        if k == "replay_jump":
            return game.step_through({"size": "index", "index": btn.id[1]}) or None
```

`or None` converts the dispatcher's `False` into this codebase's "nothing
happened, do not save" convention — the same convention the existing `return
None` fallthrough uses.

`BODY` is already imported (`ui/screen_log.py:6`); `Button`, `bevel` and
`text_center` likewise (`:7`). No new imports.

- [x] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_screen_log.py tests/test_layout.py -q`
Expected: PASS

- [x] **Step 5: Render and inspect**

Run: `python3 tools/preview.py log_replay /tmp/log_transport.png`
Expected: the transport reads `4/6` (six deltas, cursor two back), all five
controls active because both halves are live, nothing overlapping the 11 log
rows above or the Older/Newer pager below, every control ≥ 24px each dimension.
Also render the no-history case to confirm the row holds its place:
`python3 tools/preview.py log /tmp/log_plain.png` — `0/0` with all five
controls dimmed.

- [x] **Step 6: Mirror in `docs/js/screens_other.js`**

Port `_replayTransport` and the two `onButton` id cases into `ScreenLog`,
matching the Python geometry constant-for-constant (`PER_PAGE = 11`,
`REPLAY_Y = 348`, `REPLAY_H = 46`, `REPLAY_BTN_W = 56`, the five x positions
`12, 74, 136, 350, 412`, and the readout centred at `271`). Use the file's own
`bevel` / `textCenter` and its id-comparison helper, and the same pens
(`pal.btn`/`pal.tan` active, `pal.card`/`pal.dim` inert, `pal.muted` for the
readout).

- [x] **Step 7: Verify in the browser**

Open the Log screen mid-game. Step back with `<`, confirm the stats on the play
screen behind it move with the cursor. Tap a log row and confirm the game jumps
there. Confirm `<<` stops at a round boundary rather than running to the start.
Console clean.

- [x] **Step 8: Commit**

```bash
git add ui/screen_log.py docs/js/screens_other.js tests/test_screen_log.py tests/scenes.py
git commit -m "feat(log): replay transport and tap-a-row retcon

Mirrors the reference's LogButtons.js (|< << < n/N > >|) and
LogMessageDiv.js's clickable rows, which broadcast
step_through {size: index}. The round-granularity control is the one
addition: the reference only exposes it as Shift+Arrow
(useDragnHotkeys.js), and the Presto has no keyboard.

Our log stays a separate append-only record rather than becoming the
delta list - it carries timestamps and round/step tags the deltas do not,
and it must not lose entries when a redo future is truncated."
```

---

### Task 6: Verification

- [x] **Step 1: Full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS, including the layout linter over the two new scenes.

- [x] **Step 2: Regenerate shared data and confirm no drift**

Run: `python3 tools/gen_web_data.py && git diff --stat docs/js/`
Expected: no changes to `docs/js/{phases,icons,metrics}.js` — this feature
touches none of their inputs. A diff here means something was hand-edited.

- [x] **Step 3: Twin-parity check on a full round**

Play the same 16-action round in both twins and compare the delta logs
byte-for-byte:

```bash
python3 -c "
import json, sys; sys.path.insert(0, '.')
from gamestate import GameState
g = GameState(2, 26); g.clock = lambda: 1000; g.advance_view()
for fn in (lambda: g.enter_view('quest_commit'), lambda: g.set_commit(0, 5),
           lambda: g.set_commit(1, 4), lambda: g.enter_view('quest_staging')):
    s = g.snapshot(); fn(); g.add_delta(s)
for d in g.deltas: d.pop('_delta_metadata', None)
print(json.dumps(g.deltas, sort_keys=True))
" > /tmp/py_deltas.json

node --input-type=module -e "
import { GameState } from './docs/js/gamestate.js';
const g = new GameState(2, 26); g.clock = () => 1000; g.advanceView();
for (const fn of [() => g.enterView('quest_commit'), () => g.setCommit(0, 5),
                  () => g.setCommit(1, 4), () => g.enterView('quest_staging')]) {
  const s = g.snapshot(); fn(); g.addDelta(s);
}
for (const d of g.deltas) delete d._delta_metadata;
const sorted = v => Array.isArray(v) ? v.map(sorted)
  : (v && typeof v === 'object'
      ? Object.fromEntries(Object.keys(v).sort().map(k => [k, sorted(v[k])])) : v);
console.log(JSON.stringify(sorted(g.deltas)));
" > /tmp/js_deltas.json

diff /tmp/py_deltas.json /tmp/js_deltas.json && echo TWINS-AGREE
```

Expected: `TWINS-AGREE`. Any diff is a parity bug — fix the twin that departs
from the reference semantics, not the comparison.

- [x] **Step 4: Browser walkthrough of the three rebase paths**

Serve `docs/` locally, start a game, play into round 1:

- **Plain action.** On `quest_commit`, commit willpower, advance to
  `quest_staging`, tap `Back`, confirm the commits read exactly as left,
  change them, advance again, confirm `quest_staging`'s totals use the new
  commits.
- **Resolve rebase.** Commit less willpower than staging (a fail), advance
  through resolution, note the threat raise. Tap `Back`, confirm threat
  returns to its pre-fail value and `quest_history` loses the entry. Raise
  willpower above staging, advance again, confirm threat did **not** keep the
  old fail's raise and there is exactly one history entry for the round.
- **Placement rebase.** Reach a success resolution with both an active location
  and the quest open, let it split, advance to `travel`. Tap `Back`, confirm
  the split reverts and the budget is restored. Split differently, advance,
  confirm only the second split is reflected.

- [x] **Step 5: Persistence walkthrough**

Play several actions, Save & Quit, resume. Confirm `Back` still works and
steps through the pre-quit actions. Then corrupt the replay store
(`localStorage.setItem("lotr_hud_replay", "{{{")`) and reload: the game must
resume normally with `Back` simply absent.

- [x] **Step 6: Cross-round walkthrough**

Play past a round boundary. Confirm `Back` steps back across `end_round` and
that the threat raise, first-player rotation and round counter all revert
together. On the Log screen, confirm `<<` halts at the boundary.

- [x] **Step 7: Report**

Do **not** deploy to the Presto — device deploys are main-session-only per
`CLAUDE.md`. Report the suite result, the twin-parity diff result, and any
walkthrough step that did not behave as written.

---

## Self-Review

**Spec coverage.** The user's requirement was parity with DragnCards' model and
architecture, as a precise reference. Mapped: the delta engine (`get_delta`,
`delta/2` semantics, `":removed"`, `apply_delta`, `apply_delta_list`) → Task 1;
the wrapper's `deltas`/`replayStep` and the whole method set (`add_delta`,
`step_replay`, `undo`, `redo`, `step_through`, `apply_deltas_until_index`,
`apply_deltas_until_round_change`) → Task 2; the single `process_update` record
point and `Replay`'s two columns → Task 3; the UI affordance the original TODO
card asked for → Task 4; the reference's log-as-jump-target and its
`LogButtons` transport → Task 5. Reference semantics that are load-bearing and
easily lost — MapDiff's maps-only recursion, hence keyed collections; the
truncate-on-divergence rule; metadata carrying the action's log messages — are
each pinned by a named test. Four divergences are stated with the reference line
numbers that motivate them, and D1/D2 each have a test naming them.

Deliberately **not** in scope, and why: replacing `self.log` with the delta list
(the reference has no separate log; ours carries timestamps and round/step tags,
and must not lose entries when a redo future is truncated); the reference's
network delta broadcast (`go_to_replay_step`), which exists to sync remote
clients and has no analogue on a single device; the supporter paywall in
`trim_saved_deltas`, replaced by a plain `MAX_SAVED_DELTAS`.

**Placeholder scan.** Every code step carries runnable code for both twins. Two
places defer to a local helper — the JS id-comparison helper in `screen_play.js`
and `screens_other.js` — and both name the grep to run plus the geometry the
tests assert, so the contract is pinned even though the helper's name is not.
No TBDs, no "similar to Task N", no "add error handling".

Every helper, constant and pen named in the plan was checked against the tree
before it was written down, and several first drafts were wrong: there is no
`_btn` in `screen_play.py` or `screen_log.py` (both build `Button` and draw with
`bevel`/`text_center`); there is no `GAP` constant (`MARGIN` = 8 doubles as the
gap); `pal.btn_alt`/`btn_off`/`ink`/`ink_dim` do not exist (the real pens are
`btn`, `btn_ok`, `tan`, `muted`, `dim`, `card`); `tests/scenes.py`'s `_game()`
takes no arguments and scenes are built through the `_play(view, mutate)` and
`_screen(mod, cls, prep)` factories registered in a `SCENES` dict;
`tests/test_screen_log.py` has only a `_draw()` helper, so Task 5's history
helpers are new. All label widths and button geometry in Tasks 4 and 5 are
`d.measure_text` measurements, not estimates.

**Type consistency.** `get_delta` returns `dict | None` and every consumer
checks `is None` (Task 2's `add_delta`). `apply_delta` mutates and returns the
same dict; `undo`/`redo` therefore snapshot, apply, and `load_snapshot` rather
than assuming in-place effect on the object. `snapshot()`'s keys and
`load_snapshot()`'s reads are enumerated together in Task 2 Step 4 and match
field-for-field, including the three keyed collections. `step_through`'s
`options` keys (`size`, `direction`, `index`) are the reference's and are used
identically in Tasks 2 and 5. `replay_step` is `-1`-based in every twin, every
test, and the serializer. `CTA_SHORT` is keyed by full label text in both twins,
and `_cta_label`/`_ctaLabel` slice at index 6 (`len("Next: ")`) in both.

Two hazards caught and fixed rather than left to bite the implementer:

- **`step` is already an instance field** in both twins (the phase step id,
  e.g. `"3.3"`), so a `step()` method would be shadowed by the constructor's
  assignment. The reference's `step/2` becomes `step_replay`/`stepReplay`. Task
  2 Step 8 flags it, Step 9 renames it with a test asserting the field is still
  a string.
- **The narrowed CTA breaks the DISPLAY width ceiling** the suite already
  guards. This was not visible until the labels were measured: the longest is
  408px and the narrowed button has 360px usable, so six labels overflow. Task 4
  states the four remedies considered, why three fail, and ships the one the
  design system names first ("say less") as a measured `CTA_SHORT` table with
  distinctness and ceiling tests. A plan that had simply said "narrow the CTA"
  would have failed the suite on the implementer's first run.
