# Play-screen copy inventory — corrected against the Rules Reference

**Status:** for review. Nothing here is implemented yet.

Every view in play order, with the copy it **should** carry. Each line is
checked against the official Rules Reference, now parsed into
`research/rules/` and searchable as the qmd collection `lotr-lcg-rules`
(see `rules/README.md`). Citations are RR step numbers.

Legend: **KEEP** verified as-is · **FIX** currently wrong on screen ·
**ADD** missing rule worth surfacing · **CUT** unverifiable or redundant.

Copy is `BODY` unless marked. Purple = action-window voice, green = framework.

## Copy rules applied throughout

- **No em dashes.** Use two sentences. A dash invites a trailing clause, and a
  trailing clause is where vague copy hides. Splitting "resolve each When
  Revealed" into its own sentence is what exposed that it was narrower than the
  rule. All 11 dashes in the on-screen copy have been removed.
- **Match the rulebook's own words** where they are already plain. "Resolve any
  keywords and When Revealed effects" tracks the `Staging` entry's "any
  keywords and/or when revealed effects"; a paraphrase is a chance to be subtly
  wrong.
- **Name the card type.** Player cards and encounter cards are both on the
  table, so a bare "card" is ambiguous.
- **Two threats, one glyph, two colours.** The game has two unrelated things
  called threat and the copy must not blur them. They share the *same* icon
  shape and are told apart by **ink**:
  - `⟨threat:red⟩` — a **player's** threat dial, starting at the heroes'
    combined cost and eliminating at 50. RR calls it "threat level".
    Already drawn `icons.THREAT` + `pal.red`
    ([screen_play.py:119](ui/screen_play.py:119), [:770](ui/screen_play.py:770)).
  - `⟨threat:black⟩` — an **encounter card's** threat, on a location or enemy,
    which adds to the staging area and is compared against willpower at 3.4.
    RR writes it `$` and calls it "threat strength". Already drawn
    `icons.THREAT_MD` + `pal.outline`
    ([screen_play.py:340](ui/screen_play.py:340)); `pal.outline` is documented
    in [theme.py:67](ui/theme.py:67) as "true black-ish ink (staging threat
    value/icon, shadows)".

  Views 8, 9 and 21 mean red. View 13's tip and anything about the staging
  area mean black. A draft used one token for both; worse, it claimed they
  were different glyphs. The convention already exists in the code, so copy
  just has to respect it.

  Not to be confused with `threat_pen()` ([theme.py:80](ui/theme.py:80)), which
  tints a player's threat **value** green/amber/red by severity. That is a
  status colour on the number, not the icon's identity.
- **Prefer verbs over nouns for actions.** "Optionally engage" beats "optional
  engagements"; "take" is banned outright, since "take an enemy" reads as
  "take out".
- **Never name a mechanic the copy cannot afford to define.** "Each check
  engages…" leans on a term the screen never explains, and every later mention
  inherits the debt. Say what the player does instead: "each player engages…".
  Titles may still use the term, since a title labels rather than instructs.
- **Bold trigger words are reserved.** `Action`, `Forced`, `Response`,
  `When Revealed`, `Travel`, `Surge`, `Doomed` and the rest name printed card
  abilities. Never use one to describe a framework step: a draft opened
  `enc_checks` with "Forced, not optional", but RR defines `Forced` as "a bold
  trigger word" for mandatory triggered abilities and never applies it to
  engagement. Plain wording carries the meaning without the collision.
- **Let modal verbs carry optionality.** View 13 "each player **may** engage",
  view 15 "each player **engages**". The contrast is doing real work; do not
  flatten both to the same verb.
- **Third person only. Never "you".** The Presto sits between four players, so
  second person has no referent: "Lower your threat" does not say whose, and
  "1 enemy engaged with you" is unanswerable on a shared screen. A review found
  six such lines mixed in with third-person copy elsewhere. Name the actor
  instead, using RR's own vocabulary, which already distinguishes them:
  - **the active player** — the one performing the current step (2.2, 6.4a,
    6.8a). Use in diagram rungs and anywhere one player acts alone.
  - **each player** — everyone, in player order (1.2, 3.2, 5.2).
  - **the first player** — the token holder, who opens every action window and
    decides travel.
  - **the players** — the table acting as a group (4.2 travel only).

  ALL-CAPS is `LABEL` chrome per the design system, so a diagram node reads
  "Active player", not "ACTIVE PLAYER".
- **"In player order" leads the sentence it governs.** It is a frame for the
  whole instruction, so a reader needs it before they picture the action, not
  after they already have. A review found the doc split 3/3 between leading and
  trailing; views 4, 5, 13 and 17 now all lead. Diagram rungs are the exception
  and may trail it (views 4, 15), because the flow already shows the sequence
  and the rung is a label rather than a sentence.
- **State nested orderings outer-first, and make the nesting visible.** Two
  ordering rules laid side by side read as a contradiction. `combat_shadow` had
  "…to each engaged enemy, in player order. Highest engagement cost first",
  which offers no clue that one governs the other. RR 6.2 is explicit that
  player order picks *whose* enemies, and engagement cost orders *within* one
  player's enemies, so the copy says "In player order, deal … to each of **that
  player's** engaged enemies, highest engagement cost first".

These belong in `docs/superpowers/specs/2026-07-25-design-system.md` alongside
the existing copy rules once this lands.

## The recap rule

Every window screen used to open by narrating the step the player just left —
"Resources are gained and cards are drawn", "Optional engagement is over",
"Progress has been placed". The player pressed a button on that exact screen a
second ago. The recap reads as if something new happened, so it actively
misleads before it informs.

**A window screen says what you can do now, and what closes when you leave.**
A recap clause survives only when the advice depends on it — "threat has
already gone up" earns its place because it is *why* reducing threat is too
late. Otherwise it goes.

Applied below to all eight window screens.

### The window screen pattern

Consistency was a review finding: two screens expressing the same "act now or
lose it" idea in two different shapes reads as two unrelated warnings. All
eight now follow one shape.

```
[what closes, or what is still unknown]      <- positional, one line
[what to do about it]                        <- actionable, one line
```

The positional line uses **"This is the last action window before X"** wherever
that is the point, so the phrase means the same thing every time it appears.
"Last window" alone was ambiguous on a screen whose title is ACTION WINDOW.

Screens with nothing general worth saying get one line, not a padded second.
View 3 is one: the Resource window closes nothing a player can lose, so a
countdown there would be false urgency. View 10 is the other: whether anything
is worth doing before travel depends entirely on the board, and the invented
line that once filled that slot turned out to be a rules error.

View 21 is the deliberate exception to the shape. Its first line is a *past*
fact ("Threat has already gone up"), because there the damage is done and the
point is that acting now is too late. Every other screen warns before the door
closes; Refresh reports that it has.

**A window screen may also prompt verification.** The HUD's willpower, staging
threat and progress are hand-entered, so a window immediately before a step
that *consumes* those numbers is the last moment to catch a typo. View 8 is the
clearest case: resolution compares the two totals and fixes the outcome. Where
this applies, verify first, then act, because buffing a mistyped total is
wasted.

## How an action window actually works

Stated once here because it governs every window screen and both combat flows,
and because getting it wrong produced a bad Planning diagram (view 4). RR, on
action windows generally:

> When an action window opens, **the first player has the first opportunity**
> to initiate an action, or pass. Opportunities to initiate actions then
> proceed **in player order** until all players **consecutively pass**, at
> which point the action window closes and the game advances to the next step.
> …**Resolve each action completely before the next action opportunity.**

Four consequences the UI should never contradict:

1. A window is a **round-robin of single opportunities**, not a free-for-all
   and not a per-player block. One thing, resolved fully, then the next player.
2. It closes only when everyone passes **in a row**. One player acting reopens
   the rotation for everyone.
3. **Passing is a vote to close the window, not a way to opt out.** A pass
   declines *that one opportunity* and adds to the consecutive-pass count.
   It takes an unbroken round of passes by everyone to close the window; any
   action resets the streak and the rotation comes back around — explicitly
   including to the player who passed. So passing never costs you anything
   the other players did not also accept.
4. The **first player** always acts first in any window.

**What locks you out is the window closing, not your pass.** These are easy to
conflate and the old Planning copy conflated them.

### What is being passed: Actions, not Responses

The rotation above is **only** about action abilities. RR is explicit on both
sides:

- **Action** — "These abilities can only be initiated by a player during an
  action window… An action must be resolved as completely as possible before
  the next action can be initiated."
- **Response** — "**Unlike action abilities, which are resolved during action
  windows**, response abilities may be executed **after the specified
  triggering condition occurs**."

So a response is never something you pass *in a window*. It fires off its own
trigger, including in the middle of a window — a response to an ally entering
play resolves right then, without waiting for anyone's opportunity.

Responses do have their own pass sequence, but it is scoped to **one
triggering condition**, not to the window: "Response opportunities for that
triggering condition alternate between players in this manner until all players
have passed consecutively", after which "further responses to that specific
triggering condition cannot be used". The first player also gets first
opportunity there ("The first player always has the first opportunity to use an
ability in response").

**Consequence for copy:** the loop may say *actions* and be exactly right.
It must not say "cards" or "abilities" generically, which would wrongly sweep
in responses. The existing standalone `Responses.` element on other views is
correct precisely because responses sit outside the window structure.

### Terminology: never say "turn"

There are two nested things here and the word "turn" fits both, which makes any
sentence using it ambiguous. A review draft said *"Each player is the active
player once"* and, four lines later, *"passing does not end your turn… it comes
back to you"* — flatly contradictory on their face, because "turn" silently
switched levels.

Fix the vocabulary and the contradiction disappears:

| Level | Word to use | How often |
|---|---|---|
| Your stint as active player | **your window** | once per phase (RR 2.3) |
| Your slot in the rotation inside it | **an opportunity** | many, until all pass in a row |

So: *passing declines one **opportunity**, not your **window**.* The game has
no "turn" in the board-game sense, and this UI should not invent one. Applies
to the combat screens too — 6.4a/6.8a make each player active once, with
opportunities rotating inside.

### Worked example: a 4-player planning phase

Written out because the prose kept reading as contradictory. P1 holds the
first player token; player order is P1 → P2 → P3 → P4.

**The phase contains four windows** — one per active player (2.2 ↔ 2.3).

Two roles that are easy to merge and must not be:

- **First player** (P1, fixed all round until 7.4) — always gets the *first
  opportunity* in every window.
- **Active player** (rotates 2.2 ↔ 2.3) — the only one who may play allies and
  attachments in their window.

In window 1 these are the same person. **In windows 2–4 they are not**, and
that is the piece the old copy never conveyed.

#### Window 1 — active player: **P1**

| # | Opportunity | Does what | Passes in a row |
|---|---|---|---|
| 1 | **P1** *(first player + active)* | plays Gandalf **and** Beorn | 0 |
| 2 | P2 | pass | 1 |
| 3 | P3 | pass | 2 |
| 4 | P4 | triggers an Action ability | **0 — streak broken** |
| 5 | **P1** *(active)* | plays an attachment | 0 |
| 6 | P2 | pass | 1 |
| 7 | P3 | pass | 2 |
| 8 | P4 | pass | 3 |
| 9 | **P1** | pass | **4 → window closes** |

**P2 passed at #2 and was asked again at #6.** Their pass cost them nothing,
because P4 acted at #4 and reset the streak. That is the whole of "passing is
not sticky".

**P1 played two allies at #1, in one go** (Learn to Play: "any number"), and
still played an attachment later at #5. Being active is not spent by using it;
it lasts as long as the window is open.

→ *2.3: P2 becomes the active player. Return to 2.2.*

#### Window 2 — active player: **P2**

| # | Opportunity | Does what | Passes in a row |
|---|---|---|---|
| 1 | **P1** *(first player, not active)* | pass | 1 |
| 2 | **P2** *(active)* | plays an ally | **0** |
| 3 | P3 | pass | 1 |
| 4 | P4 | pass | 2 |
| 5 | P1 | pass | 3 |
| 6 | **P2** *(active)* | plays a second ally | **0** |
| 7 | P3 | pass | 1 |
| 8 | P4 | pass | 2 |
| 9 | P1 | pass | 3 |
| 10 | **P2** | pass | **4 → window closes** |

P1 still opens the rotation despite P2 being active. P1 may trigger actions
here but **may not** play allies — their own window is over.

→ *2.3: P3 active. Then P4. After P4's window closes, all players have been
active → **2.4 Planning phase ends**.*

#### What the example proves

1. Four windows per phase, not one.
2. A pass is never binding while the window is open.
3. The active player plays **any number** of cards per opportunity, and may
   play more later while the window is still open.
4. Non-active players are not spectators — they take actions in every window.
5. The rotation is anchored to the **first player**, not the active player.

The `, then actions` markers on the combat flows stay correct — they mark
*that* a window opens. This is what happens inside one.

---

## Summary of changes

**Phase views** — 12 of 13 change, plus 1 new (`round_end`):

| # | View | Change | Why |
|---|---|---|---|
| 1 | `setup_game` | **CUT** shuffle-after-searches | Unverifiable — RR shuffles at setup step 1 |
| 4 | `planning` | **FIX** + **ADD** loop | Sticky-pass claim is contradicted by RR |
| 5 | `quest_commit` | **ADD** stays committed, doesn't ready | RR 3.4 |
| 7 | `quest_staging` | **FIX** name the encounter card, widen to keywords; **ADD** deck-empty reshuffle | RR 3.3 + `Staging` |
| 9 | `quest_resolution` | **FIX** tie wording | RR 3.4 — a tie is *not* unsuccessful |
| 11 | `travel` | **ADD** staging area, optional, group decides; **CUT** "explore it first"; control must not hard-disable | RR 4.2 + `Explored` + catalog |
| 13 | `enc_optional` | **ADD** staging area, why to engage, strategy tip; **CUT** duplicate threat line | RR 5.2, 5.3, 3.4 |
| 15 | `enc_checks` | **FIX** "Forced" is reserved; **ADD** loop diagram + high-threat tip | RR 5.3 |
| 17 | `combat_shadow` | **ADD** deck-out note | RR 6.2 |
| 18 | `combat_enemy` | **FIX** caption + rung wording; **ADD** Sentinel fallback | RR 6.4 chart + `Sentinel` |
| 19 | `combat_player` | **FIX** invented window, split step, rung wording; **ADD** both Ranged rules, exhaust cost, no-damage case | RR 6.8 chart |
| 20 | `refresh` | **FIX** icon + auto-apply on load; `End Round` CTA removed | RR 7.2-7.4 |
| 22 | `round_end` | **NEW** view for 0.1; closes a parity gap in `phases.py` | RR 0.1 + upstream steps |

**Window screens** — all 8 change, per the recap rule below:

| # | View | Change |
|---|---|---|
| 3 | Resource | **CUT** recap; keep the positional line |
| 6 | Commit | **CUT** recap; "last **action** window"; tips candidate |
| 8 | Staging | **FIX** — conditional on the pending result, not static advice |
| 10 | Resolution | **FIX** — positional line only; invented "clear a location" claim cut |
| 12 | Travel | **CUT** recap; phase-locked action note, now generalised to all phases |
| 14 | Opt. Engage | **FIX** — say *why* to act: threat drives the checks |
| 16 | Checks | **FIX** — engagements are fixed; ready defenders |
| 21 | Refresh | **ADD** End of Round N + tip; round boundary moves to its CTA |

Everything else is verified unchanged. Full detail below.

---

### 1. `setup_game` — Setup

**Header** `R1 0.0` · `Setup` · **CTA** `Begin Round 1`

> Draw 6 cards. One mulligan, and the second hand must be kept.
> Resolve stage 1A Setup text in printed order.
> Keywords on setup reveals (Surge/Doomed) do resolve.
> Then flip 1A → 1B and begin.

**CUT** — "Shuffle the encounter deck AFTER setup searches" is gone.

RR's Setup entry lists 7 steps; **step 1** shuffles all player decks and the
encounter deck, and **step 7** is "Follow Scenario Setup Instructions… before
flipping the quest card". No general reshuffle after setup searches appears
anywhere, and the `Search` glossary entry does not mandate a shuffle either.
Individual setup cards may instruct one; that belongs on the card, not in
general procedure. Rule 4: if it can't be verified, it doesn't ship.

**KEEP** — mulligan wording matches RR `Mulligan` verbatim: "The player must
keep this second hand." Flip-then-begin matches setup step 7.

---

### 2. `resource` — Resource

**Header** `R1 1.R` · `Resource` · **CTA** `NEXT PHASE` / `Planning`

> Each hero gains a resource and each player draws a card, all at the same
> time. (1 each normally.)

**KEEP.** RR 1.2 "Each player **simultaneously** adds 1 resource to each of
their heroes' resource pools"; 1.3 "Each player **simultaneously** draws 1
card." The "(1 each normally)" hedge is right — effects change the amount.

---

### 3. ACTION WINDOW — Resource

**Header** `R1 1.R` · `ACTION WINDOW · RESOURCE` (purple)

> Anything played here happens before the planning phase begins.

**CUT** the opening recap — "Resources are gained and cards are drawn" just
repeats the screen the player pressed through to get here. See *the recap
rule* below; this is the case that exposed it.

---

### 4. `planning` — Planning  ⚠ rewritten

**Header** `R1 2.P` · `Planning` · **CTA** `NEXT PHASE` / `Questing: Commit`

> In player order, each player becomes the **active player** once.
>
> ```
>   ┌─► Active player
>   │   ├ plays any number of allies + attachments
>   │   │
>   │   └ meanwhile, any player may act, first player first:
>   │       ┌─► one action, or pass, in player order
>   │       └── Repeat until all pass in a row
>   │
>   └── Repeat until every player has been active
> ```
> Only actions rotate. Responses fire on their own trigger, any time.

The card line and the action loop are drawn as **concurrent** ("meanwhile"),
not sequential — see the interleaving evidence below. An earlier draft stacked
them, which implied cards must finish before actions begin.

Two nested loops, which is what makes this phase hard to state in one line:

- **Outer** — the active player rotates once through every player (RR 2.3).
- **Inner** — the action window: one action per opportunity, in player order
  from the first player, closing only on a full round of consecutive passes
  (RR's general action-window rule).

Ally and attachment play sits in the outer loop, **not** the inner one: any
number, by the active player only.

**Do the two interleave? Yes — as far as any source goes.** Weighing what we
have, in the order CLAUDE.md's rule 4 puts them:

| Source | What it says | Bearing |
|---|---|---|
| RR 2.2 | one window holding **both** permissions, no ordering stated | permits interleaving; does not require a block |
| RR general rule | passing is **not** sticky while the window is open | there is no mechanism to lock a player out mid-window |
| Learn to Play | "each player may play any number… then proceed" | a tutorial simplification — never mentions action windows at all |
| **DragnCards** | `2.2 & 2.3: Play cards in turn order — player actions **throughout**` | explicitly interleaved |
| CardGameDB thread | claims you cannot go back to allies once you act | **no citation found**; contradicted by the above |

The DragnCards line is the strongest signal short of FFG text. Its plugin data
labels **every other step** `then player actions` — the window *follows* the
step — and **2.P alone** says `player actions throughout`. That wording is a
deliberate distinction by the same author who wrote the RingsDB action-windows
guide, and it exists precisely to mark this phase as the one where actions run
alongside rather than after.

Combined with RR's non-sticky passing, the "cards first, then actions, no going
back" reading has nothing supporting it. **Treat the two as interleaved.**

**Consequence for the diagram:** showing the inner action loop *below* the card
line implies a sequence that does not exist. Prefer a layout that reads as
"these are both available while you are active" — e.g. the action loop bracketed
alongside the card line rather than after it. Whatever the layout, the copy must
not say cards come first, and must not say you cannot go back.

**Data gap to fix during implementation:** our `phases.py` records
`2.P … "2.2-2.3 Play cards in turn order", action_window: True` and **drops the
`player actions throughout` suffix**. Upstream's three shapes (`then` /
`throughout` / `after each combat substep`) are exactly what decides whether a
step gets a window screen, so the distinction should be captured in the data
rather than re-derived from prose each time.

Rewritten table-facing. An earlier draft was second person ("your window",
"comes back to you"), which is wrong for a device shared by four players — it
reads as addressing whoever is holding it. It also omitted that the rotation
starts with the **first player**, not the active player, which is the single
most confusable point (see the worked example above).

**Space concern for implementation:** this is five lines plus a rule of thumb,
at `BODY`. The Planning view also carries the players matrix and progress
rings. If it does not fit, the fix is to say less — not to drop to `LABEL`.
Candidate cut: the "First player starts" clause, which matters most in windows
2–4 and least on a first read.

**Cadence resolved — "one per opportunity" was wrong, and is removed.**

An earlier draft inferred that the active player plays allies one per rotation
slot, coming back around. **Learn to Play contradicts that directly**, and it
is primary FFG text:

> **Starting with the first player and proceeding clockwise, each player may
> play any number of ally and attachment cards from their hand.** To play a
> card, a player must pay the card's cost… After each player has had an
> opportunity to play cards, proceed to the quest phase.

So the active player plays **any number** in their own go. That also fixes the
reading of RR 2.2's "as many… as they desire and can afford **at this time**" —
"at this time" means *while they are the active player*, not *spread across
rotations*. The two books agree once read together.

The worked example above still holds for **actions** — that rotation is real
and is what RR's general action-window rule describes. What was wrong was
forcing ally play into the same cadence.

**FIX.** Current screen says *"Once you pass on playing allies you cannot
return to it this turn."* RR contradicts the mechanism:

> if a player passes their opportunity to act, but all other players do not
> consecutively pass in sequence, the original player **may still take an
> action** when the progression comes back around to that player.

What is actually true, in two parts:

- **Who may play allies:** RR **2.2** permits ally/attachment play to **the
  active player** only.
- **How long they may:** until the window closes — and the window closes only
  when *all players consecutively pass*, not when the active player passes
  once. RR **2.3** then makes the next player active, and "if all players have
  been the active player this phase, proceed", so each player is active exactly
  once per phase.

So the old copy reached a roughly right conclusion — you cannot play allies
again later in the phase — through a mechanism that does not exist, and in
doing so taught the player something false about *actions*, which remain
available to them in every subsequent player's window.

Sharpest version of the distinction: **your pass does not lock you out; the
window closing does, and closing it takes everyone.** Concretely — you are
active, you pass, another player triggers an action; the streak breaks, the
rotation returns to you, and you may still play an ally.

**Diagram corrected after review.** An earlier draft showed
`…then actions → play allies → …then actions`, which invented a structure the
rules do not have and implied allies must all be played in one burst between
two action opportunities. They do not. Per the general action-window rule, a
window is a **single round-robin of one-thing-at-a-time opportunities**:

> When an action window opens, the first player has the first opportunity to
> initiate an action, or pass. Opportunities to initiate actions then proceed
> in player order until all players consecutively pass… **Resolve each action
> completely before the next action opportunity.**

The active player plays allies **one at a time**, taking each opportunity in
that same rotation, coming back around as long as the window stays open (RR 2.2:
"remains open until all players consecutively pass"). Non-active players are
not idle — they take ordinary actions in the same rotation.

**Ally play is *additional*, not instead.** A draft read "Everyone else may
take actions", which excluded the one player the rule explicitly includes.
RR 2.2: the active player, "**in addition to** triggering standard action
abilities", is permitted to play ally and attachment cards. So every player —
active included — may trigger actions; the active player alone may *also* play
allies and attachments. Corrected to "Any player may take actions, in player
order."

**On "can the first player choose to be active first or pass?"** — no choice
about the *role*: 2.3 advances the active player in player order, and player
order begins with the first player, so the first player is active first by
position. What they *can* do is pass their action opportunities and play
nothing. Being active is positional; using it is optional.

**Note on `Active Player`** — RR's glossary defines it as "a player who is
obligated to perform (or granted the option to perform) a specific game
function during a framework step or special action window". So the term is not
Planning-specific; it is the same role the combat views use (6.4a, 6.8a). Worth
keeping the wording identical across all three screens.

---

### 5. `quest_commit` — Questing: Commit

**Header** `R1 3.2` · `Questing: Commit` · **CTA** `NEXT PHASE` / `Questing: Staging`

> In player order, exhaust characters to commit them and add their willpower.
> They stay committed for the whole phase and do not ready at resolution.

**KEEP** first line — RR 3.2 near-verbatim: "In player order, each player has
an opportunity to commit any number of their characters to the quest. To
commit a character to a quest, a player must exhaust the character."

**ADD** second line — RR 3.4: "Characters committed to a quest are considered
committed to that quest through the end of the quest phase… Those characters
do not ready at the end of this step." Actionable: it is why a quester cannot
also defend.

---

### 6. ACTION WINDOW — Questing: Commit

> This is the last action window before staging.
> Anything played now resolves before any encounter card is revealed.

**CUT** "Characters are committed" (recap). The rest stays — "not revealed
yet" is not a recap, it is the whole reason this window matters: you are
acting on known information for the last time. Matches 3.2 → 3.3.

**"last *action* window"** — the bare "last window" was ambiguous on a screen
whose own title is ACTION WINDOW; it could read as "last screen". Say which
kind of window it is.

**Candidate for stage-contextual tips.** This is the strongest place in the
round for them: the player is deciding commitments against a deck they cannot
yet see, so anything the catalog knows about *this stage* is decision-relevant
before it is too late. We already ship the data — `docs/data/tips.json` carries
per-stage `stages` tips, loaded via `quest_catalog.tips_for()` / `tipsFor()`,
covering 122 scenarios. Today only `QuestCardModal` reads them.

Open design questions if we do it: whether a stage tip replaces or joins the
generic window copy, and what the fallback is for the ~2/3 of scenarios with no
distilled tips (the button already handles absence by staying disabled, so the
window screen needs an equivalent graceful empty state). Worth a decision
before implementation, not during.

---

### 7. `quest_staging` — Questing: Staging

**Header** `R1 3.3` · `Questing: Staging` · **CTA** `NEXT PHASE` / `Questing: Resolution`

> Reveal 1 **encounter card** per player, one at a time. Resolve any keywords
> and When Revealed effects before the next.
> If the encounter deck empties, shuffle the discard pile back in.

**FIX** the first line, twice over.

*Card type.* "1 card per player" never says *which* card type, on a screen
where player cards are also in play. Naming the encounter card fixes it.

*Scope.* "resolve each When Revealed" is narrower than the rule. The `Staging`
glossary gives the per-card procedure as: reveal → "Resolve any **keywords
and/or when revealed effects**" → place. Step 3.3's own wording mentions only
when-revealed abilities, but the glossary is the fuller statement and the two
are not in conflict — 3.3 is describing the ordering constraint, not
enumerating what resolves.

This matters most for **Surge**, which reveals an *additional* encounter card:
copy that mentions only When Revealed understates how many cards can hit the
table from a single reveal. Doomed likewise raises threat at staging. Our own
`setup_game` copy already says "Keywords on setup reveals (Surge/Doomed) do
resolve" — the staging line should not be narrower than the setup line about
the same mechanic.

**Not changed: no "In player order".** The suggestion was to open this line the
way view 5 does. It cannot, and the contrast in RR is deliberate:

- 3.2 — "**In player order**, each player has an opportunity to commit…"
- 3.3 — "**The encounter deck** reveals one card per player."

RR uses "in player order" wherever it applies, and does not here. Nor do
players individually reveal: the *deck* reveals, and "per player" is a **count**
that scales the reveal to table size — the cards are not dealt to anyone and do
not belong to the player they were counted for. Writing "each player reveals
and resolves 1 encounter card" would assert both an ordering and an ownership
the rules do not have, and ownership especially matters because a When Revealed
often reads "each player…" rather than affecting one player.

The underlying complaint was right — the line was awkward and ambiguous — but
the fix is naming the card type, not adding player order.

**KEEP** the rest — RR 3.3 verbatim in substance: "revealed one at a time,
with any when revealed abilities being resolved before the next card is
revealed."

**Also verified while here** — the `Staging` glossary entry gives the per-card
procedure, and our copy is consistent with it: reveal → resolve keywords and
When Revealed → place (staging area for enemy/location/objective, discard for
treachery).

**ADD** second line — RR 3.3: "If the encounter deck is ever empty during the
quest phase, the encounter discard pile is shuffled and reset back into the
encounter deck." Note this reshuffle is scoped to the **quest phase**; the
combat-phase deck-out behaves differently (see view 17), which is exactly why
both are worth stating.

---

### 8. ACTION WINDOW — Questing: Staging

**Always shown:**

> This is the last action window before quest resolution.
> Confirm the tracker matches the board.

**Plus one line conditional on the pending result**, which this view already
computes and displays:

Every conditional line opens **"Without actions,"** so it reads as a
consequence this window can still change, not a verdict. That phrase is the
tie-in between the pending number and the reason the player is looking at an
action window at all.

| Pending | Conditional line | Cited |
|---|---|---|
| Fail, and a player would reach 50 | `Without actions, P3 is eliminated at 50 ⟨threat:red⟩.` | RR: "If a player's threat level reaches 50, that player is immediately eliminated" |
| Fail | `Without actions, each player raises ⟨threat:red⟩ by 3.` | RR 3.4 (player threat) |
| Tie | `Without actions, no progress and no ⟨threat:red⟩. Each +1 ⟨willpower⟩ places 1 ⟨progress⟩.` | RR 3.4: "not quested successfully or unsuccessfully" |
| Success, room left | `Each +1 ⟨willpower⟩ places 1 more ⟨progress⟩.` | RR 3.4 |
| Success, at or past the stage's points | `⟨progress⟩ past 8 is discarded.` | Quest overflow does not carry forward (p.22) |

⟨threat:red⟩, ⟨willpower⟩ and ⟨progress⟩ are the game icons, not the words, per
the design system's icon vocabulary. Every threat on this view is the
**player** dial, so it is red ink. Nothing here refers to a location's or
enemy's threat, which would be ⟨threat:black⟩.

**Why "Without actions," and not a bare statement.** A line reading
"P3 is eliminated at 50" states a fact the player cannot obviously act on, and
on an action-window screen that reads like a verdict already delivered. The
prefix makes the whole line conditional and puts the outcome inside the
player's control, which is the one thing this screen exists to communicate. It
also does the work the rejected coaching drafts were trying to do — prompting
the player to consider acting — without naming plays or telling them how.

**Success splits in two, and the split is load-bearing.** Stating the exchange
rate ("each +1 ⟨willpower⟩ places 1 more ⟨progress⟩") is only true while the
stage has room. Past its quest points the extra is **discarded**, so the same
line would be advising a play that wastes cards. Same for the tie: +1 willpower
turns a tie into a 1-progress success, which is the cheapest win on the board
and easy to miss because a tie reads as failure.

Note the success lines drop the `Without actions,` prefix. Nothing bad is
pending, so there is no consequence to hold off; the fact *is* the invitation.
The prefix belongs only where the pending result is one the player would want
to change.

**Which cap to test.** The discard applies to the **quest card**, not to
locations: progress fills the active location first and its overflow *does*
flow on to the quest (RR 3.4), while progress past the **stage's** quest points
is discarded on advance (p.22). So the "room left" test is against remaining
quest points plus any unfilled active-location capacity, not against the quest
card alone. Getting this backwards would tell a player their willpower is
wasted while a location is still absorbing it.

**FIX**, rewritten twice. The first pass ("Last chance to change either total.
The comparison happens next and fixes the result.") had two faults:

*Voice drift.* View 6 says "This is the last action window before staging."
This one said "Last chance to change either total", a different shape for the
same idea. Both are last-window-before-X screens and should read alike. See
*the window screen pattern* below.

*Two jobs, tangled.* The screen is doing two things at this moment and the
copy blurred them:

1. **Verify the tallies.** Willpower and staging threat are hand-entered on the
   previous screens. Resolution compares them and fixes the outcome, so an
   entry error here silently produces a wrong result. This is the last screen
   where it can be caught.
2. **Change the tallies.** Effects that add willpower or remove staging threat
   are playable now and not after.

"Check both totals, then boost willpower or reduce staging threat" does both,
in the order the player needs them: no point buffing a total that was mistyped.

*"either total"* also went. Naming **willpower** and **staging threat** matches
the two figures the view already displays, and the rest of the round names its
numbers rather than gesturing at them.

**Why it went conditional.** Three static drafts were rejected in review, and
the reason they all failed is the same: they **coached**. "Check both totals,
then boost willpower or reduce staging threat" tells a player something they
already know — anyone sitting in this window knows those two numbers decide the
quest. Generic strategy advice is noise on a screen the player reaches every
round.

What the app knows and the player might not is the **pending result**. This
view already computes and shows it ("You will gain 4 at resolution"), so the
copy can react to the actual game state instead of lecturing. That turns the
line from advice into information, which is the same reason the Refresh and
Travel windows work.

Faults from the rejected drafts, recorded so they do not recur:

- **Do not restate the obvious.** If a competent player already knows it, it is
  not worth a line. Prefer a fact the app computed, or a consequence of the
  rules they may not have connected. This is *not* a ban on explaining why a
  step exists: view 13 earns its tip because the reason to engage voluntarily
  is non-obvious and RR-derived.
- **No doubled urgency.** The positional line states the deadline; a second
  "now" or "while you can" adds pressure without information.
- **No vague verbs.** "Change them" names no action.

**Rules behind each conditional**, all verified:

- **Elimination** is immediate at 50, so a pending failure that crosses it is
  the single most important thing on the screen. The Refresh view already
  previews threat this way (`P3 41→42!`), so the treatment is consistent.
- **Failure raises *each* player's threat** by the difference (RR 3.4), which
  is why the line is per-player, not a single number.
- **A tie is neither success nor failure** (RR 3.4) and does nothing at all.
  Worth saying, because a tie looks like a failure on a tracker.
- **Overshoot is wasted.** Progress beyond the stage's quest points is
  discarded, not carried forward (p.22). A player about to overcommit
  willpower is spending cards for nothing, and nothing else in the round tells
  them.

The player's own levers stay unstated, which is deliberate: lowering threat,
reducing staging threat, and exploring the active location so progress reaches
the quest card are all real plays, but naming them is the coaching that got
cut. The `Without actions,` prefix carries the prompt to act; choosing *which*
action is the player's.

**Open:** whether the conditional line replaces "Confirm the tracker matches the
board" or sits below it. Three lines may not fit at `BODY` alongside this
view's widgets.

Still the window the RingsDB guide singles out as most often missed, and 3.3 →
3.4 is where the result gets locked.

---

### 9. `quest_resolution` — Questing: Resolution  ⚠ tie wording

**Header** `R1 3.4` · `Questing: Resolution` · **CTA** `NEXT PHASE` / `Travel`

Outcome lines:

| Outcome | Copy |
|---|---|
| willpower > threat | `Place 4 ⟨progress⟩` **[DISPLAY]** · "Location fills first, then the quest." |
| willpower < threat | `Each player raises ⟨threat:red⟩ by 3` **[DISPLAY]** |
| **equal** | `No ⟨progress⟩, no ⟨threat:red⟩.` **[DISPLAY]** · "Neither successful nor unsuccessful." |

Then, per outcome, because the tracker behaves differently in each:

| Outcome | Line |
|---|---|
| success | `Allocate the ⟨progress⟩, then Next: Travel applies it.` |
| fail | `Tracker raised each player's ⟨threat:red⟩. Enter any card effects yourself.` |
| tie | *(nothing to apply)* |

**FIX.** Current copy reads *"Quest unsuccessful — a tie, no change"*
([ui/screen_play.py:746](ui/screen_play.py:746), [:762](ui/screen_play.py:762)).
RR 3.4 denies that explicitly:

> If the combined committed Ò score is equal to the $ score in the staging
> area, the players have **not quested successfully or unsuccessfully**: no
> progress tokens are placed, and the players do not increase their dials.

This one can cause a misplay: cards trigger off "if the players
**unsuccessfully** quest", and a tie must not fire them. The tie is already
handled correctly in code — only the label is wrong.

Em dash removed from the tie line at the same time; it is two sentences now,
per the copy rules.

**Check while there:** failure raises **each player's** threat by the
difference (RR 3.4), not a single shared amount.

**KEEP** "Location fills first, then the quest" — RR 3.4 note.

**ADD: say what the tracker does, which is not the same in each outcome.** A
draft put one line on all three ("Tracker updated. Enter any card effects
yourself"), which is wrong for success. `resolve_quest`
([gamestate.py:810](gamestate.py:810)) is explicit in its own docstring:
success "returns budget for the allocation modal; **does NOT place progress**",
failure "raises each living player's threat by the shortfall", tie "no change".

So on a **failure** the tracker has already moved the dials and the player only
needs to layer card effects on top; on a **success** nothing has been recorded
yet and the player still has to allocate progress between location, quest and
side quests before the CTA commits it. Telling them "tracker updated" in that
state would invite them to walk away from an unapplied result.
Without that, a careful player cannot tell whether the number on screen is a
prediction they still have to enact or a change already recorded, so they
either double-apply it or distrust the tracker.

**And say what the tracker cannot know.** This is the more important half. The
HUD computes the outcome from two hand-entered totals; it has no idea a card
just moved progress, cancelled the threat raise, or placed a token elsewhere.
Those effects are exactly the ones that get silently forgotten, because the
screen looks authoritative and settled. "Enter any card effects yourself" marks
the boundary between what was computed and what the player still owns.

This boundary is not unique to this view — the same is true anywhere the HUD
derives a number. Resolution is where it matters most because the value is
applied automatically and the round moves on. Worth deciding during
implementation whether this becomes a standard element wherever the tracker
writes state, rather than a one-off line here.

---

### 10. ACTION WINDOW — Questing: Resolution

> This is the last action window before travel.

**FIX**, twice. The original ("Progress has been placed. The travel opportunity
comes next.") was recap plus schedule and told the player nothing.

My replacement — *"Clear a just-revealed location before it becomes the active
one"* — was worse, because it was **wrong**, and it was my invention rather
than anything a source says. Two faults:

- **Locations do not become active on their own.** A location revealed during
  staging goes to the **staging area**. It becomes the active location only if
  the players *travel* to it, and travel is a group choice with the first
  player deciding (RR 4.2). The line describes an automatic progression that
  does not exist.
- **"Clear" is undefined** for a card sitting in the staging area.

Traced back, the idea came from the RingsDB guide's gloss on the 3.4 window
(deal with a location before Travel). That reading assumes travel is forced.
It is not, except where a specific quest card says so, which makes it a
scenario-specific claim and not something general copy may assert.

**Left as the positional line alone.** Unlike views 8 and 14, this window has
no general lever worth naming: whether anything is worth doing here depends
entirely on the board. Saying only what is true beats inventing a reason for
the screen to exist. Same treatment as view 3.

Deliberately **not** duplicated here: "travel is blocked while a location is
active" is real (RR 4.2) but belongs to view 11, which already says it. Two
screens in a row making the same point is the drift this pass exists to remove.

---

### 11. `travel` — Travel

**Header** `R1 4.2` · `Travel` · **CTA** `NEXT PHASE` / `Encounter: Opt. Engage`

> Travel to one location in the **staging area**. It is optional: the players
> decide as a group, and the first player has the final say.
> No travel while a location is active.

Conditional, when a location is already active:

> A location is already active, so there is no travel this phase.

**ADD "Travel is optional."** RR 4.2 gives the first player "the final decision
on **whether** and where to travel", and describes the phase as an
"**opportunity** to travel". Nothing in the round compels it. This was missing
and it is the single most useful thing the screen can say: every other phase
tells you to do something, so a bare list of travel constraints reads as an
instruction to travel.

**KEEP** the group decision — RR 4.2: "The players (as a group) have the
opportunity to travel to any one location in the staging area." Travel is the
one phase with no player order at all, and the tiebreak is not obvious.

**KEEP** the block, which is RR 4.2: "Players cannot travel to a new location
if another location card is active."

**CUT "Explore it first."** It advises something the player generally cannot do
at this point in the round. A location is explored when progress on it reaches
its quest points (`Explored`: "If the number of progress tokens on a location
is equal to or greater than its quest points, that location is considered
explored"), and progress is placed at **3.4**, which is already over by the
time this screen appears. Exploring during the travel phase needs a card effect
that places progress out of sequence, which is the exception, not the
instruction.

RR's own sentence does continue "the players must explore the active location
before traveling elsewhere", but that is stating the *precondition* for a
future travel, not an action available now. Copying the clause across turned a
constraint into a suggestion the player cannot act on.

**ADD "staging area".** RR 4.2 travels "to any one location **in the staging
area**". Without naming it, "travel to a location" is ambiguous on a table
holding locations in two places, and it hides the fact that the choice is drawn
from exactly the set the player just watched arrive during staging.

### The travel control must not be hard-disabled

The obvious implementation of "no travel while a location is active" is to grey
out the travel control. **The card data says that would be wrong.** Every one of
the three rules above is overridden by printed cards:

| General rule | Cards that override it | Examples |
|---|---|---|
| Travel is optional | **29** | `The Nine Walkers`, `The Hunt is Up!`: "During the travel phase, the players **must** travel to a location, if able" |
| Travel happens in 4.2 | **7** | `Strider's Path`: "Response: After a location is revealed… **immediately travel** to that location"; `Dreadful Gap`, `Down the Brandywine` |
| One active location | **7** | `The Gates of Moria`: "**There can be 2 active locations**"; `Fisherman's Dock`: "(There are now 2 active locations)"; `Thrór's Map` |

Plus a long tail of scenario-specific bans (`Players cannot travel to West Bank
locations`, `The players cannot travel here unless they are at stage 3B`) that
no general rule predicts.

**Design rule this implies: the HUD tracks, it does not enforce.** Where the
tracker would block a legal play, it must offer a way through. Concretely for
this view: dim the travel control and show the conditional line, but keep it
operable, because a player at `The Gates of Moria` legitimately has two active
locations and a player holding `Strider's Path` legitimately travels outside
this phase. A control that is merely *discouraged* communicates the rule
without lying about the exceptions.

This generalises past travel. Any place the UI is tempted to enforce a rule,
check the catalog first: this game's design is largely *printed exceptions to
the framework*, so a tracker that hard-codes the framework will eventually be
wrong at the table, and it will be wrong in exactly the unusual situation where
the player most needs it.

---

### 12. ACTION WINDOW — Travel

> This is the last action window in the travel phase.
> "Travel Action:" abilities work only here.

**Generalise this to every phase.** RR: "Some action abilities have a phase name
as a precursor to the word 'Action.' Such abilities… can only be initiated
during an action window **in the specified phase**." That makes a phase-locked
action the one thing genuinely lost when a phase ends, so it earns a line in
every phase, not just travel.

Counted in the compiled card data (6,037 cards with text):

| Prefix | Cards | Phase | Say it on |
|---|---|---|---|
| `Planning Action:` | **42** | Planning | view 4 |
| `Combat Action:` | **42** | Combat | view 18 |
| `Quest Action:` | **38** | Quest | view 6 (first quest window) |
| `Travel Action:` | **25** | Travel | view 12 |
| `Refresh Action:` | **18** | Refresh | view 21 |
| `Encounter Action:` | **8** | Encounter | view 14 (first encounter window) |
| `Resource Action:` | **1** | Resource | **omit** |

Three calls that follow from the counts:

- **Once per phase, not once per window.** The quest phase has three window
  screens (6, 8, 10) and the encounter phase two (14, 16). `Quest Action:` is
  live across all of them, so saying it on each is repetition; put it on the
  first window of the phase, where the phase still has the most left to run.
- **Omit Resource.** One card in the entire catalog prints `Resource Action:`.
  A line that applies to 1 of 6,037 cards is not worth the space, and this
  keeps view 3 at its single line.
- **`Valour Action:` (9) is not a phase** and must never be added to this
  pattern. Valour is a keyword condition (threat-based), not a step of the
  round, so a Valour Action is not lost when a phase ends.

**CUT** the recap. The card-text claim stays and is verified against the
compiled card data: 25 cards print `Travel Action:`. Adding "last window for
them" makes it actionable rather than trivia.

---

### 13. `enc_optional` — Encounter: Opt. Engage

> In player order, each player may engage 1 enemy in the **staging area**.
> Engagement cost is ignored here, so a player can engage an enemy far above
> their ⟨threat:red⟩.

Plus a strategy tip, in the tip treatment:

> Optionally engage to protect weaker players. Engaged enemies leave the
> staging area and won't contribute their ⟨threat:black⟩ next round.

**ADD "in the staging area".** RR 5.2 says it outright: "one option to engage
one enemy **in the staging area**". Without it, "engage 1 enemy" does not say
where the enemy comes from, and staging is the only legal source.

**CUT "Your threat decides which enemies can engage you next."** Two reasons:

- It duplicates view 14, which now says "Lower your threat and fewer enemies
  can reach you" on the window that sits between this step and the checks.
  Same point, better placed, since that is the window where a player can still
  act on it.
- "next" was ambiguous and the natural repair is wrong. Engagement checks are
  **5.3**, the next *step* inside the **same** phase; the encounter phase runs
  5.1 to 5.4. Writing "in the next phase" would point at combat and be plainly
  incorrect.

**ADD the reason to engage voluntarily.** The old copy stated the rule
(engagement cost does not matter) without saying why a player would ever use
it, which is the actual question this screen raises. The answer falls straight
out of the contrast between the two steps, so it needs no strategy claim:

- **5.2** — "The enemy's engagement cost has **no bearing** on this procedure."
- **5.3** — an enemy engages only if its engagement cost "is equal to or lower
  than this player's threat level".

So optional engagement is the one moment a player can pull an enemy whose
engagement cost sits far above their threat, which the checks would never hand
them. That is the mechanical point of the step and it is fully cited.

**ADD the strategy tip.** Both motives raised in review — shielding a player
who cannot handle an enemy, and reducing staging threat — turn out to be the
same mechanical fact seen from two sides, which is what makes them worth one
line rather than two.

An engaged enemy sits in front of a player, **not in the staging area**. So an
enemy taken at 5.2:

- is not among the "enemies remaining in the staging area" that 5.3 checks
  against, so it cannot engage anybody else this round; and
- is not among "all cards in the staging area" whose threat strength 3.4
  compares next round.

Both halves are RR-cited, so this is a consequence of the rules rather than
table opinion. It also answers the question the screen actually raises: the
step is optional, so why opt in.

A note on how this was nearly lost. An earlier draft cut both motives as
"coaching", generalising from a correction about **view 8**, where the rejected
copy restated something every player already knows (that willpower and threat
decide the quest). That is a different thing. This tip is non-obvious, is
derived from the rules, and was explicitly asked for. The rule worth keeping
from view 8 is *do not restate the obvious*, not *never explain why a step
exists*.

---

### 14. ACTION WINDOW — Encounter: Opt. Engage

> This is the last action window before engagement checks.
> Lower ⟨threat:red⟩ now and fewer enemies can engage.

**FIX.** Old copy was pure recap plus a schedule note. RR 5.3 makes the
actionable version obvious: engagement checks compare each enemy's engagement
cost against **your threat level**, so threat reduction played here directly
changes which enemies engage. That is the only reason to act in this window.

---

### 15. `enc_checks` — Encounter: Checks

> Not optional. In player order, each player engages one enemy at a time.
>
> ```
>   ┌─► First player engages the staging enemy with the
>   │   highest engagement cost at or below their ⟨threat:red⟩
>   │   Each remaining player does the same
>   └── Repeat until no enemy in staging can engage anyone
> ```

Plus a strategy tip, in the tip treatment:

> Higher ⟨threat:red⟩ pulls bigger enemies.

**FIX.** The old line ("One check engages one enemy: the highest engagement
cost that is ≤ your threat") was accurate but led with its weakest part and
buried the two things a player needs.

**"Check" is gone from the body.** Both the old copy and my first rewrite built
their sentences on a noun the screen never defines: *a check* is RR's name for
one player comparing their threat level against the staging enemies, and
nothing on screen says so. Leading with "Each check…" asks the player to price
a term before they have it, and every later reference ("checks repeat") inherits
the debt.

Describing the action instead removes the need for the term entirely: **in
player order, each player engages** the qualifying enemy, and that repeats. The
view title can keep the word, because a title labels rather than instructs, and
by the time it matters the body has shown what happens.

General rule this suggests: **do not name a mechanic the copy does not have
room to define.** Prefer the verb form of what a player does.

**ADD "Not optional."** The step immediately before this one is *optional*
engagement, and the two screens sat next to each other with nothing marking the
difference. This is the whole distinction between 5.2 and 5.3, and it belongs
first.

**"Forced" was the wrong word and is banned.** A draft opened "Forced, not
optional." `Forced` is a **reserved trigger word**: RR's `Forced` entry reads
"Forced is a bold trigger word. If the word 'Forced' precedes a triggered
ability, the ability's initiation is mandatory." It names a class of card
ability, and RR never uses it for engagement checks. Putting it on a framework
step invites the player to read it as the keyword.

The same trap applies to `Action`, `Response`, `When Revealed`, `Travel`,
`Surge`, `Doomed` and every other bold trigger word: **use them only for the
printed ability they name.** Plain "Not optional" carries the meaning with no
collision.

The modal verb already does quiet work here too: view 13 says players **may
engage**, this one says each player **engages**. Keep that contrast intact.

**ADD the tip.** Two consequences of RR 5.3, neither obvious from the rule as
stated:

- **Higher threat pulls bigger enemies**, not just more of them. The
  check takes "the enemy with the **highest** engagement cost that is equal to
  or lower than this player's threat level", so raising threat does not merely
  make engagement likelier, it changes *which* enemy arrives. A player at 40
  pulls the 38-cost enemy that a player at 20 could never draw.
- **A single player can be engaged repeatedly.** RR: "Once all players have made
  an engagement check, the first player makes **second** engagement check.
  Players continue making engagement checks in this manner until there are no
  enemies remaining in the staging area that can engage any of the players." So
  the highest-threat player can absorb several enemies in one encounter phase.
  This pairs with view 13's tip, which is the lever for doing something about
  it.

### The loop diagram, added after review

I first argued against a diagram here on the grounds that the loop body was a
single repeated action. **That was a misreading of 5.3.** There are two nested
loops, and the outer one's body is a whole player-order pass:

> The first player compares their threat level against the engagement cost of
> each of the enemies in the staging area… After the first player makes an
> engagement check, the next player (in player order) makes an engagement
> check. **Once all players have made an engagement check, the first player
> makes second engagement check.** Players continue making engagement checks in
> this manner until there are no enemies remaining in the staging area that can
> engage any of the players.

So the shape is: each player engages one enemy in player order, then the whole
rotation runs again, and again, until no enemy in staging can engage anybody.
Structurally that is the same nested loop as Planning, not the flat repetition
I described.

**Every loop view has the same three-part shape.** A review found views 18 and
19 had no framing line at all and buried "in player order" in a caption *below*
the flow, while 4 and 15 stated it above. Now all four read:

```
[framing line]      what the whole loop is, leading with "In player order,"
[the diagram]       the loop body and its exit
[note]              one consequence, optional
```

The framing line is what tells a reader whether the diagram is one pass or a
rotation, so it has to come before the diagram, not after it. Stating the
player order twice (above *and* inside a rung) was also trimmed: view 15's
inner rung dropped its ", in player order" once the framing line carried it.

**Loop exits are always written `Repeat until <condition>`.** Every diagram's
closing rung states the exit the same way, so the shape reads identically
across the four views that have one. Earlier drafts mixed forms ("another
enemy? repeat", "Any enemy still able to engage? Start over", and a Planning
rung that simply ran the sentence on), which made four diagrams look like four
unrelated notations. A question-shaped rung is worse than a statement here: it
asks the player to work out the answer at the exact moment they want to be
told it.

The test itself still holds: **draw the loop when the body has two or more
steps, or when something happens between them; otherwise say it in a
sentence.** What failed was counting the steps, not the rule. Worth noting the
failure mode, because it is the third time in this pass that a single prose
sentence ("this repeats until…") hid a structure the rules actually specify:
compressing a loop into a clause makes it easy to stop seeing it.

By the corrected count, `enc_checks` earns a diagram, combat keeps both of
its, and Planning does too.

**Implementation note: there is no engagement-cost icon.** `ui/icons.py` ships
`THREAT`, `WILLPOWER`, `ATTACK`, `DEFENSE` and `ARCHERY` only, so engagement
cost has to be spelled out as words. Do not substitute ⟨threat:black⟩ for it:
engagement cost and threat strength are different printed values on the same
enemy card, and swapping them would be a rules error, not a styling choice.

---

### 16. ACTION WINDOW — Encounter: Checks

> This is the last action window before combat.
> Questers are still exhausted, so ready defenders.

**FIX.** Old copy was recap plus schedule.

A draft of this line said "who you are fighting is now fixed", which
overstates: RR 5.3 says an enemy may engage "through an engagement check,
**through a card effect**, or through a player's choice", so the engagement
set is not frozen after 5.3. Dropped that framing.

What is solid: 5.3 is the last step before 6.1, and RR 3.4 leaves everyone who
quested exhausted ("Those characters do not ready at the end of this step"),
so readying a defender here is the concrete play. Pairs with view 5.

The earlier archery claim stays removed — archery appears on the play-sequence
chart but its timing is not stated in RR's numbered steps, so it is still
uncited.

---

### 17. `combat_shadow` — Combat: Shadow Cards

> In player order, deal 1 facedown shadow card to each of that player's
> engaged enemies, highest engagement cost first.
> If the encounter deck runs out, those enemies get none this round.

**KEEP** first line — **now verified.** This carried an *unverified* flag for
months. RR 6.2 confirms both clauses: "Deal shadow cards to each player's
enemies **in player order**… deal to the enemy with the **highest engagement
cost first**, to the enemy with the next highest engagement cost second."

**ADD** second line — RR 6.2: "If the encounter deck runs out of cards, any
enemies that have not been dealt shadow cards are not dealt shadow cards this
round." No reshuffle here, unlike the quest phase (view 7).

---

### 18. `combat_enemy` — Combat: Enemy Attacks  ⚠ loop caption

**Header** `R1 6.E` · `Combat: Enemy Attacks` · **CTA** `NEXT PHASE` / `Combat: Player Attacks`

> In player order, each player resolves an attack from each enemy engaged
> with them.
>
> ```
>   ┌─► Active player chooses an engaged enemy   , then actions
>   │   Declare a defender (optional)            , then actions
>   │     if none, another player's Sentinel may defend
>   │   Reveal and resolve the shadow effect     , then actions
>   │   Determine combat damage                  , then actions
>   └── Repeat until the active player has no eligible enemies left
> ```
> Undefended attacks: the active player assigns all the damage to one of their
> own heroes. Defence does not reduce it.

**Confirmed: a window really does follow "choose an enemy."** Raised in review
as suspicious, and RR's own timing chart settles it. Every rung here is
followed by `ACTION WINDOW` in the chart:

```
6.4b Enemy attack initiates (active player chooses enemy)
     ACTION WINDOW
6.4.1 Declare defender
     ACTION WINDOW
6.4.2 Reveal and resolve shadow effect
     ACTION WINDOW
6.4.3 Determine combat damage
     ACTION WINDOW
6.4.4 Enemy attack ends
```

That window is the one that matters most in the whole phase: the enemy is
chosen but no defender is committed, which is where cancel-the-attack and
ready-a-defender effects land.

**Rung wording tightened to RR's.** "Reveal the shadow card" became "Reveal and
resolve the shadow effect" (6.4.2's own title) because revealing is not the
part that hurts, and "Deal damage" became "Determine combat damage" (6.4.3),
which is the step that also covers the case where defence absorbs it all and no
damage is dealt.

**"Resolves an attack from each enemy", not "resolves every enemy."** The
shorter phrasing said nothing about *what* gets resolved and could be read as
defeating them. RR 6.3 gives the exact frame: "In the steps that follow, **each
enemy that is engaged with a player will have one opportunity to make an
attack**." So the unit being resolved is an attack, and there is exactly one
per enemy.

That also settles half of the open question about attack caps: **the one-per
limit is real on the enemy side** (6.3, and 6.4a's "eligible enemy is one that
has **not yet attacked this round**"). It is still unstated on the player side,
where 6.7 says only that "each player will have **opportunities** to declare
attacks" with no per-enemy cap. The two flows are asymmetric here as well, so
view 19 must not borrow this wording.

**FIX** the framing, and move it **above** the diagram. The old caption sat
below the flow and read "Repeat for each engaged enemy, in player order", which
was enemy-major, as if the table cycles players per enemy. RR is
player-major:

- **6.4a** the active player chooses an eligible enemy, resolves it, and
  repeats; "If no eligible enemies remain for the active player to choose,
  proceed to 6.5."
- **6.5** "The next player (in player order) becomes the active player. Return
  to step 6.4a."

Within your own enemies you choose the order freely — engagement cost does
**not** order attacks (that only applies at 6.2 and 5.3).

**ADD Sentinel, as a sub-rung not a step.** Raised in review as the defensive
counterpart to Ranged, and it is, but the two are shaped differently and the
diagram should not pretend otherwise:

- **Ranged is its own numbered step.** 6.8.1 sits in RR's chart with an
  `ACTION WINDOW` after it, so it gets a full rung in view 19.
- **Sentinel is a conditional fallback inside 6.4.1.** RR's `Sentinel` entry:
  "A character with the sentinel keyword may be declared as a defender during
  enemy attacks that are made against other players. **A character may declare
  sentinel defense after the player engaged with the enemy making the attack
  declares no defenders.**"

That ordering is the whole point and is easy to get wrong: a Sentinel character
cannot preempt, the engaged player must decline to defend first. An indented
"if none" line under Declare a defender says exactly that. Giving Sentinel its
own rung would imply an independent opportunity and invite a table to play it
too early.

Worth carrying if there is room: the sentinel defender "must exhaust and meet
any other requirements necessary to defend the attack", so it is not free.

**FIX the undefended line: it never said *which* hero.** RR 6.4.3 answers all
three parts the old wording left open:

> If an attack is undefended, all damage from the attack must be **assigned to
> a single hero controlled by the active player**… **A character's Ú does not
> absorb damage from undefended attacks.**

- **Who takes it:** a hero controlled by the **active player**, not any
  character and not another player's. "One hero" alone left that open at a
  four-player table.
- **Who decides:** the active player assigns it, so it is a choice, not a
  forced target.
- **Not splittable, and not reduced:** it goes to a **single** hero, and
  defence does not soak any of it. The second half is the part players most
  often get wrong, since defence reduces damage in every other case.

Also from 6.4.3, worth carrying in a detail panel if there is room: if a
defending character leaves play before damage is assigned, the attack becomes
undefended and these rules apply to it after all.

**Optional add** (RR 6.4.3, if room): defence does not absorb undefended
damage, and a defender leaving play before damage makes the attack undefended.

---

### 19. `combat_player` — Combat: Player Attacks  ⚠ missing step

**Header** `R1 6.P` · `Combat: Player Attacks` · **CTA** `NEXT PHASE` / `Refresh`

> In player order, each player **may** declare attacks on engaged enemies.
>
> ```
>   ┌─► Active player exhausts characters to attack 1 of their
>   │   engaged enemies
>   │     if every attacker has Ranged, any player's engaged enemy
>   │   Other players' Ranged may exhaust to join   , then actions
>   │   Determine attack strength                   , then actions
>   │   Determine combat damage                     , then actions
>   └── Repeat until the active player declares no more attacks
> ```

Plus a standing note, always shown:

> This is the last window to lower player ⟨threat:red⟩ to avoid elimination at
> refresh.

**Ranged appears TWICE in this flow, and the old diagram had only one of them.**
This is the biggest gap the refinement pass found. RR uses the keyword for two
different things one step apart:

- **6.8b, choosing the target.** "The active player chooses 1 enemy **with whom
  they are currently engaged**, and exhausts any number of characters they
  control to declare them as attackers against that enemy. **If each of the
  attacking characters declared during this step has ranged, the attack may be
  declared against any enemy that is engaged with any player.**" So an
  all-ranged attack can reach across the table. This was missing entirely, and
  it is the one that changes what a player may do.
- **6.8.1, joining someone else's attack.** "Any number of ranged characters
  controlled by **other players** may exhaust to be declared as attackers." The
  old diagram had this one, worded as "other players may join their ranged",
  which read as nonsense.

Drawn as a sub-rung and a rung respectively, which mirrors view 18: there,
`Sentinel` is an indented conditional under Declare a defender, and here the
all-ranged targeting exception is an indented conditional under the declare
step. Both keywords let another player's characters cross into your combat, so
they should look alike.

**ADD the exhaust cost and the engagement restriction.** 6.8b requires the
active player to **exhaust** the attackers, and restricts the target to an
enemy "with whom they are currently engaged" (outside the all-ranged case).
Neither was on screen. The old opening rung, "Active player declares the target
and attackers", named the step without saying what it costs or what it may
target.

**"Engaged" is never dropped as a qualifier.** Enemies live in exactly two
places, the staging area and in front of a player, and almost every combat rule
turns on which. "Attack 1 of their enemies" reads as though a player might
reach into staging; RR 6.8b is explicit that the target is "1 enemy **with whom
they are currently engaged**". The Ranged exception widens *whose* enemy without
loosening *where* it is, and the sub-rung has to carry both halves: 6.8b allows
"any enemy that **is engaged with any player**", so it reads "any player's
engaged enemy". Dropping either word loses something. Without "player's" it
sounds like any enemy anywhere including staging; without "engaged" it sounds
like Ranged reaches into staging, which it does not.

Applies to both flows and every rung in them. View 18 already carried it
("chooses an engaged enemy", "each enemy engaged with them"); view 19 lost it
during the third-person rewrite, which is worth noting as a hazard: a
mechanical find-and-replace on pronouns can quietly drop a load-bearing
adjective.

**The framing line said "engaged with them" and contradicted its own diagram.**
The sub-rung directly below it grants an all-Ranged attack against "any
player's enemy" (6.8b), so scoping the opening to *your* enemies made the
exception look like a mistake. "Engaged enemies" is the accurate scope: it
covers enemies engaged with anyone, and still excludes the staging area, which
is the distinction that actually matters here. The default and the exception
then live where they belong, on the rung and its sub-rung.

Worth noting as a pattern: a framing line that summarises a diagram can quietly
narrow it. This is the second time in the pass (view 18's "resolves every
enemy" was the first) that the one-line summary asserted something the flow
below it did not.

**ADD the elimination warning, because this is the last window that can prevent
it.** Nothing between 6.8.3's window and 7.3 lets a player act, so a threat
total that will cross 50 at refresh has to be flagged here or not at all.

**It is unconditional, and that is the point.** A draft fired it only when
`threat + threat_per_round >= 50`. The catalog says the HUD cannot compute that
sum: **67 cards** interact with the refresh raise, and several replace it
outright.

- `Escape From Mount Gram` — "**Instead of raising their threat by 1 during the
  refresh phase**, each player raises their threat by the number of completed
  quests…"
- `Nalir` — "At the beginning of the refresh phase, raise your threat by 1 **for
  each player in the game**", so +4 at a full table.
- `Slopes of the Valley` — "either raise each player's threat by 2, or each
  player cannot ready…"
- `Tamed Mûmak` — "Forced: At the end of the round, raise your threat by 1", on
  top of the framework raise.

A conditional built on `threat_per_round` would therefore fail **silently and
in the dangerous direction**: a player at 44 facing `Nalir` in a four-player
game gets no warning at all. An always-on note costs one line and never lies.

This is the travel-control principle again, and it is now the third time it has
decided a design question: **the HUD tracks, it does not enforce.** Where the
app cannot know the true number, it should prompt the players to check rather
than compute a wrong answer confidently.

**Optionality moved to the opening line, and the note is gone.** Two review
findings, both about rules I had already written down and then broke:

- **Optionality lives in one slot.** View 15 opens "Not optional"; this one had
  "Attacking is optional" stranded in a note below the diagram. Same idea, two
  places. It now rides the modal verb in the opening line ("each player **may**
  declare attacks"), which is the mechanism already recorded for views 13 and
  15 and needs no extra sentence.
- **The no-damage line was restating arithmetic.** I added "If the enemy's
  defence matches your attack strength, no damage is dealt", citing 6.8.3. But
  6.8.3 defines damage as attack minus defence, so "you get nothing when
  defence is higher" is what subtraction means, not a rule a player could miss.
  It is the same *restate the obvious* fault the view 8 drafts were rejected
  for, committed after the rule was in the doc.

**View 19 therefore gets no note at all.** View 18's undefended line survives
because it is genuinely counterintuitive: defence does *not* reduce undefended
damage, which contradicts how defence works everywhere else. Nothing on the
player-attack side is surprising in that way, and padding a slot to match a
neighbouring view is how the recap sentences got there in the first place.

**The two combat flows are NOT symmetrical, and the old diagram got it
backwards.** RR's timing chart:

```
6.8b Player attack initiates (active player declares target of attack and attacker(s))
6.8.1 Ranged option
     ACTION WINDOW
6.8.2 Determine attack STR
     ACTION WINDOW
6.8.3 Determine combat damage
     ACTION WINDOW
6.8.4 Player attack ends
```

Three corrections fall out of it:

- **No window after 6.8b.** Unlike the enemy flow, where a window follows the
  choose step (6.4b), declaring the target and attackers here runs straight
  into the ranged option. The old diagram put `, then actions` on it, inventing
  a window the chart does not have.
- **Declaring the target and the attackers is one step,** not two. 6.8b is
  "active player declares target of attack **and** attacker(s)". The old
  diagram split it into "Choose an enemy" and "Declare attackers" with a window
  between them, which does not exist.
- **The ranged option is where the first window actually is,** and the old
  diagram was the only rung *without* `, then actions`. Exactly inverted.

**Rung wording tightened to RR's.** "Total attack vs defence" conflated two
steps: 6.8.2 is attack strength alone ("Add up the total Û of all characters
that are currently attacking"), and defence only enters at 6.8.3 when damage is
determined.

**ADD** the ranged step — RR **6.8.1 Ranged option**: "Any number of ranged
characters controlled by **other players** may exhaust to be declared as
attackers." Currently absent entirely, and it is the step most easily missed
at a multiplayer table.

**FIX** the caption for the same player-major reason as view 18 (RR 6.8a/6.9).

**CUT / verify** — "1 attack per engaged enemy" is not stated in RR 6.7 or
6.8a, which say only that the active player "may declare an attack against one
of their enemies" and repeat. Either find the citation or drop the cap; do not
ship it unverified.

---

### 20. `refresh` — Refresh

**Header** `R1 7.R` · `Refresh` · **CTA** `NEXT PHASE` / `Resource`

> Simultaneously ready all exhausted cards.
> Tracker raised each player's ⟨threat:red⟩ by 1 and passed the first player
> token clockwise.

**FIX: use the icon, and say the tracker will do it.** Two changes.

*Icon.* "threat +1" was bare words on a screen whose whole subject is the
player dial. It is ⟨threat:red⟩ by the icon convention, and the view already
draws that glyph in its per-player preview.

*Automatic increment, and the line now splits by who does what.*
`end_round()` ([gamestate.py:627](gamestate.py:627)) raises every living
player's threat, so the +1 is applied by the **End Round** CTA, not by the
player and not on arriving at this screen. The preview (`P3 41→42!`) is a
forecast; pressing the CTA is what makes it real.

A draft listed the threat raise alongside readying and passing the token, as
though all three were table actions, then added a second sentence saying the
CTA applied it. That said it twice and still blurred the boundary. Split
instead: **line 1 is what the players do at the table** (ready cards, pass the
token, neither of which the HUD tracks), **line 2 is what the button does**
(the only tracked change in the phase).

### Implementation: splitting `end_round()`

`end_round()` ([gamestate.py:627](gamestate.py:627)) currently does four things
in one call: raise threat, rotate the first player, bump the round number, and
reset to the first step. The design above splits it in two:

| When | What |
|---|---|
| **Refresh view loads** | raise each living player's ⟨threat:red⟩ (7.3), pass the first player token (7.4) |
| **Window CTA** | bump the round number, reset to step `1.R` (7.5 → 0.1 → 0.0) |

Four things to get right, in rough order of how badly they bite:

1. **It must be one delta, recorded on entry.** The back button is delta
   replay, so an auto-apply that is not captured as a delta cannot be undone,
   and the player would reverse into a view whose numbers had already moved.
   This is the same class of bug as the history-navigation regression that
   `_replay_moved` was added to catch.
2. **It must be idempotent across re-entry.** Navigating back and forward
   again, or a redraw, must not raise threat twice. Guard on state, not on a
   "have I drawn yet" flag.
3. **Elimination can now happen on arrival.** A player at 49 is eliminated the
   instant this view loads, before anyone can act. That is correct per RR (50
   is immediate), and it is exactly what view 21's copy already warns about,
   but the view has to render that state rather than assume everyone survived
   the increment.
4. **The window's first actor changes.** The token passes at 7.4, *before* the
   window opens, and RR gives the first player the first opportunity in any
   window. So the refresh window is run by the **new** first player, not the
   one who held the token all round. Nothing in the UI says this today.

Note `p.threat_per_round` is per-player, so "+1" is the normal case rather than
a constant. If a hero or effect changes it, the copy should follow the
`(1 each normally)` hedge used on view 2.

**KEEP** the rest, which matches RR: 7.2 "Simultaneously ready all exhausted
cards"; 7.3 "Each player simultaneously increases their threat by 1"; 7.4
"passes the first player token to the next player (clockwise) to their left."

The per-player preview (`P3 41→42!`) is right to warn: RR — "If a player's
threat level reaches **50**, that player is immediately eliminated."

---

### 21. ACTION WINDOW — Refresh

**Header** `R3 7.R` · `ACTION WINDOW · REFRESH` (purple) ·
**CTA** `NEXT PHASE` / `End of Round`

> Last action window of Round 3. End of round effects resolve after it.

Plus a strategy tip, in the tip treatment:

> Last chance to use allies that leave play at end of round. Anything exhausted
> now stays exhausted into Round 4.

### What this window is actually for (research)

Raised in review: is this window accurate to game state, and what do people use
it for? Both answered.

**Yes, the state is accurate, and deliberately so.** By the time the window
opens, 7.3 has raised threat and 7.4 has passed the token. So the screen is
correct to show the **new** first player and any elimination that just fired.
Neither is a rendering artifact of the auto-apply design; it is what RR's chart
prescribes.

**What it is used for**, from the 18 cards in the catalog that print
`Refresh Action:`:

| Use | Cards |
|---|---|
| **Threat reset** | `Aragorn` — "Reduce your threat to your starting threat level. (Limit once per game.)" |
| **Card draw** | `Peace, and Thought` — exhaust 2 heroes, draw 5 |
| **Deck manipulation** | `Messenger Raven`, `Kahliel's Headdress` |
| **Healing** | `Half-pint`, `Mushroom Gatherer` |
| **Progress** | `Mithril Lode`, `Escape from Darkness` |
| **Enemy removal** | `Sniveling Courtier`, `Worms of the North` |

**Aragorn is the window in miniature, and confirms our copy.** His reset is a
`Refresh Action:`, so it can only be used *after* 7.3 has already added the +1.
Community discussion states the consequence plainly: a player at 49 leaving the
combat phase hits 50 at 7.3 and is eliminated **before** they can use it. That
is exactly what view 21's second line says, arrived at independently from the
chart, and it is the strongest argument for keeping that line.

**The tip carries one warning and one opportunity**, which is the honest shape
of this window: it is cheap in tempo and expensive in bodies.

*The cost.* 7.2 is the framework's **only** ready step. The window sits at 7.4,
after it, so a character exhausted here carries that state into the next round
rather than being refreshed at its start.

Worded "**into** Round 4", not "for all of Round 4". The framework will not
ready it again until the next 7.2, but **78 cards** in the catalog ready a
character outside that step (`Westfold Horse-Breaker`, "Discard to choose and
ready a hero"; `Behind Strong Walls`, "Ready a defending Gondor character").
Claiming the whole round would be the same over-reach as the travel control:
stating a framework rule as though printed cards cannot break it. Every exhaust-cost card in the table
above (`Peace, and Thought`, `Mushroom Gatherer`, `Mithril Lode`, `Dark Pit`)
is mortgaging a character for a full round, not spending a spare tap on a
freshly readied board. That is the opposite of what the timing looks like at a
glance, which is exactly why it earns the line.

*The opportunity.* **220 cards** in the catalog carry an "at the end of the
round" effect, and the canonical one is `Gandalf`: "At the end of the round,
discard Gandalf from play." This window is the last moment such a card is still
in play, so anything a departing ally can still do has to be done here or not
at all. Our own `rules/action-windows.md` already listed "last use of departing
allies" for 7.4; the catalog count is what makes it worth screen space rather
than a footnote.

Two others were considered and left out. **Threat reduction** is the obvious
use, but the main copy already leads with threat, so the tip would repeat it.
**Once-per-round resets** (91 cards carry the limit) let a player use an ability
here and again early next round, which is real but is a combo insight rather
than something the window itself teaches.

**Name the mandatory trigger, and get its order right.** A draft opened with a
bare "End of Round 3", which labels the boundary but never says what the game
does at it. Every other phase view names its framework step ("ready all
exhausted cards", "each player engages…"); this one named nothing.

The order is the part that is easy to invert. **The window resolves first, and
end of round effects fire after it**, at 0.1, which now has its own screen
(view 22). "when it closes" was written before that view existed and implied
the effects resolved as part of leaving this screen; they get their own step. "The end of a round is an
important game milestone that may be referenced in card text, either as a point
at which an ability may or must resolve, or as a point at which a lasting
effect or constant ability begins or expires." So it is *actions, then end of
round effects*, not the reverse.

That ordering is also what makes the tip true. `Gandalf` is discarded at 0.1,
which is **after** this window, so the window really is the last moment he is
in play. Copy that implied end-of-round effects had already resolved would
contradict its own tip.

**Put the round boundary in the CTA.** This is the last window of the round, so
it is the only screen that can mark the boundary without lying about where it
falls. The CTA then reads
`NEXT PHASE / Resource (Round 4)`, which tells the table two things at once:
what phase comes next, and that the round counter has turned.

That also removes the `End Round` anomaly flagged earlier. Every view now
carries the same `NEXT PHASE / <next>` CTA, and no button does double duty.

**CUT the elimination note, and move the warning to where it can be acted on.**
The line read "Threat has already gone up. Reducing it now cannot undo an
elimination that already happened." It is true, and useless: it tells a player
they have lost and that nothing can be done. Worse, it papers over a design
flaw rather than fixing it.

**The flaw:** with 7.3 applied automatically on the previous screen, a player
at 49 is eliminated the instant that screen loads, having never been warned.
And RR's chart shows there is **no action window anywhere between the end of
combat and 7.3**:

```
6.8.3 Determine combat damage     ACTION WINDOW   <- last chance to act
6.8.4 / 6.9 / 6.10 / 6.11 Combat phase ends
7.1 / 7.2 Ready all cards / 7.3 Raise threat / 7.4 Pass token
                                  ACTION WINDOW   <- too late
```

So the last actionable moment is inside the **player attacks** flow, which is
view 19. That is where the warning belongs, and it is now a conditional there:
`P3 is at 49 and reaches 50 at refresh. This is the last window to lower it.`

This is the same principle as view 8's conditional lines: **warn while the
outcome can still change, and state the outcome once it cannot.** View 20 keeps
reporting the elimination as fact, because by then it is one.

Worth noting the irony that surfaced it. `Aragorn`'s threat reset is a
`Refresh Action:`, so it fires in *this* window, after 7.3, and the community
example is precisely a player at 49 who is eliminated before they can use him.
The card that looks like the answer to this problem is the clearest proof the
warning has to come earlier.

---

### 22. `round_end` — End of Round  *(new)*

**Header** `R3 0.1` · `End of Round 3` · **CTA** `NEXT PHASE` / `Resource (Round 4)`

> Resolve any "at the end of the round" effects.
> Anything lasting "until the end of the round" expires now.

**Header reads `R3`, not `R4`.** Raised in review as possibly
`R4 0.1 · End of Round 3`. It should be `R3`: RR 0.1 is "This step formalizes
the end of a game round. **Proceed to step 0.0 of the next game round**", so
0.1 is still the **current** round's final step and round 4 does not begin
until 0.0, which is past this screen's CTA. Showing `R4` beside step `0.1`
would pair a round number with a step that does not belong to it.

**The title still names the round: `End of Round 3`.** A draft dropped the
number as redundant with the `R3` chip, and every other view does put only the
phase name in that slot (`Refresh`, `Travel`). This view earns the exception,
because it is the one screen where two round numbers are live at once: the
round being closed and the round named in the CTA (`Resource (Round 4)`).
Without the number in the title, "End of Round" beside a button offering Round
4 reads as though round 4 is what is ending.

Redundancy with the chip is the cheaper problem. This is the only boundary in
the game where getting the round wrong is possible, so it is worth one repeated
digit.

The round counter turns on this view's CTA, which is why that button alone
names the incoming round: `NEXT PHASE / Resource (Round 4)`.

**Why this needs to exist.** Raised in review, and it turns out to be a
**parity gap** rather than a new idea. Upstream models the step:

```
"7.5", "text": "7.5: End of the Refresh phase"
"0.1", "text": "0.1: End of the round"
```

Our `phases.py` transcribes `0.0` but stops there: there is no `0.1`. The round
currently ends as a side effect of pressing a CTA, with nothing on screen at
the moment RR says abilities fire.

**What happens at 0.1**, per RR: "The end of a round is an important game
milestone that may be referenced in card text, either as a point at which an
ability may or must resolve, or as a point at which a lasting effect or
constant ability begins or expires."

Both halves are heavily printed:

| At 0.1 | Cards | Example |
|---|---|---|
| Forced "at the end of the round" | **220** | `Gandalf` — "At the end of the round, discard Gandalf from play" |
| "until the end of the round" expiring | **183** | stat boosts, threat suppression |

`Tamed Mûmak` ("Forced: At the end of the round, raise your threat by 1") is
the sharp case: it raises threat *after* the refresh raise, so a player can be
eliminated at 0.1 having survived 7.3. Nothing in the UI marks that moment
today.

**It is not an action window.** RR's chart puts the last `ACTION WINDOW` after
7.4; 7.5 and 0.1 carry none. So this view is a resolution checklist, not a
window screen, and it must not use the purple window treatment.

**The round-boundary CTA moves here** from view 21, which now reads
`NEXT PHASE / End of Round`. That is more accurate anyway: the round does not
end when the refresh window closes, it ends at 0.1.

**Always shown, every round.** It costs one screen per round even when nothing
resolves, and that is the right trade: the rounds where a player has forgotten
`Gandalf` leaves play, or that a boost expired, are exactly the rounds where no
conditional could have known to prompt them. Same reasoning as view 19's
standing threat note. A checklist that only appears when the app is confident
it is needed is a checklist that goes missing precisely when it matters.

**Also fix the data.** Adding the step means `phases.py` gains `0.1` and
`docs/js/phases.js` is regenerated by `tools/gen_web_data.py` (never
hand-edited, per the iron rules), keeping both twins and upstream in lockstep.

---

## Open questions for you

1. **Planning loop** — resolved in favour of keeping the diagram. By the test
   in view 15, a loop is drawn when its body has two or more steps, and
   Planning's does (the active player's card play plus the action rotation
   running alongside it). Three views now carry loop diagrams: 4, 15 and both
   combat halves.
2. **Where does "how a window works" live?** The round-robin rule above is
   true of all eight windows. Options: state it on the first window screen of
   each game, put it behind a help affordance, or leave it out of the UI and
   keep it as our own reference. Repeating it on all eight is not viable at
   `BODY` size.
3. **`combat_player` attack cap** — do you know the citation for one attack per
   enemy? Otherwise it comes out.
4. **Window-screen naming** — still unresolved from before: `ACTION WINDOW ·
   QUEST` (phase) vs `· AFTER STAGING` (what it follows).
5. **Window-screen frequency** — always in the flow, or once per window per
   game?
6. **Refresh CTA anomaly — resolved.** `End Round` is gone. 7.3 and 7.4 now
   apply automatically when the refresh view loads, which is where RR puts them
   (the chart runs 7.3, 7.4, then `ACTION WINDOW`, then 7.5), and the round
   boundary moves to the window screen's CTA. See the implementation notes on
   view 20.

## Source

All citations are the official Rules Reference (©2021, Revised Core),
`research/rules/rules-reference.md`, indexed as `lotr-lcg-rules`. Re-check any
line with:

```bash
qmd query "your question here" -c lotr-lcg-rules
```
