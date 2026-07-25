# RingsDB Deck Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a player attach their published RingsDB.com deck to their HUD player slot by its numeric deck ID, so the HUD can show their heroes, spheres, and a starting-threat prefill without manual entry — while degrading cleanly to today's fully-manual flow whenever the deck can't be resolved (no ID entered, ID entered but not yet synced, device offline, bad ID).

**Architecture:** A new pure module (`ringsdb.py` / `docs/js/ringsdb.js`) turns a RingsDB decklist + a small set of hero card records into a compact `deck` summary attached to a `Player`. Resolution happens two different ways depending on twin, both producing the *same* summary shape:
- **Web** (real internet in the browser): a live, unauthenticated `fetch()` against RingsDB's public API, confirmed CORS-open for exactly this use — a bare, header-free `GET`.
- **Firmware** (no network stack shipped yet — WiFi is `ROADMAP.md`'s M2, "Planned" not "Shipped"; see Context): a **flash-local read** of a file pre-fetched on a networked dev machine by a new CLI tool, `tools/fetch_ringsdb_deck.py`, deployed with the exact `mpremote cp -r docs/data/ :/data/` step already used for the card catalog. No new deploy mechanism, no new device capability required.

Entry is via a **numeric keypad modal** (0–9 + backspace + confirm) on both twins (see "Deck-ID entry" below). Reaching the linking UI itself required one correction to the codebase's existing (but unwired) plumbing — see "Verified: `PlayerSettingsModal` has no entry point today" below — which Task 4 fixes as part of wiring this feature in.

**Tech Stack:** ES modules (web, Canvas, `fetch`) + MicroPython (firmware, flash `json.load`); a small stdlib-only Python CLI tool (`urllib.request`, matching `tools/build_card_data.py`'s own dependency-free style); pytest + the scene layout linter.

**Context — device networking today (verified):** `ROADMAP.md` lists under `## Planned`: *"M2 — Connectivity: WiFi provisioning by QR to a Presto-hosted page, a known-networks list with auto-connect, and an on-device Network settings screen."* — not under `## Shipped`. `ui/screen_settings.py` (read directly) renders its Network/Tunes row via `self._app_tile(d, pal, x, y, icon, label, enabled=False)` under the literal label `"APPS  (coming soon)"`. The Presto's RP2350 does carry a real WiFi radio — Pimoroni's own product page (`https://shop.pimoroni.com/en-us/products/presto`, fetched live this session) lists **"16MB of QSPI flash supporting XiP"** and **"8MB of PSRAM"** alongside the wireless spec — so this plan's firmware-side design (pre-fetch + flash file) is a deliberate scoping choice for *today's* unshipped-networking reality, not a hardware ceiling. Once M2 ships, `ringsdb.py`'s `load_deck` can gain a live-fetch branch with **zero change** to `summarize_decklist` or the data shape.

**Verified: `PlayerSettingsModal` has no entry point today.** `grep -rn "PlayerSettingsModal"` across the whole repo turns up the class definition in `ui/modals.py` / `docs/js/screens.js`, and construction only from `tests/test_modals.py` — no screen or modal in either twin ever opens it (`PlayersDetailModal`, the modal players actually reach by tapping the Players zone, has its own separate inline threat/willpower editor and never delegates to it). This plan's Task 4 gives `PlayerSettingsModal` a real entry point (a tap on a player's label in `PlayersDetailModal`) as part of landing the RingsDB deck row there — the natural home for it, since `PlayerSettingsModal` already edits `starting_threat` (exactly the field a linked deck prefills).

**Router constraint (verified by reading `main.py`'s dispatch loop directly):** a modal's `on_button` can only return `"close"` / `"cancel"` / `None` to the loop that owns it — there is no return value that swaps in a *different* modal. Every existing case that needs modal-to-modal handoff (`pending_quest_card`, `pending_side_quest_pick`) does it by setting a flag on `game`, returning `"close"`, and letting a pre-tap check in the main loop (`if modal is None and ...: modal = XModal(...); continue`) open the next modal once the loop is clear. This plan's whole hand-off chain (Players list → Settings → Keypad → back to Settings, resolved) is built the same way — see Task 4.

**Verified against the live RingsDB API** (fetched fresh this session, timestamps below are from those responses — not sourced from RingsDB's own docs page alone):

- **Decklist endpoint:** `GET https://ringsdb.com/api/public/decklist/{id}.json`. The API doc page (`https://ringsdb.com/api/doc`, fetched live) shows the route as `/decklist/{decklist_id}` constrained by a `\d+` pattern — a bare non-negative integer, no auth. Real response (`.../decklist/20968.json`, trimmed):
  ```json
  {
    "id": 20968, "name": "The Best Deck",
    "date_creation": "2021-05-28T16:25:50-04:00", "date_update": "2026-07-09T05:11:11-04:00",
    "user_id": 10363,
    "heroes": {"04101": 1, "05001": 1, "07002": 1, "22081": 1},
    "slots": {"01014": 1, "01023": 1, "...": "...44 more entries..."},
    "sideslots": [], "version": "1.0", "is_published": true, "starting_threat": 33
  }
  ```
  No `sphere` field at the deck level — sphere comes from each hero's own card record. **`starting_threat` cross-checked by hand against this exact deck's heroes** (all four fetched live): Glorfindel (04101, threat 5) + Beregond (05001, threat 10) + Gríma (07002, threat 9) + Gildor Inglorion (22081, threat 9) = **33**, matching `starting_threat` exactly — reliable enough to use directly rather than recomputing, though the summary keeps it as its own field rather than assuming the identity holds for every deck.
- **Card endpoint:** `GET https://ringsdb.com/api/public/card/{code}.json`. Real response (`.../card/01001.json`, trimmed): `{"code":"01001","name":"Aragorn","type_code":"hero","sphere_code":"leadership","sphere_name":"Leadership","threat":12,"willpower":2,...,"pack_name":"Core Set","url":"https://ringsdb.com/card/01001"}`.
- **Player-cards-only, confirmed by exhaustive enumeration, not assumption:** fetched the entire public export (`GET /api/public/cards/`, 1315 cards) and computed the distinct `type_code` set directly: `['ally', 'attachment', 'contract', 'event', 'hero', 'player-objective', 'player-side-quest', 'treasure']` — no `enemy` / `location` / `treachery` / encounter-side `quest` type anywhere. `GET /api/public/scenario/1.json` (Passage Through Mirkwood) exposes only aggregate encounter-set counts (`"normal_enemies": 16, ...`), never individual encounter cards. **This plan only ever needs `type_code == "hero"` records** — well inside the verified-safe zone.
- **CORS:** confirmed live — `curl -D - -H "Origin: https://andrhamm.com" .../decklist/20968.json` returns `Access-Control-Allow-Origin: *` alongside `Cache-Control: max-age=600, public`. The API doc page states the same. **Fetches must stay bare, header-free `GET`s** — an `OPTIONS` preflight against `/api/public/cards/` 405s with no CORS headers, which only matters if a caller adds custom headers (this plan's calls never do).
- **Failure modes, verified directly (both differ from what you'd guess):**
  - A **bad/unpublished decklist ID** (`.../decklist/999999999.json`) returns **HTTP 200 with an empty body** — not a 404. `json.load`/`.json()` on an empty body raises a decode error either way, so the broad `except`/`catch` in this plan's code still degrades correctly, but the plan's own comments say "empty body," not "404," so a future reader isn't misled.
  - A **bad card code** (`.../card/99999.json`) returns **HTTP 500 with a valid JSON error body**: `{"error":{"code":500,"message":"Internal Server Error"}}`. This one matters functionally: Python's `urllib.request.urlopen` raises `HTTPError` on any non-2xx status (caught by `fetch_one`'s `try/except`), but **browser `fetch()` does not reject on a non-2xx status** — `response.json()` on this body succeeds and returns `{"error": {...}}` as if it were a real card. `summarize_decklist`/`summarizeDecklist` (Task 1) therefore validate a resolved hero record (has a `name`, no `error` key) rather than just checking it's truthy — this is a real correctness fix, not defensive padding, verified by this exact response.
  - `GET /api/oauth2/decks` (the only endpoint that could answer "what decks does user X have") returns **HTTP 500** with no data when called unauthenticated — confirming there is no usable public username→decks lookup; a player must already know their own deck's numeric ID (visible in its RingsDB URL).
- **No documented rate limit** beyond "conform to HTTP caching best practices" (`https://ringsdb.com/api/`); responses carry `Cache-Control: max-age=600`. `robots.txt` (fetched live) blocks several named AI-crawler user agents site-wide but disallows no `/api/` path — moot regardless, since this is a user's own app fetching on their own behalf, not a crawler.
- **Copyright:** RingsDB's API page states card text/graphics are FFG-copyrighted; the site is unaffiliated with FFG. This plan never stores or displays `text`/`flavor` (rules text) from RingsDB — only structural fields (`name`, `sphere_code`, `threat`); hero portraits are not fetched either. Same "structural data only" posture `tools/build_card_data.py` already takes with DragnCards.

## Deck-ID entry: options considered

Real IDs are **not small** (`20968` is 5 digits; a site running since ~2016 with sequential IDs runs higher for newer decks) — this rules out a naive "+/-" stepper outright, and the actual RingsDB HTML deck URL (`ringsdb.com/decklist/view/{id}/{slug}`) confirms IDs are the primary artifact, slugs are cosmetic.

| Option | Verdict |
|---|---|
| Plain `+`/`-` stepper (single-unit, like `ui/widgets.py`'s `stepper()`) | **Rejected.** Unusable at this ID range — dialing `45843` one unit at a time is up to 45,843 taps. Every stepper already in this codebase (threat, quest points) is for small bounded ranges; deck IDs aren't one. |
| Web-side text entry that syncs to the device | **Rejected.** Verified directly: web (`localStorage`, `docs/js/main.js`) and firmware (`/state.json`, `main.py`) are two fully independent persistence stores today, bridged only by the maintainer's manual, main-session-only `mpremote cp` step (`CLAUDE.md`, "Device access"). Building a new sync channel (file export/import, a QR carrying a payload) just to save typing a 6-digit number on one twin is disproportionate — and would still leave firmware needing *some* on-device entry method for players who never touch the web twin at all. |
| QR code — **Presto scans one** (phone shows a deck-ID QR, device reads it) | **Rejected, hardware.** The Presto has no camera. (This repo's own `docs/superpowers/specs/2026-07-24-wireless-camera-feasibility.md` is a feasibility study for a *separate, external* battery-powered camera pod for board photos — it exists precisely because the Presto itself has no imaging hardware; nothing in `ROADMAP.md` or `design/roadmap.md` lists one shipped or planned.) |
| QR code — **Presto displays one**, phone submits the ID to it | **Rejected, for now.** This needs the Presto to host something a phone can reach over the same network — i.e. M2 connectivity, verified above as "Planned," not shipped. Worth revisiting once M2 lands (a QR to a tiny Presto-hosted form could then *replace* the keypad for this one field) — noted here, not built now, since building against unshipped connectivity would block this plan on a different one. |
| **12-key numeric keypad modal** (0–9, backspace, confirm) | **Recommended.** Bounded to `len(digits) + 1` taps regardless of ID magnitude; built from widgets already in this codebase (`Button`, `bevel`, the `_footer`/`footer` Cancel/Confirm pair); identical on both twins, so no web/firmware UX divergence; needs no new device capability, no new sync channel, and no camera. |

**Recommendation: the numeric keypad**, justified against the device's actual input surface (tap-only, no drag-scroll, no keyboard, no camera, no shipped network) rather than against a hypothetical richer one. **If the user prefers web-side entry with sync instead**, the change would be a plain `<input type="number">` in the web `PlayerSettingsModal` plus a small new export/import (e.g. a JSON the maintainer copies via `mpremote cp` alongside the catalog deploy carrying `{player_index: deck_id}` pairs) — strictly more moving parts than the keypad for a typing-convenience gain on one twin only, which is why it isn't the default.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then firmware.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter.
- **RingsDB data is optional at every layer**, exactly like the quest catalog (`quest_catalog.py`'s own convention: on ANY failure, return `None`/`[]`/`{}` so the caller falls back to today's manual entry). A player with no deck linked, an unresolved ID, or a fetch/file-read failure sees the *exact* Player Settings experience that exists today.
- **Fetches are bare, header-free `GET`s.** Never add custom headers to a RingsDB request.
- **Never fetch or store RingsDB `text`/`flavor` fields** — only `code`, `name`, `sphere_code`, `threat` are read off a card record, only for `type_code == "hero"` records, and only after the record passes the "is this a real card, not an error body" check (see Task 1).
- **`docs/data/` stays gitignored and regenerated, never hand-edited** (confirmed: `.gitignore` line 13 is a bare `docs/data/`) — pre-fetched decks land in `docs/data/decks/`, already covered by that same line.
- **Deck IDs are per-player, not per-game** — `Player.deck_id`/`Player.deck`.
- **A modal cannot open another modal directly** (see Router constraint above) — every hand-off in this plan goes through a `pending_*` flag on `GameState`, consumed by `main.py`/`docs/js/main.js`'s main loop, matching `pending_quest_card`/`pending_side_quest_pick` exactly.
- Touch targets ≥ 24px each dimension; everything within 480×480; no text collisions (linter-enforced).

## File structure

- `ringsdb.py` (new) + `docs/js/ringsdb.js` (new) — pure `summarize_decklist`/`summarizeDecklist` + `load_deck` (firmware flash read).
- `tools/fetch_ringsdb_deck.py` (new) — CLI pre-fetch tool, writes `docs/data/decks/<id>.json`.
- `gamestate.py` (`Player.__init__`, `to_dict`/`from_dict`, three new `pending_*` fields) + `docs/js/gamestate.js` (mirror).
- `ui/modals.py` (new `DeckEntryModal`; extend `PlayerSettingsModal` + `PlayersDetailModal`) + `docs/js/screens.js` (mirror).
- `main.py` + `docs/js/main.js` — three new pending-flag blocks in the main loop.
- `tests/test_ringsdb.py` (new), `tests/test_fetch_ringsdb_deck.py` (new), `tests/test_deck_entry_modal.py` (new), `tests/scenes.py`.

---

### Task 1: `ringsdb.py` — pure deck-summary logic + `Player` model fields

**Files:**
- Create: `ringsdb.py`
- Modify: `gamestate.py` (`Player.__init__`, `GameState.to_dict`/`from_dict`'s player loop)
- Test: `tests/test_ringsdb.py` (new)

**Interfaces (Produces):**
- `summarize_decklist(decklist, heroes_by_code) -> dict` — pure. `decklist` is a raw RingsDB decklist response; `heroes_by_code` is `{code: card_record}` for (at least) the codes in `decklist["heroes"]`. Returns `{"name": str, "starting_threat": int, "heroes": [{"code","name","sphere_code","threat"}, ...], "spheres": [str, ...]}` (deduped, first-appearance order). A code missing from `heroes_by_code`, **or present but not a real card record** (RingsDB's own verified 500-with-JSON-error-body shape), is skipped, not a crash.
- `Player` gains `deck_id = None` (str; the raw entered ID, kept even unresolved) and `deck = None` (the `summarize_decklist` shape, or `None`).
- Serialization: `deck_id`/`deck` added to the player dicts in `to_dict`/`from_dict` (default `None`).

- [ ] **Step 1: Write the failing test** (`tests/test_ringsdb.py`), using the real deck fetched live this session (RingsDB deck 20968, "The Best Deck") so the fixtures double as a regression check against RingsDB's actual shape:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ringsdb

DECKLIST = {
    "id": 20968, "name": "The Best Deck", "starting_threat": 33,
    "heroes": {"04101": 1, "05001": 1, "07002": 1, "22081": 1},
    "slots": {"01014": 1, "01023": 1}, "sideslots": [], "version": "1.0",
}
# Real hero records fetched live for this exact deck - threats sum to 33,
# matching starting_threat above (see the plan's Context section).
HEROES_BY_CODE = {
    "04101": {"code": "04101", "name": "Glorfindel", "type_code": "hero", "sphere_code": "spirit", "threat": 5},
    "05001": {"code": "05001", "name": "Beregond", "type_code": "hero", "sphere_code": "tactics", "threat": 10},
    "07002": {"code": "07002", "name": "Gríma", "type_code": "hero", "sphere_code": "lore", "threat": 9},
    # 22081 (Gildor Inglorion) deliberately absent - a partial-resolution failure
}

def test_summarize_decklist_basic_shape():
    d = ringsdb.summarize_decklist(DECKLIST, HEROES_BY_CODE)
    assert d["name"] == "The Best Deck"
    assert d["starting_threat"] == 33
    assert [h["code"] for h in d["heroes"]] == ["04101", "05001", "07002"]
    assert d["heroes"][0] == {"code": "04101", "name": "Glorfindel", "sphere_code": "spirit", "threat": 5}

def test_summarize_decklist_dedupes_spheres_in_first_appearance_order():
    d = ringsdb.summarize_decklist(DECKLIST, HEROES_BY_CODE)
    assert d["spheres"] == ["spirit", "tactics", "lore"]

def test_summarize_decklist_skips_unresolved_hero_codes():
    d = ringsdb.summarize_decklist(DECKLIST, {})
    assert d["heroes"] == [] and d["spheres"] == []
    assert d["name"] == "The Best Deck" and d["starting_threat"] == 33   # deck-level fields unaffected

def test_summarize_decklist_skips_error_bodies_not_just_missing_codes():
    # Verified live: a bad card code returns HTTP 500 with a *valid JSON*
    # error body, not an exception and not falsy. A resolver that only
    # checked `if not card: skip` would silently add a name=None ghost
    # hero here - this guards against that exact response shape.
    heroes = dict(HEROES_BY_CODE)
    heroes["22081"] = {"error": {"code": 500, "message": "Internal Server Error"}}
    d = ringsdb.summarize_decklist(DECKLIST, heroes)
    assert [h["code"] for h in d["heroes"]] == ["04101", "05001", "07002"]

def test_player_has_deck_fields_by_default():
    import gamestate
    p = gamestate.Player("P1", 25)
    assert p.deck_id is None and p.deck is None

def test_deck_fields_round_trip():
    import gamestate
    g = gamestate.GameState(1, 25)
    g.players[0].deck_id = "20968"
    g.players[0].deck = ringsdb.summarize_decklist(DECKLIST, HEROES_BY_CODE)
    g2 = gamestate.GameState.from_dict(g.to_dict())
    assert g2.players[0].deck_id == "20968"
    assert g2.players[0].deck["name"] == "The Best Deck"

def test_deck_fields_default_none_on_old_saves():
    import gamestate
    d = gamestate.GameState(1, 25).to_dict()
    del d["players"][0]["deck_id"]; del d["players"][0]["deck"]   # simulate a pre-existing save
    g = gamestate.GameState.from_dict(d)
    assert g.players[0].deck_id is None and g.players[0].deck is None
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_ringsdb.py -q` → `ModuleNotFoundError: No module named 'ringsdb'`.

- [ ] **Step 3: Implement `ringsdb.py`:**

```python
"""RingsDB deck resolution: turn a fetched/loaded decklist + hero card
records into the small summary a Player actually needs. Pure logic only -
see fetch_deck() (web, docs/js/ringsdb.js) and load_deck() (firmware,
below) for the twin-specific I/O. Never reads/stores card `text`/`flavor`
(FFG-copyrighted rules text) - only structural fields, and only for
type_code=="hero" records. Verified against the live API - see
docs/superpowers/plans/2026-07-25-ringsdb-integration.md.
"""


def _is_hero_record(card):
    """True if `card` looks like a real RingsDB card record rather than an
    API error body. Verified live: a bad/renumbered card code returns HTTP
    500 with a *valid JSON* error payload ({"error": {...}}) - not an
    exception and not falsy, so a bare `if card:` check would silently let
    it through. Firmware's urllib raises on that same response (caught by
    fetch_one's try/except in tools/fetch_ringsdb_deck.py); browser
    fetch() does not raise on non-2xx status, so summarize_decklist /
    summarizeDecklist need this guard directly."""
    return bool(card) and "error" not in card and bool(card.get("name"))


def summarize_decklist(decklist, heroes_by_code):
    """decklist: a raw RingsDB /api/public/decklist/<id>.json response.
    heroes_by_code: {code: card_record} for (at least) decklist["heroes"]'s
    codes - a code missing here, or resolving to something that fails
    _is_hero_record, is skipped, not a crash. Returns {"name",
    "starting_threat", "heroes": [...], "spheres": [...]}."""
    heroes = []
    spheres = []
    for code in decklist.get("heroes", {}):
        card = heroes_by_code.get(code)
        if not _is_hero_record(card):
            continue
        heroes.append({"code": code, "name": card.get("name"),
                       "sphere_code": card.get("sphere_code"), "threat": card.get("threat")})
        sc = card.get("sphere_code")
        if sc and sc not in spheres:
            spheres.append(sc)
    return {"name": decklist.get("name"), "starting_threat": decklist.get("starting_threat"),
            "heroes": heroes, "spheres": spheres}


DECKS_PATH = "/data/decks/%s.json"


def load_deck(deck_id):
    """Firmware: read a deck pre-fetched onto flash by
    tools/fetch_ringsdb_deck.py (see that tool's docstring). Thin wrapper,
    not host-tested (no /data/ on the dev host) - on ANY failure (not
    pre-fetched, corrupt file, no /data/ deploy yet) returns None so the
    caller falls back to showing the raw deck_id as unresolved, exactly
    like quest_catalog.py's load_scenario()/load_icons() precedent."""
    import json
    try:
        with open(DECKS_PATH % deck_id) as f:
            return json.load(f)
    except Exception:
        return None
```

Add to `gamestate.py`'s `Player.__init__` (immediately after `self.commit_touched = False`):
```python
        self.deck_id = None    # RingsDB numeric deck id, kept even if unresolved
        self.deck = None       # ringsdb.summarize_decklist() shape, or None
```
Add two keys to the player dict comprehension in `to_dict` (after `"commit_touched": p.commit_touched`): `"deck_id": p.deck_id, "deck": p.deck,`. Add to `from_dict`'s player loop (after `p.commit_touched = pd.get("commit_touched", False)`): `p.deck_id = pd.get("deck_id"); p.deck = pd.get("deck")`.

- [ ] **Step 4: Run tests → PASS.** `python3 -m pytest tests/test_ringsdb.py -q`.

- [ ] **Step 5: Mirror in `docs/js/ringsdb.js`** and `docs/js/gamestate.js` (keep dict keys `deck_id`/`deck` snake_case in `toDict`/`fromDict`, matching every other field in this file — e.g. `commit_touched`, `quest_history` — per the file's own header comment: *"Port of gamestate.py — method-for-method."*):

```javascript
// Port of ringsdb.py — method-for-method.
function isHeroRecord(card) {
  return !!card && !("error" in card) && !!card.name;
}

export function summarizeDecklist(decklist, heroesByCode) {
  const heroes = [];
  const spheres = [];
  for (const code of Object.keys(decklist.heroes ?? {})) {
    const card = heroesByCode[code];
    if (!isHeroRecord(card)) continue;
    heroes.push({ code, name: card.name, sphere_code: card.sphere_code, threat: card.threat });
    if (card.sphere_code && !spheres.includes(card.sphere_code)) spheres.push(card.sphere_code);
  }
  return { name: decklist.name ?? null, starting_threat: decklist.starting_threat ?? null, heroes, spheres };
}

export const DECKS_PATH = "/data/decks/%s.json";   // unused on web - fetchDeck (Task 2) hits the live API instead
```

- [ ] **Step 6: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(ringsdb): deck-summary logic + Player.deck_id/deck fields"`.

---

### Task 2: `tools/fetch_ringsdb_deck.py` — the pre-fetch CLI + web's live `fetchDeck`

**Files:**
- Create: `tools/fetch_ringsdb_deck.py`
- Modify: `docs/js/ringsdb.js` (add `fetchDeck`)
- Test: `tests/test_fetch_ringsdb_deck.py` (new)

**Interfaces (Produces):**
- CLI: `python3 tools/fetch_ringsdb_deck.py <deck_id> [<deck_id> ...]` — for each ID, fetches the decklist, then one card fetch per hero code, calls `ringsdb.summarize_decklist`, and writes `docs/data/decks/<id>.json`. Prints one line per ID and exits non-zero only if *every* ID failed (matches `build_card_data.py`'s own pass/fail signal convention).
- `fetchDeck(deckId)` (web, async) — the same fetch-then-summarize sequence with browser `fetch()`. Returns the `summarize_decklist` shape, or `null` on any failure — never throws, matching `quest_catalog.js`'s `loadPlayerSideQuests()` failure-swallowing convention.

- [ ] **Step 1: Write the failing test** (`tests/test_fetch_ringsdb_deck.py`) — the live network call itself is not host-tested (no live network in CI, matching every other `tools/`-fetches-the-internet precedent in this repo), but argument parsing and file-writing are, via a monkeypatched fetch function:

```python
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import fetch_ringsdb_deck as tool

DECKLIST = {"id": 1, "name": "Test Deck", "starting_threat": 30,
           "heroes": {"01001": 1}, "slots": {}, "sideslots": []}
CARD = {"code": "01001", "name": "Aragorn", "type_code": "hero", "sphere_code": "leadership", "threat": 12}

def test_fetch_one_writes_summary_json(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_get_json", lambda url: DECKLIST if "decklist" in url else CARD)
    out_dir = tmp_path / "decks"
    tool.fetch_one("1", out_dir=str(out_dir))
    with open(out_dir / "1.json") as f:
        d = json.load(f)
    assert d["name"] == "Test Deck" and d["heroes"][0]["name"] == "Aragorn"

def test_fetch_one_returns_none_on_network_failure(tmp_path, monkeypatch):
    def boom(url):
        raise OSError("network down")
    monkeypatch.setattr(tool, "_get_json", boom)
    assert tool.fetch_one("999", out_dir=str(tmp_path)) is None
    assert not os.path.exists(tmp_path / "999.json")

def test_fetch_one_returns_none_on_bad_hero_code(tmp_path, monkeypatch):
    # Verified live: a bad card code raises urllib.error.HTTPError (a
    # non-2xx status) rather than returning success - fetch_one's
    # try/except must catch that too, not just plain network errors.
    import urllib.error
    def get(url):
        if "decklist" in url:
            return DECKLIST
        raise urllib.error.HTTPError(url, 500, "Internal Server Error", {}, None)
    monkeypatch.setattr(tool, "_get_json", get)
    assert tool.fetch_one("1", out_dir=str(tmp_path)) is None
```

- [ ] **Step 2: Run to verify it fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/fetch_ringsdb_deck.py`:**

```python
"""Pre-fetch RingsDB decks for offline/on-device use: writes docs/data/
decks/<id>.json (gitignored under the existing docs/data/ rule - never
hand-edit, regenerated only). Run on a networked machine; the normal
`mpremote cp -r docs/data/ :/data/` deploy step ships the result to the
device, which then reads it via ringsdb.load_deck() with no network of
its own. See docs/superpowers/plans/2026-07-25-ringsdb-integration.md.

Usage: python3 tools/fetch_ringsdb_deck.py <deck_id> [<deck_id> ...]
"""
import json, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ringsdb

API = "https://ringsdb.com/api/public"
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "docs", "data", "decks")


def _get_json(url):
    # Bare, header-free GET - RingsDB's CORS allowance (and general
    # good-citizenship) assumes no custom headers; see the plan's CORS
    # note. A non-2xx response (e.g. a since-renumbered hero code -> 500,
    # verified live) raises urllib.error.HTTPError here, caught below.
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def fetch_one(deck_id, out_dir=DEFAULT_OUT_DIR):
    """Fetch + summarize one deck; write <out_dir>/<deck_id>.json. Returns
    the summary dict, or None (and writes nothing) on any failure -
    including a bad/unpublished deck id, which RingsDB answers with HTTP
    200 and an EMPTY body (verified live - not a 404), so json.load raises
    a decode error here just like any other failure mode; this catches
    all of them uniformly rather than special-casing status codes."""
    try:
        decklist = _get_json("%s/decklist/%s.json" % (API, deck_id))
        heroes_by_code = {}
        for code in decklist.get("heroes", {}):
            heroes_by_code[code] = _get_json("%s/card/%s.json" % (API, code))
        summary = ringsdb.summarize_decklist(decklist, heroes_by_code)
    except Exception:
        return None
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "%s.json" % deck_id), "w") as f:
        json.dump(summary, f)
    return summary


def main(argv):
    if not argv:
        print("Usage: python3 tools/fetch_ringsdb_deck.py <deck_id> [<deck_id> ...]")
        return 1
    ok = 0
    for deck_id in argv:
        summary = fetch_one(deck_id)
        if summary:
            print("%s: %s (%d heroes)" % (deck_id, summary["name"], len(summary["heroes"])))
            ok += 1
        else:
            print("%s: fetch failed" % deck_id)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests → PASS.** `python3 -m pytest tests/test_fetch_ringsdb_deck.py -q`.

- [ ] **Step 5: Try it live (manual, not part of the pytest gate).** `python3 tools/fetch_ringsdb_deck.py 20968` against the real RingsDB API — confirm `docs/data/decks/20968.json` matches Task 1's fixture shape, and `git status` shows it untracked (covered by the existing `docs/data/` gitignore line). Then `python3 tools/fetch_ringsdb_deck.py 999999999` (an unpublished ID, verified live to 200-with-empty-body) — confirm it prints `"999999999: fetch failed"` and writes nothing.

- [ ] **Step 6: Implement `fetchDeck` in `docs/js/ringsdb.js`** (below `summarizeDecklist` from Task 1):
```javascript
const API = "https://ringsdb.com/api/public";

export async function fetchDeck(deckId) {
  try {
    const decklist = await (await fetch(`${API}/decklist/${deckId}.json`)).json();
    const heroesByCode = {};
    for (const code of Object.keys(decklist.heroes ?? {})) {
      heroesByCode[code] = await (await fetch(`${API}/card/${code}.json`)).json();
    }
    return summarizeDecklist(decklist, heroesByCode);
  } catch {
    return null;
  }
}
```
(A bad hero code's HTTP-500-with-JSON-body does **not** throw here — `response.json()` succeeds — which is exactly why `summarizeDecklist`'s `isHeroRecord` guard from Task 1 does the real work on this twin, not this `catch`.)

- [ ] **Step 7: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(ringsdb): fetch_ringsdb_deck CLI + web fetchDeck"`.

---

### Task 3: `DeckEntryModal` — numeric keypad (both twins)

**Files:**
- Modify: `ui/modals.py` (new `DeckEntryModal`), `docs/js/screens.js` (mirror)
- Modify: `tests/scenes.py`
- Test: `tests/test_deck_entry_modal.py` (new)

**Interfaces (Produces):**
- `DeckEntryModal(game, player_index)` — internal state `self.digits` (str, up to 8 chars — generous headroom past any real RingsDB id today). `on_button` returns `"redraw"` for digit/backspace taps, `"close"` for Cancel or a successful Confirm (which sets `player.deck_id` **and** flags `game.pending_deck_resolve` — see Task 4; this modal never fetches/reads flash itself), `None` for a disabled Confirm (empty `digits`).
- Layout: header "Link RingsDB Deck"; a digit readout (or "Enter deck ID" placeholder) at y≈80; a 4×3 keypad grid (1–9, blank, 0, backspace) filling y≈130–370, each key 96×56 (well over the 24px minimum); footer Cancel/Confirm at `CANCEL_Y=404` via the shared `_footer`/`footer` helper.

- [ ] **Step 1: Write the failing test** (`tests/test_deck_entry_modal.py`) — the shared `_footer` helper's Confirm button carries id `("save",)` (`save_label` only changes the *label*), verified by reading `ui/modals.py` directly:

```python
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import DeckEntryModal

def _game():
    return gamestate.GameState(2, 25)

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_digit_taps_build_the_id():
    g = _game()
    m = DeckEntryModal(g, 0)
    _draw(m, g)
    for ch in "209":
        btn = next(b for b in m.buttons if b.id == ("digit", ch))
        assert m.on_button(btn) == "redraw"
    assert m.digits == "209"

def test_backspace_removes_last_digit():
    g = _game()
    m = DeckEntryModal(g, 0)
    m.digits = "209"
    _draw(m, g)
    back = next(b for b in m.buttons if b.id[0] == "backspace")
    m.on_button(back)
    assert m.digits == "20"

def test_confirm_disabled_when_empty():
    g = _game()
    m = DeckEntryModal(g, 0)
    _draw(m, g)
    confirm = next(b for b in m.buttons if b.id[0] == "save")
    assert m.on_button(confirm) is None

def test_confirm_sets_deck_id_and_flags_resolve():
    g = _game()
    m = DeckEntryModal(g, 1)
    m.digits = "20968"
    _draw(m, g)
    confirm = next(b for b in m.buttons if b.id[0] == "save")
    assert m.on_button(confirm) == "close"
    assert g.players[1].deck_id == "20968"
    assert g.pending_deck_resolve == 1

def test_cancel_does_not_touch_deck_id():
    g = _game()
    g.players[0].deck_id = "111"
    m = DeckEntryModal(g, 0)
    m.digits = "999"
    _draw(m, g)
    cancel = next(b for b in m.buttons if b.id[0] == "cancel")
    assert m.on_button(cancel) == "close"
    assert g.players[0].deck_id == "111"     # unchanged
```

- [ ] **Step 2: Run to verify it fails** — `AttributeError: pending_deck_resolve` (added in Task 4) will also surface here; add the three `pending_*` fields from Task 4's Step 3 to `GameState.__init__`/`to_dict`/`from_dict` now if doing Tasks 3+4 out of order, or do Task 4's model changes first — either order is fine since they touch disjoint files.

- [ ] **Step 3: Implement `DeckEntryModal` in `ui/modals.py`:**

```python
class DeckEntryModal:
    """Numeric-keypad entry for a RingsDB deck id - a stepper is unusable
    at real RingsDB id lengths (5-6+ digits; tens of thousands of taps)
    and there's no web<->device sync channel to justify a web-only text
    entry path instead (see docs/superpowers/plans/
    2026-07-25-ringsdb-integration.md, "Deck-ID entry: options
    considered"). Only sets player.deck_id + flags resolution on confirm;
    the actual fetch/flash-read happens in main.py's pending_deck_resolve
    block (Task 4) so this stays a pure input widget with no I/O of its
    own."""

    KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "<-"]

    def __init__(self, game, player_index):
        self.game = game
        self.i = player_index
        self.digits = ""
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Link RingsDB Deck", 240, 24, 3, pal.gold)
        shown = self.digits if self.digits else "Enter deck ID"
        text_center(d, pal, shown, 240, 80, 3, pal.tan if self.digits else pal.dim)

        kw, kh, gap, x0, y0 = 96, 56, 12, 60, 130
        for idx, key in enumerate(self.KEYS):
            col, row = idx % 3, idx // 3
            x, y = x0 + col * (kw + gap), y0 + row * (kh + gap)
            if not key:
                continue
            bevel(d, pal, x, y, kw, kh, pal.btn, t=2)
            label = "<-" if key == "<-" else key
            text_center(d, pal, label, x + kw / 2, y + kh / 2 - 10, 3, pal.tan)
            bid = ("backspace",) if key == "<-" else ("digit", key)
            self.buttons.append(Button(bid, x, y, kw, kh))

        _footer(d, pal, self.buttons, save_label="Confirm")

    def on_button(self, btn):
        k = btn.id[0]
        if k == "digit":
            if len(self.digits) < 8:
                self.digits += btn.id[1]
            return "redraw"
        if k == "backspace":
            self.digits = self.digits[:-1]
            return "redraw"
        if k == "cancel":
            return "close"
        if k == "save":
            if not self.digits:
                return None
            self.game.players[self.i].deck_id = self.digits
            self.game.pending_deck_resolve = self.i
            return "close"
        return None
```

- [ ] **Step 4: Run tests → PASS** (after Task 4's `pending_deck_resolve` field exists).

- [ ] **Step 5: Mirror in `docs/js/screens.js`** (`DeckEntryModal`, same `KEYS` grid, `digits` state, `footer(ctx, this.buttons, "Confirm")`).

- [ ] **Step 6: Add scenes** to `tests/scenes.py`: `deck_entry_empty`, `deck_entry_partial` (a few digits typed). Render: `python3 tools/preview.py deck_entry_partial /tmp/de.png` — confirm the keypad grid is legible and every key clears 24px. `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 7: Full suite + commit.** `git add -A && git commit -m "feat(ringsdb): DeckEntryModal numeric keypad"`.

---

### Task 4: Wire it up — reachable `PlayerSettingsModal`, deck row, resolution, starting-threat prefill

**Files:**
- Modify: `gamestate.py` + `docs/js/gamestate.js` (three new `pending_*` fields)
- Modify: `ui/modals.py` (`PlayersDetailModal` label tap, `PlayerSettingsModal` deck row), `docs/js/screens.js` (mirror)
- Modify: `main.py`, `docs/js/main.js` (three new pending-flag main-loop blocks)
- Test: extend `tests/test_deck_entry_modal.py`

**Interfaces:**
- `GameState` gains three fields, each an `int` player-index or `None`, serialized like `pending_elim`:
  - `pending_player_settings` — set by `PlayersDetailModal` when a player's **label** is tapped (a new tap target — today the label is drawn but never registered as a `Button`); the main loop opens `PlayerSettingsModal(game, i)` once `modal is None`.
  - `pending_deck_entry` — set by `PlayerSettingsModal`'s new "RingsDB Deck" row; the main loop opens `DeckEntryModal(game, i)`.
  - `pending_deck_resolve` — set by `DeckEntryModal`'s Confirm (Task 3); the main loop resolves `player.deck_id` (flash read / async fetch) into `player.deck`, then reopens `PlayerSettingsModal(game, i)` so the row immediately reflects the outcome.
- `PlayerSettingsModal` gains a "RingsDB Deck" row (between the Elimination help text, which ends ~y=314, and the footer at `CANCEL_Y=404` — verified there is no other free vertical space in this modal: every other row is already packed floor-to-ceiling). Shows `"Not linked - tap to add"` (no `deck_id`), `"Deck #<id> - not synced"` (`deck_id` set, `deck` still `None`), or the resolved deck's name + spheres (`deck` set). Tapping it sets `pending_deck_entry` and returns `"close"`.
- `PlayerSettingsModal.__init__`'s `self.st` seeds from `player.deck["starting_threat"]` **only if** a deck is resolved **and** `starting_threat` is still at its just-added-player default of `0` — `self.st = p.deck["starting_threat"] if (p.deck and p.starting_threat == 0) else p.starting_threat`. A deliberately-configured value is never silently overwritten; the stepper stays editable afterward regardless.

- [ ] **Step 1: Write the failing tests** (extend `tests/test_deck_entry_modal.py`):

```python
def test_player_label_tap_flags_pending_player_settings():
    from ui.modals import PlayersDetailModal
    g = _game()
    m = PlayersDetailModal(g)
    _draw(m, g)
    row = next(b for b in m.buttons if b.id == ("settings", 0))
    assert m.on_button(row) == "close"
    assert g.pending_player_settings == 0

def test_player_settings_deck_row_flags_pending_deck_entry():
    from ui.modals import PlayerSettingsModal
    g = _game()
    m = PlayerSettingsModal(g, 1)
    _draw(m, g)
    row = next(b for b in m.buttons if b.id[0] == "deck_row")
    assert m.on_button(row) == "close"
    assert g.pending_deck_entry == 1

def test_player_settings_prefills_starting_threat_from_resolved_deck():
    from ui.modals import PlayerSettingsModal
    g = _game()
    g.players[0].starting_threat = 0
    g.players[0].deck = {"name": "The Best Deck", "starting_threat": 33, "heroes": [], "spheres": ["spirit"]}
    m = PlayerSettingsModal(g, 0)
    assert m.st == 33

def test_player_settings_does_not_override_customized_threat():
    from ui.modals import PlayerSettingsModal
    g = _game()
    g.players[0].starting_threat = 28   # already set deliberately
    g.players[0].deck = {"name": "The Best Deck", "starting_threat": 33, "heroes": [], "spheres": ["spirit"]}
    m = PlayerSettingsModal(g, 0)
    assert m.st == 28
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Model changes.** In `gamestate.py`'s `GameState.__init__`, immediately after `self.pending_side_quest_pick = False` (and its comment block), add:
```python
        self.pending_player_settings = None   # player index whose PlayerSettingsModal
                                               # should open once modal is None (label
                                               # tapped in PlayersDetailModal) - same
                                               # pending-flag pattern as pending_quest_card
        self.pending_deck_entry = None        # player index whose DeckEntryModal should
                                               # open once modal is None (RingsDB linking)
        self.pending_deck_resolve = None      # player index whose deck_id should be
                                               # resolved (flash read / fetch) once modal
                                               # is None, then PlayerSettingsModal reopened
```
Add all three to `to_dict` (default the current value) and `from_dict` (`d.get("pending_player_settings", None)` etc.), following `pending_elim`'s exact pattern. Mirror in `docs/js/gamestate.js`.

- [ ] **Step 4: `PlayersDetailModal` label tap.** In `ui/modals.py`'s `PlayersDetailModal.draw`, after the label if/else block (before the `_editor_row` calls), add a registered tap target sized past the visual 36×22 label chip to clear the 24px minimum in both dimensions:
```python
            self.buttons.append(Button(("settings", i), label_x - 20, cy - 14, 40, 28))
```
In `on_button`, add (before the `if k in ("t", "w"):` check):
```python
        if k == "settings":
            self.game.pending_player_settings = i
            return "close"
```
(`i` here is `btn.id[1]` — bind it at the top of `on_button` alongside the existing `k = btn.id[0]` line, or read `btn.id[1]` directly.) Mirror in `docs/js/screens.js`'s `PlayersDetailModal`.

- [ ] **Step 5: `PlayerSettingsModal` deck row + prefill.** Change `self.st = p.starting_threat` to the prefill rule above. In `draw`, add before the `_footer(d, pal, self.buttons)` call:
```python
        p = self.game.players[self.i]
        dy = 328
        row = Button(("deck_row",), 16, dy - 6, 452, 56)
        bevel(d, pal, row.x, row.y, row.w, row.h, pal.card, t=2)
        text_left(d, pal, "RINGSDB DECK", 30, dy + 4, 1, pal.dim)
        if p.deck:
            spheres = "/".join(s.title() for s in p.deck["spheres"]) or "no heroes resolved"
            label = "%s (%s)" % (p.deck["name"], spheres)
        elif p.deck_id:
            label = "Deck #%s - not synced" % p.deck_id
        else:
            label = "Not linked - tap to add"
        text_left(d, pal, label, 30, dy + 22, 2, pal.tan)
        self.buttons.append(row)
```
In `on_button`, add (before the `if k == "save":` check):
```python
        if k == "deck_row":
            self.game.pending_deck_entry = self.i
            return "close"
```
Mirror in `docs/js/screens.js`'s `PlayerSettingsModal`.

- [ ] **Step 6: Run tests → PASS.**

- [ ] **Step 7: Main-loop wiring.** In `main.py`, add `import ringsdb` near the top. After the existing `pending_side_quest_pick` block (and before the "game over" check), add three blocks modeled on the `pending_quest_card` block:
```python
        # Players-zone label tap wants PlayerSettingsModal opened once the
        # Players-detail modal has closed (same pending-flag pattern as
        # pending_quest_card above).
        if modal is None and active == "play" and game.pending_player_settings is not None:
            from ui.modals import PlayerSettingsModal
            i = game.pending_player_settings
            game.pending_player_settings = None
            modal = PlayerSettingsModal(game, i)
            dirty = True
            continue

        # PlayerSettingsModal's deck row wants DeckEntryModal opened once
        # it has closed.
        if modal is None and active == "play" and game.pending_deck_entry is not None:
            from ui.modals import DeckEntryModal
            i = game.pending_deck_entry
            game.pending_deck_entry = None
            modal = DeckEntryModal(game, i)
            dirty = True
            continue

        # DeckEntryModal's Confirm wants deck_id resolved (flash read -
        # can't happen mid-tap) and PlayerSettingsModal reopened to show
        # the outcome.
        if modal is None and active == "play" and game.pending_deck_resolve is not None:
            i = game.pending_deck_resolve
            game.pending_deck_resolve = None
            p = game.players[i]
            if p.deck_id:
                p.deck = ringsdb.load_deck(p.deck_id)   # None on any failure - row shows "not synced"
            from ui.modals import PlayerSettingsModal
            modal = PlayerSettingsModal(game, i)
            dirty = True
            continue
```

- [ ] **Step 8: Mirror in `docs/js/main.js`.** Same three blocks; the resolve step is `async` (the only twin divergence in this task):
```javascript
if (!modal && active === "play" && game.pending_player_settings !== null) {
  const i = game.pending_player_settings;
  game.pending_player_settings = null;
  modal = new PlayerSettingsModal(game, i);
  dirty = true;
} else if (!modal && active === "play" && game.pending_deck_entry !== null) {
  const i = game.pending_deck_entry;
  game.pending_deck_entry = null;
  modal = new DeckEntryModal(game, i);
  dirty = true;
} else if (!modal && active === "play" && game.pending_deck_resolve !== null) {
  const i = game.pending_deck_resolve;
  game.pending_deck_resolve = null;
  const p = game.players[i];
  if (p.deck_id) {
    fetchDeck(p.deck_id).then(deck => {
      p.deck = deck;
      modal = new PlayerSettingsModal(game, i);
      dirty = true;
    });
  } else {
    modal = new PlayerSettingsModal(game, i);
    dirty = true;
  }
}
```
(Import `PlayerSettingsModal`, `DeckEntryModal` from `./screens.js` and `fetchDeck` from `./ringsdb.js` at the top of `main.js`, alongside the existing screen/modal imports. Place this block adjacent to wherever the existing `pending_quest_card`/`pending_side_quest_pick` equivalent lives in the JS main loop.)

- [ ] **Step 9: Add scenes** for the deck row states (`player_settings_deck_linked`, `player_settings_deck_unsynced`) to `tests/scenes.py`. `python3 tools/preview.py player_settings_deck_linked /tmp/psd.png` — confirm the row doesn't collide with the Elimination help text above or the footer below. `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 10: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(ringsdb): reachable PlayerSettingsModal + deck linking + starting-threat prefill"`.

---

### Task 5: Integration — live web fetch + on-device pre-fetched read + offline fallback

**Files:** none new (verification + any fixes surfaced).

- [ ] **Step 1: Web, live.** Serve the site, start a 2-player game, open Players (Players zone) → tap P1's label → Player Settings → tap the RingsDB Deck row → key in `20968` (a real published deck, verified live) → Confirm. Confirm the row updates to "The Best Deck (Spirit/Tactics/Lore)" and, if P1's starting threat is still 0, the stepper now reads 33. Check the Network tab: exactly the expected `GET`s (one decklist + one per hero), no extra headers, all 200s.
- [ ] **Step 2: Web, bad ID.** Enter `999999999` (verified live: 200 + empty body). Confirm the row falls back to `"Deck #999999999 - not synced"` and nothing else breaks.
- [ ] **Step 3: Firmware, pre-fetched.** `python3 tools/fetch_ringsdb_deck.py 20968`, then the normal deploy (`python3 tools/build_card_data.py && mpremote cp -r docs/data/ :/data/`). On-device, link P1 to `20968` via the keypad; confirm it resolves **instantly** (local flash read, no spinner) with the same summary as the web run.
- [ ] **Step 4: Firmware, not pre-fetched.** On-device, link a player to an ID that was never fetched. Confirm the row shows "not synced" and the game is otherwise fully playable (manual starting-threat entry still works) — the additive/never-blocking constraint holds.
- [ ] **Step 5: Full suite.** `python3 -m pytest tests/ -q` green; every new scene renders cleanly via `tools/preview.py`.
- [ ] **Step 6: Report** the four walkthroughs (screenshots / device photos where relevant) and commit any fixes found.

---

## Self-Review

**Spec coverage:** endpoints + real fetched examples, verified fresh this session (not assumed from the old docs page alone) → Context section, with two *corrections* to what a naive read of RingsDB's docs would suggest (empty-body bad-ID, JSON-error-body bad-hero-code) that materially change Task 1's implementation; player-cards-only confirmed by exhaustive `type_code` enumeration over the full 1315-card export → Context; deck-entry mechanism → "Deck-ID entry: options considered" evaluates all four options named in the brief (stepper, web-sync, QR, "something else" = the keypad) with concrete, verified rejection reasons for each, not a bare TBD; what the HUD does with a linked deck (heroes, starting threat, sphere info) → Task 1 (`summarize_decklist`) + Task 4 (deck row + prefill); offline/on-device degradation → `tools/fetch_ringsdb_deck.py`'s pre-fetch-to-flash design (Task 2) plus the explicit "not synced" state verified end-to-end in Task 5.

**A verified gap the old assumption would have missed:** `PlayerSettingsModal` — the natural home for a starting-threat-prefilling deck row — has no entry point in either twin today (confirmed by grepping the whole repo, not assumed). Task 4 fixes this as the mechanism for reaching the new feature, rather than silently building on top of dead code or inventing a parallel, redundant settings surface.

**Placeholder scan:** every task carries a complete, runnable test file and complete implementation code. The router's actual modal-to-modal constraint (verified by reading `main.py`'s dispatch loop directly, not assumed from the M4-B precedent alone) shapes Task 4's three-hop `pending_*` design explicitly, rather than hand-waving "wire it up."

**Type consistency:** `summarize_decklist(decklist, heroes_by_code)`'s return shape is defined once (Task 1) and consumed identically by `tools/fetch_ringsdb_deck.py`, `fetchDeck`, and `PlayerSettingsModal`'s row + prefill (Task 4). The `pending_player_settings` → `pending_deck_entry` → `pending_deck_resolve` chain is specified once (Task 4) and used identically by both twins' main loops, web's only divergence being the `Promise`-then-reopen shape required by `fetch`'s asynchrony (Step 8).

**Cross-twin:** every task is web-first-then-firmware; the one genuine twin divergence (web resolves via async `fetch`, firmware via a sync flash read of a pre-fetched file) is called out in Architecture and threaded consistently through Task 2 and Task 4.
