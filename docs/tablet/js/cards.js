// Stage-card face lookup for the tablet twin. The compiled catalog's stage
// cards are `{ faces: [{name, side: "A"|"B"|..., text, ...}, ...], ... }` -
// there is no top-level card.name/card.text (pane.js's quest_setup branch and
// rail.js's stage pill both used to read those top-level fields directly and
// so always rendered the "no card" branch).
//
// This is deliberately positional, mirroring docs/js/ui.js's frontFace()/
// backFace() rather than matching a printed side letter: quest cards print
// their side on the physical card, but that letter is not always "A"/"B" -
// measured over the 514 catalog stage cards, 16 run "C"/"D", 5 "E"/"F", 1
// "G"/"H", and 10 more pair unevenly (see ui.js's frontFace comment, from the
// 2026-07-30 playtest of The Oath). game.quest.side, in contrast, is a
// game-state flag that gamestate.js only ever sets to the literal "A" or "B"
// (preloadScenario/advanceStage assign "A", flipToB assigns "B") - it names
// *which* face is currently up, not what letter is printed on it. Matching
// card.faces by `f.side === game.quest.side` would therefore return nothing
// for every irregularly-lettered card - the exact bug frontFace/backFace
// exist to avoid - so this indexes by position instead: "A" -> faces[0],
// "B" -> faces[1] (falling back to faces[0] for a card with only one face).
export function faceOf(card, side) {
  const faces = card?.faces ?? [];
  if (!faces.length) return null;
  return side === "B" ? (faces[1] ?? faces[0]) : faces[0];
}

// The face to resolve before round 1 - always the printed front, regardless
// of quest.side (which is still "A" at that point anyway).
export function frontFace(card) {
  return faceOf(card, "A");
}
