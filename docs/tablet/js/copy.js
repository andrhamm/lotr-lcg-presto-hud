// Tablet-only chrome strings. Nothing in dom.js/primitives.js/app.js is
// allowed to inline a string a player reads - it comes from here so the
// design-system copy rules have one place to hold the line.
export const CHROME = {
  next: "Next",
  players: "Players",
  quest: "Quest",
  staging: "Staging",
  log: "Game log",
  round: "Round",
  newGame: "New game",
  resume: "Resume",
  scenario: "Scenario",
  begin: "Begin",
  eliminated: "Eliminated",
  noLocation: "no active location",
  sideQuest: "+ side quest",
  threat: "Threat",
  enemies: "Enemies",
  locations: "Locations",
  step: "step",
  firstPlayer: "first player",
  withoutActions: "Without actions",
  checksMade: "Checks made",
  checksSummary: "%d in staging, %d engaged",
  reset: "Reset",
  placeProgress: "Place progress",
  victory: "Victory!",
  defeat: "Defeat",
  trackerCounts: "The tracker shows %d engaged and %d in staging.",
  location: "Location",
  sideQuestLabel: "Side Quest",
  stage: "Stage",
  resolveQuestCta: "Resolve Quest. ",
  nextPrefix: "Next: ",
  endOfRound: "End of Round ",
  back: "‹ Back",
  edit: "Edit",
  menu: "Menu",
  all: "All",
  elimAt: "elimination at",
  done: "Done",
  cancel: "Cancel",
  playersSheetFooter: "Every change is logged as it happens. Done just closes the sheet.",
  newGameWarning: "The current game is saved until you start a new one.",
  // The elimination sheet (Task 3). "%d" is the fmt() placeholder used the
  // same way OUTCOME's templates are (docs/js/viewcopy.js) - see
  // sheet_elim.js. The only rules claim in elimEliminateBody is "threat at
  // or above the elimination level eliminates the player" - Rules Reference,
  // "Elimination" (7.4); nothing here invents a card example beyond that.
  elimTitle: "P%d reaches %d",
  elimEliminate: "Eliminated",
  elimEliminateBody: "Threat at or above the elimination level eliminates the player.",
  elimAvert: "Averted by card effect",
  elimAvertBody: "Threat drops to %d, player stays in.",
  elimLevelQuestion: "Elimination level changed?",
  elimSet: "Set",
  // The quest sheet (Task 4).
  progress: "Progress",
  questPoints: "Quest points",
  activeLocations: "Active locations",
  sideQuestsHeader: "Side quests",
  explored: "Explored",
  toStaging: "Back to staging",
  replace: "Replace",
  remove: "Remove",
  addLocation: "+ Add location",
  // Verbatim QuestingProgressModal's own fallback (docs/js/screens.js) for a
  // condition stage with no card-supplied advance sentence.
  questConditionFallback: "This stage advances on a condition, not on progress.",
  // A location's printed X with no coded spec at all (xshape.js's "blank"
  // shape) - verbatim LocationConfigModal's own line for this exact case
  // (docs/js/screens.js ~2052-2056, review finding 1).
  xElsewhere: "the card prints X and defines it elsewhere",
  // The location picker (Task 5) - LocationPickModal is its canvas-modal
  // reference (docs/js/screens.js), minus pagination (the sheet scrolls)
  // and the "how it arrived" toggle (inferred from ui.sheet.back instead -
  // see sheet_locpick.js).
  locpickTitleNew: "Travel",
  locpickTitleChange: "Change Location",
  locpickPrompt: "Pick the location - or enter it manually.",
  locpickReplacing: "Replaces the current location (%s/%s discarded).",
  manualEntry: "Manual entry",
  travelHere: "Travel",
  // The confirm CTA's label when back is not "play" - the location arrives
  // by card effect (the quest sheet's "+ Add location"), not a travel the
  // players paid for, so the button should not claim one either. Mirrors
  // LocationPickModal's own footer/travel-button label switch verbatim
  // ("Travel"/"Add" on `this.back !== "progress"`).
  addHere: "Add",
  pickPoints: "Quest points",
  pickContribution: "Threat contribution",
  contributionNote: "Its threat leaves the staging area while it is active.",
  locpickStats: "threat %s · %s quest points",
  // The side-quest picker (Task 6) - SideQuestPickModal is its canvas-modal
  // reference (docs/js/screens.js), minus pagination-by-canvas-space (this
  // sheet still pages, sheet_sqpick.js's own PER_PAGE, but scrolls too) and
  // its "manual" footer button behaves the same in both: no steppers, an
  // instant zero-point placeholder logged and left for the quest sheet's own
  // steppers to fill in.
  sqpickTitle: "Add Side Quest",
  sqpickEmpty: "No side-quest catalog data available.",
  sqpickEmptyHint: "Use Manual entry below.",
  sqpickPickSphere: "Pick a sphere - or enter manually.",
  sqpickPickOne: "%s - pick one, then Add.",
  sqpickBack: "‹ Spheres",
  // "Manual entry" itself is manualEntry (locpick's own key, above) - the
  // two pickers share the one label rather than carrying a duplicate string
  // (review finding 4).
  sqpickAdd: "Add",
  sqpickNoSphere: "No sphere",
  sqpickOneQuest: "1 quest",
  sqpickManyQuests: "%d quests",
  sqpickPts: "%d pts",
  sqpickPrev: "‹ Prev",
  sqpickNext: "Next ›",
  sqpickPage: "%d/%d",
  // The resolution sheet (Task 7) - ResolutionModal's own six steps
  // (docs/js/screens.js), one string per thing it says. The rules claims
  // here are the twin's, verbatim where a player could act on them:
  // "Progress hasn't reached target - confirm" (its _drawAdvance warning)
  // and "%s excess → quest card" (_drawLocation), which is the rulebook's
  // p.15 rule that a location's excess progress flows on to the quest card -
  // already in CLAUDE.md's verified-mechanics list. Nothing new is asserted.
  allResolved: "All resolved",
  resolveContinue: "Continue",
  resolveRevealed: "Stage %s revealed",
  sideA: "Side A",
  sideB: "Side B",
  // A face the catalog has, that prints no game text of its own. Said per
  // face, under that face's own caption, so a blank front never reads as
  // "this stage has nothing to do" when the back is where its rules live.
  noCardText: "No card text",
  resolveFlip: "Flip to Side B → %s qp",
  locationExplored: "Location Explored",
  progressOf: "%s/%s progress",
  resolveExcess: "%s excess → quest card",
  choosePath: "Choose a path",
  firstPlayerChooses: "First player chooses",
  randomPath: "Random",
  randomize: "Randomize for me",
  branchPoints: "%s quest points",
  questCleared: "Quest %s cleared",
  underfilled: "Progress hasn't reached target - confirm",
  revealStage: "Reveal Stage %s",
  finalStage: "That was the final stage!",
  declareVictory: "Declare Victory",
  notYet: "Not yet - keep playing",
  markComplete: "Mark Complete",
  leaveAsIs: "Leave as-is",
  // The sailing test sheet (Task 8) - SailingModal's own captions/sub-lines
  // (docs/js/screens.js), verbatim: "CURRENT HEADING"/"RESULT" are LABEL
  // captions (stored sentence-case here like every other LABEL string -
  // the .label CSS rule does the uppercasing), and the three sub-line
  // states are spelled out as whole sentences rather than one template with
  // an embedded "s", the same way sqpickOneQuest/sqpickManyQuests are two
  // keys instead of one.
  sailingTest: "Sailing test",
  currentHeading: "Current heading",
  result: "Result",
  apply: "Apply",
  sailNoWheels: "no wheels found - heading stays",
  sailWheelFound: "1 wheel found - shift on-course",
  sailWheelsFound: "%d wheels found - shift on-course",
  sailStepOff: "1 step off-course (card effect)",
  sailStepsOff: "%d steps off-course (card effect)",
};
