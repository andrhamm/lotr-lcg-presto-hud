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
  if (!spec) return null;
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
