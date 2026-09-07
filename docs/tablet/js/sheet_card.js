// The card quick view: the card, big, with a table of what it is.
//
// Every card the client draws opens this - the Overview's grid, the location
// picker's rows - because a 96px thumbnail is an identifier, not something
// you can read. The printed card is the authority for what it does (CLAUDE.md
// iron rule 4), so this shows it rather than describing it.
//
// The table deliberately does NOT restate the card. Its text, its art and its
// printed stat column are all legible at this size; what the picture cannot
// tell you is which set it belongs to, when that set came out, and how many
// copies of it are in the deck - so that is what the table leads with, and
// the printed values follow as a reference rather than as a substitute.
//
// The seat is `ui.sheet = { kind: "card", name, files, face, facts }` -
// `files` is the card's face image FILENAMES (cardimage.js's faceFiles),
// front first, `face` is the index showing, and `facts` is cardFacts()'s
// [label, value] rows. app.js reads all of it off the tapped element, so
// there is no card index to keep in sync and the renderers stay pure.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip } from "./primitives.js";

function statTable(facts) {
  if (!facts?.length) return "";
  const rows = facts.map(([k, v]) =>
    h`<div class="cardview-row"><dt class="label">${CHROME.cardFacts[k] ?? k}</dt><dd class="body">${v}</dd></div>`).join("");
  return h`<dl class="cardview-facts">${raw(rows)}</dl>`;
}

export function renderCardSheet(game, ui) {
  const s = ui.sheet ?? {};
  const files = s.files ?? [];
  const face = Math.min(s.face ?? 0, Math.max(files.length - 1, 0));
  const src = ui.imagePrefix && files[face] ? ui.imagePrefix + files[face] : null;
  // 198 catalog encounter cards carry two different face images; the rest
  // carry one, and offering a flip there would be a control that shows the
  // same picture twice.
  const flip = files.length > 1
    ? chip({ act: "card_flip", label: h`${CHROME.flipCard}`, tone: "tan" })
    : "";
  const art = src
    ? h`<img class="cardview-art" src="${src}" alt="">`
    : h`<div class="cardview-art is-missing"><p class="body secondary">${CHROME.cardArtMissing}</p></div>`;
  // The modal carries its own top bar, the way the screens do: the subject on
  // the left, the way out on the right. A Close at the FOOT of a tall card is
  // a scroll away from the thing you just opened.
  return h`<header class="cardview-bar">
<h1 class="display">${s.name ?? ""}</h1>
<div class="cardview-tools">${raw(flip)}${raw(chip({ act: "sheet_close", label: h`${CHROME.close}`, tone: "tan" }))}</div>
</header>
<div class="cardview-body">${raw(art)}${raw(statTable(s.facts))}</div>`;
}
