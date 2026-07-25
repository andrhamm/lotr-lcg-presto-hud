"""Quest catalog: cycle/source grouping over the M4-A card-data index, for
the quest-picker screens (Pick Cycle / Choose Scenario) — M4-B, Task 3.

`group_by_cycle`/`cycles_for` are pure and host-tested (tests/test_quest_
catalog.py). `load_index`/`load_scenario` are thin flash-read wrappers and
are NOT host-tested — there is no /data/ directory on the dev host, only on
the device flash filesystem (see docs/js/quest_catalog.js for the web twin,
which fetches the same paths relative to the Pages root instead).
"""

import json
import re

# Verified product/cycle order (see docs/superpowers/plans/
# 2026-07-24-quest-picker-bcore.md Task-2 findings — includes the "Ered
# Mithrin" cycle the original brief omitted). Cycle names not in this list
# sort immediately before "Other" (see _cycle_rank) rather than raising.
CYCLE_ORDER = [
    "Core Set", "Shadows of Mirkwood", "The Dwarrowdelf", "Against the Shadow",
    "The Ring-maker", "The Angmar Awakened", "The Dream-chaser", "The Haradrim",
    "Ered Mithrin", "The Vengeance of Mordor", "Hobbit Saga", "LotR Saga",
    "Standalone/PoD",
    # Fan-made (A Long Extended Party). These only ever appear under the
    # Scenario Source screen's community option - group_by_cycle filters on
    # `source` first - so they never interleave with the official cycles
    # above. Order and names come from the DragnCards plugin's own menu
    # files; see tools/alep.py.
    "ALeP - Children of Eorl & Oaths of the Rohirrim",
    "ALeP - The Shire's Reckoning & Fell Summer",
    "ALeP - Print on Demand",
    "ALeP - Other",
    "Other",
]

INDEX_PATH = "/data/index.json"
SCENARIO_PATH = "/data/scenarios/%s.json"
PLAYERS_INDEX_PATH = "/data/players/index.json"
PLAYERS_PACK_PATH = "/data/players/%s.json"
ICONS_PATH = "/data/icons.json"
TIPS_PATH = "/data/tips.json"

_REPEAT_HYPHENS = re.compile(r"-{2,}")
_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")


def slugify(name):
    """A display name (e.g. a "sets to gather" row label) -> the same slug
    shape tools/build_card_data.py's own slugify() produces (mirrored, not
    imported - tools/ is host-only build tooling, this module ships to the
    device/browser runtime): lowercase, any run of non-alphanumerics
    becomes one hyphen, no leading/trailing hyphen. Never raises (falsy
    input -> "").

    "The Steward's Fear" -> "the-steward-s-fear" - the exact "-s-" shape
    normalize_icon_key()'s possessive rule exists to undo."""
    s = (name or "").strip().lower()
    s = _NON_ALNUM_RUN.sub("-", s)
    return s.strip("-")


def _cycle_rank(cycle):
    """Sort key: CYCLE_ORDER position. A cycle name absent from the list
    (shouldn't happen given build_card_data.py's own "Other" fallback, but
    kept defensive) ranks just before "Other" rather than falling off the
    end or raising."""
    if cycle in CYCLE_ORDER:
        return CYCLE_ORDER.index(cycle)
    return CYCLE_ORDER.index("Other") - 0.5


def _earliest_date(scenarios):
    """The group's display date: the earliest non-null releaseDate among its
    scenarios (YYYY-MM strings sort lexicographically = chronologically), or
    None if every scenario's releaseDate is null (true for all scenarios as
    of Task 2 — B-data is expected to fill these in)."""
    dates = [s["releaseDate"] for s in scenarios if s.get("releaseDate")]
    return min(dates) if dates else None


def group_by_cycle(scenarios, source):
    """Group `scenarios` (index.json `scenarios[]` entries) by cycle for one
    picker source ("official"/"alep"), for the Pick Cycle / Choose Scenario
    screens.

    - Keeps only playable quests (stageCount > 0), excluding non-quest sets
      (encounter, campaign) and Nightmare variants. Nightmare is matched both by
      `kind=="nightmare"` and by the "<base name> - Nightmare" naming, because
      some Nightmare decks ship replacement quest cards and so land as
      `kind=="quest"`. They surface via the Scenario Options Mode toggle, never
      as separate pickable rows.
    - Groups ordered by CYCLE_ORDER (stable: ties keep first-seen order).
    - Scenarios within a group ordered by `name`.

    Returns [{"cycle": str, "date": str|None, "scenarios": [entry, ...]}].
    """
    groups = {}
    for scn in scenarios:
        if (scn.get("source") != source or scn.get("kind") == "nightmare"
                or scn.get("stageCount", 0) <= 0
                or (scn.get("name") or "").endswith(" - Nightmare")):
            continue
        groups.setdefault(scn.get("cycle", "Other"), []).append(scn)

    out = []
    for cycle in sorted(groups, key=_cycle_rank):
        scns = sorted(groups[cycle], key=lambda s: s.get("name", ""))
        out.append({"cycle": cycle, "date": _earliest_date(scns), "scenarios": scns})
    return out


def cycles_for(index, source):
    """[{"cycle", "date", "count"}] for the Pick Cycle screen — same
    filtering/order as group_by_cycle, over a whole loaded index.json dict
    (as returned by load_index())."""
    groups = group_by_cycle(index.get("scenarios", []), source)
    return [{"cycle": g["cycle"], "date": g["date"], "count": len(g["scenarios"])}
            for g in groups]


def load_index():
    """Read the whole catalog index from flash. Thin wrapper, not host-tested."""
    with open(INDEX_PATH) as f:
        return json.load(f)


def load_scenario(slug):
    """Read one scenario's full stage/card data from flash. Thin wrapper,
    not host-tested."""
    with open(SCENARIO_PATH % slug) as f:
        return json.load(f)


def side_quests(player_db):
    """Flatten every pack's cards["sideQuest"] into a name-sorted list of
    {"id","name","points","sphere","pack"} for the side-quest picker
    (M4-B sidequest, Task 1). `player_db` is a list of loaded pack dicts
    (players/<pack>.json shape - see tools/build_card_data.py's emit()) or a
    dict of them keyed by slug (players/index.json's "slug" field); either
    is accepted since callers may already have one or the other on hand.

    `points` is the first non-null questPoints across the card's faces, else
    0 - 2 of the 14 known player side quests are variable "X" quests with
    every face's questPoints null (Protect the Innocent, Rally the West);
    those show 0 here and the player edits the real value once seated."""
    packs = player_db.values() if isinstance(player_db, dict) else player_db
    out = []
    for pack in packs:
        pack_name = pack.get("pack", "")
        cards = (pack.get("cards") or {}).get("sideQuest") or []
        for card in cards:
            points = 0
            for face in card.get("faces") or []:
                qp = face.get("questPoints")
                if qp is not None:
                    points = qp
                    break
            out.append({"id": card.get("id"), "name": card.get("name"),
                        "points": points, "sphere": card.get("sphere"),
                        "pack": pack_name})
    out.sort(key=lambda s: s["name"] or "")
    return out


def load_player_side_quests():
    """Read every pack listed in players/index.json (a bare JSON array of
    {"slug","name","cardCount"}, per build_card_data.py's emit()) and
    flatten via side_quests(). Thin flash-read wrapper, not host-tested (see
    the module docstring) - on ANY failure (no /data/ deploy yet, a missing
    or corrupt pack file, ...) returns [] so the side-quest picker's caller
    falls back to today's manual "+ Side quest" entry rather than erroring
    (per the plan's Global Constraints: catalog data is optional at
    runtime)."""
    try:
        with open(PLAYERS_INDEX_PATH) as f:
            index = json.load(f)
        packs = []
        for entry in index:
            with open(PLAYERS_PACK_PATH % entry["slug"]) as f:
                packs.append(json.load(f))
        return side_quests(packs)
    except Exception:
        return []


def location_set_slugs(scenario):
    """The scenarios/<slug>.json files that between them hold every location
    this scenario can put into play: its "sets to gather" (the committed Hall
    of Beorn enrichment's `includedSets`, slugified), or its own slug alone
    when it has no gather list.

    The fallback is not a rare path - the enrichment covers 108 scenarios and
    the rest fall back here, which is exactly why the picker keeps its manual
    stepper (see LocationPickModal)."""
    scn = scenario or {}
    sets = scn.get("includedSets") or []
    if sets:
        return [slugify(name) for name in sets]
    return [scn["slug"]] if scn.get("slug") else []


def locations_for(scenario, packs):
    """Every location `scenario` can put into play, as a name-sorted list of
    {"id","name","points","threat","set"} for the location picker.

    The union is load-bearing. A scenario's own scenarios/<slug>.json carries
    only cards whose encounterSet IS that scenario's set, so Passage Through
    Mirkwood's own file holds 2 of its 6 locations - the other 4 live in the
    Dol Guldur Orcs and Spiders of Mirkwood files it gathers. `packs` is a
    dict of loaded scenario files keyed by slug; a gather-list name with no
    file (14 of 309 catalog-wide) is skipped rather than raising, and packs
    NOT in the gather list are ignored.

    `points`/`threat` are the first non-null questPoints/threat across the
    card's faces, else 0 - 15 catalog locations are variable or
    condition-explored with a null questPoints on every face, and 21 are
    multi-face. Same rule side_quests() uses for the variable "X" quests;
    those show 0 and the player edits the real value at the table.

    Deduped by (name, encounterSet): the same card can be reachable through
    two gather entries. `quantity` is deliberately NOT carried - the HUD does
    not model the encounter deck and must not imply it knows what is left in
    it."""
    packs = packs or {}
    out = []
    seen = {}
    for slug in location_set_slugs(scenario):
        pack = packs.get(slug)
        if not pack:
            continue
        for card in (pack.get("encounter") or {}).get("location") or []:
            key = (card.get("name"), card.get("encounterSet"))
            if key in seen:
                continue
            seen[key] = True
            points = 0
            threat = 0
            for face in card.get("faces") or []:
                if not points and face.get("questPoints") is not None:
                    points = face["questPoints"]
                if not threat and face.get("threat") is not None:
                    threat = face["threat"]
            out.append({"id": card.get("id"), "name": card.get("name"),
                        "points": points, "threat": threat,
                        "set": card.get("encounterSet")})
    out.sort(key=lambda l: l["name"] or "")
    return out


def load_locations(slug):
    """Read scenario `slug`'s own card file plus every file on its gather
    list from flash, and flatten via locations_for(). Thin flash-read
    wrapper, not host-tested (see the module docstring) - on ANY failure (no
    /data/ deploy yet, an unpicked or uncatalogued quest, a corrupt file,
    ...) returns [] so LocationPickModal opens straight on its manual
    stepper rather than erroring (per the plan's Global Constraints: catalog
    data is optional at runtime). Individual missing set files are already
    skipped by locations_for, so one absent set never costs the others."""
    if not slug:
        return []
    try:
        scenario = load_scenario(slug)
    except Exception:
        return []
    packs = {}
    for set_slug in location_set_slugs(scenario):
        try:
            with open(SCENARIO_PATH % set_slug) as f:
                packs[set_slug] = json.load(f)
        except Exception:
            continue
    try:
        return locations_for(scenario, packs)
    except Exception:
        return []


def normalize_icon_key(slug):
    """Fold a catalog encounterSet slug or a docs/data/icons.json key onto a
    common form so icon_for() can match across the small, mostly-cosmetic
    differences between the two sources (our catalog slugs come from set
    names; the icon pack's come from its own filenames) - apostrophes
    rendered as "-s-"/"-s", a leading "the-" article, doubled hyphens, and
    Nightmare-suffixed variants of an otherwise identical set. Never raises
    (falsy input -> "").

    Order matters: nightmare-suffix is dropped before the possessive fix so
    "...-s-nightmare" can't leave a dangling "-s"; "the-" is stripped after,
    so a normalized "the-...-s-..." lines up with a plain "...-..." key."""
    if not slug:
        return ""
    s = slug.lower()
    if s.endswith("-nightmare"):
        s = s[:-len("-nightmare")]
    s = s.replace("-s-", "s-")
    if s.endswith("-s"):
        s = s[:-2] + "s"
    if s.startswith("the-"):
        s = s[len("the-"):]
    return _REPEAT_HYPHENS.sub("-", s)


def icon_for(slug, icons):
    """The rasterized mask (a list[int], see tools/build_icons.py) for
    catalog `slug` out of a loaded `icons` dict (load_icons()'s "icons"
    map), or None if there's no reasonable match - the caller (icon_slot())
    keeps its placeholder glyph in that case, never a crash or a blank hole.

    Three tries, cheapest/most-precise first: the exact slug; the
    normalized slug tried as-is against `icons`' (unnormalized) keys; and
    finally both sides normalized, for the cases where each source keeps a
    different one of two forms (e.g. one has a "the-" article the other
    dropped). Never raises - falsy `slug`/`icons` just fall through to
    None."""
    if not slug or not icons:
        return None
    if slug in icons:
        return icons[slug]
    norm = normalize_icon_key(slug)
    if norm in icons:
        return icons[norm]
    for key, mask in icons.items():
        if normalize_icon_key(key) == norm:
            return mask
    return None


def load_icons():
    """Read the rasterized set/scenario icon masks from flash
    (tools/build_icons.py's docs/data/icons.json "icons" map). Thin
    wrapper, not host-tested (see the module docstring) - on ANY failure
    (no /data/ deploy yet, build_icons.py found no SVG pack and wrote an
    empty map, a corrupt file, ...) returns {} so icon_for() always misses
    and every icon_slot() falls back to its placeholder glyph rather than
    erroring (per the plan's Global Constraints: catalog data is optional
    at runtime)."""
    try:
        with open(ICONS_PATH) as f:
            return json.load(f).get("icons", {})
    except Exception:
        return {}


def tips_for(slug, stage, tips):
    """{"tips": [...], "attribution": {...}} for catalog `slug` at `stage`
    (a stage NUMBER - card["stage"], not an index into game.stages - `tips`
    keys its "stages" map by stage number as a string; `stage` may be
    passed as either an int or a str), or None when there is nothing to
    show (unknown slug, or an entry whose general/stages both come up
    empty for this stage) - the modal's Tips button stays in its disabled
    state in that case (M4-B tips, Task 2).

    Merges that stage's own notes with the scenario-wide `general` notes,
    stage-specific first (a player mid-stage cares about this stage's
    branch-specific gotchas before the scenario's general threat-watch
    advice). Never raises - a falsy/malformed `tips` (e.g. {} from a
    load_tips() failure) just means every lookup misses."""
    entry = (tips or {}).get(slug)
    if not entry:
        return None
    stage_tips = (entry.get("stages") or {}).get(str(stage)) or []
    general = entry.get("general") or []
    merged = list(stage_tips) + list(general)
    if not merged:
        return None
    return {"tips": merged, "attribution": entry.get("attribution") or {}}


def load_tips():
    """Read the per-scenario strategy tips from flash (tools/build_tips.py's
    docs/data/tips.json "scenarios" map). Thin wrapper, not host-tested (see
    the module docstring) - on ANY failure (no /data/ deploy yet, tips.json
    wasn't generated this build, a corrupt file, ...) returns {} so
    tips_for() always misses and the Tips button stays in its disabled
    state rather than erroring (per the plan's Global Constraints: tips are
    optional at runtime)."""
    try:
        with open(TIPS_PATH) as f:
            return json.load(f).get("scenarios", {})
    except Exception:
        return {}
