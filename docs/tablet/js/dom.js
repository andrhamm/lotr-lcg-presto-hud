// HTML from tagged templates. Every interpolation is escaped unless it is a
// raw() fragment; arrays are joined. That is the whole safety story for a
// client that renders card names and log text it did not write.
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = s => String(s).replace(/[&<>"']/g, c => ESC[c]);
export class Raw { constructor(html) { this.html = html; } }
export const raw = html => new Raw(html);
const one = v => (v instanceof Raw ? v.html : Array.isArray(v) ? v.map(one).join("") : esc(v ?? ""));
export const h = (strings, ...vals) =>
  strings.reduce((out, s, i) => out + s + (i < vals.length ? one(vals[i]) : ""), "");
export const cx = (...names) => names.filter(Boolean).join(" ");

// %s/%d template fill, in order. Half a dozen sheets each carry their own
// copy of this (pane.js, sheet_elim.js, sheet_locpick.js, sheet_sqpick.js,
// sheet_sailing.js, sheet_resolve.js - each comment names the others as
// "the same helper"); this is a fresh consumer's home, not a retrofit of
// those six, so strip.js imports it from here rather than adding a seventh
// copy-pasted definition.
export const fmt = (t, ...a) => { let i = 0; return t.replace(/%[sd]/g, () => a[i++]); };
