// The card quick view: one card's art, big, with a flip when it has two
// sides.
//
// Every card the client draws opens this - the Overview's card grid, the
// location picker's rows - because a 96px thumbnail is an identifier, not
// something you can read. The printed text is on the card, and the card is
// the authority (CLAUDE.md iron rule 4), so showing it larger is the whole
// feature: nothing here paraphrases anything.
//
// The seat is `ui.sheet = { kind: "card", name, caption, files, face }` -
// `files` is the card's face image FILENAMES (cardimage.js's faceFiles),
// front first, and `face` is the index being shown. app.js reads the files
// off the tapped element's dataset, so there is no card index to keep in
// sync and the renderers stay pure.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, cta } from "./primitives.js";

export function renderCardSheet(game, ui) {
  const s = ui.sheet ?? {};
  const files = s.files ?? [];
  const face = Math.min(s.face ?? 0, Math.max(files.length - 1, 0));
  const src = ui.imagePrefix && files[face] ? ui.imagePrefix + files[face] : null;
  // 198 catalog encounter cards carry two different face images; the rest
  // carry one, and offering a flip there would be a control that shows the
  // same picture twice.
  const flip = files.length > 1
    ? chip({ act: "card_flip", label: h`${CHROME.flipCard}`, tone: "gold" })
    : "";
  const art = src
    ? h`<img class="cardview-art" src="${src}" alt="">`
    : h`<div class="cardview-art is-missing"><p class="body secondary">${CHROME.cardArtMissing}</p></div>`;
  const sideNote = files.length > 1
    ? h`<span class="label">${face === 0 ? CHROME.stageSideA : CHROME.stageSideB}</span>` : "";
  return h`<header class="cardview-head">
<div><h1 class="display">${s.name ?? ""}</h1>${s.caption ? raw(h`<p class="label">${s.caption}</p>`) : ""}</div>
<div class="cardview-tools">${raw(sideNote)}${raw(flip)}</div>
</header>
${raw(art)}
<div class="cta-row">${raw(cta({ act: "sheet_close", label: CHROME.close, tone: "plain" }))}</div>`;
}
