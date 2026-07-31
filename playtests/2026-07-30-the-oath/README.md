# The Oath — solo playtest, 2026-07-30

A full game of **The Oath** played true-solo against the web twin, driving the
real UI, to see what the HUD gets right and where it fails a player who trusts
it. **Result: victory in round 9.** Official score **123** (lower is better).

## Setup

| | |
|---|---|
| Scenario | The Oath (Dark of Mirkwood / Two-Player Limited Edition Starter), standard mode |
| Encounter deck | 31 cards — all of *The Oath* + *The Goblins*, less the 1A setup removals |
| Deck | [RingsDB 27650](https://ringsdb.com/decklist/view/27650/) — Aragorn / Éowyn / Dúnhere, 29 starting threat |
| RNG seed | `1045977623` — every shuffle and draw replays exactly from it |
| App | web twin at `localhost:8643`, driven by pointer events at true device coordinates |

*Stalking Goblin is excluded from the encounter deck: it is a Campaign Mode
burden, added only by `the-oath-campaign`'s setup text. This is a standard-mode
game.*

## Files

| | |
|---|---|
| `engine.py` | The harness. Owns the shuffled decks, the RNG, and the ledger — the three things a human at the table owns and a HUD does not. Not a rules engine; every rules decision was made by the player. |
| `log.md` | Rendered narrative of the whole game. Committed. |
| `log.jsonl` | Append-only ledger, 119 entries, one per action with the state after it. Gitignored — its snapshots embed verbatim card text. |
| `state.json` | Live state mirror. Gitignored, same reason. |

Nothing in the ledger was ever rewritten. Four of my own errors are in there as
correction entries rather than edits — a decking bug that binned both copies of
a card, a duplicated Beorn, a phantom Goblin Sniper the round-7 search failed to
remove from the deck, and a resource misallocation that cost Dúnhere two rounds
of readying.

## Reproducing

```bash
python3 engine.py init 1045977623
```

Then replay the decisions in `log.md`. Same seed, same cards, in the same order.

## What it found

16 UX and data findings, ranked in the session review. The headline: the
stage-advance panel reads `st.face_a.text` only (`docs/js/screens.js:1705`), so
the **75 of 514** quest stage cards across the catalog whose rules text sits on
side B all report *"No setup instructions for this stage."* The Oath's stage 2 is
one of them, and stage 3B's *"cannot be defeated while Goblin Troop is in play"*
is another — so the HUD offered victory with Goblin Troop alive on the board.
