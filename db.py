"""The data client: the ONLY place the firmware touches storage.

Every read and write goes through here - `tests/test_no_stray_io.py` enforces
it by grepping the rest of the tree. That is the point of the module: caching,
formats and durability are decisions with one home instead of being spread
across `main.py` and `quest_catalog.py` with four ad-hoc closure caches.

Three collections, because measurement says they are three different problems:

  catalog   immutable, built at deploy, keyed random read
  session   the live game: state + log + delta journal, written every tap
  history   finished games, appended once, aggregated later

The numbers that shaped this, all measured on the device (Presto/RP2350,
MicroPython 1.26):

  * a durable write is **~50 ms and FLAT** - rewriting 1500 B costs the same
    whether the file held 0 or 100 KB. `press_feedback` holds the button for
    90 ms, so that window fits about ONE write. Nothing here may be a
    whole-file rewrite of something that grows.
  * `json.loads` is **pure Python** on this build (`type(json.loads)` is
    `<class 'function'>`) while `struct.unpack` is C, so binary wins outright
    for anything tabular. See tools/build_catalog_pack.py.
  * `gc.collect()` scales with the LIVE set (~70 ns/byte: 4 ms at 64 KB,
    70 ms at 1 MB), so a small resident cache is a latency win, not just a
    memory one. Parsing index.json alone used to hold ~263 KB.

There is no swappable `Store` interface. It was considered and cut: the
bake-off rejected every alternative engine (SQLite corrupts and hangs, TinyDB
is ~40x slower than files, btree's `open()` never returns), so nothing will be
swapped; and a lowest-common-denominator get/put/append/scan cannot express
truncate, compact or delete, which the session genuinely needs.
"""

import gc
import json
import struct

import gamestate
import quest_catalog

STATE_PATH = "/state.json"
STATE_TMP = "/state.tmp"        # atomic-write staging file
LOG_PATH = "/log.bin"           # append-only game log
REPLAY_JOURNAL = "/replay.bin"  # append-only delta journal
REPLAY_LEGACY = "/replay.json"  # pre-journal whole-file store; read-only
PREFS_PATH = "/device.json"
HISTORY_PATH = "/history.bin"   # append-only finished games
ROLLUP_PATH = "/stats.json"     # precomputed aggregates over history

DEFAULT_PREFS = {"brightness": 100, "scene": "phase"}


# -- framing -----------------------------------------------------------------
# 2-byte little-endian length, then the payload. Shared by every append-only
# store so there is one framing to get right.

def _append(path, recs):
    if not recs:
        return
    buf = bytearray()
    for r in recs:
        payload = json.dumps(r).encode()
        buf += struct.pack("<H", len(payload)) + payload
    with open(path, "ab") as f:
        f.write(buf)


def _read(path):
    """Stops at the first short or corrupt record rather than skipping it.

    A gap means the tail is untrustworthy, and for a delta stream applying
    records past a gap produces a WRONG state rather than a missing one - the
    silent-wrong-undo that gamestate._migrate_delta's note calls out as the
    dangerous failure.
    """
    try:
        with open(path, "rb") as f:
            blob = f.read()
    except Exception:
        return []
    out = []
    i = 0
    while i + 2 <= len(blob):
        (n,) = struct.unpack_from("<H", blob, i)
        i += 2
        if i + n > len(blob):
            break
        try:
            out.append(json.loads(blob[i:i + n]))
        except Exception:
            break
        i += n
    return out


def _remove(*paths):
    import os
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass


class Session:
    """The live game. **Gameplay touches RAM only; storage happens in the
    background.**

    A tap calls `record()`, which appends to an in-memory queue and returns —
    no I/O at all, measured at well under a millisecond. The durable work is
    drained by `tick()`, which the main loop calls only on frames where there
    is nothing to draw, so it never lands on a frame the player is waiting for.

    Why it must be cooperative rather than a real background thread: Pimoroni
    disables `MICROPY_PY_THREAD` for the Presto (boards/presto/mpconfigboard.h),
    so there is no second core and no sidecar process available from Python.
    The main loop's idle path is the equivalent, and it is enough because the
    work is small: an append is ~2 ms, and the one expensive operation (the
    ~89 ms state rewrite) is both bounded to one per tick and only reached once
    the queue is empty.

    `tick()` does **at most one** unit of work per call, so no single idle frame
    can stall. `flush()` drains everything and is used only where the game is
    ending or being put down — save-and-quit, game over, a `game` rebind.

    The queue is tagged with the game object it came from. `main.py` rebinds
    `game` on new-game and end-game, and a queued write derived from a
    different game is garbage (the same hazard `pending[1] is game` already
    guards for deltas), so a rebind drops the queue rather than applying it.
    """

    #: Journal records drained per tick. One append is ~2 ms, so a small batch
    #: stays invisible inside the 20 ms loop while still keeping up with taps.
    BATCH = 16

    #: Idle ticks with an empty queue before the state checkpoint is written.
    #: The checkpoint is the one expensive operation (~89 ms: a full rewrite
    #: plus rename), and doing it on the frame after every tap put ~89 ms of
    #: background work in the middle of play. Waiting for the player to stop
    #: tapping moves it into the gaps that already exist - reading a card,
    #: moving tokens - where nothing is waiting on it. At a 20 ms loop this is
    #: ~60 ms of quiet, and the journal already holds everything meanwhile.
    IDLE_BEFORE_STATE = 3

    #: Quiet frames (20 ms each) before ANY durable work starts. The loop only
    #: polls touch once per iteration, so every millisecond spent writing is a
    #: millisecond of unresponsive screen. Four frames is ~80 ms of stillness -
    #: shorter than any real gap between taps, long enough that a run of taps
    #: never collides with a write.
    QUIET_FRAMES = 4

    def __init__(self):
        self._queue = []          # [("l"|"r", record)]
        self._owner = None        # the game the queue describes
        self._state_dirty = False
        self._idle = 0            # consecutive ticks with nothing queued

    def record(self, game):
        """Called on EVERY tap. RAM only - never touches storage."""
        if self._owner is not game:
            # A rebind invalidates anything queued for the previous game.
            self._queue = []
            self._owner = game
        for r in game.take_log_appends():
            self._queue.append(("l", r))
        for r in game.take_replay_appends():
            self._queue.append(("r", r))
        self._state_dirty = True
        self._idle = 0            # the player is active again

    def tick(self, game):
        """One bounded unit of durable work. Idle frames only.

        Returns True if something was written, so `flush()` can spin on it.
        Journal first, state last: the journal is what makes the state
        reconstructable, and it is the cheap one.
        """
        if self._owner is not game:
            return False
        # `_idle == 0` on entry means a tap arrived since the last tick, i.e.
        # the player is mid-run. Draining then would put a ~55 ms append into
        # every gap between taps, which is exactly the background cost this is
        # supposed to avoid - so hold the records in RAM and write them in one
        # batch, either when enough have piled up or when the run stops.
        self._idle += 1
        # Wait for real quiet before touching storage at all. The loop is
        # single-threaded: while a write runs, hw.poll() does NOT, so a tap
        # arriving mid-write waits for it. Starting on the frame right after a
        # redraw put a ~110 ms stall exactly where the next tap lands.
        if self._idle < self.QUIET_FRAMES:
            return False
        if self._queue:
            return self._drain_batch()
        if self._state_dirty:
            # Wait for a real pause before paying for the checkpoint. Nothing
            # is at risk meanwhile: the journal is already durable, and it is
            # what reconstructs the state.
            if self._idle <= self.QUIET_FRAMES + self.IDLE_BEFORE_STATE:
                return False
            self.save_state(game)
            self._state_dirty = False
            return True
        return False

    def force_state(self, game):
        """Checkpoint now, skipping the idle wait. For flush points."""
        if self._owner is game and self._state_dirty:
            self.save_state(game)
            self._state_dirty = False

    def _drain_batch(self):
        """Write one batch of queued journal records. Returns True if it wrote."""
        if not self._queue:
            return False
        # ONE file per call. Draining both stores in a single tick meant two
        # ~55 ms appends back to back - 110 ms with no touch polling.
        kind = self._queue[0][0]
        path = LOG_PATH if kind == "l" else REPLAY_JOURNAL
        batch = [r for k, r in self._queue[:self.BATCH] if k == kind]
        try:
            _append(path, batch)
        except Exception:
            pass
        keep = []
        dropped = 0
        for k, r in self._queue:
            if k == kind and dropped < len(batch):
                dropped += 1
            else:
                keep.append((k, r))
        self._queue = keep
        return True

    def flush(self, game):
        """Drain everything. For save-and-quit, game over, and before a rebind
        - points where the player is not mid-tap and correctness beats speed.

        Goes straight at the queue rather than through tick(): tick() declines
        to write while the player looks active, which is right for a background
        frame and wrong for a flush. Routing flush through it meant a
        save-and-quit could return with records still in RAM.
        """
        if self._owner is not game:
            return
        guard = 0
        while self._drain_batch() and guard < 10000:
            guard += 1
        self.force_state(game)

    def pending(self):
        """Queued records not yet durable. For tests and diagnostics."""
        return len(self._queue)

    def save_state(self, game):
        """Atomic: temp file, then rename over the target.

        `open(path,"w")` truncates before the data lands, so a power cut left
        an unloadable save - the one file whose loss actually costs the player
        their game. Rename over an existing target is permitted here (8.6 ms).
        """
        try:
            import os
            import time
            with open(STATE_TMP, "w") as f:
                json.dump({"saved_at": time.time(), "state": game.to_dict()}, f)
            os.rename(STATE_TMP, STATE_PATH)
        except Exception:
            pass

    def save_log(self, game):
        """Append only the rows this action created or rewrote."""
        try:
            _append(LOG_PATH, game.take_log_appends())
        except Exception:
            pass

    def save_replay(self, game):
        """Append this action's journal ops; no-op when there are none."""
        try:
            _append(REPLAY_JOURNAL, game.take_replay_appends())
        except Exception:
            pass

    def commit(self, game):
        """What a tap does: queue, and return. Kept as the tap-path name so
        call sites read the same in both twins; the work happens in tick()."""
        self.record(game)

    def load_state(self):
        """Raw saved dict, or None. Callers own the rehydration."""
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except Exception:
            return None

    def load_log(self, game):
        recs = _read(LOG_PATH)
        if not recs:
            return
        try:
            game.log = gamestate.fold_log(recs)
            game._seq = max(game._seq, max(e.get("seq", 0) for e in game.log))
        except Exception:
            pass

    def load_replay(self, game):
        """Prefer the journal; fall back to the pre-journal store and seed."""
        ops = _read(REPLAY_JOURNAL)
        if ops:
            try:
                deltas, step = gamestate.fold_replay(ops)
                game.replay_from_dict({"deltas": deltas, "replay_step": step})
                return
            except Exception:
                pass
        try:
            with open(REPLAY_LEGACY) as f:
                game.replay_from_dict(json.load(f))
            if game.deltas:
                _append(REPLAY_JOURNAL, game.seed_replay_journal())
        except Exception:
            game.replay_from_dict(None)

    def exists(self):
        try:
            import os
            os.stat(STATE_PATH)
            return True
        except Exception:
            return False

    def clear(self):
        _remove(STATE_PATH, STATE_TMP, LOG_PATH, REPLAY_JOURNAL, REPLAY_LEGACY)


class History:
    """Finished games: appended once each, aggregated for stats screens.

    Append is O(1) forever (~63 ms, independent of how many games are stored).
    Reading them ALL is not: 4000 games took 15.9 s, and a second sort over
    them took 50 s once ~875 KB was live and GC began thrashing. So the
    common screens read the rollup, which is a couple of KB, and only an
    explicit "browse every game" pays for a scan.
    """

    def append(self, record):
        try:
            _append(HISTORY_PATH, [record])
            self._bump_rollup(record)
        except Exception:
            pass

    def scan(self):
        """Every finished game, oldest first. O(n) - prefer rollup()."""
        return _read(HISTORY_PATH)

    def rollup(self):
        try:
            with open(ROLLUP_PATH) as f:
                return json.load(f)
        except Exception:
            return {"games": 0, "wins": 0, "rounds": 0, "by_scenario": {},
                    "best": None}

    def _bump_rollup(self, rec):
        """Fold one finished game into the aggregates, O(1).

        Maintained incrementally on purpose: recomputing from a full scan is
        what makes a stats screen unusable once the history is large.
        """
        r = self.rollup()
        r["games"] = r.get("games", 0) + 1
        if rec.get("won"):
            r["wins"] = r.get("wins", 0) + 1
        r["rounds"] = r.get("rounds", 0) + (rec.get("rounds") or 0)
        slug = rec.get("scn") or "?"
        by = r.setdefault("by_scenario", {})
        e = by.setdefault(slug, {"played": 0, "won": 0})
        e["played"] += 1
        if rec.get("won"):
            e["won"] += 1
        best = r.get("best")
        if rec.get("won") and (best is None
                               or (rec.get("rounds") or 0) < best.get("rounds", 1 << 30)):
            r["best"] = {"scn": slug, "rounds": rec.get("rounds"),
                         "players": rec.get("players")}
        try:
            with open(ROLLUP_PATH, "w") as f:
                json.dump(r, f)
        except Exception:
            pass

    def clear(self):
        _remove(HISTORY_PATH, ROLLUP_PATH)


class DataClient:
    """Catalog reads with pinned caches, plus the session and history stores.

    Caching policy is driven by the measured read costs, and the working set is
    kept small on purpose because GC pause tracks the live set: the whole
    pinned catalog is ~35 KB, where a collect costs 2-3 ms.
    """

    def __init__(self):
        self._pack = None          # CatalogPack, pinned
        self._index = None         # index-shaped view, pinned
        self._icons = None         # pinned (38 KB, used across screens)
        self._tips = None          # pinned
        self._side_quests = None   # pinned - was re-read on EVERY tap
        self._bundles = {}         # slug -> scenario bundle, pinned per game
        self.session = Session()
        self.history = History()

    # -- catalog ------------------------------------------------------------
    def index(self):
        """Prefer catalog.bin; fall back to index.json.

        PROPAGATES on failure, deliberately: main.py surfaces it as
        CatalogUnavailableScreen ("no silent downgrade - a bug to see, not to
        paper over"). The catalog reads below never raise, because they are
        optional at runtime; this one is not.
        """
        if self._index is None:
            if self._pack is None:
                self._pack = quest_catalog.load_catalog_pack()
            if self._pack is not None:
                self._index = quest_catalog.pack_as_index(self._pack)
            else:
                self._index = quest_catalog.load_index()
        return self._index

    def scenario(self, slug):
        """One scenario's full record. Propagates, like index()."""
        b = self._bundles.get(slug)
        if b is not None:
            return b["scenario"]
        return quest_catalog.load_scenario(slug)

    def bundle(self, slug):
        """Every static datapoint this scenario needs, in one go, pinned.

        ~10 KB measured (8.5 KB detail + ~712 B locations + ~748 B tips), so
        after this returns there is not a single catalog read during play.
        Replaces four inconsistent paths: the scenario dict held on a screen
        AND deep-copied into game.stages, locations read lazily on the first
        Travel tap, all 122 scenarios' tips loaded to show one, and a re-read
        on resume.
        """
        b = self._bundles.get(slug)
        if b is not None:
            return b
        try:
            scn = quest_catalog.load_scenario(slug)
        except Exception:
            return None
        b = {"scenario": scn,
             "stages": ((scn or {}).get("quest") or {}).get("stages") or [],
             "locations": quest_catalog.load_locations(slug),
             "tips": self.tips()}
        # One scenario at a time: the picked scenario cannot change mid-game,
        # and holding several would grow the live set for no reader.
        self._bundles = {slug: b}
        gc.collect()
        return b

    def locations(self, slug):
        b = self._bundles.get(slug)
        if b is not None:
            return b["locations"]
        return quest_catalog.load_locations(slug)

    def side_quests(self):
        if self._side_quests is None:
            self._side_quests = quest_catalog.load_player_side_quests()
        return self._side_quests

    def icons(self):
        if self._icons is None:
            self._icons = quest_catalog.load_icons()
        return self._icons

    def tips(self):
        if self._tips is None:
            self._tips = quest_catalog.load_tips()
        return self._tips

    def release_game(self):
        """Drop the per-game pins when a game ends."""
        self._bundles = {}
        gc.collect()

    # -- prefs --------------------------------------------------------------
    def load_prefs(self):
        try:
            with open(PREFS_PATH) as f:
                d = json.load(f)
            return {"brightness": d.get("brightness", 100),
                    "scene": d.get("scene", "phase")}
        except Exception:
            return dict(DEFAULT_PREFS)

    def save_prefs(self, prefs):
        try:
            with open(PREFS_PATH, "w") as f:
                json.dump(prefs, f)
        except Exception:
            pass
