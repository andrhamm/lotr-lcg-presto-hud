// The app bar: one fixed chrome band across the top of the setup screens.
//
// It replaces a stack of three separate things (a Back chip, a step stamp, a
// DISPLAY wizard title) plus a fourth in the pane below it (the scenario's own
// DISPLAY heading and its breadcrumb). That arrangement had four problems, all
// of them about rank:
//
//   - TWO DISPLAY TITLES. "Choose a scenario" in the corner and "Stage 1 ·
//     Flies and Spiders" in the pane, same size, same colour, same face. The
//     eye cannot tell which one is the page.
//   - A TITLE THAT GOES STALE. "Choose a scenario" holds the most valuable
//     position on the screen - first read, top left - to say what the Back
//     chip and the step stamp already say, and it stops being true the moment
//     you pick one.
//   - A SHOUTING BREADCRUMB. "PASSAGE THROUGH MIRKWOOD · CORE SET · CORE SET
//     (MIRKWOOD PATHS) · 3 STAGES" put the most important text on the screen
//     in the treatment this design system uses to DEMOTE things, twice over
//     (the pack and the cycle are usually the same words).
//   - NO RANK. The step stamp, the breadcrumb, the rail's section headers and
//     the metadata were all LABEL - four jobs, one treatment.
//
// So: ONE subject, one title, whose content changes. Before a scenario is
// picked the subject IS "Choose a scenario"; after, it is the scenario, and
// the selected stage rides beside it as its own chip rather than being
// concatenated into the title string. The duplication cannot come back,
// because there is only one place a title can be.
//
// The band itself is the same chrome vocabulary as the play screen's strip -
// `--well` ground, a bottom border, a fixed height - so every screen in this
// client has the same thing at the top and the content below it starts at the
// same place.
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { chip, reloadButton } from "./primitives.js";
import { setIcon } from "./seticon.js";

// `title` is what this screen is about right now. `meta` is the dense metadata
// under it (LABEL, where LABEL belongs); `aside` is already-rendered markup for
// the band's right zone - the step's own forward action, so the eye finds
// "what next" in the same place on every screen instead of at the foot of a
// pane whose height depends on its content.
//
// There is no step stamp. "STEP 1 OF 2" sat beside the Back chip saying what
// the Back chip's own label now says outright ("Main Menu" / "Scenario"), and
// two pieces of chrome describing the same thing is what made this corner
// noisy in the first place.
export function setupHead({ title, meta = null, icon = null, iconHave = null, mark = null, aside = "", back, backLabel }) {
  // The mark is large on purpose: it is the one piece of the band that is not
  // text, and at 34px it read as a bullet beside the title rather than as the
  // scenario's own symbol.
  const glyph = mark ?? (icon ? setIcon(icon, 56, iconHave) : "");
  return h`<header class="appbar">
<div class="appbar-nav">${raw(chip({ act: back, label: h`${backLabel}`, tone: "tan" }))}</div>
<div class="appbar-subject">${raw(glyph)}
<div class="appbar-text"><h1 class="display">${title}</h1>${meta ? raw(h`<p class="label">${meta}</p>`) : ""}</div>
</div>
<div class="appbar-aside">${raw(reloadButton({ inline: true }))}${raw(aside)}</div>
</header>`;
}
