// Icon fill colours shared by every tablet render module that draws an
// icons_svg.js glyph inline (an SVG fill="" attribute in a string builder
// can't read a CSS custom property, so these stay literal rgb() strings).
// One module so rail.js/pane.js/strip.js can't restate the same numbers and
// drift - values are docs/js/ui.js's `pal` (see RGB + pal.threatPen/shaded),
// matching design/stat-system.md's stat-colour rules: player threat red with
// a charcoal shadow, enemy/staging threat black with a light edge, willpower
// gold, progress green with a brown shadow.
export const THREAT_RED = "rgb(247,101,62)";        // pal.red
export const THREAT_SHADOW = "rgb(7,5,3)";          // pal.bevel_d
export const THREAT_BLACK = "rgb(0,0,0)";           // pal.outline
export const THREAT_BLACK_EDGE = "rgb(96,86,54)";   // pal.bevel_l
export const WILLPOWER_GOLD = "rgb(214,180,110)";   // pal.gold
export const TRAIL_GREEN = "rgb(136,168,92)";       // pal.green
export const TRAIL_BROWN = "rgb(104,70,34)";        // pal.brown
