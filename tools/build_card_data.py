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

def build_outputs(stream, meta=None):
    meta = meta or {"generated": "", "source": ""}
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
        index_scn.append({
            "slug": slug, "name": enc, "pack": group[0]["pack"],
            "kind": scenarios[slug]["kind"],
            "stageCount": len(quest["stages"]) if quest else 0,
            "sailing": sailing,
            "hasNightmare": slugify(enc + " - Nightmare") in enc_groups,
            "modes": [m["name"] for m in modes],
            "counts": {k: len(v) for k, v in encounter.items()},
        })

    packs, players_index = {}, []
    for slug, group in player_groups.items():
        by_type = {}
        for c in group:
            by_type.setdefault(_type_key(c["type"]), []).append(c)
        packs[slug] = {"pack": player_name[slug], "cards": by_type}
        players_index.append({"slug": slug, "name": player_name[slug], "cardCount": len(group)})

    index = {
        "generated": meta["generated"], "source": meta["source"], "disclaimer": DISCLAIMER,
        "scenarios": sorted(index_scn, key=lambda s: (s["pack"] or "", s["name"])),
        "packs": sorted(players_index, key=lambda p: p["name"]),
        "rules": bool(rules),
    }
    return {"index": index, "scenarios": scenarios,
            "players": {"index": players_index, "packs": packs}, "rules": rules}

RAW = "https://raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/{sha}/tsvs/cardDb.tsv"
API = "https://api.github.com/repos/seastan/dragncards-lotrlcg-plugin/commits/main"
SOURCE_FILE = os.path.join(os.path.dirname(__file__), "data", "cardDb.SOURCE.txt")

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
    out = build_outputs(io.StringIO(text),
                        meta={"generated": datetime.date.today().isoformat(),
                              "source": "seastan/dragncards-lotrlcg-plugin@%s tsvs/cardDb.tsv" % sha})
    emit(out, args.out)
    print("Wrote %d scenarios, %d player packs, %d rules to %s"
          % (len(out["scenarios"]), len(out["players"]["packs"]), len(out["rules"]), args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
