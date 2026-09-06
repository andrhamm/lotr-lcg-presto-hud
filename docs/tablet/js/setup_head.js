// The header both setup steps wear. One module, because the complaint it
// answers ("no header or instruction at all... very poor UX") is about the
// FLOW, not about one screen: a player needs to know where they are, how far
// through, what this step wants, and how to go back - and needs it in the
// same place each time.
//
// DISPLAY title, LABEL step stamp, a Back chip, and an OPTIONAL BODY
// sentence. Optional is the point: a step whose controls already say what
// they want gets no sentence at all. Step 1 had one ("Pick a cycle, then a
// quest. Its details open on the right.") and it was narrating the layout,
// which is the kind of line no app you would want to use writes.
import { h, raw, fmt } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip } from "./primitives.js";

export function setupHead({ step, title, hint = null, back }) {
  return h`<header class="setup-head">
<div class="setup-head-nav">${raw(chip({ act: back, label: h`${CHROME.back}`, tone: "tan" }))}
<span class="label">${fmt(CHROME.setupStep, step)}</span></div>
<h1 class="display">${title}</h1>
${hint ? raw(h`<p class="body secondary">${hint}</p>`) : ""}
</header>`;
}
