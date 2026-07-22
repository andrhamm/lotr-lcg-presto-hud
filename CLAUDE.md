# LOTR LCG Presto HUD — working notes for Claude

Touchscreen companion HUD for *LOTR: The Card Game*. Two synchronized
implementations:

- **Firmware** (MicroPython, Pimoroni Presto): `gamestate.py`, `phases.py`,
  `ui/`, `main.py`. Deploy with `mpremote` (device auto-runs `main.py`).
- **Web twin** (`docs/`, GitHub Pages: https://andrhamm.com/lotr-lcg-presto-hud/):
  ES-module mirror, same screens/protocol/metrics, localStorage persistence.

## Iron rules

1. **Web first, then firmware.** New features are built and verified in
   `docs/js/`, then ported to the Python. The two stay in lockstep —
   a change that lands in one and not the other is unfinished work.
2. `tools/gen_web_data.py` regenerates shared data (turn sequence, icon
   masks, font metrics) whenever `phases.py`, `ui/icons.py`, or the metrics
   change. Never hand-edit `docs/js/{phases,icons,metrics}.js`.
3. `python3 -m pytest tests/` must stay green (includes the layout linter
   over every screen scene). Add scenes for new screens/modals.
4. Rules claims about the game get verified against the rulebook/FAQ before
   they ship in UI text.

## The TODO board (TODO.md)

`TODO.md` is an Obsidian Kanban board (also plain markdown). Columns:
**Ideas** (user inbox — never work these directly), **Ready** (groomed,
workable), **In Progress**, **Blocked**, **Done**.

Card protocol — a card is one deliverable, moved between columns by editing
the file:

```
- [ ] Short imperative title
  - notes: context, links
  - claim: <worker-id> <date>      when work starts (move to In Progress)
  - blocked: <concrete reason>     when stuck (move to Blocked)
  - done: <commit sha>             when finished (move to Done, tick box)
```

- Grooming Ideas → Ready needs the user (scope/priority is theirs); only
  suggest, don't promote silently.
- One card per worker at a time. Claim before working; unclaim (remove
  claim line) if abandoning.
- A card leaving In Progress goes to exactly one of Done or Blocked —
  never silently back to Ready.

## Background workers

When the main session is idle — waiting on user input, or waiting on
long-running background agents/builds — pick up **Ready** cards with
background workers as time allows:

- Spawn via the Agent tool with `isolation: "worktree"` so workers never
  collide with the main session's tree. One card per agent, the card text
  is the task brief.
- Workers follow the iron rules (web first, tests green, regenerate shared
  data) and commit in their worktree; the main session merges/pushes and
  moves the card to Done with the commit sha.
- Do not deploy to the Presto from workers — device deploys happen only in
  the main session (serial port is single-user, and the user may be mid-game).
- On any worker failure or open question, move the card to Blocked with a
  concrete `blocked:` reason. Never leave a card claimed-but-idle.

**Surface blockers:** whenever ending a turn to the user, if Blocked is
non-empty, list those cards and their reasons in one short line each.

## Device access (main session only)

- Port: `/dev/cu.usbmodem*` via `mpremote`. Stop any running tethered
  session before copying files. The port drops occasionally — if it
  vanishes, the device still runs standalone from flash; ask the user to
  replug rather than retrying blind.
- After deploying, relaunch `main.py` in a background Bash task and check
  its output file for tracebacks before declaring success.
