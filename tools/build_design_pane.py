"""Build the Claude Design review pane from real pipeline renders.

The pane's only job is arrangement and labelling. Every image in it comes from
`tools/preview.py` driving `tests/scenes.py` - the same builders the layout
lint uses and the same draw calls the device executes. No card contains a CSS
impression of a device widget, because that is how three earlier retheme
attempts got judged against things the hardware cannot draw.

One card per screen, holding that screen's variants side by side. The card's
first line carries the `@dsCard` marker the Design System pane indexes on.

Images are embedded as data URIs so a card is self-contained and no path
resolution is involved. That is fine at probe scale (a handful of screens);
a full 118-screen round should switch to separate asset files, which is what
--assets does.

Usage:
    python3 tools/build_design_pane.py --variants type --out build/pane
"""
import argparse
import base64
import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tests.fake_hardware as fh

# -- variant sets ----------------------------------------------------------
# A variant is (label, blurb, type binding). Round 1 varies type ONLY, with
# colour held fixed: changing the font changes character widths, which changes
# wrapping, which changes every layout the linter checks - so deciding a
# palette on top of a font that is later dropped throws the palette work away.
TYPE_VARIANTS = [
    ("A - bitmap8",
     "The status quo. 8px glyphs, an 8/16/24px ladder across LABEL/BODY/DISPLAY.",
     {1: ("font8", 1), 2: ("font8", 2), 3: ("font8", 3)}),
    ("B - font14_outline",
     "Outlined 14px glyphs at BODY, doubled for DISPLAY. Necessarily a hybrid: "
     "font14 has no size below 14px, so LABEL falls back to font8.",
     {1: ("font8", 1), 2: ("font14_outline", 1), 3: ("font14_outline", 2)}),
    ("C - font6",
     "Uppercase-only. Disqualified by the design system's own rule - ALL CAPS "
     "is how this system demotes text, so a title bar cannot wear it - and "
     "shown here only to make that concrete.",
     {1: ("font6", 1), 2: ("font6", 2), 3: ("font6", 3)}),
]

def _look_variants():
    """Round 2: one variant per candidate skin, type held at the round-1 result.

    Colour and chrome vary; the font does not, because round 1 measured the
    alternatives and kept bitmap8.
    """
    from tools.skins_round2 import ROUND2
    return [(s.name, s.note, s) for s in ROUND2]


VARIANT_SETS = {"type": TYPE_VARIANTS, "look": _look_variants}

PROBES = [
    ("play_quest_staging", "Play", "Densest phase view: header, stat strip, guidance band, meter, counters, nav"),
    ("play_planning", "Play", "Loop diagram - framing line, rungs, framework and window bands"),
    ("players_detail_modal", "Modals", "Tokens and progress rings, per-player editing"),
    ("choose_scenario", "Setup", "Repeating list rows, icon slots, release metadata"),
    ("quest_card_modal_long_text", "Quest", "Long printed card text with the [...] more affordance"),
    ("log", "System", "Dense tabular metadata - the one legitimate LABEL use"),
]


def all_scenes():
    """Every scene, grouped for the pane by the area its name implies."""
    import tests.scenes
    known = {s[0]: (s[1], s[2]) for s in PROBES}
    prefixes = (
        ("play_", "Play"), ("resolution_", "Progress"),
        ("questing_progress", "Progress"), ("location_", "Progress"),
        ("quest_", "Quest"), ("side_quest", "Quest"), ("sailing", "Quest"),
        ("choose_scenario", "Setup"), ("pick_cycle", "Setup"),
        ("scenario_", "Setup"), ("setup", "Setup"), ("firstrun", "Setup"),
        ("catalog_", "Setup"), ("phases_", "System"), ("log", "System"),
        ("settings", "System"), ("about", "System"), ("boot", "System"),
        ("gameover", "System"), ("legend", "System"), ("counter", "System"),
        ("led_", "System"), ("elim_", "Modals"), ("players_", "Modals"),
    )
    out = []
    for name in sorted(tests.scenes.SCENES):
        if name in known:
            out.append((name, known[name][0], known[name][1]))
            continue
        group = next((g for p, g in prefixes if name.startswith(p)), "Other")
        out.append((name, group, ""))
    return out


def _render(scene, variant, font_default="font8"):
    """A scene rendered under one variant, as PNG bytes.

    A variant is either a type binding (round 1) or a Skin (round 2). Both go
    through the same path, because the whole point of the apparatus is that a
    look is a value the renderer takes as input.
    """
    import importlib
    import tempfile
    import tests.scenes
    from tools.preview import render

    is_skin = hasattr(variant, "colors")
    binding = variant.type_binding if is_skin else variant

    fh.set_type_binding(binding)
    if is_skin:
        tests.scenes.SKIN = variant
    try:
        importlib.reload(tests.scenes)
        if is_skin:
            tests.scenes.SKIN = variant
        hw, _ = tests.scenes.SCENES[scene]()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        # preview.render owns the call-dispatch loop, which is the thing that
        # must stay identical to the device. Never duplicate it here.
        render(hw.display.calls, path, font=font_default)
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data
    finally:
        fh.set_type_binding(None)
        tests.scenes.SKIN = None
        importlib.reload(tests.scenes)


CARD_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px;
       font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, sans-serif; }
h1 { font-size: 20px; margin: 0 0 4px; }
.sub { opacity: .7; margin: 0 0 20px; font-size: 14px; }
.row { display: flex; flex-wrap: wrap; gap: 20px; }
figure { margin: 0; flex: 0 1 auto; }
figure img { display: block; width: 480px; max-width: 100%; height: auto;
             image-rendering: pixelated; border-radius: 4px; }
figcaption { margin-top: 8px; max-width: 480px; }
figcaption b { display: block; font-size: 14px; }
figcaption span { display: block; opacity: .7; font-size: 13px; margin-top: 2px; }
.note { margin-top: 24px; padding: 12px 14px; border-radius: 6px;
        font-size: 13px; opacity: .85;
        background: color-mix(in srgb, currentColor 7%, transparent); }
@media (max-width: 1060px) { .row { flex-direction: column; } }
"""


def card_html(scene, blurb, group, variants):
    """One screen's card: every variant side by side, labelled."""
    figs = []
    for label, note, png in variants:
        b64 = base64.b64encode(png).decode("ascii")
        figs.append(
            '    <figure>\n'
            '      <img alt="%s, %s" src="data:image/png;base64,%s">\n'
            '      <figcaption><b>%s</b><span>%s</span></figcaption>\n'
            '    </figure>' % (scene, label, b64, label, note))
    return (
        '<!-- @dsCard group="%s" -->\n'
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<title>%s</title>\n<style>%s</style>\n'
        '<h1>%s</h1>\n<p class="sub">%s</p>\n'
        '<div class="row">\n%s\n</div>\n'
        '<p class="note">Rendered through tools/preview.py from tests/scenes.py '
        '- the same draw calls the device executes, drawn with the device\'s own '
        'glyph masks. Not a CSS mockup.</p>\n'
        % (group, scene, CARD_CSS, scene, blurb, "\n".join(figs)))


def build(variant_set, out_dir, scenes=None):
    variants = VARIANT_SETS[variant_set]
    if callable(variants):
        variants = variants()
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for scene, group, blurb in (scenes or PROBES):
        rendered = []
        for label, note, binding in variants:
            rendered.append((label, note, _render(scene, binding)))
            print("  %-28s %s" % (scene, label))
        path = os.path.join(out_dir, "%s.html" % scene)
        with open(path, "w") as f:
            f.write(card_html(scene, blurb, group, rendered))
        written.append(path)
        print("wrote %s (%d KB)" % (path, os.path.getsize(path) // 1024))
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variants", default="type", choices=sorted(VARIANT_SETS))
    ap.add_argument("--out", default="build/pane")
    ap.add_argument("--all-scenes", action="store_true",
                    help="every scene in tests/scenes.py, not just the probes")
    args = ap.parse_args()
    scenes = None
    if args.all_scenes:
        scenes = all_scenes()
    files = build(args.variants, args.out, scenes)
    print("\n%d cards in %s" % (len(files), args.out))


if __name__ == "__main__":
    main()
