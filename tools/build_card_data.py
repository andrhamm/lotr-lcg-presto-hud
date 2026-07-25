"""Compile the DragnCards cardDb.tsv into normalized JSON (index + scenarios +
player DB + rules). Source of truth is the pinned TSV; never hand-edit the
output. See docs/superpowers/specs/2026-07-24-card-data-pipeline-design.md."""
import csv, json, re, os, shutil, argparse, datetime, urllib.request, urllib.error, io

HEADER = ["databaseId","name","imageUrl","cardBack","type","packName",
          "deckbuilderQuantity","setUuid","numberInPack","encounterSet","unique",
          "sphere","traits","keywords","cost","side","engagementCost","threat",
          "willpower","attack","defense","hitPoints","questPoints","victoryPoints",
          "cornerText","text","shadow","tags"]

_INT_FIELDS = ("cost","engagementCost","threat","willpower","attack","defense",
               "hitPoints","questPoints","victoryPoints")

# Curated pack -> {cycle, source, date} metadata, keyed by the scenario's
# `packName` exactly as it appears in the DragnCards TSV. Every pack that
# currently produces a scenario in docs/data/index.json must have an entry
# here; PACK_META.get(pack, {}) falls back to cycle "Other" / source
# "official" for anything not yet catalogued (new packs upstream).
#
# Cycle + source verified 2026-07-24 against Hall of Beorn's product-by-cycle
# listing (https://hallofbeorn.com/LotR/Products), Wikipedia's "The Lord of
# the Rings: The Card Game" article, and Fantasy Flight's own product pages;
# ALeP (A Long-extended Party, https://alongextendedparty.com/) membership
# checked against alongextendedparty.com/available-content/. See
# .superpowers/sdd/task-2-report.md for the full citation trail — notably,
# "The Dark of Mirkwood" is an OFFICIAL FFG scenario pack (MEC102, part of
# the 2022-23 "Revised Content" relaunch, re-releasing the two quests from
# the "Two-Player Limited Edition Starter"), not ALeP as originally assumed.
# No ALeP scenario currently appears in the upstream TSV, so no pack below
# is "alep" yet; ALeP's real product names (for future reference) are
# Children of Eorl / The Aldburg Plot / Fire on the Eastemnet / The Gap of
# Rohan / The Glittering Caves / Mustering of the Rohirrim / Blood in the
# Isen (Oaths of the Rohirrim cycle), The Shire's Reckoning / Strange News
# in Bree / Fangs in the Dark / The Brandywine Pursuit (Fell Summer cycle),
# and the standalone The Scouring of the Shire / The Nine are Abroad / The
# Siege of Erebor / The Hobbit / The Mirror of Galadriel.
#
# Release dates (B-data, catalog-enrichment plan Task 2) - "YYYY-MM", keyed
# by the same exact packName strings as PACK_META itself (grouped the same
# way, purely so the two are easy to eyeball against each other; this dict
# carries no other structure). RELEASE_DATES.get(p) is None both for a pack
# genuinely absent from the dict and for one present with an explicit None
# value - _official() below doesn't need to (and doesn't) distinguish them.
#
# Sourced 2026-07-24 from two independent, actively-maintained community
# databases, cross-checked against each other at month granularity and
# against Wikipedia's cycle-level year table as a coarse sanity check:
#   - Hall of Gondor - Release Dates (US): https://hallofgondor.com/release-dates/
#     A page maintained specifically to track this, citing an FFG "News" post
#     per product.
#   - RingsDB's public pack API: https://ringsdb.com/api/public/packs/
#     (RingsDB is the LOTR-LCG deckbuilder in the NetrunnerDB/ThronesDB
#     family; its own Hall of Beorn credit + card-level RingsDbCardId cross-
#     references from hallofbeorn.com's Export API corroborate it as an
#     established, actively-relied-upon community data source, not a
#     one-off.)
# 87 of 106 packs got a verified month:
#   - 82 packs: both sources agree at month granularity (many to the exact
#     day).
#   - 5 packs (Dark of Mirkwood, Race Across Harad, Revised Core Set, The
#     Mountain of Fire, The Mumakil) had the two sources disagree; resolved
#     via a primary FFG source (an archive.org-cached FFG "News" article,
#     since fantasyflightgames.com itself 403s automated fetches - same
#     block task-2-report.md hit) or, where no primary article was found
#     directly, weekday plausibility (this dataset's releases land on a
#     Wed/Thu/Fri 79% of the time - 89 of RingsDB's 113 dated packs; a
#     challenger date landing on a Mon/Sat/Sun lost the tie-break). Two of
#     these five (Dark of Mirkwood, Revised
#     Core Set) are the 2022 "Revised Content" relaunch, where RingsDB's
#     date is demonstrably wrong by years (e.g. it dates "The Dark of
#     Mirkwood" to 2011-04, two days after Core Set - clearly a mis-keyed
#     row, not a real alternate release) - not used as a tie-break
#     participant for those two, only HoG + a direct primary citation were
#     used. See docs/superpowers/plans/2026-07-24-catalog-enrichment.md
#     Task 2 for the full per-pack sourcing trail.
#   - 19 packs stay None, not guessed: 18 are Nightmare Decks, which neither
#     source dates at all (their release wasn't tracked as a distinct
#     "pack" by either site); the 19th, Two-Player Limited Edition Starter,
#     had an unresolved year-scale conflict (RingsDB: 2017-07; Hall of
#     Gondor: 2018-08, the date it was confirmed bundled into that year's
#     "Limited Collector's Edition" alongside the Steam early-access
#     launch - it's plausible that's a re-bundling of an already-released
#     2017 product rather than its original release, but no primary source
#     for a standalone 2017 release was found to confirm that reading, so
#     the conflict is left unresolved rather than guessed).
# Wikipedia's own product table was cross-checked too (used only as a coarse
# sanity check, not a tie-break input): 22 of the 31 comparable entries
# match at the year level; the other 9 are all cases where Wikipedia's bare
# "release year" cell is exactly one year earlier than what HoG+RingsDB
# agree on together (day-exact, for several of the nine) - consistent with
# Wikipedia recording an announcement/expected year rather than the actual
# ship date for those particular rows, not with a problem in this dict.
RELEASE_DATES = {
    # Core Set
    'Core Set': "2011-04", 'Core Set - Nightmare': None, 'Revised Core Set': "2022-01",
    # Shadows of Mirkwood
    'Shadows of Mirkwood - Nightmare': None, 'The Hunt for Gollum': "2011-07",
    'Conflict at the Carrock': "2011-08", 'A Journey to Rhosgobel': "2011-09",
    'The Hills of Emyn Muil': "2011-09", 'The Dead Marshes': "2011-11",
    'Return to Mirkwood': "2011-11",
    # The Dwarrowdelf
    'Dwarrowdelf - Nightmare': None, 'Khazad-dum': "2012-01",
    'Khazad-dum - Nightmare': None, 'The Redhorn Gate': "2012-03",
    'Road to Rivendell': "2012-03", 'The Watcher in the Water': "2012-04",
    'The Long Dark': "2012-05", 'Foundations of Stone': "2012-06",
    'Shadow and Flame': "2012-08",
    # Against the Shadow
    'Against the Shadow - Nightmare': None, 'Heirs of Numenor': "2012-11",
    'Heirs of Numenor - Nightmare': None, 'The Stewards Fear': "2013-05",
    'The Druadan Forest': "2013-05", 'Encounter at Amon Din': "2013-07",
    'Assault on Osgiliath': "2013-08", 'The Blood of Gondor': "2013-10",
    'The Morgul Vale': "2013-11",
    # The Ring-maker
    'Ringmaker - Nightmare': None, 'The Voice of Isengard': "2014-02",
    'The Voice of Isengard - Nightmare': None, 'The Dunland Trap': "2014-06",
    'The Three Trials': "2014-07", 'Trouble in Tharbad': "2014-08",
    'The Nin-in-Eilph': "2014-10", "Celebrimbor's Secret": "2014-11",
    'The Antlered Crown': "2014-12",
    # The Angmar Awakened
    'Angmar Awakened - Nightmare': None, 'The Lost Realm': "2015-04",
    'The Lost Realm - Nightmare': None, 'The Wastes of Eriador': "2015-07",
    'Escape from Mount Gram': "2015-07", 'Across the Ettenmoors': "2015-09",
    'The Treachery of Rhudaur': "2015-09", 'The Battle of Carn Dum': "2015-11",
    'The Dread Realm': "2015-12",
    # The Dream-chaser
    'Dreamchaser - Nightmare': None, 'The Grey Havens': "2016-02",
    'The Grey Havens - Nightmare': None, 'Flight of the Stormcaller': "2016-05",
    'The Thing in the Depths': "2016-06", 'Temple of the Deceived': "2016-06",
    'The Drowned Ruins': "2016-09", 'A Storm on Cobas Haven': "2016-09",
    'The City of Corsairs': "2016-10",
    # The Haradrim
    'The Sands of Harad': "2016-11", 'The Mumakil': "2017-02",
    'Race Across Harad': "2017-03", 'Beneath the Sands': "2017-05",
    'The Black Serpent': "2017-07", 'The Dungeons of Cirith Gurat': "2017-12",
    'The Crossings of Poros': "2018-02",
    # Ered Mithrin
    'The Wilds of Rhovanion': "2018-06", 'The Withered Heath': "2018-08",
    'Roam Across Rhovanion': "2018-10", 'Fire in the Night': "2018-12",
    'The Ghost of Framsburg': "2019-02", 'Mount Gundabad': "2019-04",
    'The Fate of Wilderland': "2019-06",
    # The Vengeance of Mordor
    'A Shadow in the East': "2019-08", 'Wrath and Ruin': "2019-11",
    'The City of Ulfast': "2020-01", 'Challenge of the Wainriders': "2020-02",
    'Under the Ash Mountains': "2020-06", 'The Land of Sorrow': "2020-08",
    'The Fortress of Nurn': "2020-10",
    # Hobbit Saga
    'The Hobbit - Over Hill and Under Hill': "2012-08",
    'The Hobbit - Over Hill and Under Hill - Nightmare': None,
    'The Hobbit - On the Doorstep': "2013-02",
    'The Hobbit - On the Doorstep - Nightmare': None,
    # LotR Saga
    'The Black Riders': "2013-09", 'The Black Riders - Nightmare': None,
    'The Road Darkens': "2014-10", 'The Road Darkens - Nightmare': None,
    'The Treason of Saruman': "2015-04", 'The Treason of Saruman - Nightmare': None,
    'The Land of Shadow': "2015-11", 'The Land of Shadow - Nightmare': None,
    'The Flame of the West': "2016-08", 'The Mountain of Fire': "2017-10",
    # Standalone/PoD
    'The Massing at Osgiliath': "2011-09", 'The Battle of Lake-Town': "2012-10",
    'The Stone of Erech': "2013-10", 'The Old Forest': "2014-11",
    'The Ruins of Belegost': "2016-02", 'Fog on the Barrow-downs': "2015-01",
    'Murder at the Prancing Pony': "2016-02", 'The Siege of Annuminas': "2017-03",
    'Attack on Dol Guldur': "2018-02", "The Wizard's Quest": "2019-06",
    'The Woodland Realm': "2019-06", 'The Mines of Moria': "2020-07",
    'Escape from Khazad-dum': "2020-07", 'The Hunt for the Dreadnaught': "2020-12",
    'Two-Player Limited Edition Starter': None, 'Dark of Mirkwood': "2022-02",
}

def _official(cycle, packs):
    return {p: {"cycle": cycle, "source": "official", "date": RELEASE_DATES.get(p)} for p in packs}

PACK_META = {}
PACK_META.update(_official("Core Set", [
    "Core Set", "Core Set - Nightmare", "Revised Core Set",
]))
PACK_META.update(_official("Shadows of Mirkwood", [
    "Shadows of Mirkwood - Nightmare",
    "The Hunt for Gollum", "Conflict at the Carrock", "A Journey to Rhosgobel",
    "The Hills of Emyn Muil", "The Dead Marshes", "Return to Mirkwood",
]))
PACK_META.update(_official("The Dwarrowdelf", [
    "Dwarrowdelf - Nightmare",
    "Khazad-dum", "Khazad-dum - Nightmare", "The Redhorn Gate",
    "Road to Rivendell", "The Watcher in the Water", "The Long Dark",
    "Foundations of Stone", "Shadow and Flame",
]))
PACK_META.update(_official("Against the Shadow", [
    "Against the Shadow - Nightmare",
    "Heirs of Numenor", "Heirs of Numenor - Nightmare", "The Stewards Fear",
    "The Druadan Forest", "Encounter at Amon Din", "Assault on Osgiliath",
    "The Blood of Gondor", "The Morgul Vale",
]))
PACK_META.update(_official("The Ring-maker", [
    "Ringmaker - Nightmare",
    "The Voice of Isengard", "The Voice of Isengard - Nightmare",
    "The Dunland Trap", "The Three Trials", "Trouble in Tharbad",
    "The Nin-in-Eilph", "Celebrimbor's Secret", "The Antlered Crown",
]))
PACK_META.update(_official("The Angmar Awakened", [
    "Angmar Awakened - Nightmare",
    "The Lost Realm", "The Lost Realm - Nightmare", "The Wastes of Eriador",
    "Escape from Mount Gram", "Across the Ettenmoors",
    "The Treachery of Rhudaur", "The Battle of Carn Dum", "The Dread Realm",
]))
PACK_META.update(_official("The Dream-chaser", [
    "Dreamchaser - Nightmare",
    "The Grey Havens", "The Grey Havens - Nightmare", "Flight of the Stormcaller",
    "The Thing in the Depths", "Temple of the Deceived", "The Drowned Ruins",
    "A Storm on Cobas Haven", "The City of Corsairs",
]))
PACK_META.update(_official("The Haradrim", [
    "The Sands of Harad", "The Mumakil", "Race Across Harad",
    "Beneath the Sands", "The Black Serpent", "The Dungeons of Cirith Gurat",
    "The Crossings of Poros",
]))
PACK_META.update(_official("Ered Mithrin", [
    "The Wilds of Rhovanion", "The Withered Heath", "Roam Across Rhovanion",
    "Fire in the Night", "The Ghost of Framsburg", "Mount Gundabad",
    "The Fate of Wilderland",
]))
PACK_META.update(_official("The Vengeance of Mordor", [
    "A Shadow in the East", "Wrath and Ruin", "The City of Ulfast",
    "Challenge of the Wainriders", "Under the Ash Mountains",
    "The Land of Sorrow", "The Fortress of Nurn",
]))
PACK_META.update(_official("Hobbit Saga", [
    "The Hobbit - Over Hill and Under Hill",
    "The Hobbit - Over Hill and Under Hill - Nightmare",
    "The Hobbit - On the Doorstep", "The Hobbit - On the Doorstep - Nightmare",
]))
PACK_META.update(_official("LotR Saga", [
    "The Black Riders", "The Black Riders - Nightmare",
    "The Road Darkens", "The Road Darkens - Nightmare",
    "The Treason of Saruman", "The Treason of Saruman - Nightmare",
    "The Land of Shadow", "The Land of Shadow - Nightmare",
    "The Flame of the West", "The Mountain of Fire",
]))
PACK_META.update(_official("Standalone/PoD", [
    # Gen Con / Fellowship / custom-scenario-kit PoD releases, plus the two
    # standalone starter/scenario-pack products (same two quests, two
    # printings — see note above).
    "The Massing at Osgiliath", "The Battle of Lake-Town", "The Stone of Erech",
    "The Old Forest", "The Ruins of Belegost", "Fog on the Barrow-downs",
    "Murder at the Prancing Pony", "The Siege of Annuminas",
    "Attack on Dol Guldur", "The Wizard's Quest", "The Woodland Realm",
    "The Mines of Moria", "Escape from Khazad-dum", "The Hunt for the Dreadnaught",
    "Two-Player Limited Edition Starter", "Dark of Mirkwood",
]))

def parse_int(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None

def parse_tags(s):
    s = (s or "").strip()
    if not s:
        return None, None
    try:
        return json.loads(s), None
    except (ValueError, TypeError):
        return None, s

def parse_tsv(stream):
    reader = csv.DictReader(stream, fieldnames=None, delimiter="\t",
                            quoting=csv.QUOTE_NONE)
    return [row for row in reader]

def _s(row, key):
    v = (row.get(key) or "").strip()
    return v or None

def normalize_face(row):
    face = {"side": _s(row, "side"),
            "name": _s(row, "name"),
            "image": _s(row, "imageUrl"),
            "keywords": _s(row, "keywords"),
            "cornerText": _s(row, "cornerText"),
            "text": _s(row, "text"),
            "shadow": _s(row, "shadow")}
    for k in _INT_FIELDS:
        face[k] = parse_int(row.get(k))
    return face

def group_cards(rows):
    order, groups = [], {}
    for row in rows:
        cid = (row.get("databaseId") or "").strip()
        if not cid:
            continue
        if cid not in groups:
            groups[cid] = []
            order.append(cid)
        groups[cid].append(row)
    cards = []
    for cid in order:
        grp = sorted(groups[cid], key=lambda r: (r.get("side") or ""))
        first = grp[0]
        tags, tags_raw = parse_tags(first.get("tags"))
        cards.append({
            "id": cid,
            "type": (first.get("type") or "").strip(),
            "name": _s(first, "name"),
            "pack": _s(first, "packName"),
            "encounterSet": _s(first, "encounterSet"),
            "number": parse_int(first.get("numberInPack")),
            "cardBack": _s(first, "cardBack"),
            "setUuid": _s(first, "setUuid"),
            "quantity": parse_int(first.get("deckbuilderQuantity")),
            "unique": (first.get("unique") or "").strip().lower() in ("true","1","yes"),
            "sphere": _s(first, "sphere"),
            "traits": _s(first, "traits"),
            "keywords": _s(first, "keywords"),
            "image": _s(first, "imageUrl"),
            "tags": tags,
            "tagsRaw": tags_raw,
            "faces": [normalize_face(r) for r in grp],
        })
    return cards

def slugify(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

def is_sailing(card):
    return any("sailing" in (f.get("keywords") or "").lower() for f in card["faces"])

def _quest_card_view(card):
    qp = next((f["questPoints"] for f in card["faces"] if f["questPoints"] is not None), 0)
    vic = next((f["victoryPoints"] for f in card["faces"] if f["victoryPoints"] is not None), None)
    return {
        "questPoints": qp,
        "victory": vic,
        "sailing": is_sailing(card),
        "faces": [{"side": f["side"], "name": f["name"], "text": f["text"]} for f in card["faces"]],
    }

def _branch_kind(cards):
    joined = " ".join((f["text"] or "") for c in cards for f in c["faces"] if f["side"] == "B").lower()
    if "at random" in joined:
        return "random"
    if "first player" in joined or "choose" in joined or "chosen" in joined:
        return "choice"
    return "random"

def shape_quest(quest_cards):
    by_stage, skipped = {}, 0
    for card in quest_cards:
        stage = card["faces"][0].get("cost")
        if stage is None:
            skipped += 1
            continue
        by_stage.setdefault(stage, []).append(card)
    stages = []
    for stage in sorted(by_stage):
        cards = sorted(by_stage[stage], key=lambda c: c["number"] if c["number"] is not None else 0)
        entry = {"stage": stage, "cards": [_quest_card_view(c) for c in cards]}
        if len(cards) > 1:
            entry["branch"] = _branch_kind(cards)
        stages.append(entry)
    return {"stages": stages, "skipped": skipped}

DISCLAIMER = ("Unofficial companion. Not affiliated with or endorsed by Fantasy "
              "Flight Games. The Lord of the Rings is a trademark of Middle-earth "
              "Enterprises. Card text © FFG.")

def _type_key(t):
    if not t:
        return "unknown"
    parts = t.split()
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

def _is_mode(card):
    return (card["name"] or "").strip().endswith("Mode")

def _scenario_kind(cards):
    types = {c["type"] for c in cards}
    if "Quest" in types:
        return "quest"
    if "Nightmare" in types:
        return "nightmare"
    if types <= {"Campaign", "Objective"} and any(c["type"] == "Campaign" for c in cards):
        return "campaign"
    return "encounter"

def build_outputs(stream, meta=None, enrichment=None):
    meta = meta or {"generated": "", "source": ""}
    enr_scenarios = (enrichment or {}).get("scenarios") or {}
    cards = group_cards(parse_tsv(stream))
    enc_groups, enc_name, player_groups, player_name, rules = {}, {}, {}, {}, []
    for c in cards:
        if c["type"] == "Rules":
            rules.append(c)
        elif c["encounterSet"]:
            s = slugify(c["encounterSet"])
            enc_groups.setdefault(s, []).append(c)
            enc_name.setdefault(s, c["encounterSet"])
        else:
            pk = c["pack"] or "unknown"
            s = slugify(pk)
            player_groups.setdefault(s, []).append(c)
            player_name.setdefault(s, pk)

    scenarios, index_scn = {}, []
    for slug, group in enc_groups.items():
        enc = enc_name[slug]
        quest_cards = [c for c in group if c["type"] == "Quest"]
        modes = [c for c in group if c["type"] in ("Campaign", "Objective") and _is_mode(c)]
        campaign = [c for c in group if c["type"] == "Campaign" and not _is_mode(c)]
        used = set(id(c) for c in quest_cards + modes + campaign)
        encounter = {}
        for c in group:
            if id(c) in used:
                continue
            encounter.setdefault(_type_key(c["type"]), []).append(c)
        quest = shape_quest(quest_cards) if quest_cards else None
        sailing = bool(quest_cards) and any(is_sailing(c) for c in quest_cards)
        scenarios[slug] = {
            "slug": slug, "name": enc, "pack": group[0]["pack"],
            "kind": _scenario_kind(group), "sailing": sailing,
            "quest": quest, "encounter": encounter, "modes": modes, "campaign": campaign,
        }
        pack_meta = PACK_META.get(group[0]["pack"], {})
        index_entry = {
            "slug": slug, "name": enc, "pack": group[0]["pack"],
            "kind": scenarios[slug]["kind"],
            "stageCount": len(quest["stages"]) if quest else 0,
            "sailing": sailing,
            "hasNightmare": slugify(enc + " - Nightmare") in enc_groups,
            "modes": [m["name"] for m in modes],
            "counts": {k: len(v) for k, v in encounter.items()},
            "cycle": pack_meta.get("cycle", "Other"),
            "source": pack_meta.get("source", "official"),
            "releaseDate": pack_meta.get("date"),
        }
        # B-data (catalog-enrichment plan, Task 3): merge Hall of Beorn's
        # sets-to-gather enrichment when tools/build_hob_enrichment.py's
        # output is available (see _load_enrichment/main). Optional and
        # absent-tolerant by construction - enr_scenarios is {} when there's
        # no enrichment at all, and .get(slug) is None for any scenario the
        # fetcher skipped, so both fields below are simply omitted rather
        # than written as null/empty in either case.
        included_sets = (enr_scenarios.get(slug) or {}).get("includedSets")
        if included_sets:
            scenarios[slug]["includedSets"] = included_sets
            index_entry["gatherCount"] = len(included_sets)
        index_scn.append(index_entry)

    packs, players_index = {}, []
    for slug, group in player_groups.items():
        by_type = {}
        for c in group:
            by_type.setdefault(_type_key(c["type"]), []).append(c)
        packs[slug] = {"pack": player_name[slug], "cards": by_type}
        players_index.append({"slug": slug, "name": player_name[slug], "cardCount": len(group)})

    # Provenance (Task 3, Step 2): only claim Hall of Beorn as a source when
    # enrichment was actually merged above - an absent/corrupt enrichment
    # file must not leave a stale credit behind (see _load_enrichment).
    source = meta["source"]
    if enr_scenarios:
        source += "; hallofbeorn.com/Export/Search (sets-to-gather enrichment)"
    index = {
        "generated": meta["generated"], "source": source, "disclaimer": DISCLAIMER,
        "scenarios": sorted(index_scn, key=lambda s: (s["pack"] or "", s["name"])),
        "packs": sorted(players_index, key=lambda p: p["name"]),
        "rules": bool(rules),
    }
    return {"index": index, "scenarios": scenarios,
            "players": {"index": players_index, "packs": packs}, "rules": rules}

RAW = "https://raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/{sha}/tsvs/cardDb.tsv"
API = "https://api.github.com/repos/seastan/dragncards-lotrlcg-plugin/commits/main"
SOURCE_FILE = os.path.join(os.path.dirname(__file__), "data", "cardDb.SOURCE.txt")
# tools/build_hob_enrichment.py's default --out - see _load_enrichment/main.
ENRICHMENT_FILE = os.path.join(os.path.dirname(__file__), "data", "enrichment.json")

def _load_enrichment(path):
    """Best-effort load of tools/build_hob_enrichment.py's output
    ({"scenarios": {slug: {"includedSets": [...]}}}}) for build_outputs()'s
    optional merge. Returns None on ANY failure - file absent (enrichment
    was never fetched: offline dev, or a CI run whose enrichment step hit
    its continue-on-error), corrupt JSON, or an unexpected shape - never
    raises. Matches quest_catalog.py's load_icons()/load_player_side_
    quests() posture: a missing optional data source degrades silently
    rather than failing the caller (see the plan's Global Constraints -
    enrichment must never fail a catalog build or a Pages deploy)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data.get("scenarios"), dict) else None
    except Exception:
        return None

def _dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def emit(outputs, out_dir):
    for sub in ("scenarios", "players"):
        d = os.path.join(out_dir, sub)
        if os.path.isdir(d):
            shutil.rmtree(d)
    _dump(outputs["index"], os.path.join(out_dir, "index.json"))
    for slug, scn in outputs["scenarios"].items():
        _dump(scn, os.path.join(out_dir, "scenarios", slug + ".json"))
    _dump(outputs["players"]["index"], os.path.join(out_dir, "players", "index.json"))
    for slug, pack in outputs["players"]["packs"].items():
        _dump(pack, os.path.join(out_dir, "players", slug + ".json"))
    _dump(outputs["rules"], os.path.join(out_dir, "rules.json"))

def _read_pin():
    with open(SOURCE_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("sha="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("No sha in %s — run with --refresh once." % SOURCE_FILE)

def _refresh_pin():
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github.sha"})
    try:
        with urllib.request.urlopen(req) as resp:
            sha = resp.read().decode().strip()
    except urllib.error.URLError as e:
        raise SystemExit("Failed to resolve upstream sha from %s: %s" % (API, e))
    os.makedirs(os.path.dirname(SOURCE_FILE), exist_ok=True)
    with open(SOURCE_FILE, "w", encoding="utf-8") as f:
        f.write("url=%s\nsha=%s\n" % (RAW, sha))
    return sha

def main(argv=None):
    ap = argparse.ArgumentParser(description="Compile DragnCards cardDb.tsv to JSON.")
    ap.add_argument("--refresh", action="store_true", help="re-pin to upstream HEAD sha")
    ap.add_argument("--out", default=os.path.join("docs", "data"))
    ap.add_argument("--enrichment", default=ENRICHMENT_FILE,
                     help="optional tools/build_hob_enrichment.py output to merge "
                          "in (default: %(default)s); a missing or corrupt file is "
                          "silently skipped - see CLAUDE.md's Card data section")
    args = ap.parse_args(argv)
    if not os.path.exists(SOURCE_FILE) and not args.refresh:
        raise SystemExit("No pin file — run once with --refresh.")
    sha = _refresh_pin() if args.refresh else _read_pin()
    print("Fetching cardDb.tsv at %s ..." % sha)
    try:
        with urllib.request.urlopen(RAW.format(sha=sha)) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise SystemExit("Failed to fetch TSV at sha %s: %s\nTry --refresh to re-pin." % (sha, e))
    enrichment = _load_enrichment(args.enrichment)
    if enrichment is None:
        print("build_card_data: no sets-to-gather enrichment at %r - scenarios will "
              "fall back to their own set only (run tools/build_hob_enrichment.py to "
              "add it)" % args.enrichment)
    else:
        print("build_card_data: merging sets-to-gather enrichment for %d scenarios "
              "from %r" % (len(enrichment.get("scenarios") or {}), args.enrichment))
    out = build_outputs(io.StringIO(text),
                        meta={"generated": datetime.date.today().isoformat(),
                              "source": "seastan/dragncards-lotrlcg-plugin@%s tsvs/cardDb.tsv" % sha},
                        enrichment=enrichment)
    emit(out, args.out)
    print("Wrote %d scenarios, %d player packs, %d rules to %s"
          % (len(out["scenarios"]), len(out["players"]["packs"]), len(out["rules"]), args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
