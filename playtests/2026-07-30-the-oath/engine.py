#!/usr/bin/env python3
"""Playtest harness: real randomness + an append-only ledger for one game.

This is NOT a rules engine. It owns the three things a human at the table
owns and a HUD does not: the shuffled decks, the dice-roll of a draw, and a
record of what happened. Every rules decision is made by the player; every
*random* outcome and every state change goes through here so the game is
reproducible and auditable after the fact.

Files, all in this directory:
  log.jsonl   append-only. One JSON object per action, with the full state
              after it. Never rewritten, never truncated.
  state.json  derived convenience mirror of the newest log entry.
  log.md      human-readable render of log.jsonl (regenerate with `render`).

Randomness is a single random.Random stream seeded once at `init`. Its
internal state is persisted between invocations so the sequence is continuous
and the whole game replays exactly from the seed.
"""

import json
import os
import random
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "log.jsonl")
STATE = os.path.join(HERE, "state.json")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


# ---------------------------------------------------------------- card data

def _ringsdb_cards():
    with open(os.path.join(HERE, "_ringsdb_core.json")) as fh:
        return {c["code"]: c for c in json.load(fh)}


def _encounter_pool():
    """All cards in encounter sets 'The Oath' + 'The Goblins'.

    Dark of Mirkwood rulebook: "The Oath encounter deck is built with all the
    cards from the following encounter sets: The Oath and The Goblins."
    Stalking Goblin is excluded: it is a Campaign Mode burden, added only by
    the-oath-campaign's setup text ("Shuffle the Stalking Goblin burden enemy
    into the encounter deck"). We are playing standard mode.
    """
    pool = []
    for slug in ("the-oath", "the-goblins"):
        path = os.path.join(REPO, "docs", "data", "scenarios", slug + ".json")
        with open(path) as fh:
            data = json.load(fh)
        for kind, cards in data.get("encounter", {}).items():
            for c in cards:
                if c["name"] == "Stalking Goblin":
                    continue  # campaign burden, not standard mode
                face = c["faces"][0]
                for _ in range(c["quantity"]):
                    pool.append({
                        "name": c["name"],
                        "type": kind,
                        "set": c["encounterSet"],
                        "traits": c.get("traits"),
                        "threat": face.get("threat"),
                        "threat_kind": face.get("threatKind"),
                        "quest_points": face.get("questPoints"),
                        "engagement": face.get("engagementCost"),
                        "attack": face.get("attack"),
                        "defense": face.get("defense"),
                        "hp": face.get("hitPoints"),
                        "keywords": face.get("keywords"),
                        "victory": face.get("victoryPoints"),
                        "text": face.get("text"),
                        "shadow": face.get("shadow"),
                    })
    return pool


def _player_deck():
    """The 50-card deck from RingsDB decklist 27650, minus the three heroes."""
    cards = _ringsdb_cards()
    with open(os.path.join(HERE, "_ringsdb_deck_27650.json")) as fh:
        dl = json.load(fh)
    deck = []
    for code, n in dl["slots"].items():
        if code in dl["heroes"]:
            continue
        c = cards[code]
        for _ in range(n):
            deck.append({
                "code": code,
                "name": c["name"],
                "type": c["type_name"],
                "sphere": c["sphere_name"],
                "cost": c.get("cost"),
                "willpower": c.get("willpower"),
                "attack": c.get("attack"),
                "defense": c.get("defense"),
                "hp": c.get("health"),
                "traits": c.get("traits"),
                "text": c.get("text"),
                "unique": c.get("is_unique"),
            })
    return deck, dl


def _heroes():
    cards = _ringsdb_cards()
    with open(os.path.join(HERE, "_ringsdb_deck_27650.json")) as fh:
        dl = json.load(fh)
    out = []
    for code in dl["heroes"]:
        c = cards[code]
        out.append({
            "code": code,
            "name": c["name"],
            "sphere": c["sphere_name"],
            "threat_cost": c["threat"],
            "willpower": c["willpower"],
            "attack": c["attack"],
            "defense": c["defense"],
            "hp": c["health"],
            "traits": c.get("traits"),
            "text": c.get("text"),
            "damage": 0,
            "exhausted": False,
            "resources": 0,
            "attachments": [],
        })
    return out


# ------------------------------------------------------------------ ledger

def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _read_state():
    with open(STATE) as fh:
        return json.load(fh)


def _rng_from(state):
    rng = random.Random()
    st = state["_rng"]
    rng.setstate((st[0], tuple(st[1]), st[2]))
    return rng


def _stash_rng(state, rng):
    s = rng.getstate()
    state["_rng"] = [s[0], list(s[1]), s[2]]


# Zones whose contents are bulk card records. The snapshot keeps their card
# NAMES only: full printed text is identical for every copy and already lives
# in docs/data, so repeating it in every entry made log.jsonl 32KB per action
# (~10MB for a full game) for zero added information. Zones the player reasons
# about card-by-card - staging, engaged, allies, active_location - stay whole,
# because those carry per-copy mutable state (damage, progress, attachments).
_BULK = ("deck", "hand", "discard", "encounter_deck", "encounter_discard",
         "set_aside", "victory_display")


def _slim(state):
    out = {}
    for k, v in state.items():
        if k == "_rng":
            continue
        out[k] = [c["name"] for c in v] if k in _BULK else v
    return out


def _append(state, op, args, note, result):
    seq = state.get("_seq", 0) + 1
    state["_seq"] = seq
    entry = {
        "seq": seq,
        "ts": _now(),
        "round": state.get("round"),
        "step": state.get("step"),
        "op": op,
        "args": args,
        "note": note,
        "result": result,
        "state_after": _slim(state),
    }
    with open(LOG, "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    with open(STATE, "w") as fh:
        json.dump(state, fh, indent=1)
    return entry


def _names(cards):
    return [c["name"] for c in cards]


# --------------------------------------------------------------- commands

def cmd_init(args):
    seed = int(args[0]) if args else random.SystemRandom().randrange(2**31)
    if os.path.exists(LOG):
        sys.exit("log.jsonl already exists - refusing to clobber an existing game")
    rng = random.Random(seed)
    deck, dl = _player_deck()
    enc = _encounter_pool()
    heroes = _heroes()

    state = {
        "_seq": 0,
        "seed": seed,
        "scenario": "The Oath",
        "mode": "standard",
        "players": 1,
        "round": 0,
        "step": "setup",
        "threat": sum(h["threat_cost"] for h in heroes),
        "threat_per_round": 1,
        "heroes": heroes,
        "hand": [],
        "deck": deck,
        "discard": [],
        "allies": [],
        "engaged": [],
        "staging": [],
        "active_location": None,
        "quest": {"stage": 1, "side": "A", "name": "After the Raid",
                  "progress": 0, "points": None},
        "victory_display": [],
        "encounter_deck": enc,
        "encounter_discard": [],
        "set_aside": [],
        "notes": [],
    }
    rng.shuffle(state["deck"])
    rng.shuffle(state["encounter_deck"])
    _stash_rng(state, rng)
    _append(state, "init", {"seed": seed},
            f"Seeded RNG with {seed}. Player deck {len(deck)} cards, encounter pool "
            f"{len(enc)} cards; both shuffled.",
            {"player_deck": len(deck), "encounter_deck": len(enc),
             "starting_threat": state["threat"],
             "heroes": _names(heroes)})
    print(json.dumps({"seed": seed, "threat": state["threat"],
                      "heroes": _names(heroes),
                      "deck": len(deck), "encounter": len(enc)}, indent=1))


def cmd_draw(args):
    n = int(args[0])
    note = args[1] if len(args) > 1 else "Draw."
    state = _read_state()
    drawn = [state["deck"].pop(0) for _ in range(n)]
    state["hand"].extend(drawn)
    _append(state, "draw", {"n": n}, note,
            {"drawn": _names(drawn), "hand_size": len(state["hand"]),
             "deck_left": len(state["deck"])})
    print(json.dumps({"drawn": _names(drawn), "hand": _names(state["hand"]),
                      "deck_left": len(state["deck"])}, indent=1))


def cmd_reveal(args):
    n = int(args[0]) if args else 1
    note = args[1] if len(args) > 1 else "Reveal encounter card(s)."
    state = _read_state()
    out = []
    for _ in range(n):
        if not state["encounter_deck"]:
            rng = _rng_from(state)
            state["encounter_deck"] = state["encounter_discard"]
            state["encounter_discard"] = []
            rng.shuffle(state["encounter_deck"])
            _stash_rng(state, rng)
            _append(state, "encounter_reshuffle", {}, "Encounter deck empty: "
                    "shuffle the discard pile to form a new deck (RR 'Encounter Deck').",
                    {"size": len(state["encounter_deck"])})
            state = _read_state()
        out.append(state["encounter_deck"].pop(0))
    _append(state, "reveal", {"n": n}, note,
            {"revealed": _names(out), "deck_left": len(state["encounter_deck"])})
    print(json.dumps([{k: c[k] for k in ("name", "type", "threat", "quest_points",
                                         "engagement", "attack", "defense", "hp",
                                         "keywords", "victory", "text", "shadow")}
                      for c in out], indent=1))


def cmd_search_encounter(args):
    """Remove a named card from the encounter deck (setup / card-effect searches)."""
    name = args[0]
    dest = args[1]           # staging | set_aside | engaged | encounter_discard
    note = args[2] if len(args) > 2 else f"Search encounter deck for {name}."
    state = _read_state()
    idx = next((i for i, c in enumerate(state["encounter_deck"])
                if c["name"] == name), None)
    if idx is None:
        sys.exit(f"{name} not found in encounter deck")
    card = state["encounter_deck"].pop(idx)
    state[dest].append(card)
    _append(state, "search_encounter", {"name": name, "dest": dest}, note,
            {"found": name, "deck_left": len(state["encounter_deck"])})
    print(json.dumps(card, indent=1))


def cmd_shuffle_encounter(args):
    note = args[0] if args else "Shuffle the encounter deck."
    state = _read_state()
    rng = _rng_from(state)
    rng.shuffle(state["encounter_deck"])
    _stash_rng(state, rng)
    _append(state, "shuffle_encounter", {}, note,
            {"size": len(state["encounter_deck"])})
    print(f"shuffled {len(state['encounter_deck'])} encounter cards")


def cmd_random_discard(args):
    """Discard N random cards from hand (Tangled Grove travel cost, etc)."""
    n = int(args[0])
    note = args[1] if len(args) > 1 else "Discard random card(s) from hand."
    state = _read_state()
    rng = _rng_from(state)
    got = []
    for _ in range(n):
        if not state["hand"]:
            break
        i = rng.randrange(len(state["hand"]))
        got.append(state["hand"].pop(i))
    state["discard"].extend(got)
    _stash_rng(state, rng)
    _append(state, "random_discard", {"n": n}, note,
            {"discarded": _names(got), "hand_size": len(state["hand"])})
    print(json.dumps({"discarded": _names(got), "hand": _names(state["hand"])}, indent=1))


def cmd_mill(args):
    """Discard the top N cards of the player deck (Goblintown Scavengers)."""
    n = int(args[0])
    note = args[1] if len(args) > 1 else "Discard top card(s) of player deck."
    state = _read_state()
    got = [state["deck"].pop(0) for _ in range(min(n, len(state["deck"])))]
    state["discard"].extend(got)
    _append(state, "mill", {"n": n}, note,
            {"discarded": [{"name": c["name"], "cost": c["cost"]} for c in got],
             "deck_left": len(state["deck"])})
    print(json.dumps([{"name": c["name"], "cost": c["cost"]} for c in got], indent=1))


def cmd_patch(args):
    """Apply a player decision to the state. JSON on stdin, note in argv.

    stdin: {"path.to.key": value, ...} using dotted paths, or a list of
           {"op": "append"|"remove"|"set", "path": ..., "value": ...}
    """
    note = args[0]
    payload = json.load(sys.stdin)
    state = _read_state()
    ops = payload if isinstance(payload, list) else [
        {"op": "set", "path": k, "value": v} for k, v in payload.items()]

    def resolve(path):
        parts = path.split(".")
        node = state
        for p in parts[:-1]:
            node = node[int(p)] if p.isdigit() else node[p]
        return node, parts[-1]

    for o in ops:
        node, key = resolve(o["path"])
        k = int(key) if key.isdigit() else key
        if o["op"] == "set":
            node[k] = o["value"]
        elif o["op"] == "append":
            node[k].append(o["value"])
        elif o["op"] == "extend":
            node[k].extend(o["value"])
        elif o["op"] == "remove":
            # Removes ONE card, not every copy sharing the title. The first
            # version filtered on name and silently binned both Celebrian's
            # Stones when only one was played (seq 31) - a decking error the
            # ledger caught only because the hand count was checked by hand.
            if o.get("index") is not None:
                node[k].pop(o["index"])
            else:
                idx = next((i for i, x in enumerate(node[k])
                            if x.get("name") == o["value"]), None)
                if idx is None:
                    sys.exit(f"remove: {o['value']} not found in {o['path']}")
                node[k].pop(idx)
        elif o["op"] == "pop":
            node[k].pop(o.get("index", 0))
        elif o["op"] == "inc":
            node[k] = (node[k] or 0) + o["value"]
        else:
            sys.exit("unknown op " + o["op"])
    _append(state, "patch", ops, note, {"ok": True})
    print("ok")


def cmd_note(args):
    """Record a decision, a rules citation, or a UX observation."""
    state = _read_state()
    _append(state, "note", {}, args[0], {"kind": args[1] if len(args) > 1 else "play"})
    print("noted")


def cmd_show(args):
    state = _read_state()
    h = state["heroes"]
    print(f"R{state['round']} {state['step']}  threat {state['threat']}")
    print(f"quest {state['quest']['stage']}{state['quest']['side']} "
          f"{state['quest']['name']} {state['quest']['progress']}/{state['quest']['points']}")
    for x in h:
        att = ",".join(a["name"] for a in x["attachments"])
        print(f"  HERO {x['name']:10} {x['willpower']}/{x['attack']}/{x['defense']} "
              f"hp {x['hp'] - x['damage']}/{x['hp']} res {x['resources']}"
              f"{' EXH' if x['exhausted'] else ''}{'  [' + att + ']' if att else ''}")
    for a in state["allies"]:
        att = ",".join(x["name"] for x in a.get("attachments", []))
        print(f"  ALLY {a['name']:10} {a.get('willpower')}/{a.get('attack')}/{a.get('defense')} "
              f"hp {a['hp'] - a.get('damage', 0)}/{a['hp']}"
              f"{' EXH' if a.get('exhausted') else ''}{'  [' + att + ']' if att else ''}")
    print(f"  active location: {state['active_location']}")
    print(f"  staging: {[(c['name'], c.get('progress', 0)) for c in state['staging']]}")
    print(f"  engaged: {[(c['name'], c.get('damage', 0)) for c in state['engaged']]}")
    print(f"  hand ({len(state['hand'])}): {_names(state['hand'])}")
    print(f"  deck {len(state['deck'])} | discard {len(state['discard'])}")
    print(f"  enc deck {len(state['encounter_deck'])} | enc discard "
          f"{len(state['encounter_discard'])} | victory {_names(state['victory_display'])}")
    print(f"  set aside: {_names(state['set_aside'])}")


def cmd_render(args):
    """Render log.jsonl -> log.md."""
    lines = ["# The Oath - solo playtest log", "",
             "Append-only. Generated from `log.jsonl`; do not hand-edit.", ""]
    round_now = None
    with open(LOG) as fh:
        for raw in fh:
            e = json.loads(raw)
            r = e.get("round")
            if r != round_now:
                round_now = r
                lines.append("")
                lines.append(f"## Round {r}" if r else "## Setup")
                lines.append("")
            st = e.get("step") or ""
            res = e.get("result") or {}
            head = f"**{e['seq']:03d}** `{st}` *{e['op']}* - {e['note']}"
            lines.append(head)
            if e["op"] in ("draw", "reveal", "random_discard", "mill",
                           "search_encounter", "init"):
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(res))
                lines.append("```")
            lines.append("")
    with open(os.path.join(HERE, "log.md"), "w") as fh:
        fh.write("\n".join(lines))
    print("wrote log.md")


CMDS = {k[4:]: v for k, v in list(globals().items()) if k.startswith("cmd_")}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit("usage: engine.py {" + "|".join(CMDS) + "} [args...]")
    CMDS[sys.argv[1]](sys.argv[2:])
