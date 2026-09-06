// The header both setup steps wear. One module, because the complaint it
// answers ("no header or instruction at all... very poor UX") is about the
// FLOW, not about one screen: a player needs to know where they are, how far
// through, what this step wants, and how to go back - and needs it in the
// same place each time.
//
// DISPLAY title, LABEL step stamp, one BODY sentence of instruction (design
// system: anything read as a sentence is BODY), and a Back chip. Nothing
// here is decorative; a step with nothing to say has no business adding a
// line to say it.
import { h, raw, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip } from "./primitives.js";

export function setupHead({ step, title, hint, back }) {
  return h`<header class="setup-head">
<div class="setup-head-nav">${raw(chip({ act: back, label: h`${CHROME.back}`, tone: "tan" }))}
<span class="label">${fmt(CHROME.setupStep, step)}</span></div>
<h1 class="display">${title}</h1>
<p class="body secondary">${hint}</p>
</header>`;
}
