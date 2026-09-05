"""The tablet client's pure modules, driven under node the way
test_twin_parity.py drives the model. Render functions return strings and
never touch `document`, which is what makes this possible."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _stage(tmp):
    """Copy docs/js and docs/tablet/js so ../../js imports resolve."""
    for sub in ("js", os.path.join("tablet", "js")):
        src = os.path.join(ROOT, "docs", sub)
        dst = os.path.join(tmp, sub)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if f.endswith(".js"):
                shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    with open(os.path.join(tmp, "package.json"), "w") as f:
        f.write('{"type":"module"}')


def node(probe):
    """Run `probe` (an ES module body) from tablet/js/ and return its JSON."""
    exe = shutil.which("node")
    if exe is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        _stage(tmp)
        path = os.path.join(tmp, "tablet", "js", "probe.mjs")
        with open(path, "w") as f:
            f.write(probe)
        r = subprocess.run([exe, path], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, "tablet module failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


def test_h_escapes_interpolations_but_not_raw():
    js = node("""
import { h, raw } from "./dom.js";
console.log(JSON.stringify({
  esc: h`<b>${"<i>&"}</b>`,
  raw: h`<b>${raw("<i>x</i>")}</b>`,
  list: h`<ul>${["a", raw("<li>b</li>")]}</ul>`,
}));
""")
    assert js["esc"] == "<b>&lt;i&gt;&amp;</b>"
    assert js["raw"] == "<b><i>x</i></b>"
    assert js["list"] == "<ul>a<li>b</li></ul>"


def test_primitives_are_buttons_with_actions():
    js = node("""
import { chip, cta, counter, band } from "./primitives.js";
console.log(JSON.stringify({
  chip: chip({ act: "open_log", label: "Open" }),
  cta: cta({ act: "advance", label: "Next: Travel" }),
  counter: counter({ label: "Staging area", icon: "", value: 4, act: "stg" }),
  band: band({ kind: "window", text: "Responses.", sub: "Last window." }),
}));
""")
    assert 'data-act="open_log"' in js["chip"] and js["chip"].startswith("<button")
    assert 'data-act="advance"' in js["cta"] and "Next: Travel" in js["cta"]
    assert 'data-act="stg-"' in js["counter"] and 'data-act="stg+"' in js["counter"]
    assert ">4<" in js["counter"]
    assert 'class="band band-window"' in js["band"] and "Last window." in js["band"]


def test_stat_icons_are_generated_from_the_masks():
    js = node("""
import { ICONS, icon } from "../../js/icons_svg.js";
console.log(JSON.stringify({ names: Object.keys(ICONS).sort().slice(0, 4),
  threat: icon("THREAT", 28, "#f7653e", "#070503") }));
""")
    assert "THREAT" in js["names"] or "ARCHERY" in js["names"]
    assert js["threat"].startswith("<svg") and 'viewBox="0 0 20 20"' in js["threat"]
    assert js["threat"].count("<path") == 2      # shadow first, then the fill
