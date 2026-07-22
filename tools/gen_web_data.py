"""Regenerate docs/js data modules (phases, icon masks, text metrics) from the
Python firmware source, guaranteeing web/device parity. Run after changing
phases.py, ui/icons.py, or the font metrics."""
# The generation logic lives inline in the repo history; simplest invocation:
#   python3 tools/gen_web_data.py
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import phases
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
print("regenerated docs/js data modules")
