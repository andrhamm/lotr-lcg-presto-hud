// The client's own chrome iconography: transport, chevrons, marks.
//
// These were Unicode dingbats in the markup - "⏮", "◀", "▶", "⏭", "↻", "⚑",
// "◆", "✓", "✕", "‹", "›" - which is fine until the platform disagrees about
// what they are. iOS has no text glyph for most of that range in its UI faces
// and falls back to Apple Color Emoji, so the transport bar, the reload and
// the row marks rendered as full-colour emoji on the iPad while looking like
// plain type in every desktop browser. Nothing in this app's visual language
// is a colour emoji.
//
// So they are drawn here instead, as inline SVG on one 24x24 grid, in
// `currentColor` - which means every one of them inherits the ink of whatever
// it sits in (a tan chip, a gold pinned row, a dimmed-out transport button)
// and needs no per-use colour. Same reason the set icons are recoloured to
// the palette gold at build time rather than tinted at the call site.
//
// Deliberately geometric and flat: the game's own icons (icons_svg.js) are
// pixel-art masks lifted from the Presto's bitmaps and carry the game's
// vocabulary - a threat crown, a willpower eye. These carry the APP's, and
// the two should not be mistaken for each other.
import { h, raw } from "./dom.js";

// Solid shapes, no strokes: a stroked triangle at 14px is mush, and the
// palette's contrast ramp is built for filled marks.
const PATHS = {
  // Transport. The bars are the "jump to the end" pair; the bare triangles
  // are step-by-step.
  first: "M7 5v14h2.4V5H7zm11 0-7.4 7 7.4 7V5z",
  prev: "M16.5 5 8 12l8.5 7V5z",
  next: "M7.5 5 16 12l-8.5 7V5z",
  last: "M17 5v14h-2.4V5H17zM6 5l7.4 7L6 19V5z",
  // A ring with a break and an arrowhead - a reload, not a recycle symbol.
  reload: "M12 5a7 7 0 1 0 6.3 4h-2.4A4.7 4.7 0 1 1 12 7.3V10l4.2-3.4L12 3.2V5z",
  // The first-player marker: a pennant on a staff.
  flag: "M6 3h1.7v18H6V3zm3 1.2 9 3.4-9 3.4V4.2z",
  // The placeholder where a set has no symbol in the pack.
  diamond: "M12 5.5 18.5 12 12 18.5 5.5 12 12 5.5z",
  check: "M9.6 16.2 5.4 12l-1.6 1.6 5.8 5.8L20.2 8.8 18.6 7.2 9.6 16.2z",
  close: "M18.3 7.3 16.7 5.7 12 10.4 7.3 5.7 5.7 7.3 10.4 12l-4.7 4.7 1.6 1.6L12 13.6l4.7 4.7 1.6-1.6L13.6 12l4.7-4.7z",
  // Chevrons: the "this goes somewhere" mark, and the pager's two directions.
  chevronRight: "M9.4 4.6 7.8 6.2 13.6 12l-5.8 5.8 1.6 1.6L16.8 12 9.4 4.6z",
  chevronLeft: "M14.6 4.6 7.2 12l7.4 7.4 1.6-1.6L10.4 12l5.8-5.8-1.6-1.6z",
  plus: "M13.2 5h-2.4v5.8H5v2.4h5.8V19h2.4v-5.8H19v-2.4h-5.8V5z",
  minus: "M5 10.8h14v2.4H5v-2.4z",
};

// `px` sizes the box; the path is always drawn on the same 24 grid, so a
// 14px chevron and a 34px reload are the same shape at two sizes rather than
// two drawings.
//
// aria-hidden throughout: every one of these sits inside a control that
// already carries its own label or title, so a screen reader announcing the
// shape as well would just say it twice.
export function glyph(name, px = 20) {
  const d = PATHS[name];
  if (!d) return "";
  return h`<svg class="glyph" viewBox="0 0 24 24" width="${px}" height="${px}" aria-hidden="true" focusable="false"><path d="${d}" fill="currentColor"/></svg>`;
}

// A label with a trailing chevron - the shape a dozen chips and CTAs share
// ("Edit ›", "Open ›", "More notes ›", "Continue ›"). The arrow used to be a
// literal "›" inside the copy string, which put a rendering decision inside
// the words and meant every one of them carried its own emoji risk.
export function withChevron(label, dir = "right", px = 16) {
  const mark = glyph(dir === "left" ? "chevronLeft" : "chevronRight", px);
  return dir === "left" ? h`${raw(mark)}${label}` : h`${label}${raw(mark)}`;
}
