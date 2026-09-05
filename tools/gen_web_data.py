"""Regenerate docs/js data modules (phases, icon masks, text metrics, copy)
from the Python firmware source, guaranteeing web/device parity. Run after
changing phases.py, ui/icons.py, viewcopy.py, xtargets.py, or the font
metrics."""
# The generation logic lives inline in the repo history; simplest invocation:
#   python3 tools/gen_web_data.py
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import phases
import viewcopy
import xtargets
from ui import icons
from tests.fake_hardware import BITMAP8_W

root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "js")

out = ["// GENERATED from phases.py - do not edit (tools/gen_web_data.py)"]
out.append("export const PHASES = %s;" % json.dumps(phases.PHASES))
out.append("export const STEPS = %s;" % json.dumps(phases.STEPS))
out.append("export const STEP_ORDER = %s;" % json.dumps(phases.STEP_ORDER))
out.append("export function step(id) { return STEPS.find(s => s.id === id); }\n"
           "export function phase(id) { return PHASES.find(p => p.id === id); }")
open(os.path.join(root, "phases.js"), "w").write("\n".join(out))

names = [n for n in dir(icons) if n.isupper() and isinstance(getattr(icons, n), list)]
out = ["// GENERATED from ui/icons.py - do not edit (tools/gen_web_data.py)"]
for n in names:
    mask = getattr(icons, n)
    out.append("export const %s = [%d, %s];" % (n, len(mask), json.dumps([str(r) for r in mask])))
out.append("""
export function drawIcon(ctx, mask, x, y, color, scale = 1) {
  const [size, rows] = mask;
  const top = size - 1;
  ctx.fillStyle = color;
  for (let row = 0; row < size; row++) {
    const bits = BigInt(rows[row]);
    let col = 0;
    while (col < size) {
      if ((bits >> BigInt(top - col)) & 1n) {
        let run = col;
        while (run < size && ((bits >> BigInt(top - run)) & 1n)) run++;
        ctx.fillRect(x + col * scale, y + row * scale, (run - col) * scale, scale);
        col = run;
      } else col++;
    }
  }
}""")
open(os.path.join(root, "icons.js"), "w").write("\n".join(out))

# The same masks as SVG path data, for the tablet client (which draws with
# the DOM, not a framebuffer). One path per icon: each horizontal run of set
# pixels is an "M x y h w v1 h-w z" rectangle. shape-rendering: crispEdges at
# the draw site keeps the pixel look at any size.
def _runs_path(mask):
    n = len(mask)
    d = []
    for y, row in enumerate(mask):
        x = 0
        while x < n:
            if (row >> (n - 1 - x)) & 1:
                x0 = x
                while x < n and (row >> (n - 1 - x)) & 1:
                    x += 1
                d.append("M%d %dh%dv1h-%dz" % (x0, y, x - x0, x - x0))
            else:
                x += 1
    return "".join(d)

out = ["// GENERATED from ui/icons.py - do not edit (tools/gen_web_data.py)",
       "export const ICONS = %s;" % json.dumps(
           {n: {"size": len(getattr(icons, n)), "path": _runs_path(getattr(icons, n))}
            for n in names}, sort_keys=True),
       """
// An inline SVG of one mask. `shadow`, when given, is drawn first offset by
// (1, 1) - the charcoal under the red helm, the brown under the ranger.
export function icon(name, px, fill, shadow = null) {
  const m = ICONS[name];
  if (!m) return "";
  const sh = shadow
    ? `<path d="${m.path}" fill="${shadow}" transform="translate(1 1)"></path>` : "";
  return `<svg viewBox="0 0 ${m.size} ${m.size}" width="${px}" height="${px}" `
    + `shape-rendering="crispEdges" style="display:block;flex:none">${sh}`
    + `<path d="${m.path}" fill="${fill}"></path></svg>`;
}
"""]
open(os.path.join(root, "icons_svg.js"), "w").write("\n".join(out) + "\n")

out = ["// GENERATED from tests/fake_hardware.py - device bitmap8 metrics"]
out.append("export const BITMAP8_W = %s;" % json.dumps(BITMAP8_W))
out.append("""export function measureText(s, scale = 1) {
  s = String(s);
  if (!s.length) return 0;
  let w = 0;
  for (const c of s) w += (BITMAP8_W[c] ?? 4);
  return (w + s.length - 1) * scale;
}""")
open(os.path.join(root, "metrics.js"), "w").write("\n".join(out))

# Play-screen copy. Every uppercase dict/list/str in viewcopy is exported
# verbatim, so adding a new copy group needs no change here. Tuples become JS
# arrays - LOOP_FLOW's rungs read as [label, opensWindow, subRung].
out = ["// GENERATED from viewcopy.py - do not edit (tools/gen_web_data.py)"]
for n in sorted(d for d in dir(viewcopy)
                if d.isupper()
                and isinstance(getattr(viewcopy, d), (dict, list, str))):
    out.append("export const %s = %s;" % (n, json.dumps(getattr(viewcopy, n))))
open(os.path.join(root, "viewcopy.js"), "w").write("\n".join(out) + "\n")

# What a printed X counts (xtargets.py). The TABLE is generated; the tiny bit
# of arithmetic that reads it is hand-mirrored below, because a generator that
# emitted functions would be a code generator rather than a data one.
out = ["// GENERATED from xtargets.py - do not edit (tools/gen_web_data.py)"]
for n in sorted(d for d in dir(xtargets)
                if d.isupper() or d.startswith("AUTO_")):
    v = getattr(xtargets, n)
    if isinstance(v, (dict, list, str)):
        out.append("export const %s = %s;" % (n, json.dumps(v)))
out.append("""
export function labelFor(target) {
  return TARGETS[target]?.label ?? null;
}

export function autoFor(target) {
  return TARGETS[target]?.auto ?? null;
}

// value = mul * count + add, never below zero.
export function valueOf(count, mul = 1, add = 0) {
  return Math.max(0, mul * count + add);
}

// The number to put on screen, or null when the player has not supplied a
// count yet. AUTO_PLAYERS, AUTO_STAGE and AUTO_HIGHEST_THREAT ignore `count`
// and recompute from the tracked value - that is the whole point of tagging
// those separately: "X is 4 per player" must follow the player count without
// anyone touching a stepper.
//
// AUTO_ENEMIES and AUTO_STAGING_LOCATIONS are tracker-backed, not
// unconditionally auto: when the client tracks the board they behave the
// same way - followed, and a stale supplied count cannot override them.
// Otherwise `enemies`/`stagingLocations` are null and this falls back to the
// count path exactly as before, so the player supplies the count.
// GameState.xContext() supplies every tracked value by these option names,
// omitting the two tracker-only keys until the client tracks the board.
export function resolve(spec, { count = null, players = 1, stage = 1,
                                highestThreat = 0, enemies = null,
                                stagingLocations = null } = {}) {
  // Python's `if not spec` is falsy on an empty dict too, not just None -
  // matched here explicitly, since {} is truthy in JS.
  if (!spec || Object.keys(spec).length === 0) return null;
  const mul = spec.mul ?? 1, add = spec.add ?? 0;
  switch (autoFor(spec.target)) {
    case AUTO_PLAYERS: return valueOf(players, mul, add);
    case AUTO_STAGE: return valueOf(stage, mul, add);
    case AUTO_HIGHEST_THREAT: return valueOf(highestThreat, mul, add);
    case AUTO_ENEMIES:
      if (enemies !== null) return valueOf(enemies, mul, add);
      break;
    case AUTO_STAGING_LOCATIONS:
      if (stagingLocations !== null) return valueOf(stagingLocations, mul, add);
      break;
  }
  if (count === null) return null;
  return valueOf(count, mul, add);
}""")
open(os.path.join(root, "xtargets.js"), "w").write("\n".join(out) + "\n")

print("regenerated docs/js data modules")
