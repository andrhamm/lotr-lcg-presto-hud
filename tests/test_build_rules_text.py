import json, os, subprocess, sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import build_rules_text as brt
FIX = os.path.join(ROOT, "tests", "fixtures")

def test_parse_splits_merged_headings_and_keeps_one_text():
    doc = brt.parse(open(os.path.join(FIX, "rules_fixture.md")).read())
    s = doc["sections"]
    assert s["1.1"] == {"ids": ["1.1"], "title": "Resource phase begins", "text": "Fixture text for one one.", "see_also": []}
    assert s["1.3"]["ids"] == ["1.3", "1.4"] and s["1.4"] is s["1.3"]
    assert s["1.3"]["title"] == "Draw cards · Resource phase ends"
    assert s["6.4a"]["text"] == "Fixture text for six four a."

def test_parse_collects_glossary_and_see_also():
    doc = brt.parse(open(os.path.join(FIX, "rules_fixture.md")).read())
    g = doc["glossary"]["Player Elimination"]
    # The fixture wraps this entry's "See also:" onto a second markdown line
    # (blank line, then the remaining terms, blank line, then a "-----"
    # separator) the way the real corpus does - both wrapped terms must land
    # in see_also, and text must carry neither the separator nor a "See also"
    # fragment.
    assert g["text"] == "Fixture: a player leaves the game when the fixture says so."
    assert g["see_also"] == ["Threat", "Threat Elimination Level"]
    assert "-----" not in g["text"] and "See also" not in g["text"]
    assert doc["glossary"]["Threat"]["text"] == "Fixture threat entry."
    assert doc["faq"] == []

def test_build_writes_json_and_is_a_noop_when_present(tmp_path):
    out = tmp_path / "rules_text.json"
    brt.build(FIX, str(out), corpus_name="rules_fixture.md")
    d = json.loads(out.read_text())
    assert d["book"] == "Rules Reference" and "1.1" in d["sections"] and d["source"]["sha256"]
    mtime = out.stat().st_mtime
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_rules_text.py"), "--corpus", FIX, "--corpus-name", "rules_fixture.md", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0 and "already" in r.stdout.lower() and out.stat().st_mtime == mtime

def test_missing_corpus_is_a_friendly_exit(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_rules_text.py"), "--corpus", str(tmp_path), "--out", str(tmp_path / "x.json")], capture_output=True, text=True)
    assert r.returncode != 0 and "Traceback" not in r.stderr and "research/rules" in (r.stderr + r.stdout)
