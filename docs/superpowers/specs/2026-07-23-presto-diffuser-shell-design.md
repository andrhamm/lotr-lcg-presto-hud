# Presto Diffuser Shell — v1 Design (snug-fit milestone)

Status: approved 2026-07-23. Side project (CAD), not part of the game HUD.

## Purpose

A translucent 3D-printed shell that caps the void behind the Pimoroni Presto
(the concave side of the bent-aluminium chassis, between the strut and behind
the screen). Long-term it diffuses the back-facing RGB LEDs and holds 2×18650
cells. **v1 goal is narrow: a full shell that achieves a snug, registered fit
on the Presto via an edge grip.** Everything else is deferred.

## Ground-truth Presto geometry (all caliper/true-scale anchored)

Built by `presto_build.FCMacro`. Bent 2mm aluminium sheet, strut-flat pose:

| Param | Value | Source |
|---|---|---|
| Body width (extrude) | 92.22 mm | caliper |
| Sheet thickness | 2.0 mm | caliper |
| Ground-to-top height | ~104 mm | caliper 106 (2% trace) |
| Base depth (bend-front→strut-tip) | 80 mm | caliper |
| Back-panel length LB | 94.6 mm | trace, true scale |
| Strut length LS | 68.4 mm | anchored to 80mm |
| Bend radius RB | 10.6 mm | trace |
| Strut angle | 21.8° | trace |
| Strut-tip corner R | 9 mm | test-print |
| Panel-top corner R | 5 mm (placeholder) | unverified |

The shell macro **reuses this exact geometry** so grip surfaces track the sheet
and stay correct if any Presto param changes.

## Shell shape

Side profile (strut-flat pose), single-bend wedge echoing the Presto body:

- panel-top → **flat top ~22 mm** (horizontal) → bend → **steep back face**
  (~12° from vertical, steeper than the screen's 22° lean) → strut-tip
- Extruded across **98.22 mm** = 92.22 body + 3 mm proud on each side
- Wall thickness **~3 mm**
- Back (largest) face prints face-down on the bed
- **3 mm fillet** on the two side↔back-face edges

## Fit interface — the whole point of v1

Grips the **full mouth perimeter**: panel-top free edge, strut-tip free edge,
and both width-end side edges.

- Rebate capturing the 2 mm sheet free edge:
  **3 mm outer overhang + 2 mm sheet channel + inner lip (2 mm deep)** on the
  inner face.
- **Clearance ~0.18 mm** on grip faces — a per-print tunable knob (like RCORN).
- The wedge floats off the panel center (LED/diffusion gap); exact standoff is
  deferred (needs LED-height measurement) and not required for the edge-grip test.

## Construction approach (macro)

`presto_shell.FCMacro`, reusing the profile math + anchors from `presto_build`:

1. Rebuild the Presto sheet solid `P` (2 mm band, 92.22 wide).
2. `PC` = `P` dilated by CLEAR (0.18 mm) — the seat gap.
3. Shell outer profile (closed wire, YZ plane): exposed side = flat-top + steep
   back; Presto side = 3 mm outside the sheet outer face, wrapping the free edges.
4. `SHELL_full` = extrude that profile 98.22 mm (centered on width).
5. `SHELL` = `SHELL_full − PC` → carves seat, rebate, side grip.
6. Wall it to 3 mm (`makeThickness`, removing the mouth/seat faces) so the grip
   lips remain.
7. 3 mm fillet on side↔back edges.

Verify each boolean by volume + orthographic render before declaring done.

## Tunable knobs

flat-top length (22), wall (3), overhang (3), grip clearance (0.18),
side-back fillet (3), lip depth (2).

## Deferred (explicitly out of scope for v1)

2×18650 bay (across width), retention/attachment, USB-C cutout (left side),
diffusion window / LED standoff, translucent-material optical tuning.

## Success criterion

A full test print that seats onto the Presto with a snug, registered grip on the
mouth perimeter — no rock, no gaps, removable. Clearance tuned by reprinting the
knob if needed.
