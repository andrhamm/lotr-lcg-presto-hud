# RingsDB Deck Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a player attach their published RingsDB.com deck to their HUD player slot by its numeric deck ID, so the HUD can show their heroes, starting threat, and spheres without manual entry — while degrading cleanly to today's fully-manual flow whenever the deck can't be resolved (no ID entered, ID entered but not yet fetched, device offline).

**Architecture:** A new pure module (`ringsdb.py` / `docs/js/ringsdb.js`) turns a RingsDB decklist + a small set of card records into a compact `deck` summary attached to a `Player`. Resolution happens two different ways depending on twin, both producing the *same* summary shape:
- **Web** (has real internet in the browser): a live, unauthenticated `fetch()` against RingsDB's public API, verified CORS-open (`Access-Control-Allow-Origin: *`) for exactly this use — a bare, header-free `GET`.
- **Firmware** (no network stack yet — WiFi is M2, planned but unshipped; see Context): a **flash-local read** of a file pre-fetched on a networked dev machine by a new CLI tool, `tools/fetch_ringsdb_deck.py`, and deployed with the exact same `mpremote cp -r docs/data/ :/data/` step already used for the card catalog. No new deploy mechanism, no new device capability required.

Entry is via a **numeric keypad modal** (0–9 + backspace + confirm) on both twins — deck IDs are confirmed pure numeric, so a bounded-tap keypad is both sufficient and the simplest cross-twin-identical UI (see "Deck-ID entry: options considered" below for why this beats a stepper or a web-only entry path).

**Tech Stack:** ES modules (web, Canvas, `fetch`) + MicroPython (firmware, flash `json.load`); a small stdlib-only Python CLI tool (`urllib.request`, matching `tools/build_card_data.py`'s own dependency-free style); pytest + the scene layout linter.

**Context — device networking today:** `ROADMAP.md` lists **"M2 — Connectivity: WiFi provisioning..."** under **Planned** (not Shipped); `ui/screen_settings.py`'s Network tile is rendered `enabled=False` ("APPS (coming soon)"). The Presto's RP2350 does carry a real WiFi 4 / Bluetooth radio (Raspberry Pi RM2 module) per Pimoroni's own product page (https://shop.pimoroni.com/en-us/products/presto) and independent hardware writeups (e.g. https://www.cnx-software.com/2025/04/14/pimoroni-presto-raspberry-pi-rp2350-4-inch-wireless-desktop-touch-display/), so this plan's firmware-side design (pre-fetch + flash file) is a deliberate scoping choice for *today's* unshipped-networking reality, not a hardware limitation — once M2 ships, `ringsdb.py`'s `load_deck` can gain a live-fetch branch with **zero change** to `summarize_decklist` or the data shape.

**Verified against the live RingsDB API** (fetched fresh this session — see citations inline below; nothing in this plan is sourced from RingsDB's own docs alone without a live-response cross-check):

- **Decklist endpoint:** `GET https://ringsdb.com/api/public/decklist/{id}.json` — `{id}` is a bare non-negative integer (confirmed via https://ringsdb.com/api/doc, regex `\d+`; a slug-suffixed URL like the *website's* `/decklist/view/{id}/{slug}` 404s against the API). No auth. Real trimmed response (`https://ringsdb.com/api/public/decklist/20968.json`):
  ```json
  {
    "id": 20968, "name": "The Best Deck",
    "date_creation": "2021-05-28T16:25:50-04:00", "date_update": "2026-07-09T05:11:11-04:00",
    "user_id": 10363,
    "heroes": { "04101": 1, "05001": 1, "07002": 1, "22081": 1 },
    "slots": { "01014": 1, "01023": 1, "...": "...44 more entries..." },
    "sideslots": [], "version": "1.0", "is_published": true, "starting_threat": 33
  }
  ```
  No `sphere` field at the deck level — sphere comes from each hero's own card record. `starting_threat` (int) was cross-checked against the sum of its heroes' individual `threat` costs on two separate real decks and matched both times (not a coincidence to rely on blindly forever, but reliable enough to use directly rather than recomputing).
- **Card endpoint:** `GET https://ringsdb.com/api/public/card/{code}.json` (one card; also `.../cards/{pack_code}.json` for a whole pack, and `.../cards/` for all ~1315 — this plan uses the single-card form to avoid pulling the full DB just to resolve 3–4 heroes). Real trimmed response (`https://ringsdb.com/api/public/card/01001.json` — Aragorn):
  ```json
  { "code": "01001", "name": "Aragorn", "type_code": "hero", "sphere_code": "leadership",
    "sphere_name": "Leadership", "threat": 12, "willpower": 2, "attack": 3, "defense": 2,
    "health": 5, "traits": "Dúnedain. Noble. Ranger.", "pack_name": "Core Set",
    "url": "https://ringsdb.com/card/01001" }
  ```
- **Player-cards-only, confirmed by exhaustive enumeration** (not assumed): every `type_code` across all ~1315 cards in `https://ringsdb.com/api/public/cards/` is one of `hero, ally, event, attachment, treasure, contract, player-side-quest, player-objective` — no `enemy`/`location`/`treachery`/encounter-side `quest` type exists anywhere in the public API. Even `GET /api/public/scenario/{id}.json` (e.g. `.../scenario/1.json`, Passage Through Mirkwood) exposes only encounter-set **names and aggregate counts** ("normal_enemies": 16, ...), never individual encounter cards. **This plan only ever needs hero (`type_code:"hero"`) records** — well inside the verified-safe zone.
- **CORS:** documented at https://ringsdb.com/api/ ("Public API responses include a CORS header: `Access-Control-Allow-Origin:*`") and independently confirmed by inspecting live response headers on four endpoints, including a request that sent an explicit `Origin: https://andrhamm.com` header. One nuance: an `OPTIONS` preflight against `/api/public/cards/` returns `405` with no CORS headers — irrelevant as long as the fetch stays a plain, header-free `GET` (a CORS "simple request", no preflight triggered). **This plan's `fetch()` calls must not add custom headers.**
- **No documented rate limit** beyond "conform to HTTP caching best practices" (https://ringsdb.com/api/); responses carry `Cache-Control: max-age=600`. `robots.txt` (https://ringsdb.com/robots.txt) blocks several named AI-crawler user agents site-wide but does not disallow any `/api/` path — irrelevant here regardless, since this is a user's own app fetching on their own behalf, not a crawler.
- **No public username→decks lookup.** Only `GET /api/oauth2/decks` ("all decks of the authenticated user") exists for that, and it requires registered OAuth2 client credentials (email the maintainer). **A player must already know their own deck's numeric ID** (visible in the deck's RingsDB URL) — there is no in-app deck *search*, only deck *entry by ID*. Out of scope to build OAuth for this plan; noted as a possible future enhancement, not attempted here.
- **Copyright:** RingsDB's footer states card text/graphics are FFG-copyrighted and the site is unaffiliated with FFG. This plan never stores or displays `text`/`flavor` (rules text) from RingsDB — only structural fields (`name`, `sphere_code`, `threat`, hero portraits are **not** fetched/displayed either, keeping this well inside the same "structural data only" posture the existing `tools/build_card_data.py` pipeline already takes with DragnCards).

## Deck-ID entry: options considered

The task brief named two starting options; both have real problems once the ID format was actually verified (pure numeric, but **not small** — real IDs like `20968`/`45843` run 4–6 digits):

| Option | Problem |
|---|---|
| Plain `+`/`-` stepper (single-unit) | Unusable at this ID range — dialing "45843" one unit at a time is up to 45,843 taps. Steppers in this codebase (`ui/widgets.py:stepper`) are for small bounded ranges (threat, quest points), not open-ended IDs. |
| Web-side entry that syncs to the device | There is **no existing sync channel** between the web twin (`localStorage`) and the firmware (flash) — they are two fully independent persistence stores today, bridged only by the maintainer's manual, main-session-only `mpremote cp` deploy step (`CLAUDE.md`, "Device access"). Building a *new* live sync path (QR code, file export/import, etc.) just to carry a 6-digit number is a disproportionate amount of new infrastructure for what it saves. |

**Recommendation (this plan's default): a 12-key numeric keypad modal** (0–9, backspace, confirm) — bounded to `len(digits) + 1` taps regardless of ID size, implementable on both twins with the existing `Button`/`bevel` widgets, and needs no new plumbing beyond the modal itself. Web *additionally* gets a plain text `<input>`-free convenience: none needed, actually — since the keypad is fast enough that there's no reason to diverge the two twins' input UI here (unlike, say, free-text search, which would legitimately need a browser text field). **If the user prefers web-side entry with sync instead:** the change would be to add a `deck_id` field to the web `Player Setup`/`PlayerSettingsModal` UI as a plain text `<input type="number">`, plus a new export/import mechanism (e.g. a small JSON the maintainer copies via `mpremote cp` alongside the catalog deploy) carrying just `{player_index: deck_id}` pairs for the firmware to pick up — strictly more moving parts than the keypad for a small typing-convenience gain, which is why it isn't the default here.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then firmware.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter.
- **RingsDB data is optional at every layer, exactly like the quest catalog** (`quest_catalog.py`'s own documented convention: "on ANY failure ... returns None/[] so the caller falls back to today's manual entry"). A player with no deck linked, an unresolved ID, or a fetch/file-read failure must see the *exact* Player Setup / Player Settings experience that exists today — this plan is strictly additive.
- **Fetches are bare, header-free `GET`s** (see CORS note above) — never add custom headers to a RingsDB request, or the (header-free-only) CORS allowance breaks.
- **Never fetch or store RingsDB `text`/`flavor` fields** (FFG-copyrighted rules text) — only `code`, `name`, `sphere_code`, `threat`, `pack_name` are read off a card record, and only for `type_code == "hero"` records.
- **`docs/data/` stays gitignored and regenerated, never hand-edited** (Iron rule from `CLAUDE.md`) — pre-fetched decks land in `docs/data/decks/`, following the exact same rule as the rest of `docs/data/`.
- **Deck IDs are per-player, not per-game** — `Player.deck_id`/`Player.deck`, not a `GameState`-level field.
- Touch targets ≥ 24px each dimension; everything within 480×480; no text collisions (linter-enforced).

## File structure

- `ringsdb.py` (new) + `docs/js/ringsdb.js` (new) — pure `summarize_decklist` + the twin-specific I/O wrapper (`fetch_deck` web / `load_deck` firmware).
- `tools/fetch_ringsdb_deck.py` (new) — CLI pre-fetch tool, writes `docs/data/decks/<id>.json`.
- `gamestate.py` (`Player.__init__`, `to_dict`/`from_dict`) + `docs/js/gamestate.js` (mirror) — `deck_id`/`deck` fields.
- `ui/modals.py` (new `DeckEntryModal`; extend `PlayerSettingsModal`) + `docs/js/screens.js` (mirror).
- `tests/test_ringsdb.py` (new), `tests/test_fetch_ringsdb_deck.py` (new), `tests/test_deck_entry_modal.py` (new), `tests/scenes.py`.

---

### Task 1: `ringsdb.py` — pure deck-summary logic + `Player` model fields

**Files:**
- Create: `ringsdb.py`
- Modify: `gamestate.py` (`Player.__init__` ~`:132-140`, `GameState.to_dict`/`from_dict`'s player loop)
- Test: `tests/test_ringsdb.py` (new)

**Interfaces (Produces):**
- `summarize_decklist(decklist, heroes_by_code) -> dict` — pure. `decklist` is a raw RingsDB decklist response (the shape above); `heroes_by_code` is `{code: card_record}` for exactly the codes in `decklist["heroes"]`. Returns:
  ```
  {"name": str, "starting_threat": int,
   "heroes": [{"code": str, "name": str, "sphere_code": str, "threat": int}, ...],
   "spheres": [str, ...]}   # deduped sphere_codes, first-appearance order
  ```
  `heroes` is ordered by `decklist["heroes"]` dict iteration order (RingsDB's own hero ordering). A hero code missing from `heroes_by_code` (a resolution partial-failure) is skipped, not a crash — `heroes` may end up shorter than `decklist["heroes"]`.
- `Player` gains `deck_id = None` (str; the raw entered numeric ID, kept even unresolved) and `deck = None` (the `summarize_decklist` shape, or `None`).
- Serialization: `deck_id`/`deck` added to the player dicts in `to_dict`/`from_dict` (default `None`/`None`).

- [ ] **Step 1: Write the failing test** (`tests/test_ringsdb.py`), using the real (trimmed) fixtures from the Context section above so the test doubles as a regression check against RingsDB's actual shape:

```python
import ringsdb

DECKLIST = {
    "id": 20968, "name": "The Best Deck", "starting_threat": 33,
    "heroes": {"04101": 1, "05001": 1, "07002": 1, "22081": 1},
    "slots": {"01014": 1, "01023": 1}, "sideslots": [], "version": "1.0",
}
HEROES_BY_CODE = {
    "04101": {"code": "04101", "name": "Éowyn", "type_code": "hero", "sphere_code": "spirit", "threat": 5},
    "05001": {"code": "05001", "name": "Glorfindel", "type_code": "hero", "sphere_code": "lore", "threat": 10},
    "07002": {"code": "07002", "name": "Bilbo Baggins", "type_code": "hero", "sphere_code": "lore", "threat": 9},
    # 22081 deliberately absent - a partial-resolution failure
}

def test_summarize_decklist_basic_shape():
    d = ringsdb.summarize_decklist(DECKLIST, HEROES_BY_CODE)
    assert d["name"] == "The Best Deck"
    assert d["starting_threat"] == 33
    assert [h["code"] for h in d["heroes"]] == ["04101", "05001", "07002"]
    assert d["heroes"][0] == {"code": "04101", "name": "Éowyn", "sphere_code": "spirit", "threat": 5}

def test_summarize_decklist_dedupes_spheres_in_first_appearance_order():
    d = ringsdb.summarize_decklist(DECKLIST, HEROES_BY_CODE)
    assert d["spheres"] == ["spirit", "lore"]     # lore appears twice (Glorfindel, Bilbo), once in output

def test_summarize_decklist_skips_unresolved_hero_codes():
    d = ringsdb.summarize_decklist(DECKLIST, {})
    assert d["heroes"] == [] and d["spheres"] == []
    assert d["name"] == "The Best Deck" and d["starting_threat"] == 33   # deck-level fields unaffected

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
type_code=="hero" records. See docs/superpowers/plans/
2026-07-24-ringsdb-integration.md for the verified API shapes this mirrors.
"""


def summarize_decklist(decklist, heroes_by_code):
    """decklist: a raw RingsDB /api/public/decklist/<id>.json response.
    heroes_by_code: {code: card_record} for (at least) decklist["heroes"]'s
    codes - a code missing here (partial fetch failure) is skipped, not a
    crash. Returns {"name", "starting_threat", "heroes": [...], "spheres": [...]}."""
    heroes = []
    spheres = []
    for code in decklist.get("heroes", {}):
        card = heroes_by_code.get(code)
        if not card:
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

Add to `gamestate.py`'s `Player.__init__` (next to `self.commit_touched = False`):
```python
        self.deck_id = None    # RingsDB numeric deck id, kept even if unresolved
        self.deck = None       # ringsdb.summarize_decklist() shape, or None
```
Add to the player dict comprehension in `to_dict`: `"deck_id": p.deck_id, "deck": p.deck,`. In `from_dict`'s player loop: `p.deck_id = pd.get("deck_id"); p.deck = pd.get("deck")`.

- [ ] **Step 4: Run tests → PASS.** `python3 -m pytest tests/test_ringsdb.py -q`.

- [ ] **Step 5: Mirror in `docs/js/ringsdb.js`** (`summarizeDecklist`, `DECKS_PATH` unused on web — see Task 2 for `fetchDeck`) and `docs/js/gamestate.js` (`deckId`/`deck`... **no** — keep dict keys `deck_id`/`deck` snake_case in `toDict`/`fromDict` per the established convention; camelCase is fine for any local JS variables only).

- [ ] **Step 6: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(ringsdb): deck-summary logic + Player.deck_id/deck fields"`.

---

### Task 2: `tools/fetch_ringsdb_deck.py` — the pre-fetch CLI + web's live `fetchDeck`

**Files:**
- Create: `tools/fetch_ringsdb_deck.py`
- Modify: `docs/js/ringsdb.js` (add `fetchDeck`)
- Test: `tests/test_fetch_ringsdb_deck.py` (new)

**Interfaces (Produces):**
- CLI: `python3 tools/fetch_ringsdb_deck.py <deck_id> [<deck_id> ...]` — for each ID, fetches `https://ringsdb.com/api/public/decklist/<id>.json`, then one `https://ringsdb.com/api/public/card/<code>.json` per hero code, calls `ringsdb.summarize_decklist`, and writes `docs/data/decks/<id>.json`. Prints one line per ID (`"20968: The Best Deck (4 heroes)"` or `"99999999: fetch failed - <reason>"`) and exits non-zero if *every* ID failed (matches `build_card_data.py`'s own pattern of a clear pass/fail signal for CI/manual runs).
- `fetchDeck(deckId)` (web, async) — `docs/js/ringsdb.js`: the same fetch-then-summarize sequence, browser `fetch()` instead of `urllib.request`. Returns the `summarize_decklist` shape, or `null` on any failure (network error, 404 for a bad ID, malformed JSON) — never throws, matching `quest_catalog.js`'s `loadPlayerSideQuests()` failure-swallowing convention.

- [ ] **Step 1: Write the failing test** (`tests/test_fetch_ringsdb_deck.py`) — the network call itself is not host-tested (no live network in CI, matching every other `tools/`-fetches-the-internet precedent in this repo), but the **argument parsing and file-writing** are, via a monkeypatched fetch function:

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

def test_fetch_one_returns_none_on_failure(tmp_path, monkeypatch):
    def boom(url):
        raise OSError("network down")
    monkeypatch.setattr(tool, "_get_json", boom)
    assert tool.fetch_one("999", out_dir=str(tmp_path)) is None
    assert not os.path.exists(tmp_path / "999.json")
```

- [ ] **Step 2: Run to verify it fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/fetch_ringsdb_deck.py`:**

```python
"""Pre-fetch RingsDB decks for offline/on-device use: writes docs/data/
decks/<id>.json (gitignored, regenerated - never hand-edit, same rule as
the rest of docs/data/). Run on a networked machine; the normal
`mpremote cp -r docs/data/ :/data/` deploy step ships the result to the
device, which then reads it via ringsdb.load_deck() with no network of
its own. See docs/superpowers/plans/2026-07-24-ringsdb-integration.md.

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
    # good-citizenship) assumes no custom headers; see the plan's CORS note.
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def fetch_one(deck_id, out_dir=DEFAULT_OUT_DIR):
    """Fetch + summarize one deck; write <out_dir>/<deck_id>.json. Returns
    the summary dict, or None (and writes nothing) on any failure."""
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

- [ ] **Step 5: Try it live (manual, not part of the pytest gate)** — `python3 tools/fetch_ringsdb_deck.py 20968` against the real RingsDB API; confirm `docs/data/decks/20968.json` is written and matches the shape from Task 1's fixtures. Confirm `docs/data/decks/` is covered by the existing `docs/data/` gitignore entry (`git status` shows it untracked, not "would be added").

- [ ] **Step 6: Implement `fetchDeck` in `docs/js/ringsdb.js`:**
```js
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

- [ ] **Step 7: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(ringsdb): fetch_ringsdb_deck CLI + web fetchDeck"`.

---

### Task 3: `DeckEntryModal` — numeric keypad (both twins)

**Files:**
- Modify: `ui/modals.py` (new `DeckEntryModal`), `docs/js/screens.js` (mirror)
- Modify: `tests/scenes.py`
- Test: `tests/test_deck_entry_modal.py` (new)

**Interfaces (Produces):**
- `DeckEntryModal(game, player_index)` / `DeckEntryModal(game, playerIndex)` — internal state `self.digits` (str, up to 8 chars, built by keypad taps). `on_button` returns `"redraw"` for digit/backspace taps, `"close"` for Cancel or a successful Confirm (which — see Task 4 — hands off resolution to the caller rather than fetching itself, keeping this modal a pure input widget), `None` for a disabled Confirm (empty `digits`).
- Layout: header "Link RingsDB Deck"; a large digit readout (or "Enter deck ID" placeholder) at y≈80; a 4×3 keypad grid (digits 1-9, blank, 0, backspace) filling y≈130-370, each key ≥ 56×56 (comfortably over the 24px minimum); footer Cancel/Confirm at y=404 (reuse `_footer`).

- [ ] **Step 1: Write the failing test** (`tests/test_deck_entry_modal.py`):

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
    for d in "209":
        btn = next(b for b in m.buttons if b.id == ("digit", d))
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
    confirm = next(b for b in m.buttons if b.id[0] == "confirm")
    assert m.on_button(confirm) is None

def test_confirm_closes_with_digits_and_sets_deck_id():
    g = _game()
    m = DeckEntryModal(g, 1)
    m.digits = "20968"
    _draw(m, g)
    confirm = next(b for b in m.buttons if b.id[0] == "confirm")
    assert m.on_button(confirm) == "close"
    assert g.players[1].deck_id == "20968"

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

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement `DeckEntryModal` in `ui/modals.py`:**

```python
class DeckEntryModal:
    """Numeric-keypad entry for a RingsDB deck id - see docs/superpowers/
    plans/2026-07-24-ringsdb-integration.md for why a keypad (bounded taps)
    beats a +/- stepper at this id range. Only sets player.deck_id on
    confirm; resolving it to player.deck (fetch/load) is the caller's job
    (PlayerSettingsModal, Task 4) - kept out of this modal so it stays a
    pure input widget with no I/O of its own."""

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
        if k == "save":               # _footer's confirm id is "save"
            if not self.digits:
                return None
            self.game.players[self.i].deck_id = self.digits
            return "close"
        return None
```

(`_footer`'s Confirm button carries id `("save",)` per its existing signature (`save_label="Confirm"` only changes the *label*, not the id) — Task 3's test above matches on `b.id[0] == "confirm"`; **use `"save"` in the real implementation** to match `_footer`'s actual contract, and update the test's `confirm = next(b for b in m.buttons if b.id[0] == "save")` accordingly before running it. This is called out explicitly here because `_footer` is shared code the implementer must check, not re-derive.)

- [ ] **Step 4: Run tests → PASS** (after the `"save"`-vs-`"confirm"` id correction above).

- [ ] **Step 5: Mirror in `docs/js/screens.js`** (`DeckEntryModal`, same `KEYS` grid, `digits` state).

- [ ] **Step 6: Add scenes** to `tests/scenes.py`: `deck_entry_empty`, `deck_entry_partial` (a few digits typed). Render: `python3 tools/preview.py deck_entry_partial /tmp/de.png` — confirm the keypad grid is legible and every key clears 24px. `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 7: Full suite + commit.** `git add -A && git commit -m "feat(ringsdb): DeckEntryModal numeric keypad"`.

---

### Task 4: Wire it up — `PlayerSettingsModal` deck row + resolution + starting-threat prefill

**Files:**
- Modify: `ui/modals.py` (`PlayerSettingsModal`), `docs/js/screens.js` (mirror)
- Modify: `main.py`, `docs/js/main.js` (pending-flag dispatch — deck resolution needs flash/network I/O, same constraint that already forces `pending_quest_card`/`pending_side_quest_pick` through the main loop)
- Test: extend `tests/test_deck_entry_modal.py` or a new `tests/test_player_settings_deck.py`

**Interfaces:**
- `PlayerSettingsModal` gains a "RingsDB Deck" row between "Elimination level" and the footer (y≈330): shows "Not linked" (no `deck_id`), `"Deck #<id> - not synced"` (`deck_id` set, `deck` still `None`), or the resolved deck's name + `", ".join(sphere_code for sphere_code in deck["spheres"])` + hero names (`deck` set). Tapping it sets `self.game.pending_deck_entry = self.i` and returns `"close"` — same "close self, flag the next modal, let the main loop open it" pattern already used by `pending_quest_card`/`pending_side_quest_pick` (a modal can't stack another modal, and reading `/data/decks/*.json` or a live `fetch` is I/O the modal's synchronous `on_button` can't perform mid-tap).
- New `GameState` field `pending_deck_entry = None` (int player-index, or `None`), serialized like its `pending_*` siblings.
- Main-loop block (modeled on the `pending_quest_card` block): when `modal is None and game.pending_deck_entry is not None`, open `DeckEntryModal(game, game.pending_deck_entry)`; clear the flag.
- **Resolving** a newly-entered `deck_id` (after `DeckEntryModal` closes with one set) is itself a second pending-flag hop, because resolution is I/O: reuse the *same* `pending_deck_entry` flag, now interpreted as "re-open Player Settings and resolve" — concretely, `DeckEntryModal.on_button`'s `"save"` case additionally sets `game.pending_deck_resolve = self.i` (a second int-or-None flag) instead of returning straight to nothing; the main loop, on seeing it, calls `ringsdb.load_deck(deck_id)` (firmware) or the web equivalent (async `fetchDeck`, Task 2) and stores the result on `player.deck` before reopening `PlayerSettingsModal(game, i)` so the row immediately reflects the outcome (resolved name, or still "not synced" on failure).
- When resolution succeeds, `PlayerSettingsModal.__init__` initializes `self.st` from `player.deck["starting_threat"]` **only if** `player.deck` was just newly resolved *and* the player hasn't already customized `starting_threat` this session — simplest correct rule that needs no extra state: `self.st = player.deck["starting_threat"] if (player.deck and player.starting_threat == 0) else player.starting_threat`. (Rationale: a freshly-added player defaults `starting_threat=0` in every path that doesn't already set it deliberately; a real, already-configured player is never silently overwritten.) The stepper is still editable afterward — this only seeds the initial value shown.

- [ ] **Step 1: Write the failing tests** (extend `tests/test_deck_entry_modal.py`):

```python
def test_deck_row_tap_sets_pending_deck_entry_and_closes():
    g = _game()
    from ui.modals import PlayerSettingsModal
    m = PlayerSettingsModal(g, 0)
    _draw(m, g)
    row = next(b for b in m.buttons if b.id[0] == "deck_row")
    assert m.on_button(row) == "close"
    assert g.pending_deck_entry == 0

def test_deck_entry_save_sets_pending_deck_resolve():
    g = _game()
    m = DeckEntryModal(g, 1)
    m.digits = "20968"
    _draw(m, g)
    save = next(b for b in m.buttons if b.id[0] == "save")
    m.on_button(save)
    assert g.players[1].deck_id == "20968"
    assert g.pending_deck_resolve == 1

def test_player_settings_prefills_starting_threat_from_resolved_deck():
    g = _game()
    g.players[0].starting_threat = 0
    g.players[0].deck = {"name": "X", "starting_threat": 33, "heroes": [], "spheres": []}
    from ui.modals import PlayerSettingsModal
    m = PlayerSettingsModal(g, 0)
    assert m.st == 33

def test_player_settings_does_not_override_customized_threat():
    g = _game()
    g.players[0].starting_threat = 28   # already set deliberately
    g.players[0].deck = {"name": "X", "starting_threat": 33, "heroes": [], "spheres": []}
    from ui.modals import PlayerSettingsModal
    m = PlayerSettingsModal(g, 0)
    assert m.st == 28
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement.** `gamestate.py`: add `self.pending_deck_entry = None` and `self.pending_deck_resolve = None` to `__init__` (both plain `int|None`), plus `to_dict`/`from_dict` entries (default `None`).

`PlayerSettingsModal.__init__`: change `self.st = p.starting_threat` to the prefill rule above. `draw`: add the deck row before `_footer(...)`:
```python
        p = self.game.players[self.i]
        dy = 330
        icons.draw(d, icons.LEADERSHIP if False else icons.THREAT, 30, dy, pal.tan)  # placeholder glyph; swap for a deck/card icon if one exists in ui/icons.py
        if p.deck:
            label = "%s (%s)" % (p.deck["name"], ", ".join(p.deck["spheres"]) or "?")
        elif p.deck_id:
            label = "Deck #%s - not synced" % p.deck_id
        else:
            label = "Not linked"
        row = Button(("deck_row",), 16, dy - 6, 452, 40)
        bevel(d, pal, row.x, row.y, row.w, row.h, pal.card, t=2)
        text_left(d, pal, "RingsDB Deck", 30, dy - 20, 1, pal.dim)
        text_left(d, pal, label, 30, dy + 8, 2, pal.tan)
        self.buttons.append(row)
```
`on_button`: add `if k == "deck_row": self.game.pending_deck_entry = self.i; return "close"`.

`DeckEntryModal.on_button`'s `"save"` case becomes:
```python
        if k == "save":
            if not self.digits:
                return None
            self.game.players[self.i].deck_id = self.digits
            self.game.pending_deck_resolve = self.i
            return "close"
```

Main loop (`main.py`, modeled on the `pending_quest_card` block):
```python
        if modal is None and active == "play" and game.pending_deck_entry is not None:
            from ui.modals import DeckEntryModal
            modal = DeckEntryModal(game, game.pending_deck_entry)
            game.pending_deck_entry = None
            dirty = True
            continue
        if modal is None and active == "play" and game.pending_deck_resolve is not None:
            import ringsdb
            i = game.pending_deck_resolve
            game.pending_deck_resolve = None
            p = game.players[i]
            if p.deck_id:
                p.deck = ringsdb.load_deck(p.deck_id)   # None on any failure - fine, row shows "not synced"
            from ui.modals import PlayerSettingsModal
            modal = PlayerSettingsModal(game, i)
            dirty = True
            continue
```

- [ ] **Step 4: Run tests → PASS.**

- [ ] **Step 5: Mirror in `docs/js/screens.js`/`docs/js/main.js`** — the web resolve step is `async`: `game.pending_deck_resolve` triggers `fetchDeck(p.deck_id).then(deck => { p.deck = deck; modal = new PlayerSettingsModal(game, i); })` (same `Promise`-then-reopen idiom already used for `pending_quest_card`'s tips fetch).

- [ ] **Step 6: Add a scene** for the resolved-deck row (`player_settings_deck_linked`) and the unresolved row (`player_settings_deck_unsynced`) in `tests/scenes.py`. `python3 tools/preview.py player_settings_deck_linked /tmp/psd.png` — confirm the row text doesn't collide with the Elimination stepper above it or the footer below. `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 7: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(ringsdb): PlayerSettingsModal deck linking + starting-threat prefill"`.

---

### Task 5: Integration — live web fetch + on-device pre-fetched read + offline fallback

**Files:** none new (verification + any fixes surfaced).

- [ ] **Step 1: Web, live.** Serve the site, open Player Settings for P1, tap the deck row, key in `20968` (a real published deck, per Task 2's manual check), Confirm. Confirm the row updates to show "The Best Deck" + spheres, and the Starting threat stepper reflects `33` if P1 hadn't been customized yet. Check the Network tab: exactly the expected `GET`s (one decklist + one per hero), no extra headers, all 200s.
- [ ] **Step 2: Web, bad ID.** Enter an ID with no published deck (e.g. `999999999`). Confirm the row falls back to "Deck #999999999 - not synced" and nothing else breaks.
- [ ] **Step 3: Firmware, pre-fetched.** `python3 tools/fetch_ringsdb_deck.py 20968`, then the normal deploy (`python3 tools/build_card_data.py && mpremote cp -r docs/data/ :/data/`). On-device, link P1 to `20968` via the keypad; confirm it resolves **instantly** (local flash read, no spinner) with the same summary as the web run.
- [ ] **Step 4: Firmware, not pre-fetched.** On-device, link a player to an ID that was never fetched. Confirm the row shows "not synced" and the game is otherwise fully playable (manual starting-threat entry, etc.) — the additive/never-blocking constraint holds.
- [ ] **Step 5: Full suite.** `python3 -m pytest tests/ -q` green; every new scene renders cleanly via `tools/preview.py`.
- [ ] **Step 6: Report** the four walkthroughs (screenshots / device photos where relevant) and commit any fixes found.

---

## Self-Review

**Spec coverage:** endpoints + real fetched examples → Context section (decklist + card, both trimmed-but-real, with source URLs); player-cards-only confirmed by exhaustive `type_code` enumeration, not assumption → Context + Task 1's fixtures only ever construct hero records; deck-entry mechanism → "Deck-ID entry: options considered" picks the keypad with the stepper/web-sync alternatives' concrete costs stated (no bare TBD); what the HUD does with a linked deck (heroes, starting threat, sphere info) → Task 1 (`summarize_decklist`) + Task 4 (`PlayerSettingsModal` row + prefill); offline/on-device degradation → the `tools/fetch_ringsdb_deck.py` pre-fetch-to-flash design (Task 2) plus the explicit "not synced" / never-blocking states verified end-to-end in Task 5.

**Placeholder scan:** Tasks 1-4 each carry a complete, runnable test file and complete implementation code, not sketches. One deliberate internal correction is flagged in-line rather than silently fixed: Task 3's own draft test uses `"confirm"` where the shared `_footer` helper actually emits `"save"` — called out explicitly (with the fix) rather than left as a latent bug, since `_footer` is existing shared code a fresh implementer must check rather than re-derive.

**Type consistency:** `summarize_decklist(decklist, heroes_by_code)`'s return shape is defined once in Task 1 and consumed identically by `tools/fetch_ringsdb_deck.py` (Task 2), `fetchDeck` (Task 2), and `PlayerSettingsModal`'s row rendering + prefill rule (Task 4). The `pending_deck_entry`/`pending_deck_resolve` two-flag handoff is specified once (Task 4) and used identically by `DeckEntryModal`'s save handler and the main-loop blocks in both twins.

**Cross-twin:** every task is web-first-then-firmware; the one genuine twin divergence (web resolves via async `fetch`, firmware via a sync flash read of a pre-fetched file) is called out up front in Architecture and threaded consistently through Task 2 (two implementations of the same summary contract) and Task 4 (the `Promise`-then-reopen vs. synchronous-then-reopen main-loop handling).
