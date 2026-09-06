// Set icons (Task 5): a small <img> for a named encounter set/expansion,
// pulled from the SVGs tools/build_icons.py exports beside icons.json
// (docs/data/icons/svg/<slug>.svg, commit abfbd80) - the tablet's answer to
// the twin's rasterized icons.json masks (docs/js/icons.js's drawIcon), but
// as a real vector image instead of a bitmap decode, since a browser can
// just load an <img> for free.
//
// The slug is quest_catalog.js's own slugify() applied to the printed SET
// NAME - the one slug rule this client already has, not a second copy of
// tools/build_icons.py's _slug(). The two rules are NOT the same in
// general: _slug() lowercases the pack's own FILENAME (underscores to
// hyphens), while slugify() lowercases the printed NAME and turns every run
// of non-alphanumerics into one hyphen - so an apostrophe diverges ("The
// Steward's Fear" -> slugify's "the-steward-s-fear" vs. however the pack
// happened to name that file on disk). They agree for the plain-word set
// names this app actually shows a header for (see tests/test_tablet.py's
// slug-parity assertion for "Passage Through Mirkwood" / "Dol Guldur Orcs" /
// "Spiders of Mirkwood"). A set whose printed name diverges from the pack's
// filename just falls back to the placeholder glyph below - a known,
// accepted gap (apostrophes), not a second slug rule to invent.
//
// Pure string builder like every other tablet render helper: no Image()
// probe, no fetch here - a missing SVG 404s like any other <img>, and
// app.js's one delegated capture-phase `error` listener is what actually
// adds `is-missing` to the wrapper (style.css's `.seticon.is-missing img` /
// `.seticon:not(.is-missing) .seticon-fallback` pair swap the glyph in).
import { h } from "./dom.js";
import { dataUrl, slugify } from "../../js/quest_catalog.js";

export function setIcon(name, px) {
  const src = dataUrl("icons/svg/" + slugify(name) + ".svg");
  return h`<span class="seticon" style="width:${px}px;height:${px}px"><img src="${src}" alt="" loading="lazy"><i class="seticon-fallback">◆</i></span>`;
}
