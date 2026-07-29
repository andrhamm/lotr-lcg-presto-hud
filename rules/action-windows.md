# Action windows

Working notes on when players may act during a round, written for the HUD's
phase views and the planned action-window interstitial.

**Sources.** Seastan's *A Guide to Action Windows* v1.0 (RingsDB decklist
10407, 24 Nov 2018), cross-checked against the DragnCards LOTR-LCG plugin's
own step labels (`jsons/labels.json`, the same data `phases.py` was
transcribed from — same author). Everything below is our summary; no guide
text is reproduced. Where the two sources are worded differently, that is
called out rather than smoothed over.

## The shape of it

A window is the gap *after* a numbered step resolves and *before* the next one
begins. The guide names each window by the step it follows, which is why
"the 3.2 window" means "after characters are committed, before staging".

Two things that are easy to conflate:

- **Actions** need an open window. **Responses** trigger off an event and do
  not — "after X happens" fires on its own, whether or not a window is open.
  This is why the travel window sits *after* travelling: pre-travel effects are
  responses, not actions.
- **Passing is sticky within a window.** A player who declines cannot come back
  in later in that same window, even if the situation changes. In the Planning
  phase specifically, allies and attachments go in player order while actions
  may be taken out of order — and a player who has passed on playing allies
  cannot play them later that turn even if resources appear.

## Where the windows are

Mapped onto this app's `VIEW_ORDER`, so each row is a place the interstitial
could appear.

| Guide's window | Our step | Our view | What it is for |
|---|---|---|---|
| 1.3 | `1.R` | `resource_planning` | After resources and cards, before Planning |
| 2.2 | `2.P` | *(no view — see below)* | Actions interleaved **throughout** the step, which is itself the ally/attachment play |
| 3.1 | `3.1` | `quest_commit` | Before committing — last moment to add a character to the quest |
| 3.2 | `3.2` | `quest_commit` | After committing, before staging — readying, resource shuffling |
| 3.3 | `3.3` | `quest_staging` | **After staging, before resolution** — the decisive one: change willpower, remove staging threat |
| 3.4 | `3.4` | `quest_resolution` | After resolution — clear a just-revealed location before Travel |
| 4.2 | `4.2` | `travel` | After travelling — travel-cost avoidance |
| 5.2 | `5.2` | `enc_optional` | Between optional and forced engagement — engagement prevention |
| 5.3 | `5.3` | `enc_checks` | After engagement checks — last healing before archery |
| 6.2 | — | `combat_shadow` | After shadow cards are dealt, before attacks resolve — **see the note below** |
| 6.4b / 6.4.1 / 6.4.2 / 6.4.3 | `6.E` | `combat_enemy` | Per-enemy: ready a defender, discard a shadow, adjust defence, kill the attacker before damage |
| 6.8.1 / 6.8.2 / 6.8.3 | `6.P` | `combat_player` | Per-attack; the 6.8.3 one is the last window before Refresh |
| 7.4 | `7.R` | `refresh` | After threat is raised — threat reduction, last use of departing allies |

## Planning is not a "then player actions" step

Upstream marks the steps two different ways, and the difference is load-bearing:

- every window step reads "**then** player actions" — the window follows the
  step;
- `2.2-2.3` alone reads "player actions **throughout**".

Planning is the step where *playing allies and attachments is the framework
itself*, with action opportunities interleaved. So "you may play allies in the
planning action window" is the wrong shape: the card-play is the step, not the
window. The guide's own heading for it ("Special Action Window") hints at this
but does not spell it out, and the first draft of our on-screen copy got it
wrong as a result — it told the player the 1.R window was their last chance to
put allies into play, which is neither the right window nor the right activity.

The 1.R window is after resources and cards, before Planning begins. What
happens *in* it is actions and events, not ally deployment.

## The 6.2 discrepancy, resolved

The guide lists a window at 6.2. Our `phases.py` flags 6.2 `action_window:
False`, and that faithfully transcribes upstream: the plugin's label for 6.2 is
the bare `"6.2: Deal shadow cards"`, while every other window step carries a
"then player actions" / "player actions after each combat substep" marker.

**They are not actually in conflict.** Both describe the same moment — after
shadow cards are dealt, before any attack resolves. The guide names it by the
step it follows (6.2); the plugin folds it into `6.3-6.6`'s "after each combat
substep". Corroborated by community discussion of Feint timing: shadow cards
are dealt to every engaged enemy up front, and Feint is played before that
enemy's attack begins to resolve — once resolution starts, it is too late.

**Consequence for this app:** our `combat_enemy` view (`6.E` = 6.3-6.6) is
where that window lives. Do not add an interstitial to `combat_shadow` on the
strength of the guide's "6.2" label alone and then claim 6.2 is a window in our
own data — the two numbering conventions have to be reconciled first, or the
copy will contradict `phases.py`.

## Windows with no substitute

Worth surfacing, because missing them cannot be recovered later in the round:

- **3.3** is the last chance to change a quest outcome. The guide singles it
  out as the one new players most often miss.
- **5.3** is the last chance to heal before archery damage lands.
- **6.8.3** is the last window of the combat phase.
- **7.4** is after threat has already gone up — threat reduction played here
  cannot save a player who has already hit the elimination threshold.

## Out-of-sequence attacks

When a card makes an enemy attack outside the normal framework (during staging,
say), the full set of enemy-attack substeps applies, which opens windows that
would not otherwise exist at that point in the round. Combat-phase-only actions
still cannot be played, because the phase itself has not changed.

## `2.P` has no view

`2.P` is the only step flagged `action_window: True` with no view of its own:
`resource_planning` is mapped to `1.R`. So the Planning window cannot get its
own screen, and the merged view shows Planning copy under a Resource step
stamp. Splitting the two views is filed in TODO.md.

## What is still unverified

- The guide is a community document, not FFG text. The step *positions* are
  corroborated by the plugin data; the *card examples* are not independently
  checked here and should not be quoted as rules in UI copy.
- No rulebook or Rules Reference PDF is checked into this repo, so none of the
  above is verified against primary FFG text. If UI copy is going to make a
  claim a player acts on, verify that specific claim first — see CLAUDE.md's
  rule 4.
