# Tablet Client — Milestone 1: Model Changes (Both Twins) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land every model change the tablet client needs in `gamestate.py` and `docs/js/gamestate.js` together — engaged-enemy and staging counts, printed-X auto sources for them, a per-client window policy, a skip offer state, and a storage key prefix for `db.js` — with no UI change on either twin.

**Architecture:** The tablet is a third client over the same `GameState`. Iron rule 1 says the two existing twins stay in lockstep, so every field and function here lands in both languages in the same task and is compared by `tests/test_twin_parity.py`'s node probes. The Presto UI draws none of the new fields; the web twin's screens are untouched. Persistence and delta replay pick the fields up through `to_dict`/`from_dict` and `snapshot`/`load_snapshot`, which list fields by name — so each task adds its field to all four.

**Tech Stack:** Python 3 (host tests, MicroPython on device — pure-data modules, no new imports), ES modules (no build step), pytest, node (driven from pytest, as `test_twin_parity.py` already does).

**Spec:** `docs/superpowers/specs/2026-09-05-tablet-client-design.md` — sections "Model changes (both twins)", "Skips", "Persistence".

## Global Constraints

- Both twins change together in one task; a task is not done until both are green and the parity probe compares them.
- `python3 -m pytest tests/` stays green after every task (2362 tests at the start).
- Generated files (`docs/js/xtargets.js`, `docs/js/viewcopy.js`, `docs/js/phases.js`, `docs/js/icons.js`, `docs/js/metrics.js`) are never hand-edited: change the Python source and run `python3 tools/gen_web_data.py`. `tests/test_viewcopy.py` byte-compares.
- Saves and replay journals written before this milestone must still load: every new field defaults when absent (`.get(k, 0)` / `?? 0`).
- Model modules stay MicroPython-safe: no f-strings with `=`, no dataclasses, no typing imports, no new stdlib imports in `gamestate.py` / `xtargets.py`.
- Log lines that a stepper rewrites use the keyed tally (`cat="tally"`, a `key`) so eight taps stay one row, exactly as `set_staging` does.
- Commit after every task with a conventional message; do not push.
- The window policy default is `"views"`; nothing on the Presto path may observe a behaviour change under the default.

---

### Task 1: Tracked counts on the Python model

**Files:**
- Modify: `gamestate.py` (`class Player`, `GameState.__init__` where `self.staging = 0` is set, the setters near `set_staging`, `snapshot`, `load_snapshot`, `to_dict`, `from_dict`)
- Test: `tests/test_tracking.py` (new)

**Interfaces:**
- Produces: `Player.engaged: int` (default 0); `GameState.staging_enemies: int`, `GameState.staging_locations: int` (default 0); `set_engaged(index, value) -> int`, `set_staging_enemies(value) -> int`, `set_staging_locations(value) -> int` (all clamp at 0, log a keyed tally, return the stored value); `engaged_total() -> int`; `enemies_in_play() -> int` (engaged total + staging enemies).
- Log texts: `"P%d engaged enemies %d"` key `"eng%d"` (index), `"Staging enemies %d"` key `"stgen"`, `"Staging locations %d"` key `"stgloc"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tracking.py
"""The counts the tablet tracks: enemies engaged with each player, enemies
and locations in the staging area. Simple steppers on the tablet; the Presto
draws none of them. They feed skip offers and printed-X targets, and a later
computer-vision pass may fill the same fields."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import GameState


def _live():
    g = GameState(2, 25)
    g.advance_view()          # past setup, into round 1
    return g


def test_counts_default_to_zero():
    g = GameState(2, 25)
    assert [p.engaged for p in g.players] == [0, 0]
    assert g.staging_enemies == 0
    assert g.staging_locations == 0


def test_counts_round_trip_through_a_save():
    g = _live()
    g.set_engaged(1, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(3)
    r = GameState.from_dict(g.to_dict())
    assert r.players[1].engaged == 2
    assert r.players[0].engaged == 0
    assert r.staging_enemies == 1
    assert r.staging_locations == 3


def test_a_save_without_the_fields_still_loads():
    d = GameState(2, 25).to_dict()
    for pd in d["players"]:
        del pd["engaged"]
    del d["staging_enemies"]
    del d["staging_locations"]
    r = GameState.from_dict(d)
    assert r.players[0].engaged == 0
    assert r.staging_enemies == 0
    assert r.staging_locations == 0


def test_setters_clamp_at_zero():
    g = _live()
    assert g.set_engaged(0, -4) == 0
    assert g.set_staging_enemies(-1) == 0
    assert g.set_staging_locations(-1) == 0


def test_a_run_of_stepper_taps_is_one_log_row():
    g = _live()
    n = len(g.log)
    g.set_engaged(0, 1)
    g.set_engaged(0, 2)
    g.set_engaged(0, 3)
    assert g.players[0].engaged == 3
    assert len(g.log) == n + 1, "keyed tally rewrites the row"
    assert g.log[-1]["text"] == "P1 engaged enemies 3"
    g.set_staging_enemies(2)
    assert g.log[-1]["text"] == "Staging enemies 2"
    g.set_staging_locations(1)
    assert g.log[-1]["text"] == "Staging locations 1"


def test_setting_the_same_value_logs_nothing():
    g = _live()
    n = len(g.log)
    g.set_engaged(0, 0)
    g.set_staging_enemies(0)
    assert len(g.log) == n


def test_totals():
    g = _live()
    g.set_engaged(0, 2)
    g.set_engaged(1, 1)
    g.set_staging_enemies(1)
    assert g.engaged_total() == 3
    assert g.enemies_in_play() == 4


def test_the_counts_are_in_the_replay_snapshot():
    g = _live()
    g.set_engaged(1, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(2)
    s = g.snapshot()
    assert s["players"]["1"]["engaged"] == 2
    assert s["staging_enemies"] == 1
    assert s["staging_locations"] == 2


def test_a_snapshot_without_the_counts_loads_as_zero():
    g = _live()
    g.set_engaged(1, 2)
    s = g.snapshot()
    del s["players"]["1"]["engaged"]
    del s["staging_enemies"]
    del s["staging_locations"]
    g.load_snapshot(s)
    assert g.players[1].engaged == 0
    assert g.staging_enemies == 0
    assert g.staging_locations == 0


def test_undo_restores_the_counts():
    g = _live()
    before = g.begin_action()
    g.set_engaged(0, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(1)
    g.add_delta(before)
    g.undo()
    assert g.players[0].engaged == 0
    assert g.staging_enemies == 0
    assert g.staging_locations == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_tracking.py -q`
Expected: FAIL — `AttributeError: 'Player' object has no attribute 'engaged'` and `'GameState' object has no attribute 'set_engaged'`.

- [ ] **Step 3: Add the fields and setters to `gamestate.py`**

In `class Player.__init__`, after `self.commit = 0`:

```python
        self.engaged = 0  # enemies engaged with this player (the tablet's tracker)
```

In `GameState.__init__`, directly after the line `self.staging = 0`:

```python
        # The staging area's card counts. The Presto tracks only its threat;
        # the tablet steps these too, and skip offers + printed-X targets read
        # them (see set_engaged for why they are keyed tallies).
        self.staging_enemies = 0
        self.staging_locations = 0
```

Directly after the `set_staging` method:

```python
    def set_engaged(self, index, value):
        """Enemies engaged with player `index`. A keyed tally, like set_staging:
        a run of stepper taps rewrites one row rather than logging eight."""
        v = max(0, value)
        p = self.players[index]
        if v != p.engaged:
            self.log_event("P%d engaged enemies %d" % (index + 1, v),
                           cat="tally", key="eng%d" % index)
            p.engaged = v
        return p.engaged

    def engaged_total(self):
        return sum(p.engaged for p in self.players)

    def set_staging_enemies(self, value):
        v = max(0, value)
        if v != self.staging_enemies:
            self.log_event("Staging enemies %d" % v, cat="tally", key="stgen")
            self.staging_enemies = v
        return self.staging_enemies

    def set_staging_locations(self, value):
        v = max(0, value)
        if v != self.staging_locations:
            self.log_event("Staging locations %d" % v, cat="tally", key="stgloc")
            self.staging_locations = v
        return self.staging_locations

    def enemies_in_play(self):
        """What the printed X "enemies in play" counts: engaged with anyone,
        plus still in staging."""
        return self.engaged_total() + self.staging_enemies
```

- [ ] **Step 4: Carry the fields through save and replay**

In `snapshot()`, the players entry becomes:

```python
            "players": {str(i): {"threat": p.threat,
                                 "eliminated": p.eliminated,
                                 "commit": p.commit,
                                 "engaged": p.engaged}
                        for i, p in enumerate(self.players)},
```

and after `"staging": self.staging,` add:

```python
            "staging_enemies": self.staging_enemies,
            "staging_locations": self.staging_locations,
```

In `load_snapshot()`, inside the players loop after `p.commit = pd["commit"]`:

```python
            # .get: deltas recorded before the tracker existed carry no key
            p.engaged = pd.get("engaged", 0)
```

and after `self.staging = m["staging"]`:

```python
        self.staging_enemies = m.get("staging_enemies", 0)
        self.staging_locations = m.get("staging_locations", 0)
```

In `to_dict()`, the player dict gains `"engaged": p.engaged,` after `"commit": p.commit,`; after `"staging": self.staging,` add `"staging_enemies": self.staging_enemies,` and `"staging_locations": self.staging_locations,`.

In `from_dict()`, where each player is rebuilt (the line `p.commit = pd.get("commit", 0)` or equivalent), add `p.engaged = pd.get("engaged", 0)`; where `g.staging = d.get("staging", 0)` is set, add `g.staging_enemies = d.get("staging_enemies", 0)` and `g.staging_locations = d.get("staging_locations", 0)`.

- [ ] **Step 5: Run the new tests and the whole suite**

Run: `python3 -m pytest tests/test_tracking.py -q` — Expected: 10 passed.
Run: `python3 -m pytest tests/ -q` — Expected: all green. If `tests/test_gamestate_replay.py::test_snapshot_excludes_transient_and_setup_only_fields` or a snapshot-shape test enumerates keys, extend its expected set rather than weakening it.

- [ ] **Step 6: Commit**

```bash
git add gamestate.py tests/test_tracking.py
git commit -m "feat(model): engaged-enemy and staging card counts (Python twin)"
```

---

### Task 2: Tracked counts on the web twin, with the parity probe

**Files:**
- Modify: `docs/js/gamestate.js` (`class Player`, the `GameState` constructor at `this.staging = 0;`, after `setStaging`, `snapshot()`, `loadSnapshot()`, `toDict()`, `fromDict()`)
- Modify: `tests/test_twin_parity.py` (add a probe and a test)

**Interfaces:**
- Consumes: Task 1's names, camel-cased: `setEngaged(index, value)`, `engagedTotal()`, `setStagingEnemies(value)`, `setStagingLocations(value)`, `enemiesInPlay()`; fields `engaged`, `staging_enemies`, `staging_locations` (snake_case — model fields are JSON-shaped and stay snake_case in JS, as `willpower_detached` does).
- Produces: `_TRACK_PROBE` in the parity test, reusable by later tasks' probes.

- [ ] **Step 1: Write the failing parity test**

Append to `tests/test_twin_parity.py`:

```python
_TRACK_PROBE = """\
import { GameState } from "./gamestate.js";
const g = new GameState(2, 25);
g.advanceView();
const n0 = g.log.length;
g.setEngaged(0, 1); g.setEngaged(0, 2); g.setEngaged(0, 3);
g.setStagingEnemies(2);
g.setStagingLocations(1);
const clamp = g.setEngaged(1, -4);
const saved = GameState.fromDict(g.toDict());
const snap = g.snapshot();
const before = g.beginAction();
g.setEngaged(1, 5);
g.addDelta(before);
g.undo();
console.log(JSON.stringify({
  engaged: g.players.map(p => p.engaged),
  rowsAdded: g.log.length - n0,
  lastTexts: g.log.slice(-3).map(e => e.text),
  clamp,
  savedEngaged: saved.players.map(p => p.engaged),
  savedStaging: [saved.staging_enemies, saved.staging_locations],
  snapEngaged: snap.players["0"].engaged,
  snapStaging: [snap.staging_enemies, snap.staging_locations],
  totals: [g.engagedTotal(), g.enemiesInPlay()],
  undone: g.players[1].engaged,
}));
"""


def _js_facts(probe):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(os.path.join(ROOT, "docs", "js")):
            if f.endswith(".js"):
                shutil.copy(os.path.join(ROOT, "docs", "js", f),
                            os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        path = os.path.join(tmp, "probe.mjs")
        with open(path, "w") as f:
            f.write(probe)
        r = subprocess.run([node, path], cwd=tmp, capture_output=True,
                           text=True)
        assert r.returncode == 0, "web twin failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


def test_tracked_counts_behave_identically_in_both_twins():
    from gamestate import GameState

    js = _js_facts(_TRACK_PROBE)

    g = GameState(2, 25)
    g.advance_view()
    n0 = len(g.log)
    g.set_engaged(0, 1); g.set_engaged(0, 2); g.set_engaged(0, 3)
    g.set_staging_enemies(2)
    g.set_staging_locations(1)
    clamp = g.set_engaged(1, -4)
    saved = GameState.from_dict(g.to_dict())
    snap = g.snapshot()
    before = g.begin_action()
    g.set_engaged(1, 5)
    g.add_delta(before)
    g.undo()

    assert js["engaged"] == [p.engaged for p in g.players]
    assert js["rowsAdded"] == len(g.log) - n0
    assert js["lastTexts"] == [e["text"] for e in g.log[-3:]]
    assert js["clamp"] == clamp
    assert js["savedEngaged"] == [p.engaged for p in saved.players]
    assert js["savedStaging"] == [saved.staging_enemies, saved.staging_locations]
    assert js["snapEngaged"] == snap["players"]["0"]["engaged"]
    assert js["snapStaging"] == [snap["staging_enemies"], snap["staging_locations"]]
    assert js["totals"] == [g.engaged_total(), g.enemies_in_play()]
    assert js["undone"] == g.players[1].engaged
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_twin_parity.py::test_tracked_counts_behave_identically_in_both_twins -q`
Expected: FAIL — node stderr `TypeError: g.setEngaged is not a function`.

- [ ] **Step 3: Mirror the fields and setters in `docs/js/gamestate.js`**

In `class Player`'s constructor after `this.commit = 0;`:

```js
    this.engaged = 0;  // enemies engaged with this player (the tablet's tracker)
```

In the `GameState` constructor directly after `this.staging = 0;`:

```js
    // The staging area's card counts. The Presto tracks only its threat; the
    // tablet steps these too, and skip offers + printed-X targets read them
    // (see setEngaged for why they are keyed tallies).
    this.staging_enemies = 0;
    this.staging_locations = 0;
```

Directly after the `setStaging` method:

```js
  // Enemies engaged with player `index`. A keyed tally, like setStaging: a
  // run of stepper taps rewrites one row rather than logging eight.
  setEngaged(index, value) {
    const v = Math.max(0, value);
    const p = this.players[index];
    if (v !== p.engaged) {
      this.logEvent(`P${index + 1} engaged enemies ${v}`, "tally", `eng${index}`);
      p.engaged = v;
    }
    return p.engaged;
  }

  engagedTotal() { return this.players.reduce((a, p) => a + p.engaged, 0); }

  setStagingEnemies(value) {
    const v = Math.max(0, value);
    if (v !== this.staging_enemies) {
      this.logEvent(`Staging enemies ${v}`, "tally", "stgen");
      this.staging_enemies = v;
    }
    return this.staging_enemies;
  }

  setStagingLocations(value) {
    const v = Math.max(0, value);
    if (v !== this.staging_locations) {
      this.logEvent(`Staging locations ${v}`, "tally", "stgloc");
      this.staging_locations = v;
    }
    return this.staging_locations;
  }

  // What the printed X "enemies in play" counts: engaged with anyone, plus
  // still in staging.
  enemiesInPlay() { return this.engagedTotal() + this.staging_enemies; }
```

- [ ] **Step 4: Carry the fields through save and replay**

`snapshot()` players entry:

```js
      players: Object.fromEntries(this.players.map((p, i) => [String(i), {
        threat: p.threat, eliminated: p.eliminated,
        commit: p.commit, engaged: p.engaged }])),
```

and after `staging: this.staging,` add `staging_enemies: this.staging_enemies,` and `staging_locations: this.staging_locations,`.

`loadSnapshot()`: inside the players loop after `p.commit = pd.commit;` add `p.engaged = pd.engaged ?? 0;` (deltas recorded before the tracker carry no key). After `this.staging = m.staging;` add `this.staging_enemies = m.staging_enemies ?? 0;` and `this.staging_locations = m.staging_locations ?? 0;`.

`toDict()`: the player object gains `engaged: p.engaged` after `commit: p.commit`; after `staging: this.staging,` add `staging_enemies: this.staging_enemies, staging_locations: this.staging_locations,`.

`fromDict()`: after `p.commit = pd.commit ?? 0;` add `p.engaged = pd.engaged ?? 0;`; after `g.staging = d.staging ?? 0;` add `g.staging_enemies = d.staging_enemies ?? 0;` and `g.staging_locations = d.staging_locations ?? 0;`.

- [ ] **Step 5: Run the parity test and the whole suite**

Run: `python3 -m pytest tests/test_twin_parity.py -q` — Expected: all passed.
Run: `python3 -m pytest tests/ -q` — Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add docs/js/gamestate.js tests/test_twin_parity.py
git commit -m "feat(model): engaged-enemy and staging card counts (web twin, parity probe)"
```

---

### Task 3: Printed-X auto sources for the new counts, and one context helper

**Files:**
- Modify: `xtargets.py` (constants, `TARGETS` entries for `enemies_in_play` and `locations_in_staging`, `resolve`)
- Modify: `tools/gen_web_data.py` (the emitted `resolve` string, lines ~96–113)
- Regenerate: `docs/js/xtargets.js` (`python3 tools/gen_web_data.py`)
- Modify: `gamestate.py` (add `x_context()`; update the `xtargets.resolve(` call near line 1174), `docs/js/gamestate.js` (add `xContext()`; update the `resolveX(` call near line 977)
- Modify: `ui/modals.py:464` and `ui/modals.py:2034`; `docs/js/screens.js:1372` and `docs/js/screens.js:1994`
- Test: `tests/test_xtargets.py`, `tests/test_tracking.py`

**Interfaces:**
- Produces: `xtargets.AUTO_ENEMIES = "enemies"`, `xtargets.AUTO_STAGING_LOCATIONS = "staging_locations"`; `xtargets.resolve(spec, count=None, players=1, stage=1, highest_threat=0, enemies=0, staging_locations=0)`; JS `resolve(spec, { count, players, stage, highestThreat, enemies, stagingLocations })`; `GameState.x_context() -> dict` with exactly the keyword names `resolve` takes; JS `xContext()` with the option names the JS `resolve` takes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_xtargets.py`:

```python
def test_enemies_and_staging_locations_are_answered_by_the_tracker():
    # The two counts the tablet tracks. Like the other auto targets, a stale
    # supplied count must not override the tracked value.
    assert X.auto_for("enemies_in_play") == X.AUTO_ENEMIES
    assert X.auto_for("locations_in_staging") == X.AUTO_STAGING_LOCATIONS
    assert X.resolve({"target": "enemies_in_play"}, count=99, enemies=3) == 3
    assert X.resolve({"target": "enemies_in_play", "mul": 2, "add": 1},
                     count=99, enemies=3) == 7
    assert X.resolve({"target": "locations_in_staging"}, count=99,
                     staging_locations=2) == 2


def test_the_auto_set_is_exactly_the_five_tracked_values():
    auto = sorted(k for k, t in X.TARGETS.items() if t["auto"])
    assert auto == ["enemies_in_play", "highest_threat", "locations_in_staging",
                    "players", "stage_number"]
```

Append to `tests/test_tracking.py`:

```python
def test_x_context_feeds_resolve_with_the_tracked_values():
    import xtargets
    g = _live()
    g.set_engaged(0, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(2)
    ctx = g.x_context()
    assert ctx == {"players": 2, "stage": g.quest["stage_n"],
                   "highest_threat": max(p.threat for p in g.players),
                   "enemies": 3, "staging_locations": 2}
    assert xtargets.resolve({"target": "enemies_in_play"}, **ctx) == 3
    assert xtargets.resolve({"target": "players", "mul": 4}, count=None, **ctx) == 8
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_xtargets.py tests/test_tracking.py -q`
Expected: FAIL — `AttributeError: module 'xtargets' has no attribute 'AUTO_ENEMIES'` and `'GameState' object has no attribute 'x_context'`. If an existing test asserts the auto set is exactly three, it fails here too; Step 3 updates it.

- [ ] **Step 3: Extend `xtargets.py`**

After `AUTO_HIGHEST_THREAT = "highest_threat"`:

```python
# Two more since the tablet's tracker: enemies engaged with anyone plus enemies
# in staging, and locations in staging. The Presto never sets them, so on the
# device these resolve from zero - the same as before, where the player
# supplied the count; the sheet's stepper still lets them.
AUTO_ENEMIES = "enemies"
AUTO_STAGING_LOCATIONS = "staging_locations"
```

Change the two table entries:

```python
    "enemies_in_play": {"label": "Enemies in play", "auto": AUTO_ENEMIES},
```

```python
    "locations_in_staging": {"label": "Locations in staging",
                             "auto": AUTO_STAGING_LOCATIONS},
```

Replace `resolve`:

```python
def resolve(spec, count=None, players=1, stage=1, highest_threat=0,
            enemies=0, staging_locations=0):
    """The number to put on screen, or None when the player has not supplied a
    count yet.

    `spec` is a card's coded X: {"target", "mul", "add"}. An auto target
    ignores `count` entirely and recomputes from the tracked value, which is
    the whole point of tagging those separately - "X is 4 per player" must
    follow the player count without anyone touching a stepper. GameState's
    x_context() supplies every tracked value by these keyword names.
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
    if auto == AUTO_ENEMIES:
        return value_of(enemies, mul, add)
    if auto == AUTO_STAGING_LOCATIONS:
        return value_of(staging_locations, mul, add)
    if count is None:
        return None
    return value_of(count, mul, add)
```

Update the module docstring's "Only three of the 26 have one" sentence to say five, naming the two new ones. If `tests/test_xtargets.py` has a test asserting exactly three auto targets, replace its expected list with the five above (the new test already states it).

- [ ] **Step 4: Update the emitted JS `resolve` in `tools/gen_web_data.py` and regenerate**

In the `out.append("""…""")` block for xtargets, replace the `resolve` function with:

```js
// The number to put on screen, or null when the player has not supplied a
// count yet. An auto target ignores `count` and recomputes from the tracked
// value - that is the whole point of tagging those separately: "X is 4 per
// player" must follow the player count without anyone touching a stepper.
// GameState.xContext() supplies every tracked value by these option names.
export function resolve(spec, { count = null, players = 1, stage = 1,
                                highestThreat = 0, enemies = 0,
                                stagingLocations = 0 } = {}) {
  if (!spec) return null;
  const mul = spec.mul ?? 1, add = spec.add ?? 0;
  switch (autoFor(spec.target)) {
    case AUTO_PLAYERS: return valueOf(players, mul, add);
    case AUTO_STAGE: return valueOf(stage, mul, add);
    case AUTO_HIGHEST_THREAT: return valueOf(highestThreat, mul, add);
    case AUTO_ENEMIES: return valueOf(enemies, mul, add);
    case AUTO_STAGING_LOCATIONS: return valueOf(stagingLocations, mul, add);
  }
  if (count === null) return null;
  return valueOf(count, mul, add);
}
```

Run: `python3 tools/gen_web_data.py` — `docs/js/xtargets.js` now exports `AUTO_ENEMIES`, `AUTO_STAGING_LOCATIONS` (the generator emits every `AUTO_` string) and the new `resolve`.

- [ ] **Step 5: Add the context helpers and route every call site through them**

`gamestate.py`, next to `enemies_in_play`:

```python
    def x_context(self):
        """Every tracked value a printed X can resolve from, by the keyword
        names xtargets.resolve takes. One place, so a new auto target is a
        change here and in xtargets, never at a call site."""
        return {
            "players": len(self.players),
            "stage": self.quest.get("stage_n", 1),
            "highest_threat": max([p.threat for p in self.players] or [0]),
            "enemies": self.enemies_in_play(),
            "staging_locations": self.staging_locations,
        }
```

`docs/js/gamestate.js`, next to `enemiesInPlay`:

```js
  // Every tracked value a printed X can resolve from, by the option names
  // xtargets.resolve takes. One place, so a new auto target is a change here
  // and in xtargets, never at a call site.
  xContext() {
    return {
      players: this.players.length,
      stage: this.quest.stage_n ?? 1,
      highestThreat: Math.max(0, ...this.players.map((p) => p.threat)),
      enemies: this.enemiesInPlay(),
      stagingLocations: this.staging_locations,
    };
  }
```

Then replace the argument lists at the six call sites:

`gamestate.py` (~line 1174):
```python
        auto = xtargets.resolve(loc.get("threatX"), **self.x_context())
```

`ui/modals.py` (~line 464):
```python
        return xtargets.resolve(self.threat_x, count=self.threat_count,
                                **g.x_context())
```

`ui/modals.py` (~line 2034):
```python
        return xtargets.resolve(g.quest.get("x"), count=g.quest.get("xCount"),
                                **g.x_context())
```

`docs/js/gamestate.js` (~line 977):
```js
    const auto = resolveX(loc.threatX, this.xContext());
```

`docs/js/screens.js` (~line 1372):
```js
    return xtargets.resolve(g.quest.x, { count: g.quest.xCount ?? null, ...g.xContext() });
```

`docs/js/screens.js` (~line 1994):
```js
    return xtargets.resolve(this.threatX, { count: this.threatCount, ...this.game.xContext() });
```

Confirm nothing else calls `resolve(` with the old argument list: `grep -rn "resolve(" ui/ docs/js/ gamestate.py | grep -v "Promise.resolve\|xtargets.js"` shows only the six sites above.

- [ ] **Step 6: Run the tests and the whole suite**

Run: `python3 -m pytest tests/test_xtargets.py tests/test_tracking.py tests/test_viewcopy.py -q` — Expected: passed (viewcopy's regen check proves `docs/js/xtargets.js` is fresh).
Run: `python3 -m pytest tests/ -q` — Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add xtargets.py tools/gen_web_data.py docs/js/xtargets.js gamestate.py docs/js/gamestate.js ui/modals.py docs/js/screens.js tests/test_xtargets.py tests/test_tracking.py
git commit -m "feat(xtargets): enemies and staging locations resolve from the tracker; one x_context() for every call site"
```

---

### Task 4: The window policy (both twins)

**Files:**
- Modify: `gamestate.py` (module level near `window_after`; `next_view`, `prev_view`, `skips_from`, `skip_to`)
- Modify: `docs/js/gamestate.js` (module level near `windowAfter`; `nextView`, `prevView`, `skipsFrom`, `skipTo`)
- Create: `tests/conftest.py` (autouse fixture resetting the policy)
- Create: `tests/test_window_policy.py`
- Modify: `tests/test_twin_parity.py` (parametrize the skip probe by policy)

**Interfaces:**
- Produces: `WINDOW_POLICY_VIEWS = "views"`, `WINDOW_POLICY_BANDS = "bands"`, `set_window_policy(policy)`, `window_policy()`, `flow_views() -> list` (Python); `setWindowPolicy(policy)`, `windowPolicy()`, `flowViews()` (JS). Under `"bands"`, `next_view`/`prev_view` step over `aw_` views, `skips_from(view)` offers each skip on the phase view of its `from` entries, and `skip_to` logs the passed *flow* views.
- Unchanged under `"views"`: every existing test.

- [ ] **Step 1: Write the failing tests**

`tests/conftest.py`:

```python
"""Shared fixtures. The window policy is module state in gamestate; a test
that flips it must not leak into the next one."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _reset_window_policy():
    import gamestate
    yield
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_VIEWS)
```

`tests/test_window_policy.py`:

```python
"""How a step's action window reaches the player.

"views": the aw_ screens are in the flow - the Presto, where a 480px screen has
no room for a band under the framework text. "bands": the window is drawn on
its step's own view and navigation steps over the aw_ entries - the tablet,
where it is the single biggest tap saving (eight views a round become bands).
Module state, set once by the client at boot; the model is otherwise the same.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gamestate
from gamestate import (GameState, VIEW_ORDER, WINDOW_POLICY_BANDS,
                       WINDOW_POLICY_VIEWS, flow_views, is_action_window,
                       is_window_view, set_window_policy, skips_from,
                       window_policy)


def _round1():
    g = GameState(2, 25)
    g.advance_view()
    return g


def test_default_policy_is_views():
    assert window_policy() == WINDOW_POLICY_VIEWS
    assert flow_views() == VIEW_ORDER


def test_unknown_policy_is_refused():
    with pytest.raises(ValueError):
        set_window_policy("sometimes")


def test_bands_drop_every_window_view_from_the_flow():
    set_window_policy(WINDOW_POLICY_BANDS)
    assert not [v for v in flow_views() if is_window_view(v)]
    assert flow_views() == [v for v in VIEW_ORDER if not is_window_view(v)]


def test_bands_walk_the_round_without_landing_on_a_window():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    seen = [g.view]
    for _ in range(20):
        if g.view == "round_end":
            break
        g.advance_view()
        seen.append(g.view)
    assert seen == ["resource", "planning", "quest_commit", "quest_staging",
                    "travel", "enc_optional", "enc_checks", "combat_shadow",
                    "combat_enemy", "combat_player", "refresh", "round_end"]


def test_bands_step_back_over_windows_too():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("travel")
    assert g.prev_view() == "quest_staging"   # not the resolution window
    g.enter_view("combat_shadow")
    assert g.prev_view() == "enc_checks"
    g.enter_view("resource")
    assert g.prev_view() is None              # a closed round is a floor


def test_bands_keep_the_resolution_view_reachable_after_a_resolve():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("quest_resolution")
    assert g.prev_view() == "quest_staging"
    assert g.next_view() == "travel"


def test_the_skip_moves_to_the_phase_view_under_bands():
    set_window_policy(WINDOW_POLICY_BANDS)
    offering = [v for v in flow_views() if skips_from(v)]
    assert offering == ["enc_checks"]
    # and that view IS an action window: the player stands on the window the
    # skip would otherwise have eaten
    assert is_action_window("enc_checks")


def test_the_skip_lands_and_logs_the_same_under_bands():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("enc_checks")
    assert g.skip_to("combat_empty") == "combat_player"
    assert g.view == "combat_player"
    entry = " ".join(str(e.get("text", "")) for e in g.log[-2:])
    assert "Skipped combat_shadow, combat_enemy" in entry
    assert "aw_" not in entry


def test_views_policy_is_untouched():
    g = _round1()
    assert g.next_view() == "aw_resource"
    assert skips_from("aw_enc_checks")
    assert not skips_from("enc_checks")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_window_policy.py -q`
Expected: FAIL — `ImportError: cannot import name 'WINDOW_POLICY_BANDS'`.

- [ ] **Step 3: Add the policy to `gamestate.py`**

Directly after the `window_after` function:

```python
# -- window policy ---------------------------------------------------------
# How a step's action window reaches the player.
#   "views": the aw_ screens are in the flow. The Presto: a 480px screen has
#            no room for a band under the framework text.
#   "bands": the window is drawn on its step's own view, and next_view() /
#            prev_view() step over the aw_ entries. The tablet.
# Module state, set once by the client at boot. Everything else - the step
# ids, is_action_window, last_window_before, the skip landing - is identical
# under both, which is what keeps the skip's safety rule one rule.
WINDOW_POLICY_VIEWS = "views"
WINDOW_POLICY_BANDS = "bands"
_window_policy = [WINDOW_POLICY_VIEWS]


def set_window_policy(policy):
    if policy not in (WINDOW_POLICY_VIEWS, WINDOW_POLICY_BANDS):
        raise ValueError("unknown window policy: %r" % (policy,))
    _window_policy[0] = policy


def window_policy():
    return _window_policy[0]


def flow_views():
    """VIEW_ORDER as navigation sees it under the current policy."""
    if _window_policy[0] == WINDOW_POLICY_BANDS:
        return [v for v in VIEW_ORDER if not is_window_view(v)]
    return VIEW_ORDER
```

`skips_from` becomes:

```python
def skips_from(view):
    """The contextual skips offered on `view` - usually none. Under "bands" a
    skip declared from a window is offered on that window's phase view: the
    window is on the view, so the player is standing on it."""
    bands = _window_policy[0] == WINDOW_POLICY_BANDS
    out = []
    for s in SKIPS:
        origins = [phase_view_of(f) if bands else f for f in s["from"]]
        if view in origins:
            out.append(s)
    return tuple(out)
```

In `next_view`, replace the `VIEW_ORDER` walk:

```python
        order = flow_views()
        i = order.index(self.view)
        nxt = order[(i + 1) % len(order)]
        # Resolution is entered only by a successful resolve, so whichever
        # view precedes it in the flow hands straight to travel - the staging
        # window under "views", the staging view itself under "bands".
        if nxt == "quest_resolution":
            nxt = "travel"
        if self.view == "planning" and self.sailing:
            nxt = "quest_sailing"
        return nxt
```

(delete the old `if self.view == "aw_quest_staging": nxt = "travel"` line; the generic rule covers it.)

In `prev_view`, replace the final two lines:

```python
        order = flow_views()
        if v not in order:
            return None
        i = order.index(v)
        # A closed round is a hard floor: end_round() has already banked its
        # stats, bumped the counter and re-derived the willpower total.
        if i <= 0:
            return None
        prev = order[i - 1]
        # Under "bands" the resolution view sits between staging and travel in
        # the flow, but it is only entered by a resolve; going back from travel
        # without one lands on staging. Bands only: under "views" Back from
        # travel reaches the resolution window first, exactly as before.
        if (_window_policy[0] == WINDOW_POLICY_BANDS
                and prev == "quest_resolution" and not self.quest_resolved):
            return "quest_staging"
        return prev
```

In `skip_to`, replace the three lines that compute `i`, `j` and `passed`:

```python
        order = flow_views()
        i, j = order.index(self.view), order.index(landing)
        if j <= i:
            return None
        passed = order[i + 1:j]
```

- [ ] **Step 4: Run the Python tests**

Run: `python3 -m pytest tests/test_window_policy.py tests/test_phase_skip.py tests/test_flow.py -q` — Expected: passed.
Run: `python3 -m pytest tests/ -q` — Expected: all green (the `"views"` default must change nothing).

- [ ] **Step 5: Mirror in `docs/js/gamestate.js`**

Directly after `windowAfter`:

```js
// -- window policy -----------------------------------------------------------
// How a step's action window reaches the player.
//   "views": the aw_ screens are in the flow. The Presto and its twin.
//   "bands": the window is drawn on its step's own view, and nextView() /
//            prevView() step over the aw_ entries. The tablet.
// Module state, set once by the client at boot. Everything else - the step
// ids, isActionWindow, lastWindowBefore, the skip landing - is identical under
// both, which is what keeps the skip's safety rule one rule.
export const WINDOW_POLICY_VIEWS = "views";
export const WINDOW_POLICY_BANDS = "bands";
let _windowPolicy = WINDOW_POLICY_VIEWS;
export function setWindowPolicy(policy) {
  if (policy !== WINDOW_POLICY_VIEWS && policy !== WINDOW_POLICY_BANDS) {
    throw new Error(`unknown window policy: ${policy}`);
  }
  _windowPolicy = policy;
}
export const windowPolicy = () => _windowPolicy;
// VIEW_ORDER as navigation sees it under the current policy.
export const flowViews = () =>
  _windowPolicy === WINDOW_POLICY_BANDS ? VIEW_ORDER.filter(v => !isWindowView(v)) : VIEW_ORDER;
```

`skipsFrom`:

```js
// The contextual skips offered on `view` - usually none. Under "bands" a skip
// declared from a window is offered on that window's phase view: the window
// is on the view, so the player is standing on it.
export const skipsFrom = view => {
  const bands = _windowPolicy === WINDOW_POLICY_BANDS;
  return SKIPS.filter(s => s.from.map(f => (bands ? phaseViewOf(f) : f)).includes(view));
};
```

`nextView`:

```js
  nextView() {
    if (this.view === "quest_sailing") return "quest_commit";
    const order = flowViews();
    const i = order.indexOf(this.view);
    let nxt = order[(i + 1) % order.length];
    // Resolution is entered only by a successful resolve, so whichever view
    // precedes it in the flow hands straight to travel - the staging window
    // under "views", the staging view itself under "bands".
    if (nxt === "quest_resolution") nxt = "travel";
    if (this.view === "planning" && this.sailing) nxt = "quest_sailing";
    return nxt;
  }
```

`prevView`'s last two lines become:

```js
    const order = flowViews();
    if (!order.includes(v)) return null;
    const i = order.indexOf(v);
    // A closed round is a hard floor: endRound() has already banked its stats,
    // bumped the counter and re-derived the willpower total.
    if (i <= 0) return null;
    const prev = order[i - 1];
    // Under "bands" the resolution view sits between staging and travel in the
    // flow, but it is only entered by a resolve; going back from travel
    // without one lands on staging. Bands only: under "views" Back from travel
    // reaches the resolution window first, exactly as before.
    if (_windowPolicy === WINDOW_POLICY_BANDS
        && prev === "quest_resolution" && !this.quest_resolved) return "quest_staging";
    return prev;
```

`skipTo`'s index lines:

```js
    const order = flowViews();
    const i = order.indexOf(this.view), j = order.indexOf(landing);
    if (j <= i) return null;
    const passed = order.slice(i + 1, j);
```

- [ ] **Step 6: Parametrize the parity probe by policy**

In `tests/test_twin_parity.py`, change `_SKIP_PROBE` to take the policy and the origin, and compare under both:

```python
_SKIP_PROBE = """\
import { skipsFrom, lastWindowBefore, isActionWindow, VIEW_ORDER, SKIPS,
         GameState, setWindowPolicy, flowViews } from "./gamestate.js";
setWindowPolicy(%(policy)r);
const g = new GameState();
g.advanceView();
g.enterView(%(origin)r);
const landed = g.skipTo("combat_empty");
const walk = new GameState(); walk.advanceView();
const seen = [walk.view];
for (let n = 0; n < 20 && walk.view !== "round_end"; n++) { walk.advanceView(); seen.push(walk.view); }
console.log(JSON.stringify({
  offeredOn: flowViews().filter(v => skipsFrom(v).length).sort(),
  landing: lastWindowBefore("refresh"),
  landingIsWindow: isActionWindow(lastWindowBefore("refresh")),
  skipIds: SKIPS.map(s => s.id).sort(),
  landedOn: landed,
  view: g.view,
  step: g.step,
  skipText: g.log.filter(e => String(e.text || "").includes("Skipped")).map(e => e.text),
  walk: seen,
}));
"""


@pytest.mark.parametrize("policy,origin", [("views", "aw_enc_checks"),
                                           ("bands", "enc_checks")])
def test_phase_skip_behaves_identically_in_both_twins(policy, origin):
    import gamestate
    from gamestate import (GameState, SKIPS, flow_views, is_action_window,
                           last_window_before, skips_from)

    js = _js_facts(_SKIP_PROBE % {"policy": policy, "origin": origin})
    gamestate.set_window_policy(policy)

    assert js["offeredOn"] == sorted(v for v in flow_views() if skips_from(v))
    assert js["skipIds"] == sorted(s["id"] for s in SKIPS)
    assert js["landing"] == last_window_before("refresh")
    assert js["landingIsWindow"] is is_action_window(last_window_before("refresh"))

    g = GameState()
    g.advance_view()
    g.enter_view(origin)
    landed = g.skip_to("combat_empty")
    assert js["landedOn"] == landed
    assert js["view"] == g.view
    assert js["step"] == g.step
    assert js["skipText"] == [e["text"] for e in g.log if "Skipped" in str(e.get("text", ""))]

    walk = GameState()
    walk.advance_view()
    seen = [walk.view]
    for _ in range(20):
        if walk.view == "round_end":
            break
        walk.advance_view()
        seen.append(walk.view)
    assert js["walk"] == seen
```

Delete the old `_js_skip_facts` helper (the generic `_js_facts` from Task 2 replaces it).

- [ ] **Step 7: Run the parity tests and the whole suite**

Run: `python3 -m pytest tests/test_twin_parity.py tests/test_window_policy.py -q` — Expected: passed, both policies.
Run: `python3 -m pytest tests/ -q` — Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add gamestate.py docs/js/gamestate.js tests/conftest.py tests/test_window_policy.py tests/test_twin_parity.py
git commit -m "feat(flow): a per-client window policy; the tablet folds action windows into their step's view"
```

---

### Task 5: The skip offer state (both twins)

**Files:**
- Modify: `gamestate.py` (after `skip_to`), `docs/js/gamestate.js` (after `skipTo`)
- Test: `tests/test_window_policy.py`, `tests/test_twin_parity.py`

**Interfaces:**
- Produces: `GameState.skip_offer() -> dict | None` = `{"skip": <SKIPS entry>, "promoted": bool, "engaged": int, "staging_enemies": int}`; JS `skipOffer()` → `{skip, promoted, engaged, staging_enemies}` or `null`. `promoted` is true when the tracked counts say the claim holds (engaged total 0 and staging enemies 0). The player decides either way; the tablet draws a promoted offer in amber and a demoted one plain, and the confirm names the counts.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_window_policy.py`:

```python
def test_no_offer_where_no_skip_is_declared():
    g = _round1()
    assert g.skip_offer() is None


def test_offer_is_promoted_when_the_tracker_agrees_with_the_claim():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("enc_checks")
    o = g.skip_offer()
    assert o["skip"]["id"] == "combat_empty"
    assert o["promoted"] is True
    assert (o["engaged"], o["staging_enemies"]) == (0, 0)


def test_offer_is_demoted_but_still_there_when_enemies_are_tracked():
    """A tracker, not a referee: the counts inform the button, they never
    remove it. The player may know something the tracker does not."""
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("enc_checks")
    g.set_engaged(1, 2)
    g.set_staging_enemies(1)
    o = g.skip_offer()
    assert o["promoted"] is False
    assert (o["engaged"], o["staging_enemies"]) == (2, 1)
    assert g.skip_to("combat_empty") == "combat_player"


def test_offer_works_under_the_views_policy_too():
    g = _round1()
    g.enter_view("aw_enc_checks")
    assert g.skip_offer()["promoted"] is True
```

Append to `_SKIP_PROBE` in `tests/test_twin_parity.py` (inside the JSON object, before `walk`):

```js
  offer: (() => { const o = g.skipOffer(); return o && { id: o.skip.id, promoted: o.promoted, engaged: o.engaged, staging_enemies: o.staging_enemies }; })(),
  offerBeforeSkip: (() => { const h = new GameState(); h.advanceView(); h.enterView(%(origin)r); h.setEngaged(0, 1); const o = h.skipOffer(); return o && { promoted: o.promoted, engaged: o.engaged }; })(),
```

and in the test, after the `skipText` assertion:

```python
    assert js["offer"] is None                 # the skip was already taken
    h = GameState()
    h.advance_view()
    h.enter_view(origin)
    h.set_engaged(0, 1)
    o = h.skip_offer()
    assert js["offerBeforeSkip"] == {"promoted": o["promoted"], "engaged": o["engaged"]}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_window_policy.py -q` — Expected: FAIL, `AttributeError: 'GameState' object has no attribute 'skip_offer'`.

- [ ] **Step 3: Implement both twins**

`gamestate.py`, after `skip_to`:

```python
    def skip_offer(self):
        """The skip this view offers, with the tracker's opinion of it, or None.

        `promoted` means the tracked counts say the claim holds. The player
        decides either way - a tracker, not a referee - so the counts inform
        the button and never remove it: the tablet draws a promoted offer in
        amber and a demoted one plain, and the confirm names the counts.
        """
        offered = skips_from(self.view)
        if not offered:
            return None
        engaged = self.engaged_total()
        return {"skip": offered[0],
                "promoted": engaged == 0 and self.staging_enemies == 0,
                "engaged": engaged,
                "staging_enemies": self.staging_enemies}
```

`docs/js/gamestate.js`, after `skipTo`:

```js
  // The skip this view offers, with the tracker's opinion of it, or null.
  // `promoted` means the tracked counts say the claim holds. The player
  // decides either way - a tracker, not a referee - so the counts inform the
  // button and never remove it: the tablet draws a promoted offer in amber
  // and a demoted one plain, and the confirm names the counts.
  skipOffer() {
    const offered = skipsFrom(this.view);
    if (!offered.length) return null;
    const engaged = this.engagedTotal();
    return { skip: offered[0],
             promoted: engaged === 0 && this.staging_enemies === 0,
             engaged, staging_enemies: this.staging_enemies };
  }
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `python3 -m pytest tests/test_window_policy.py tests/test_twin_parity.py -q` — Expected: passed.
Run: `python3 -m pytest tests/ -q` — Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add gamestate.py docs/js/gamestate.js tests/test_window_policy.py tests/test_twin_parity.py
git commit -m "feat(flow): skip offers carry the tracker's opinion; promoted or demoted, never removed"
```

---

### Task 6: A storage key prefix for `db.js`, and the no-stray-IO scope

**Files:**
- Modify: `docs/js/db.js` (module constants, `Session`, `History`, `DataClient`)
- Modify: `tests/test_no_stray_io.py` (`test_the_web_twin_keeps_localstorage_in_its_client_too`)
- Create: `tests/test_db_prefix.py`

**Interfaces:**
- Produces: `storageKeys(prefix = "lotr-hud-") -> {state, prefs, log, replay, replayJournal, history, rollup}`; `new Session({ prefix })`, `new History({ prefix })`, `new DataClient({ prefix })` — all default to `"lotr-hud-"`, so `main.js` is unchanged. The tablet passes `"lotr-tablet-"`. The exported `STATE_KEY` … `ROLLUP_KEY` constants keep their values (they equal `storageKeys()`'s fields).

- [ ] **Step 1: Write the failing test**

`tests/test_db_prefix.py`:

```python
"""Two clients share one origin (docs/ and docs/tablet/ on the same Pages
site), so they must not share localStorage keys - a tablet save would
otherwise clobber the web twin's. The prefix is the only thing that keeps
them apart, so it is tested under node with a localStorage shim."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_PROBE = """\
const store = new Map();
globalThis.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => { store.set(k, String(v)); },
  removeItem: k => { store.delete(k); },
  key: i => [...store.keys()][i] ?? null,
  get length() { return store.size; },
};
const { Session, History, DataClient, storageKeys, STATE_KEY } = await import("./db.js");
const { GameState } = await import("./gamestate.js");
const hud = new Session();
const tab = new Session({ prefix: "lotr-tablet-" });
const g1 = new GameState(2, 25); g1.advanceView();
const g2 = new GameState(3, 30); g2.advanceView();
hud.saveState(g1);
tab.saveState(g2);
hud.saveLog(g1);
tab.saveLog(g2);
const hist = new History({ prefix: "lotr-tablet-" });
hist.append({ result: "victory", round: 9 });
const client = new DataClient({ prefix: "lotr-tablet-" });
client.savePrefs({ brightness: 50 });
console.log(JSON.stringify({
  keys: [...store.keys()].sort(),
  hudPlayers: hud.loadState().state.players.length,
  tabPlayers: tab.loadState().state.players.length,
  hudExists: hud.exists(), tabExists: tab.exists(),
  defaults: storageKeys(),
  legacyState: STATE_KEY,
  prefs: client.loadPrefs().brightness,
  cleared: (() => { tab.clear(); return [...store.keys()].sort(); })(),
}));
"""


def _run():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(os.path.join(ROOT, "docs", "js")):
            if f.endswith(".js"):
                shutil.copy(os.path.join(ROOT, "docs", "js", f), os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write(_PROBE)
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)


def test_two_prefixes_keep_two_games_apart():
    js = _run()
    assert "lotr-hud-state" in js["keys"]
    assert "lotr-tablet-state" in js["keys"]
    assert js["hudPlayers"] == 2
    assert js["tabPlayers"] == 3
    assert js["hudExists"] and js["tabExists"]


def test_the_default_prefix_is_the_web_twins_existing_keys():
    js = _run()
    assert js["defaults"]["state"] == "lotr-hud-state"
    assert js["defaults"]["replayJournal"] == "lotr-hud-replay-journal"
    assert js["defaults"]["rollup"] == "lotr-hud-stats"
    assert js["legacyState"] == "lotr-hud-state"


def test_history_and_prefs_take_the_prefix_too():
    js = _run()
    assert "lotr-tablet-history" in js["keys"]
    assert "lotr-tablet-stats" in js["keys"]
    assert "lotr-tablet-prefs" in js["keys"]
    assert js["prefs"] == 50


def test_clearing_one_client_leaves_the_other():
    js = _run()
    assert "lotr-hud-state" in js["cleared"]
    assert "lotr-tablet-state" not in js["cleared"]
    assert "lotr-tablet-log" not in js["cleared"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_db_prefix.py -q` — Expected: FAIL, node stderr names `storageKeys` as not exported.

- [ ] **Step 3: Thread the prefix through `docs/js/db.js`**

Replace the seven key constants with:

```js
// Two clients share this origin (docs/ and docs/tablet/), so every key is
// prefixed. The default is the web twin's historical prefix, so its saves
// keep loading; the tablet passes "lotr-tablet-".
export const DEFAULT_PREFIX = "lotr-hud-";
export function storageKeys(prefix = DEFAULT_PREFIX) {
  return {
    state: prefix + "state", prefs: prefix + "prefs", log: prefix + "log",
    replay: prefix + "replay",                   // legacy
    replayJournal: prefix + "replay-journal",
    history: prefix + "history", rollup: prefix + "stats",
  };
}
const _K = storageKeys();
export const STATE_KEY = _K.state;
export const PREFS_KEY = _K.prefs;
export const LOG_KEY = _K.log;
export const REPLAY_KEY = _K.replay;
export const REPLAY_JOURNAL_KEY = _K.replayJournal;
export const HISTORY_KEY = _K.history;
export const ROLLUP_KEY = _K.rollup;
```

`Session`: constructor becomes `constructor({ prefix = DEFAULT_PREFIX } = {}) { this.keys = storageKeys(prefix); … }` (keep the existing fields). Inside its methods replace `STATE_KEY` → `this.keys.state`, `LOG_KEY` → `this.keys.log`, `REPLAY_KEY` → `this.keys.replay`, `REPLAY_JOURNAL_KEY` → `this.keys.replayJournal` (`saveState`, `saveLog`, `saveReplay`, `loadState`, `loadLog`, `loadReplay`, `exists`, `clear`, and `forceState`/`tick` if they name a key).

`History`: constructor becomes `constructor({ prefix = DEFAULT_PREFIX } = {}) { this.keys = storageKeys(prefix); }`; replace `HISTORY_KEY` → `this.keys.history`, `ROLLUP_KEY` → `this.keys.rollup` in `append`, `scan`, `rollup`, `_bumpRollup`, `clear`.

`DataClient`: constructor becomes

```js
  constructor({ prefix = DEFAULT_PREFIX } = {}) {
    this._index = null;
    this._icons = null;
    this._tips = null;
    this._sideQuests = null;
    this._bundles = {};
    this.keys = storageKeys(prefix);
    this.session = new Session({ prefix });
    this.history = new History({ prefix });
  }
```

and `loadPrefs`/`savePrefs` use `this.keys.prefs` instead of `PREFS_KEY`.

Check: `grep -n "_KEY" docs/js/db.js` shows the constants only in the export block; `grep -rn "db.js\|_KEY" docs/js/main.js` shows `main.js` still constructs `new DataClient()` with no arguments and imports nothing that moved.

- [ ] **Step 4: Widen the no-stray-IO scope to the tablet**

In `tests/test_no_stray_io.py`, replace the body of `test_the_web_twin_keeps_localstorage_in_its_client_too` with a walk over both client directories:

```python
def test_the_web_twin_keeps_localstorage_in_its_client_too():
    """Same rule, same reason - the twin had three keys spread across main.js.
    The tablet client (docs/tablet/) is under the same rule from its first
    file; the directory may not exist yet."""
    offenders = []
    for sub in ("js", "tablet"):
        top = os.path.join(ROOT, "docs", sub)
        if not os.path.isdir(top):
            continue
        for dirpath, _dirs, files in os.walk(top):
            for fn in sorted(files):
                if not fn.endswith(".js") or fn == "db.js":
                    continue
                path = os.path.join(dirpath, fn)
                with open(path) as f:
                    for i, line in enumerate(f, 1):
                        if "localStorage" in line and not line.strip().startswith("//"):
                            offenders.append("%s:%d" % (os.path.relpath(path, ROOT), i))
    assert not offenders, (
        "localStorage outside docs/js/db.js at %s - route it through the client"
        % offenders)
```

- [ ] **Step 5: Run the tests and the whole suite**

Run: `python3 -m pytest tests/test_db_prefix.py tests/test_no_stray_io.py tests/test_twin_parity.py -q` — Expected: passed.
Run: `python3 -m pytest tests/ -q` — Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add docs/js/db.js tests/test_db_prefix.py tests/test_no_stray_io.py
git commit -m "feat(db): a storage key prefix so two clients on one origin keep separate saves"
```

---

## Done when

- `python3 -m pytest tests/ -q` is green with the six commits above on this branch.
- `git log --oneline -6` shows the six commits.
- The Presto and web twin behave exactly as before under the default policy: `tests/test_tap_budget.py` still walks 31 taps against its 33 gate, and every `tests/scene_hashes.txt` scene hash is unchanged (`tests/test_skin_identity.py`).
