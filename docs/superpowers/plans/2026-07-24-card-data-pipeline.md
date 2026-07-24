# Card-Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tools/build_card_data.py`, a script that compiles the full DragnCards card database (`cardDb.tsv`) into normalized JSON — a top index, per-scenario encounter files (quests shaped into stages), a player-card DB by pack, and a rules set — plus the delivery wiring (gitignore, GitHub Actions Pages build, docs).

**Architecture:** Pure Python transform. Fetch a pinned TSV → parse rows → group rows into cards by `databaseId` (faces) → partition (encounter cards by `encounterSet` into scenarios; blank-`encounterSet` cards into the player DB by `packName`; `Rules` into a rules set) → shape `Quest` cards into ordered stages (branch = multiple cards sharing a `cost`) → build indexes → emit JSON. Output is gitignored and generated in CI (Pages) and at device deploy. Tests drive the pure functions off an in-repo fixture with no network.

**Tech Stack:** Python 3 (standard library only: `csv`, `json`, `urllib`, `argparse`, `re`, `datetime`). Output consumed by both twins (web fetch, firmware `json` read). GitHub Actions for Pages.

## Global Constraints

- **Standard library only** — no third-party Python deps (the tool runs in CI and locally). Verbatim.
- **Nothing tracked carries card text or the source TSV.** Only `tools/build_card_data.py` and `tools/data/cardDb.SOURCE.txt` (a URL + pinned SHA) are committed. `docs/data/` is gitignored.
- **Tests never touch the network.** The parse/derive entry point takes an open text stream; tests feed a fixture. (`CLAUDE.md` Iron rule #3: `python3 -m pytest tests/` stays green.)
- **Deterministic output** — re-running with the same pin (and meta) yields byte-identical files. Use `json.dump(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`; sort every collection before emit.
- **Source pin** — fetch `raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/<sha>/tsvs/cardDb.tsv`, `<sha>` a commit SHA, never `main`.
- **Card identity = `databaseId`** (groups A/B faces). **Encounter vs player split = `encounterSet` presence.** **Branch stage = multiple `databaseId`s sharing one `cost`.** (All verified against the live TSV.)
- **Images not bundled** — keep `imageUrl` as a reference field only.
- **Disclaimer + provenance** embedded in `index.json`: *"Unofficial companion. Not affiliated with or endorsed by Fantasy Flight Games. The Lord of the Rings is a trademark of Middle-earth Enterprises. Card text © FFG."*
- Full spec: [[2026-07-24-card-data-pipeline-design]].

## Column order (the 28 TSV columns, 0-indexed)

```
0 databaseId  1 name  2 imageUrl  3 cardBack  4 type  5 packName
6 deckbuilderQuantity  7 setUuid  8 numberInPack  9 encounterSet  10 unique
11 sphere  12 traits  13 keywords  14 cost  15 side  16 engagementCost
17 threat  18 willpower  19 attack  20 defense  21 hitPoints  22 questPoints
23 victoryPoints  24 cornerText  25 text  26 shadow  27 tags
```

## File structure

- `tools/build_card_data.py` — the whole pipeline: pure functions (`parse_int`, `parse_tags`, `parse_tsv`, `normalize_face`, `group_cards`, `slugify`, `is_sailing`, `shape_quest`, `build_outputs`, `emit`) + a thin `main()` CLI (pin resolution, fetch, orchestrate). One cohesive tool, matching the repo's `tools/gen_web_data.py` single-file style.
- `tools/data/cardDb.SOURCE.txt` — source URL template + pinned SHA. Written by `--refresh`.
- `tests/test_card_data.py` — host tests over the pure functions.
- `tests/fixtures/cardDb_sample.tsv` — small committed sample of hand-authored rows (no network).
- `.gitignore` — add `docs/data/`.
- `.github/workflows/pages.yml` — build the DB + deploy Pages.
- `CLAUDE.md` — document the pipeline (source of truth, never hand-edit `docs/data/`, deploy step).

`docs/data/` (generated, gitignored): `index.json`, `scenarios/<slug>.json`, `players/index.json`, `players/<pack-slug>.json`, `rules.json`.

---

### Task 1: TSV parse + card grouping (faces by `databaseId`)

**Files:**
- Create: `tools/build_card_data.py`
- Create: `tests/fixtures/cardDb_sample.tsv`
- Create: `tests/test_card_data.py`

**Interfaces:**
- Produces: `HEADER: list[str]`; `parse_int(s)->int|None`; `parse_tags(s)->tuple[dict|None, str|None]`; `parse_tsv(stream)->list[dict]`; `normalize_face(row)->dict`; `group_cards(rows)->list[dict]`; `slugify(s)->str`.
- A **face** = `{side, name, image, cost, engagementCost, threat, willpower, attack, defense, hitPoints, questPoints, victoryPoints, cornerText, text, shadow, keywords}` (numerics int|None; strings None when blank).
- A **card** = `{id, type, name, pack, encounterSet, number, unique, sphere, traits, keywords, image, tags, tagsRaw, faces:[face,...]}` (faces ordered by `side`; `name`/`image`/`keywords` taken from the first face).

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/cardDb_sample.tsv` by running this once (tab-safe; real-shaped rows exercising every branch):

```python
# tools/_make_fixture.py  (run once, then delete; or paste into a python -c)
import os
COLS = ["databaseId","name","imageUrl","cardBack","type","packName","deckbuilderQuantity",
        "setUuid","numberInPack","encounterSet","unique","sphere","traits","keywords","cost",
        "side","engagementCost","threat","willpower","attack","defense","hitPoints","questPoints",
        "victoryPoints","cornerText","text","shadow","tags"]
def row(**kw):
    r = {c: "" for c in COLS}
    r.update(kw)
    return "\t".join(r[c] for c in COLS)
rows = [
  # Passage quest stage 1 (one id, two faces; QP on B)
  row(databaseId="p-9119", name="Flies and Spiders", type="Quest", packName="Core Set",
      numberInPack="119", encounterSet="Passage Through Mirkwood", cost="1", side="A",
      text="Setup: Search the encounter deck for 1 copy of the Forest Spider..."),
  row(databaseId="p-9119", name="Flies and Spiders", type="Quest", packName="Core Set",
      numberInPack="119", encounterSet="Passage Through Mirkwood", cost="1", side="B",
      questPoints="8"),
  # Stage 2
  row(databaseId="p-9120", name="A Fork in the Road", type="Quest", packName="Core Set",
      numberInPack="120", encounterSet="Passage Through Mirkwood", cost="2", side="A"),
  row(databaseId="p-9120", name="A Fork in the Road", type="Quest", packName="Core Set",
      numberInPack="120", encounterSet="Passage Through Mirkwood", cost="2", side="B",
      questPoints="2", text="Forced: When you defeat this stage, proceed to one of the 2 'A Chosen Path' stages, at random."),
  # Stage 3 branch: two ids, same cost
  row(databaseId="p-9123", name="A Chosen Path", type="Quest", packName="Core Set",
      numberInPack="123", encounterSet="Passage Through Mirkwood", cost="3", side="A"),
  row(databaseId="p-9123", name="Don't Leave the Path!", type="Quest", packName="Core Set",
      numberInPack="123", encounterSet="Passage Through Mirkwood", cost="3", side="B",
      questPoints="0", text="When Revealed: ... find and defeat Ungoliant's Spawn to win the game."),
  row(databaseId="p-9125", name="A Chosen Path", type="Quest", packName="Core Set",
      numberInPack="125", encounterSet="Passage Through Mirkwood", cost="3", side="A"),
  row(databaseId="p-9125", name="Beorn's Path", type="Quest", packName="Core Set",
      numberInPack="125", encounterSet="Passage Through Mirkwood", cost="3", side="B",
      questPoints="10", text="Players cannot defeat this stage while Ungoliant's Spawn is in play."),
  # Malformed cost quest row (skip + count)
  row(databaseId="p-bad", name="Broken Stage", type="Quest", packName="Core Set",
      numberInPack="999", encounterSet="Passage Through Mirkwood", cost="X", side="A"),
  # Encounter cards in Passage
  row(databaseId="e-spawn", name="Ungoliant's Spawn", type="Enemy", packName="Core Set",
      numberInPack="34", encounterSet="Passage Through Mirkwood", unique="false",
      traits="Creature. Spider.", engagementCost="32", threat="3", attack="5", defense="2",
      hitPoints="9", text="When Revealed: Each player must choose..."),
  row(databaseId="e-ofr", name="Old Forest Road", type="Location", packName="Core Set",
      numberInPack="96", encounterSet="Passage Through Mirkwood", threat="1", questPoints="1",
      text="Travel: ready a character."),
  row(databaseId="e-reach", name="The Necromancer's Reach", type="Treachery", packName="Core Set",
      numberInPack="103", encounterSet="Passage Through Mirkwood",
      text="When Revealed: Deal 1 damage to each exhausted character."),
  # Sailing quest (own scenario) -> sailing True
  row(databaseId="f-1", name="The Chase Begins", type="Quest", packName="The Flight of the Stormcaller",
      numberInPack="1", encounterSet="Flight of the Stormcaller", keywords="Sailing.", cost="1", side="A"),
  row(databaseId="f-1", name="The Chase Begins", type="Quest", packName="The Flight of the Stormcaller",
      numberInPack="1", encounterSet="Flight of the Stormcaller", keywords="Sailing.", cost="1", side="B",
      questPoints="8"),
  # Nightmare set (its own scenario)
  row(databaseId="nm-1", name="Flies and Spiders (Nightmare)", type="Nightmare", packName="Passage Through Mirkwood Nightmare Deck",
      numberInPack="1", encounterSet="Passage Through Mirkwood - Nightmare",
      text="Nightmare setup..."),
  # Mode card (Campaign type, name endswith 'Mode')
  row(databaseId="mode-easy", name="Easy Mode", type="Campaign", packName="The Dread Realm",
      numberInPack="1", encounterSet="The Hunt for the Dreadnaught",
      text="Setup: ... Each player draws 1 additional card."),
  # Campaign card (not a mode)
  row(databaseId="camp-1", name="The Old Forest", type="Campaign", packName="The Old Forest",
      numberInPack="1", encounterSet="The Old Forest",
      text="You are playing Campaign Mode. Setup: ..."),
  # Player cards (blank encounterSet) -> player DB by pack
  row(databaseId="hero-aragorn", name="Aragorn", type="Hero", packName="Core Set",
      numberInPack="1", unique="true", sphere="Leadership", traits="Dúnedain. Noble. Ranger.",
      cost="12", threat="12", willpower="2", attack="3", defense="2", hitPoints="5"),
  row(databaseId="ally-gandalf", name="Gandalf", type="Ally", packName="Core Set",
      numberInPack="73", unique="true", sphere="Neutral", cost="5", willpower="4", attack="4",
      defense="4", hitPoints="4", text="At the end of the round, discard Gandalf."),
  # Rules card
  row(databaseId="rules-1", name="Questing", type="Rules", packName="Core Set", numberInPack="1",
      text="Compare total willpower to total threat in the staging area."),
]
os.makedirs("tests/fixtures", exist_ok=True)
with open("tests/fixtures/cardDb_sample.tsv", "w", encoding="utf-8") as f:
    f.write("\t".join(COLS) + "\n")
    f.write("\n".join(rows) + "\n")
print("wrote tests/fixtures/cardDb_sample.tsv")
```

Run: `python3 tools/_make_fixture.py && rm tools/_make_fixture.py`

- [ ] **Step 2: Write the failing test**

Create `tests/test_card_data.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_card_data as b

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "cardDb_sample.tsv")

def load_cards():
    with open(FIXTURE, encoding="utf-8") as f:
        return b.group_cards(b.parse_tsv(f))

def test_parse_int_and_tags():
    assert b.parse_int("8") == 8
    assert b.parse_int("") is None
    assert b.parse_int("X") is None
    obj, raw = b.parse_tags('{"firstPlayerControls": true}')
    assert obj == {"firstPlayerControls": True} and raw is None
    obj, raw = b.parse_tags("not json")
    assert obj is None and raw == "not json"

def test_group_faces_by_id():
    cards = {c["id"]: c for c in load_cards()}
    # stage 1 quest: one card, two faces
    q1 = cards["p-9119"]
    assert q1["type"] == "Quest" and len(q1["faces"]) == 2
    sides = [f["side"] for f in q1["faces"]]
    assert sides == ["A", "B"]
    assert q1["faces"][1]["questPoints"] == 8
    # branch stage: two distinct ids, each one card
    assert cards["p-9123"]["faces"][1]["name"] == "Don't Leave the Path!"
    assert cards["p-9125"]["faces"][1]["questPoints"] == 10

def test_slugify():
    assert b.slugify("Passage Through Mirkwood") == "passage-through-mirkwood"
    assert b.slugify("Passage Through Mirkwood - Nightmare") == "passage-through-mirkwood-nightmare"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_card_data'` (module not created yet).

- [ ] **Step 4: Write minimal implementation**

Create `tools/build_card_data.py`:

```python
"""Compile the DragnCards cardDb.tsv into normalized JSON (index + scenarios +
player DB + rules). Source of truth is the pinned TSV; never hand-edit the
output. See docs/superpowers/specs/2026-07-24-card-data-pipeline-design.md."""
import csv, json, re

HEADER = ["databaseId","name","imageUrl","cardBack","type","packName",
          "deckbuilderQuantity","setUuid","numberInPack","encounterSet","unique",
          "sphere","traits","keywords","cost","side","engagementCost","threat",
          "willpower","attack","defense","hitPoints","questPoints","victoryPoints",
          "cornerText","text","shadow","tags"]

_INT_FIELDS = ("cost","engagementCost","threat","willpower","attack","defense",
               "hitPoints","questPoints","victoryPoints")

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
    face = {"side": (row.get("side") or "").strip(),
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add tools/build_card_data.py tests/test_card_data.py tests/fixtures/cardDb_sample.tsv
git commit -m "feat(cards): TSV parse + databaseId face grouping"
```

---

### Task 2: Quest shaping (stages + branch) + sailing

**Files:**
- Modify: `tools/build_card_data.py`
- Modify: `tests/test_card_data.py`

**Interfaces:**
- Consumes: `group_cards`, `is_sailing` (new).
- Produces: `is_sailing(card)->bool`; `shape_quest(quest_cards)->dict` returning `{"stages":[{"stage":int, "branch"?:str, "cards":[{"questPoints":int,"victory":int|None,"sailing":bool,"faces":[{"side","name","text"}]}]}], "skipped":int}`. Stages sorted ascending; a stage with >1 card carries `branch` (`"random"`/`"choice"`); malformed-`cost` quest cards counted in `skipped` and dropped.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_card_data.py`:

```python
def quest_cards_for(enc):
    return [c for c in load_cards() if c["type"] == "Quest" and c["encounterSet"] == enc]

def test_shape_quest_stages_and_branch():
    q = b.shape_quest(quest_cards_for("Passage Through Mirkwood"))
    assert q["skipped"] == 1  # the malformed 'X' cost row
    stages = q["stages"]
    assert [s["stage"] for s in stages] == [1, 2, 3]
    assert stages[0]["cards"][0]["questPoints"] == 8
    assert stages[1]["cards"][0]["questPoints"] == 2
    s3 = stages[2]
    assert s3.get("branch") == "random"
    assert sorted(c["questPoints"] for c in s3["cards"]) == [0, 10]
    # non-branch stages have no 'branch' key
    assert "branch" not in stages[0]
    # faces trimmed to side/name/text
    assert set(stages[0]["cards"][0]["faces"][0].keys()) == {"side", "name", "text"}

def test_is_sailing():
    cards = {c["id"]: c for c in load_cards()}
    assert b.is_sailing(cards["f-1"]) is True
    assert b.is_sailing(cards["p-9119"]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: FAIL — `AttributeError: module 'build_card_data' has no attribute 'shape_quest'`.

- [ ] **Step 3: Write minimal implementation**

Add to `tools/build_card_data.py`:

```python
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
    joined = " ".join((f["text"] or "") for c in cards for f in c["faces"]).lower()
    if "at random" in joined:
        return "random"
    if "first player" in joined or "choose" in joined or "chosen" in joined:
        return "choice"
    return "random"

def shape_quest(quest_cards):
    by_stage, skipped = {}, 0
    for card in quest_cards:
        stage = parse_int(card["faces"][0].get("cost"))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/build_card_data.py tests/test_card_data.py
git commit -m "feat(cards): shape quests into stages with branch + sailing"
```

---

### Task 3: Partition + `build_outputs` (scenarios / players / rules + index)

**Files:**
- Modify: `tools/build_card_data.py`
- Modify: `tests/test_card_data.py`

**Interfaces:**
- Consumes: `group_cards`, `shape_quest`, `is_sailing`, `slugify`, `parse_tsv`.
- Produces: `build_outputs(stream, meta=None)->dict` (`stream` = an open text stream of the TSV; parsed internally) with shape:
  ```
  {"index": {...}, "scenarios": {slug: scenario_obj},
   "players": {"index": [...], "packs": {slug: pack_obj}}, "rules": [card,...]}
  ```
  `meta` = `{"generated": str, "source": str}` (defaults to fixed placeholders for determinism in tests).
- `scenario_obj` = `{slug, name, pack, kind, sailing, quest|None, encounter:{typeKey:[card...]}, modes:[card...], campaign:[card...]}`. `kind ∈ quest|nightmare|campaign|encounter`.
- index scenario entry = `{slug, name, pack, kind, stageCount, sailing, hasNightmare, modes:[name...], counts:{typeKey:int}}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_card_data.py`:

```python
def build():
    with open(FIXTURE, encoding="utf-8") as f:
        return b.build_outputs(f, meta={"generated": "2026-07-24", "source": "fixture"})

def test_scenario_assembly_and_index():
    out = build()
    scn = out["scenarios"]["passage-through-mirkwood"]
    assert scn["kind"] == "quest"
    assert [s["stage"] for s in scn["quest"]["stages"]] == [1, 2, 3]
    assert len(scn["encounter"]["enemy"]) == 1
    assert len(scn["encounter"]["location"]) == 1
    assert len(scn["encounter"]["treachery"]) == 1
    # quest cards not duplicated into encounter
    assert "quest" not in scn["encounter"]
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert idx["passage-through-mirkwood"]["stageCount"] == 3
    assert idx["passage-through-mirkwood"]["hasNightmare"] is True
    assert idx["flight-of-the-stormcaller"]["sailing"] is True

def test_modes_campaign_players_rules():
    out = build()
    assert out["scenarios"]["the-hunt-for-the-dreadnaught"]["modes"][0]["name"] == "Easy Mode"
    assert out["scenarios"]["the-old-forest"]["kind"] == "campaign"
    core = out["players"]["packs"]["core-set"]
    assert any(c["name"] == "Aragorn" for c in core["cards"]["hero"])
    assert any(c["name"] == "Gandalf" for c in core["cards"]["ally"])
    assert any(c["name"] == "Questing" for c in out["rules"])
    # index carries disclaimer + source
    assert "Fantasy Flight" in out["index"]["disclaimer"]
    assert out["index"]["source"] == "fixture"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: FAIL — `AttributeError: ... 'build_outputs'`.

- [ ] **Step 3: Write minimal implementation**

Add to `tools/build_card_data.py`:

```python
DISCLAIMER = ("Unofficial companion. Not affiliated with or endorsed by Fantasy "
              "Flight Games. The Lord of the Rings is a trademark of Middle-earth "
              "Enterprises. Card text © FFG.")

_PLAYER_TYPES = {"Hero","Ally","Attachment","Event","Side Quest","Contract","Treasure"}

def _type_key(t):
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

def build_outputs(stream, meta=None):
    meta = meta or {"generated": "", "source": ""}
    cards = group_cards(parse_tsv(stream))
    enc_groups, player_groups, rules = {}, {}, []
    for c in cards:
        if c["type"] == "Rules":
            rules.append(c)
        elif c["encounterSet"]:
            enc_groups.setdefault(c["encounterSet"], []).append(c)
        else:
            player_groups.setdefault(c["pack"] or "unknown", []).append(c)

    enc_names = set(enc_groups)
    scenarios, index_scn = {}, []
    for enc, group in enc_groups.items():
        slug = slugify(enc)
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
        index_scn.append({
            "slug": slug, "name": enc, "pack": group[0]["pack"],
            "kind": scenarios[slug]["kind"],
            "stageCount": len(quest["stages"]) if quest else 0,
            "sailing": sailing,
            "hasNightmare": (enc + " - Nightmare") in enc_names,
            "modes": [m["name"] for m in modes],
            "counts": {k: len(v) for k, v in encounter.items()},
        })

    packs, players_index = {}, []
    for pack, group in player_groups.items():
        slug = slugify(pack)
        by_type = {}
        for c in group:
            by_type.setdefault(_type_key(c["type"]), []).append(c)
        packs[slug] = {"pack": pack, "cards": by_type}
        players_index.append({"slug": slug, "name": pack, "cardCount": len(group)})

    index = {
        "generated": meta["generated"], "source": meta["source"], "disclaimer": DISCLAIMER,
        "scenarios": sorted(index_scn, key=lambda s: (s["pack"] or "", s["name"])),
        "packs": sorted(players_index, key=lambda p: p["name"]),
        "rules": bool(rules),
    }
    return {"index": index, "scenarios": scenarios,
            "players": {"index": players_index, "packs": packs}, "rules": rules}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/build_card_data.py tests/test_card_data.py
git commit -m "feat(cards): partition into scenarios/players/rules + build index"
```

---

### Task 4: Emit + CLI (pin resolution / fetch / --refresh)

**Files:**
- Modify: `tools/build_card_data.py`
- Modify: `tests/test_card_data.py`

**Interfaces:**
- Consumes: `build_outputs`.
- Produces: `emit(outputs, out_dir)->None` (writes `index.json`, `scenarios/<slug>.json`, `players/index.json`, `players/<slug>.json`, `rules.json` — deterministic dumps); `main(argv=None)->int` (CLI).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_card_data.py`:

```python
import json as _json

def test_emit_writes_files(tmp_path):
    out = build()
    b.emit(out, str(tmp_path))
    idx = _json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert any(s["slug"] == "passage-through-mirkwood" for s in idx["scenarios"])
    scn = _json.loads((tmp_path / "scenarios" / "passage-through-mirkwood.json").read_text(encoding="utf-8"))
    assert scn["quest"]["stages"][0]["cards"][0]["questPoints"] == 8
    assert (tmp_path / "players" / "core-set.json").exists()
    assert (tmp_path / "rules.json").exists()

def test_emit_deterministic(tmp_path):
    out = build()
    b.emit(out, str(tmp_path / "a"))
    b.emit(out, str(tmp_path / "b"))
    a = (tmp_path / "a" / "index.json").read_bytes()
    c = (tmp_path / "b" / "index.json").read_bytes()
    assert a == c
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: FAIL — `AttributeError: ... 'emit'`.

- [ ] **Step 3: Write minimal implementation**

Add to `tools/build_card_data.py`:

```python
import os, argparse, datetime, urllib.request

RAW = "https://raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/{sha}/tsvs/cardDb.tsv"
API = "https://api.github.com/repos/seastan/dragncards-lotrlcg-plugin/commits/main"
SOURCE_FILE = os.path.join(os.path.dirname(__file__), "data", "cardDb.SOURCE.txt")

def _dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def emit(outputs, out_dir):
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
    sha = urllib.request.urlopen(req).read().decode().strip()
    os.makedirs(os.path.dirname(SOURCE_FILE), exist_ok=True)
    with open(SOURCE_FILE, "w", encoding="utf-8") as f:
        f.write("url=%s\nsha=%s\n" % (RAW, sha))
    return sha

def main(argv=None):
    ap = argparse.ArgumentParser(description="Compile DragnCards cardDb.tsv to JSON.")
    ap.add_argument("--refresh", action="store_true", help="re-pin to upstream HEAD sha")
    ap.add_argument("--out", default=os.path.join("docs", "data"))
    args = ap.parse_args(argv)
    if not os.path.exists(SOURCE_FILE) and not args.refresh:
        raise SystemExit("No pin file — run once with --refresh.")
    sha = _refresh_pin() if args.refresh else _read_pin()
    with urllib.request.urlopen(RAW.format(sha=sha)) as resp:
        text = resp.read().decode("utf-8")
    import io
    out = build_outputs(io.StringIO(text),
                        meta={"generated": datetime.date.today().isoformat(),
                              "source": "seastan/dragncards-lotrlcg-plugin@%s tsvs/cardDb.tsv" % sha})
    emit(out, args.out)
    print("Wrote %d scenarios, %d player packs, %d rules to %s"
          % (len(out["scenarios"]), len(out["players"]["packs"]), len(out["rules"]), args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_data.py -q`
Expected: PASS (9 tests). Note: `main()`/network paths are not unit-tested (no network in tests); they are exercised in Task 7.

- [ ] **Step 5: Commit**

```bash
git add tools/build_card_data.py tests/test_card_data.py
git commit -m "feat(cards): deterministic emit + pinned-fetch CLI"
```

---

### Task 5: Gitignore + CLAUDE.md documentation

**Files:**
- Modify: `.gitignore`
- Modify: `CLAUDE.md`

**Interfaces:** none (docs/config only).

- [ ] **Step 1: Add the gitignore entry**

Append to `.gitignore`:

```
# generated card DB (compiled from DragnCards; never committed — see tools/build_card_data.py)
docs/data/
```

- [ ] **Step 2: Document the pipeline in CLAUDE.md**

Under the "Iron rules" section (after rule 2), add rule text; and add a short "Card data" subsection near the device notes. Insert this subsection after the "The TODO board" section header block (before it), or at the end of the iron rules — exact text to add:

```markdown
## Card data (generated, never committed)

`tools/build_card_data.py` compiles the full DragnCards card DB into
`docs/data/` (index + per-scenario + player DB + rules). The source of truth is
the pinned TSV (`tools/data/cardDb.SOURCE.txt`); the output is **gitignored** and
regenerated — never hand-edit `docs/data/`. Refresh the pin with
`python3 tools/build_card_data.py --refresh`. Web Pages builds it in CI
(`.github/workflows/pages.yml`); the device gets it at deploy:
`python3 tools/build_card_data.py && mpremote cp -r docs/data/ :/data/`.
```

- [ ] **Step 3: Verify pytest still green**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (full suite, incl. the 9 card-data tests).

- [ ] **Step 4: Commit**

```bash
git add .gitignore CLAUDE.md
git commit -m "docs(cards): gitignore generated docs/data + document the pipeline"
```

---

### Task 6: GitHub Actions Pages workflow

**Files:**
- Create: `.github/workflows/pages.yml`

**Interfaces:** none (CI config).

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/pages.yml`:

```yaml
name: Deploy Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Build card data
        run: python3 tools/build_card_data.py --refresh
      - uses: actions/upload-pages-artifact@v3
        with:
          path: docs
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Validate YAML parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/pages.yml'))" 2>/dev/null || python3 -c "import json; print('yaml lib absent — skip')"`
Expected: no error (or the skip message if PyYAML absent — acceptable, GitHub validates on push).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci(cards): build card DB + deploy Pages via Actions"
```

---

### Task 7: Real-data validation (main session — needs network)

**Files:** none committed (output is gitignored).

**Interfaces:** none — this is the integration gate against the live TSV.

> Run in the **main session** (network + writes the gitignored `docs/data/`). Not a worktree subagent task.

- [ ] **Step 1: Refresh pin + build against the live DB**

Run: `python3 tools/build_card_data.py --refresh`
Expected: prints `Wrote N scenarios, M player packs, K rules to docs/data` with N in the low hundreds.

- [ ] **Step 2: Sanity-check the real output**

Run:
```bash
python3 - <<'PY'
import json, os
d = "docs/data"
idx = json.load(open(os.path.join(d, "index.json"), encoding="utf-8"))
scn = json.load(open(os.path.join(d, "scenarios", "passage-through-mirkwood.json"), encoding="utf-8"))
stages = [(s["stage"], [c["questPoints"] for c in s["cards"]]) for s in scn["quest"]["stages"]]
print("Passage stages:", stages)
print("enemies/locations/treacheries:",
      len(scn["encounter"].get("enemy", [])),
      len(scn["encounter"].get("location", [])),
      len(scn["encounter"].get("treachery", [])))
fl = [s for s in idx["scenarios"] if s["slug"] == "flight-of-the-stormcaller"]
print("Flight sailing:", fl[0]["sailing"] if fl else "MISSING")
print("scenario count:", len(idx["scenarios"]))
print("docs/data size (MB):", round(sum(os.path.getsize(os.path.join(r,f))
      for r,_,fs in os.walk(d) for f in fs)/1e6, 2))
PY
```
Expected: Passage stages `[(1,[8]),(2,[2]),(3,[0,10])]`; enemies/locations/treacheries `6 5 4`; Flight sailing `True`; scenario count ~200; size ~1–2 MB.

- [ ] **Step 3: Confirm nothing generated is tracked**

Run: `git status --porcelain docs/data`
Expected: **empty** (docs/data is gitignored). If anything shows, the gitignore is wrong — fix Task 5.

- [ ] **Step 4: Record acceptance**

No commit. Report the printed numbers as the acceptance result.

---

## Self-Review

**Spec coverage:** index/scenario/player/rules contract → Tasks 1–4; `databaseId` faces + branch → Tasks 1–2; encounter/player/rules partition → Task 3; sailing/kind/hasNightmare/modes/counts → Task 3; deterministic emit → Task 4; pinned fetch + `--refresh` → Task 4; gitignore + docs → Task 5; CI Pages → Task 6; licensing disclaimer/provenance → Task 3 (`DISCLAIMER`, `meta.source`); real-data validation + sizes → Task 7. Images-not-bundled: honored (only `imageUrl` string kept). Firmware full-bundle: documented (Task 5) + validated size (Task 7); the copy step is a deploy-runbook action, main-session only.

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `group_cards`→cards with `faces`; `shape_quest` consumes those cards and reads `faces[0]["cost"]`; `build_outputs` consumes `group_cards`/`shape_quest`/`is_sailing`/`slugify`; `emit` consumes `build_outputs` output keys (`index`,`scenarios`,`players`,`rules`) — all consistent. `_type_key` maps `"Side Quest"`→`"sideQuest"`, `"Objective Ally"`→`"objectiveAlly"` uniformly for both encounter buckets and player buckets.

**Note on `hasNightmare`:** relies on the base and NM sets differing exactly by the `" - Nightmare"` suffix (verified naming). If upstream naming varies, the flag is a soft link only — no functional dependency.
