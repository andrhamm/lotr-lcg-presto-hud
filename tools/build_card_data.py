"""Compile the DragnCards cardDb.tsv into normalized JSON (index + scenarios +
player DB + rules). Source of truth is the pinned TSV; never hand-edit the
output. See docs/superpowers/specs/2026-07-24-card-data-pipeline-design.md."""
import csv, json, re, os, shutil, argparse, datetime, urllib.request, urllib.error, io
import sys

# The repo root, so `import quest_catalog` works when this is run as
# `python3 tools/build_card_data.py`. emit() reuses that module's
# side_quests() so the precomputed list is identical to what the runtime
# scan produced - one source of truth, not a reimplementation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alep
import corrections as corrections_mod
import quest_catalog
# For match_key(): the scenario-order table joins on a folded name, and that
# rule must have exactly one definition - the tool that writes the table.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_scenario_order

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
    # Both printings of The Oath / The Caves of Nibin-Dum date to the Dark of
    # Mirkwood release. The starter was previously None, which left the two
    # quests as the only dateless rows in the chooser - but FFG's own
    # announcement dates the pack that made them generally available: "with
    # The Dark of Mirkwood coming in the first quarter of 2022, we can finally
    # say that we fulfilled that oath" (4 Nov 2021). 2022-02 is the month the
    # two release-date sources already agreed on for that pack, and it sits
    # inside the Q1 the article states.
    #
    # This is availability, not first printing: the quests were originally
    # exclusive to the Limited Collector's Edition, whose own month neither
    # source carries. Dating them to a limited edition almost nobody could buy
    # would be the less useful of the two true answers.
    # https://www.fantasyflightgames.com/en/news/2021/11/4/the-dark-of-mirkwood/
    'Two-Player Limited Edition Starter': "2022-02",
    'Dark of Mirkwood': "2022-02",
}

def _official(cycle, packs):
    return {p: {"cycle": cycle, "source": "official", "date": RELEASE_DATES.get(p)} for p in packs}

PACK_META = {}
# "Core Set (Mirkwood Paths)", not plain "Core Set": FFG's own announcement for
# The Dark of Mirkwood (MEC102) calls its two quests "an extension of the core
# set's Mirkwood Paths campaign", and the fiction opens straight after Escape
# from Dol Guldur - "narrowly escaped from their ordeal in Dol Guldur. After a
# brief stay in Lorien..." So the campaign is five quests, not three, and the
# two Dark of Mirkwood ones belong in this cycle rather than off in the
# Standalone/PoD grab-bag where their printing history had filed them.
# https://www.fantasyflightgames.com/en/news/2021/11/4/the-dark-of-mirkwood/
#
# Hall of Beorn groups them the same way, under a "Mirkwood Paths" product.
# The pack keeps its own name ("Two-Player Limited Edition Starter" - the
# quests' original, pre-2022 printing); only the CYCLE moves.
PACK_META.update(_official("Core Set (Mirkwood Paths)", [
    "Core Set", "Core Set - Nightmare", "Revised Core Set",
    "Two-Player Limited Edition Starter", "Dark of Mirkwood",
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
    # ("Two-Player Limited Edition Starter" and "Dark of Mirkwood" used to sit
    # here. They moved up to Core Set (Mirkwood Paths) - see the note there.)
]))

def parse_int(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None

# Fields whose printed value is not always a number, and where the difference
# matters on screen. Upstream stores four distinct things in these columns and
# parse_int flattens all of them to None, which the UI cannot tell apart:
#
#   "4"  a number                     -> draw it
#   "X"  the card literally prints X  -> no number exists; show the formula, or
#        (16 threat values, 6 quest       ask the player. A 0 here is a lie, and
#         point values)                   for threat it silently under-reports
#                                        the staging total.
#   "-"  the stat does not apply      -> draw nothing at all. Lost Island has
#        (25 quest point values)          no quest points: it flips, it never
#                                        explores. A stepper here is wrong.
#   ""   absent upstream              -> unknown; treat as X's poor cousin.
#
# So the int stays where it is and a sibling marker carries the rest. Verified
# against the pinned TSV 2026-07-29 - see tools/build_advancement.py.
_MARKED_FIELDS = ("threat", "questPoints")

def parse_marker(s):
    """'x' | 'na' | None for a printed value that is not a number."""
    s = (s or "").strip()
    if not s:
        return None
    if s.upper() == "X":
        return "x"
    if s in ("-", "–", "—"):
        return "na"
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
    for k in _MARKED_FIELDS:
        mark = parse_marker(row.get(k))
        if mark:
            face[k + "Kind"] = mark
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
            "faces": _unsmear_quest_faces(_s(first, "type"),
                                          [normalize_face(r) for r in grp]),
        })
    return cards


def _unsmear_quest_faces(card_type, faces):
    """Undo an upstream defect where a Quest card's B-side text is A's text
    with B's own appended.

    A quest card is two-sided: side A carries the story and the Setup, side B
    the quest points and the stage's own effects. In 15 of the TSV's 505 quest
    pairs the B row's text is the A text CONCATENATED with B's, so the Quest
    Cards screen showed side B repeating side A - and for The Oath's stage 1,
    where B has no text of its own, the two faces read identically.

    The evidence this is a defect and not authored repetition, checked across
    all 15 at the pinned sha:

      - 490 of 505 pairs are unaffected, so it is not how the data models a
        two-sided card.
      - 12 of the 15 have NO SEPARATOR at the join - "...to the staging
        area.This stage cannot be defeated..." - which is a concatenation
        seam, not prose.
      - Every remainder is a well-formed B-side effect on its own ("Forced:",
        "When Revealed:", "This stage gets +10 quest points per player"),
        while the A part is always Setup/story.

    So where B starts with A, B's own text is the remainder; an empty
    remainder means side B prints no effect, which is a normal card. Anything
    else is left exactly as upstream has it - this never edits text, it only
    removes a duplicated prefix.
    """
    if (card_type or "").strip().lower() != "quest":
        return faces
    a_text = next((f.get("text") or "" for f in faces
                   if (f.get("side") or "").upper() == "A"), "")
    if not a_text:
        return faces
    for f in faces:
        if (f.get("side") or "").upper() != "B":
            continue
        b_text = f.get("text") or ""
        if b_text.startswith(a_text):
            f["text"] = b_text[len(a_text):].strip() or None
    return faces

def slugify(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

def is_sailing(card):
    return any("sailing" in (f.get("keywords") or "").lower() for f in card["faces"])

def _quest_card_view(card):
    qp = next((f["questPoints"] for f in card["faces"] if f["questPoints"] is not None), 0)
    vic = next((f["victoryPoints"] for f in card["faces"] if f["victoryPoints"] is not None), None)
    # A stage printing X is not a stage worth 0. Without this the view reports
    # questPoints 0 for both, and the Progress screen cannot tell "advances on
    # a condition" from "fill a bar to X".
    kind = next((f.get("questPointsKind") for f in card["faces"]
                 if f.get("questPointsKind")), None)
    view = {
        "questPoints": qp,
        "victory": vic,
        "sailing": is_sailing(card),
        "faces": [{"side": f["side"], "name": f["name"], "text": f["text"]} for f in card["faces"]],
    }
    if kind:
        view["questPointsKind"] = kind
    return view

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

def _pack_meta(pack):
    """Curated metadata for a pack. PACK_META covers every official pack;
    ALeP packs are described by tools/alep.py instead (its own cycles, and
    source "alep" so quest_catalog.group_by_cycle files them under the
    Scenario Source screen's community option). Anything else falls back to
    cycle "Other" / source "official", as before."""
    if pack in PACK_META:
        return PACK_META[pack]
    if (pack or "").startswith("ALeP - "):
        return alep.pack_meta(pack)
    return {}


def _has_nightmare(enc, source, enc_groups, group_meta):
    """Whether a Nightmare deck exists for encounter set `enc`, FROM THE SAME
    SOURCE. Official and fan-made catalogues are kept apart everywhere else
    (the Scenario Source screen, quest_catalog.group_by_cycle), and the
    Nightmare toggle must not be the one place they leak into each other: an
    official scenario offering a Nightmare mode has to mean an official
    Nightmare deck. Pure, host-tested."""
    nm = slugify(enc + " - Nightmare")
    if nm not in enc_groups:
        return False
    nm_meta = group_meta.get(nm)
    nm_source = nm_meta[1].get("source", "official") if nm_meta else "official"
    return nm_source == source


def _group_pack_meta(group):
    """Metadata for a scenario, resolved over EVERY pack its cards come from
    rather than just the first card's.

    An encounter set is not confined to one pack: ALeP ships supplementary
    packs ("ALeP - Backup", "ALeP - The Mirror of Galadriel 2") holding a few
    cards for a scenario whose main pack is elsewhere, and whichever card
    happens to sort first decides group[0]. Keying the cycle off that put The
    Brandywine Pursuit and The Mirror of Galadriel under "ALeP - Other".

    So prefer the first pack in the group that has curated metadata, and fall
    back to the first card's pack. For official scenarios this is a no-op:
    group[0]'s pack is already in PACK_META, so it wins on the first look."""
    for c in group:
        pack = c.get("pack")
        if pack in PACK_META or pack in alep.PACK_CYCLE:
            return pack, _pack_meta(pack)
    pack = group[0]["pack"]
    return pack, _pack_meta(pack)


def build_outputs(stream, meta=None, enrichment=None, extra_rows=None,
                  corrections=None):
    """Compile the card DB. `extra_rows` are additional already-parsed TSV
    rows to compile alongside the pinned cardDb.tsv - the ALeP branch's
    per-pack TSVs (see tools/alep.py), errata already folded in by the
    caller. They use the identical column set, so they simply join the row
    list before grouping."""
    meta = meta or {"generated": "", "source": ""}
    enr_scenarios = (enrichment or {}).get("scenarios") or {}
    rows = parse_tsv(stream) + list(extra_rows or [])
    # Row level, before grouping: a correction has to be able to reach `name`
    # and `encounterSet`, not just face text, and an encounterSet rewrite is
    # what makes an upstream-split scenario slug-collide back into one.
    rows, unmatched = corrections_mod.apply_corrections(rows, corrections)
    for u in unmatched:
        print("build_card_data: correction matched nothing - %s" % u)
    cards = group_cards(rows)
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

    # Resolve each set's pack/cycle/source once up front: the hasNightmare
    # probe below needs to know the SOURCE of a set other than the one being
    # built, so it can't be computed lazily inside the loop.
    group_meta = {s: _group_pack_meta(g) for s, g in enc_groups.items()}

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
        pack, pack_meta = group_meta[slug]
        source = pack_meta.get("source", "official")
        kind = _scenario_kind(group)
        # ALeP names its Nightmare sets "<Scenario> Nightmare", without the
        # " - " the official decks use, so the name-suffix rule the picker
        # relies on doesn't catch them and they land as kind "quest" (their
        # sets ship replacement quest cards - see _scenario_kind). Mark them
        # here instead, from the pack name, so they surface via the Scenario
        # Options Mode toggle like every other Nightmare deck rather than as
        # their own pickable row.
        if source == "alep" and alep.is_nightmare_pack(pack):
            kind = "nightmare"
        scenarios[slug] = {
            "slug": slug, "name": enc, "pack": pack,
            "kind": kind, "sailing": sailing,
            "quest": quest, "encounter": encounter, "modes": modes, "campaign": campaign,
        }
        index_entry = {
            "slug": slug, "name": enc, "pack": pack,
            "kind": scenarios[slug]["kind"],
            "stageCount": len(quest["stages"]) if quest else 0,
            "sailing": sailing,
            # Same-source only. ALeP's "The Withered Heath Nightmare" slugs
            # identically to the official "The Withered Heath - Nightmare"
            # that does not exist, so without this an official scenario would
            # advertise a Nightmare mode that silently loads community cards.
            "hasNightmare": _has_nightmare(enc, source, enc_groups, group_meta),
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
        # Answer "how bad can one revealed card be?" once, here, for THIS
        # scenario. The staging estimate on the play screen used to be a
        # hardcoded 3-per-player - the same number for every scenario ever
        # published - which is not an estimate, it is a constant wearing the
        # costume of a calculation. The build already holds every pack in
        # memory and knows which sets a scenario gathers, so it can say what
        # the pool's worst printed threat actually is.
        #
        # Two fields, because one number cannot tell the whole truth: a card
        # printing a literal X (Tangled Grove: "X is the number of locations in
        # the staging area") has no printed maximum at all, and the UI has to
        # say so rather than quote a number it knows is a floor.
        pool_slugs = [slug] + [slugify(n) for n in (included_sets or [])]
        worst, has_x = 0, False
        for ps in pool_slugs:
            for card in enc_groups.get(ps) or []:
                if card["type"] == "Quest":
                    continue
                for face in card["faces"]:
                    if face.get("threatKind") == "x":
                        has_x = True
                    t = face.get("threat")
                    if isinstance(t, int) and t > worst:
                        worst = t
        index_entry["maxCardThreat"] = worst
        if has_x:
            index_entry["hasXThreat"] = True
        index_scn.append(index_entry)

    packs, players_index = {}, []
    for slug, group in player_groups.items():
        by_type = {}
        for c in group:
            by_type.setdefault(_type_key(c["type"]), []).append(c)
        packs[slug] = {"pack": player_name[slug], "cards": by_type}
        players_index.append({"slug": slug, "name": player_name[slug], "cardCount": len(group)})

    # The two committed distillations. Both are our own words compiled from
    # printed card text, live in the repo, and are merged in this same pass -
    # nothing here fetches (see CLAUDE.md: prefer committing derived output to
    # re-fetching it at build time).
    adv_hits = merge_advancement(scenarios, _load_distilled(ADVANCEMENT_FILE))
    locx_hits = merge_location_x(scenarios, _load_distilled(LOCATION_X_FILE))
    if adv_hits or locx_hits:
        print("build_card_data: merged %d stage conditions and %d location X "
              "formulas" % (adv_hits, locx_hits))
    ord_hits, ord_miss = merge_scenario_order(index_scn,
                                              _load_distilled(SCENARIO_ORDER_FILE))
    if ord_hits:
        print("build_card_data: merged play order for %d scenarios (%d "
              "unordered)" % (ord_hits, ord_miss))

    # Provenance (Task 3, Step 2): only claim Hall of Beorn as a source when
    # enrichment was actually merged above - an absent/corrupt enrichment
    # file must not leave a stale credit behind (see _load_enrichment).
    source = meta["source"]
    if enr_scenarios:
        source += "; hallofbeorn.com/Export/Search (sets-to-gather enrichment)"
    index = {
        "generated": meta["generated"], "source": source, "disclaimer": DISCLAIMER,
        # Pinned beside the card TSV (tools/data/cardDb.SOURCE.txt's
        # `image_prefix=`, task 6/R5), not fetched at build time. None when
        # `meta` carries no imagePrefix (a legacy pin, or a test fixture) -
        # quest_catalog.image_prefix()/imagePrefix() both read this key and
        # treat an absent/None value the same way.
        "imagePrefix": meta.get("imagePrefix"),
        "scenarios": sorted(index_scn, key=lambda s: (s["pack"] or "", s["name"])),
        "packs": sorted(players_index, key=lambda p: p["name"]),
        "rules": bool(rules),
    }
    return {"index": index, "scenarios": scenarios,
            "players": {"index": players_index, "packs": packs}, "rules": rules}

RAW = "https://raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/{sha}/tsvs/cardDb.tsv"
API = "https://api.github.com/repos/seastan/dragncards-lotrlcg-plugin/commits/main"
# Task 6 (tablet M5): the card-image URL prefix, pinned alongside the TSV sha
# rather than fetched at build time - see the plan's ruling R5. Card records
# carry only `image: "<id>.jpg"`; this prefix plus that id is the full URL.
IMAGE_PREFIX_RAW = ("https://raw.githubusercontent.com/seastan/"
                    "dragncards-lotrlcg-plugin/{sha}/jsons/imageUrlPrefix.json")
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

# Our own corrections to the pinned upstream card DB - committed derived data,
# same posture as enrichment.json. See tools/corrections.py.
CORRECTIONS_FILE = os.path.join(os.path.dirname(__file__), "data",
                                "corrections.json")

def _load_corrections(path):
    """Best-effort load of the committed corrections table. Absent or corrupt
    degrades to {} rather than failing a catalog build - same rule as
    _load_enrichment and _load_distilled."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

ADVANCEMENT_FILE = os.path.join(os.path.dirname(__file__), "data",
                                "advancement_distilled.json")
LOCATION_X_FILE = os.path.join(os.path.dirname(__file__), "data",
                               "location_dynamic_distilled.json")
SCENARIO_ORDER_FILE = os.path.join(os.path.dirname(__file__), "data",
                                   "scenario_order.json")

def merge_scenario_order(index_scn, order_table):
    """Stamp `order` onto each index entry from the committed Hall of Beorn
    table (tools/build_scenario_order.py).

    A GLOBAL rank, not a per-cycle one: Hall of Beorn lists products
    chronologically, so one flat sequence sorts correctly even where one of our
    cycles spans several of its products (The Ring-maker holds both "The Voice
    of Isengard" and "The Ring-maker"). The per-cycle 1..n numbering the picker
    shows is a display concern and is computed at render time from this.

    Scenarios the table does not cover keep no `order` at all and sort last -
    9 of 145 at the time of writing: 5 ALeP quests Hall of Beorn does not
    index, plus 2 bonus quests it folds into their box ("Coast of Umbar" in the
    City of Corsairs pack, "The Great Goblin" in Over Hill and Under Hill).
    Inventing a position for those would be a guess.

    Absent or corrupt table: every entry keeps no order and the picker falls
    back to date-then-name, never a build failure - same posture as the
    enrichment merge.
    """
    products = (order_table or {}).get("products") or []
    if not products:
        return 0, 0
    rank, i = {}, 0
    for prod in products:
        for name in prod.get("scenarios") or []:
            k = build_scenario_order.match_key(name.replace(" (Campaign)", ""))
            rank.setdefault(k, i)
            i += 1
    hits = miss = 0
    for entry in index_scn:
        pos = rank.get(build_scenario_order.match_key(entry.get("name")))
        if pos is None:
            miss += 1
            continue
        entry["order"] = pos
        hits += 1
    return hits, miss


def _load_distilled(path):
    """Best-effort load of one of the committed distillations. Same posture as
    _load_enrichment: absent or corrupt degrades to {} rather than failing a
    catalog build. The Progress screen falls back to showing no sentence and
    no formula, which is the pre-distillation behaviour."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def merge_advancement(scenarios, distilled):
    """Attach each stage card's distilled condition, keyed slug::stage::name.

    The name comes from whichever face carries the text, B first then A --
    the same rule the extraction used, so the keys line up. Side A is
    story/setup and side B carries the quest points, but plenty of stage
    cards print their condition on only one of the two."""
    hit = 0
    for slug, scn in scenarios.items():
        for stage in ((scn.get("quest") or {}).get("stages") or []):
            for card in (stage.get("cards") or []):
                faces = card.get("faces") or []
                b = next((f for f in faces if f.get("side") == "B"), None)
                a = next((f for f in faces if f.get("side") == "A"), None)
                face = b if (b and b.get("text")) else a
                if not face:
                    continue
                entry = distilled.get("%s::%s::%s"
                                      % (slug, stage.get("stage"),
                                         face.get("name")))
                if not entry:
                    continue
                for src, dst in (("advance", "advance"), ("lose", "lose"),
                                 ("quest_points", "questPointsX")):
                    if entry.get(src):
                        # advance/lose are sentences; quest_points is the CODED
                        # X, {"text", "target", "mul", "add"} - see xtargets.py.
                        # Carried whole: the UI reads .text to show and .target
                        # to build the control, and nothing parses the prose.
                        card[dst] = entry[src]
                hit += 1
    return hit

def merge_location_x(scenarios, distilled):
    """Attach each location face's X formula, keyed encounterSet::name::side.

    Only where the face actually prints X for that stat -- the marker, not a
    null. Guarding here as well as in build_advancement.py's validator keeps
    a stale artifact from reintroducing a formula onto a card that prints a
    real number."""
    hit = 0
    for scn in scenarios.values():
        for card in ((scn.get("encounter") or {}).get("location") or []):
            es = card.get("encounterSet")
            for face in (card.get("faces") or []):
                entry = distilled.get("%s::%s::%s"
                                      % (es, face.get("name"),
                                         face.get("side") or "-"))
                if not entry:
                    continue
                for src, stat, dst in (
                        ("quest_points", "questPoints", "questPointsX"),
                        ("threat", "threat", "threatX")):
                    if entry.get(src) and face.get(stat + "Kind") == "x":
                        face[dst] = entry[src]
                        hit += 1
    return hit

def needs_refresh(out_path, refresh):
    """False when `out_path` already exists and `refresh` wasn't asked for.
    The shared guard both derived-data fetchers (tools/build_hob_enrichment.py,
    tools/build_tips.py) consult before touching the network at all.

    Their outputs — tools/data/enrichment.json and docs/data/tips.json — are
    COMMITTED derived data (aggregated set lists / our own summaries; see
    CLAUDE.md's "What may be committed"), unlike this module's own verbatim
    card DB. So the normal case — a clean checkout, a Pages build — must be a
    no-op rather than a slow re-scrape of a third-party site; regenerating is
    an explicit, local, occasional act (`--refresh`). Lives here, next to the
    build that merges the enrichment, so the policy has one home. Pure,
    host-tested."""
    return bool(refresh) or not os.path.exists(out_path)

def _dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def emit(outputs, out_dir):
    # Last stop before disk: fold everything to glyphs the device font can
    # draw. The row-level pass runs before grouping and so misses strings
    # merged in later (includedSets, stage advance conditions, the
    # disclaimer). See corrections.fold_payload.
    outputs = corrections_mod.fold_payload(outputs)
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
    # Precomputed side-quest list. The picker needs ~15 entries; finding them
    # by opening all 105 packs cost 1.6 MB of reads and 6.4 SECONDS on the
    # Presto's flash every time "+ Side quest" was tapped. The build already
    # has every pack in memory, so it answers the question once, here.
    # quest_catalog.side_quests() is the same pure function the runtime used
    # for the scan, so the emitted list is identical by construction.
    _dump(quest_catalog.side_quests(outputs["players"]["packs"]),
          os.path.join(out_dir, "players", "side_quests.json"))
    _dump(outputs["rules"], os.path.join(out_dir, "rules.json"))

def _read_pin():
    """Read (sha, image_prefix) from the pin file - one pass, one parser, so
    a new pinned field never grows a second reader (task-6 brief: "no second
    parser"). `image_prefix` is None for a legacy pin file that predates it;
    `sha` is mandatory and its absence is still a hard SystemExit."""
    sha = image_prefix = None
    with open(SOURCE_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("sha="):
                sha = line.strip().split("=", 1)[1]
            elif line.startswith("image_prefix="):
                image_prefix = line.strip().split("=", 1)[1]
    if sha is None:
        raise SystemExit("No sha in %s — run with --refresh once." % SOURCE_FILE)
    return sha, image_prefix

def _fetch_image_prefix(sha):
    """Fetch jsons/imageUrlPrefix.json at `sha` and pick the English prefix
    (falling back to Default - see task-6 brief R5). Only called from
    --refresh; a plain build never reaches this and makes no network call
    for the image prefix. Raises SystemExit on any fetch/parse failure or a
    payload with neither key, so --refresh fails loudly rather than pinning
    a stale or empty prefix."""
    try:
        with urllib.request.urlopen(IMAGE_PREFIX_RAW.format(sha=sha)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError) as e:
        raise SystemExit("Failed to fetch image prefix at sha %s: %s" % (sha, e))
    prefixes = data.get("imageUrlPrefix") or {}
    prefix = prefixes.get("English") or prefixes.get("Default")
    if not prefix:
        raise SystemExit("imageUrlPrefix.json at sha %s has no English/Default "
                         "prefix" % sha)
    return prefix

def _refresh_pin():
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github.sha"})
    try:
        with urllib.request.urlopen(req) as resp:
            sha = resp.read().decode().strip()
    except urllib.error.URLError as e:
        raise SystemExit("Failed to resolve upstream sha from %s: %s" % (API, e))
    image_prefix = _fetch_image_prefix(sha)
    os.makedirs(os.path.dirname(SOURCE_FILE), exist_ok=True)
    with open(SOURCE_FILE, "w", encoding="utf-8") as f:
        f.write("url=%s\nsha=%s\nimage_prefix=%s\n" % (RAW, sha, image_prefix))
    return sha, image_prefix

def main(argv=None):
    ap = argparse.ArgumentParser(description="Compile DragnCards cardDb.tsv to JSON.")
    ap.add_argument("--refresh", action="store_true", help="re-pin to upstream HEAD sha")
    ap.add_argument("--out", default=os.path.join("docs", "data"))
    ap.add_argument("--enrichment", default=ENRICHMENT_FILE,
                     help="optional tools/build_hob_enrichment.py output to merge "
                          "in (default: %(default)s); a missing or corrupt file is "
                          "silently skipped - see CLAUDE.md's Card data section")
    ap.add_argument("--corrections", default=CORRECTIONS_FILE,
                     help="committed corrections to the upstream card DB "
                          "(default: %(default)s); a missing or corrupt file is "
                          "silently skipped - see tools/corrections.py")
    ap.add_argument("--no-alep", action="store_true",
                     help="skip the fan-made A Long Extended Party packs "
                          "(see tools/alep.py); official cards only")
    args = ap.parse_args(argv)
    if not os.path.exists(SOURCE_FILE) and not args.refresh:
        raise SystemExit("No pin file — run once with --refresh.")
    sha, image_prefix = _refresh_pin() if args.refresh else _read_pin()
    print("Fetching cardDb.tsv at %s ..." % sha)
    try:
        with urllib.request.urlopen(RAW.format(sha=sha)) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise SystemExit("Failed to fetch TSV at sha %s: %s\nTry --refresh to re-pin." % (sha, e))
    # ALeP is fan-made content on a separate upstream branch, and it is
    # ALL-OR-NOTHING: any failure drops it entirely rather than failing the
    # build or emitting a half-catalog. A partial fetch is the dangerous
    # case - the picker would offer scenarios whose cards never arrived -
    # whereas dropping it cleanly just restores the Scenario Source screen's
    # pre-existing "No community scenarios yet". The official card DB is the
    # critical artifact and must never be held hostage to it (same posture as
    # the optional enrichment above and icons in CI).
    alep_rows, alep_sha = [], None
    if not args.no_alep:
        try:
            alep_sha, alep_names = (alep.refresh_pin() if args.refresh
                                    else alep.read_pin())
            print("Fetching %d ALeP pack TSVs at %s ..."
                  % (len(alep_names), alep_sha))
            rows = alep.fetch_rows(alep_sha, alep_names)
            rows, orphans = alep.apply_errata(rows)
        except (SystemExit, OSError, ValueError) as e:
            alep_rows, alep_sha = [], None
            print("build_card_data: skipping ALeP community packs (%s) - the "
                  "catalog will contain official cards only" % e)
        else:
            alep_rows = rows
            print("build_card_data: %d ALeP rows after errata merge%s"
                  % (len(alep_rows),
                     "" if not orphans else
                     " (%d errata row(s) matched no card and were dropped - the "
                     "join key may have shifted upstream, see tools/alep.py)"
                     % orphans))

    corrections = _load_corrections(args.corrections)
    if corrections:
        print("build_card_data: applying %d set rename(s) and %d text fix(es) from %s"
              % (len(corrections.get("sets") or []),
                 len(corrections.get("text") or []), args.corrections))
    else:
        print("build_card_data: no corrections table at %r - upstream card text "
              "ships as-is" % args.corrections)

    enrichment = _load_enrichment(args.enrichment)
    if enrichment is None:
        print("build_card_data: no sets-to-gather enrichment at %r - scenarios will "
              "fall back to their own set only (run tools/build_hob_enrichment.py to "
              "add it)" % args.enrichment)
    else:
        print("build_card_data: merging sets-to-gather enrichment for %d scenarios "
              "from %r" % (len(enrichment.get("scenarios") or {}), args.enrichment))
    src = "seastan/dragncards-lotrlcg-plugin@%s tsvs/cardDb.tsv" % sha
    if alep_sha:
        src += "; @%s (alep branch) tsvs/*.tsv" % alep_sha
    out = build_outputs(io.StringIO(text),
                        meta={"generated": datetime.date.today().isoformat(),
                              "source": src,
                              "imagePrefix": image_prefix},
                        enrichment=enrichment,
                        extra_rows=alep_rows,
                        corrections=corrections)
    emit(out, args.out)
    print("Wrote %d scenarios, %d player packs, %d rules to %s"
          % (len(out["scenarios"]), len(out["players"]["packs"]), len(out["rules"]), args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
