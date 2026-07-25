import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_tips

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "votp_passage.html")

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/</loc></url>
<url><loc>https://visionofthepalantir.com/2023/05/08/shelobs-lair/</loc></url>
<url><loc>https://visionofthepalantir.com/shadows-of-mirkwood/</loc></url>
<url><loc>https://visionofthepalantir.com/2019/11/12/deckbuilding-celebrimbors-secret/</loc></url>
</urlset>"""


# --- extract_blocks: HTML -> plain-text candidate blocks -------------------

def test_extract_returns_plain_text_blocks():
    html = open(FIXTURE, encoding="utf-8").read()
    blocks = build_tips.extract_blocks(html)
    assert blocks and all(isinstance(b, str) for b in blocks)
    assert not any("<" in b for b in blocks)          # tags stripped


def test_extract_prefers_tips_section_and_stops_at_next_heading():
    html = open(FIXTURE, encoding="utf-8").read()
    blocks = build_tips.extract_blocks(html)
    joined = " ".join(blocks).lower()
    assert "hummerhorns" in joined                      # inside "Tips and Tricks"
    assert "playthrough video" not in joined             # next H2 section excluded
    assert "share on social media" not in joined          # trailer excluded


def test_extract_strips_script_and_nav_boilerplate():
    html = open(FIXTURE, encoding="utf-8").read()
    blocks = build_tips.extract_blocks(html)
    joined = " ".join(blocks)
    assert "tracking snippet" not in joined
    assert not any(b.strip() in ("Home", "About") for b in blocks)


def test_extract_handles_empty_input_without_raising():
    assert build_tips.extract_blocks("") == []
    assert build_tips.extract_blocks("<article></article>") == []


# --- summarize: condense to our own short phrasing, or drop ----------------

def test_summarize_respects_limits():
    tips = build_tips.summarize(["x" * 400, "short note"], max_len=140, max_tips=4)
    assert len(tips) <= 4
    assert all(len(t) <= 140 for t in tips)


def test_summarize_extracts_threat_threshold_in_own_words():
    src = "Keep your threat below 40 to avoid the Hummerhorns, who deal heavy damage."
    tips = build_tips.summarize([src], max_len=140, max_tips=4)
    assert tips == ["Stay under 40 threat - avoid Hummerhorns."]
    # genuinely reworded - neither string is a substring of the other
    assert tips[0] not in src
    assert src not in tips[0]


def test_summarize_caps_tip_count_across_many_matches():
    blocks = ["Keep your threat below %d to avoid the Watcher." % n
              for n in (10, 20, 30, 40, 50)]
    tips = build_tips.summarize(blocks, max_len=140, max_tips=4)
    assert len(tips) == 4


def test_summarize_drops_sentence_it_cannot_safely_condense():
    # Flowing prose with no recognized factual pattern (no threat threshold,
    # no negative imperative) - must be dropped rather than force-truncated
    # into a clipped quote.
    src = ("Some players like to spend a long time deliberating over which "
           "exact cards to bring, and honestly there is no single right "
           "answer here because it really depends on your group's taste.")
    assert build_tips.summarize([src], max_len=140, max_tips=4) == []


def test_summarize_never_keeps_a_long_run_of_source_words():
    # No rule recognizes this shape (it's flowing prose, not a threat-
    # threshold callout - see _RULES), so it's dropped before ever
    # reaching the similarity guard. Kept as a regression case: this used
    # to be a "Don't <clause>" sentence that the old (now-removed)
    # negative-imperative rule WOULD have matched, and _too_verbatim was
    # what stopped it from shipping as a long clipped quote - see
    # test_too_verbatim_rejects_a_long_shared_run for that guard tested
    # directly now that no surviving rule can trigger it via summarize().
    src = ("Don't leave allies undefended near the end of the round, since "
           "several treacheries punish it harshly and can swing the game.")
    assert build_tips.summarize([src], max_len=140, max_tips=4) == []


def test_too_verbatim_rejects_a_long_shared_run():
    # Direct unit test of the guard itself (see its comment in
    # test_summarize_never_keeps_a_long_run_of_source_words for why
    # summarize() can no longer exercise this via any surviving rule -
    # _THREAT_AVOID's own capture groups are too short to ever trip it).
    source = ("Don't leave allies undefended near the end of the round, "
               "since several treacheries punish it harshly.")
    candidate = "leave allies undefended near the end of the round since"
    assert build_tips._too_verbatim(candidate, source)
    assert not build_tips._too_verbatim("Stay under 40 threat - avoid Hummerhorns.",
                                         source)


def test_summarize_deduplicates_repeated_tips():
    blocks = ["Keep your threat below 40 to avoid the Hummerhorns."] * 3
    tips = build_tips.summarize(blocks, max_len=140, max_tips=4)
    assert tips == ["Stay under 40 threat - avoid Hummerhorns."]


def test_summarize_threat_avoid_stops_name_at_lowercase_word():
    # Regression (Task 1 Step 7, real-corpus audit): the rule's overall
    # re.I compile flag used to also make [A-Z] match lowercase, so the
    # "name" group swallowed trailing lowercase words too ("avoid the
    # Hummerhorns or raise their" -> name="Hummerhorns or raise their").
    src = "Keep your threat below 40 to avoid the Hummerhorns or raise their engagement cost."
    tips = build_tips.summarize([src], max_len=140, max_tips=4)
    assert tips == ["Stay under 40 threat - avoid Hummerhorns."]


def test_summarize_never_produces_avoid_colon_tips():
    # Correctness fix regression: build_tips used to rewrite a sentence-
    # initial "Don't X"/"Never X" into "Avoid: X" (see the module
    # docstring's Quality gate). That transform is removed outright - not
    # narrowed - because splicing the raw clause after "Avoid:" doesn't
    # just reword the source, it can silently invert it ("Don't be afraid
    # to scoop." - DO scoop - would have become "Avoid: be afraid to
    # scoop.", the opposite advice). Every one of these (mid-sentence
    # "don't"/"never" that was never a command in the first place, AND a
    # genuine sentence-initial imperative that the old rule WOULD have
    # matched) must now produce no tip at all - never an "Avoid: ..."
    # construction of any kind.
    cases = [
        "Characters that don't exhaust to quest are invaluable in this quest.",
        "The enemy is discarded, and the Boarding Keyword never resolves.",
        "For the same reason, I do not recommend the Lore variant.",
        "Don't bring a Swarm deck.",              # old rule's own matching example
        "Don't worry, it will be fine.",
    ]
    for src in cases:
        assert build_tips.summarize([src], max_len=140, max_tips=4) == []
    assert not hasattr(build_tips, "_rule_negative_imperative")
    assert not hasattr(build_tips, "_NEGATIVE_IMPERATIVE")


def test_summarize_drops_rather_than_truncates_an_overlong_candidate():
    # The old code path truncated an overlong candidate to max_len with a
    # "..' - a clipped copy is still a copy, and clipping risks shipping
    # an unreadable fragment. Now it's simply dropped (is_useful_tip's own
    # max_len check) - see the module docstring's "never a truncate-with-
    # '..'" - so an otherwise-well-formed _THREAT_AVOID match with an
    # overlong captured name never reaches tips.json at all.
    long_name = " ".join("Name%dxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" % i
                          for i in range(4))
    src = "Keep your threat below 40 to avoid the %s." % long_name
    assert len("Stay under 40 threat - avoid %s." % long_name) > 140
    assert build_tips.summarize([src], max_len=140, max_tips=4) == []


# --- is_useful_tip: the quality gate, tested directly -----------------------

def test_is_useful_tip_rejects_the_real_bad_samples():
    # The exact strings the tips summarizer used to emit (see the module
    # docstring's Quality gate) - every one is unreadable-to-backwards and
    # must be rejected outright.
    bad = [
        "Avoid: be afraid to scoop.",
        "Avoid: rely on them too much though.",
        "Avoid: go overboard though.",
        "Avoid: bother with easy mode.",
        "Avoid: try to complete side quests.",
    ]
    for text in bad:
        assert build_tips.is_useful_tip(text) is False, text


def test_is_useful_tip_accepts_the_real_good_sample():
    assert build_tips.is_useful_tip("Stay under 40 threat - avoid Hummerhorns.") is True


def test_is_useful_tip_rejects_dangling_trailer_without_avoid_glue():
    # Isolates the trailing-word check from the "Avoid:" glue check - no
    # leading "Avoid:" here, so this only passes if the dangling-trailer
    # rule independently fires.
    assert build_tips.is_useful_tip("Bring extra allies for this fight though.") is False


def test_is_useful_tip_rejects_unresolved_pronoun_without_avoid_glue():
    assert build_tips.is_useful_tip("Remember to defend with it every round.") is False


def test_is_useful_tip_rejects_generic_filler_with_no_game_information():
    text = "There is no single right answer here for everyone."
    assert build_tips.is_useful_tip(text) is False


def test_is_useful_tip_rejects_companion_app_meta_commentary():
    # quests/*.md notes mix real quest facts with the author's own asides
    # about the companion app - those are grammatical, self-contained
    # sentences, just not tips about how to PLAY the quest.
    text = "The HUD's progress row could optionally show an enemy track."
    assert build_tips.is_useful_tip(text) is False


def test_is_useful_tip_allows_this_plus_noun_as_a_determiner():
    # "this quest"/"this stage" is a determiner phrase with its own noun
    # right there (self-contained), unlike a bare "this"/"that" standing
    # in for something named only in a source article we don't carry over.
    text = "This quest has two progress tracks (yours + the enemy's)."
    assert build_tips.is_useful_tip(text) is True


def test_is_useful_tip_rejects_bare_demonstrative_pronoun():
    assert build_tips.is_useful_tip("Watch carefully and avoid that.") is False


def test_is_useful_tip_rejects_dangling_fragment_and_no_terminal_punctuation():
    assert build_tips.is_useful_tip("avoid the Hummerhorns near the end") is False  # lowercase start, no ".", no "!", no "?"
    assert build_tips.is_useful_tip("Avoid the Hummerhorns near the end") is False  # still no terminal punctuation


def test_is_useful_tip_rejects_too_thin_a_statement():
    assert build_tips.is_useful_tip("Stay under 40.") is False   # only 2 words


def test_is_useful_tip_respects_max_len():
    ok = "Stay under 40 threat - avoid Hummerhorns."
    assert build_tips.is_useful_tip(ok) is True
    assert build_tips.is_useful_tip(ok, max_len=10) is False


def test_is_useful_tip_rejects_empty_and_whitespace_only():
    assert build_tips.is_useful_tip("") is False
    assert build_tips.is_useful_tip("   ") is False
    assert build_tips.is_useful_tip(None) is False


# --- build_entry: {attribution, general, stages} shape ---------------------

def test_entry_carries_attribution():
    e = build_tips.build_entry("passage-through-mirkwood", "http://example/x", ["a note"])
    assert e["attribution"]["url"] == "http://example/x"
    assert e["general"] == ["a note"]


def test_entry_defaults_stages_to_empty_and_names_the_source():
    e = build_tips.build_entry("p", "http://example/x", ["a note"])
    assert e["stages"] == {}
    assert e["attribution"]["name"] == build_tips.SOURCE_NAME


def test_entry_carries_explicit_stages():
    e = build_tips.build_entry("p", "http://example/x", ["general note"],
                                stages={"3": ["stage note"]})
    assert e["stages"] == {"3": ["stage note"]}


def test_entry_attribution_override_replaces_the_default():
    e = build_tips.build_entry("p", None, ["a note"],
                                attribution={"name": build_tips.PROJECT_SOURCE_NAME, "url": ""})
    assert e["attribution"] == {"name": build_tips.PROJECT_SOURCE_NAME, "url": ""}


# --- sitemap -> slug/URL map, and the slug matcher --------------------------

def test_parse_sitemap_keeps_only_dated_post_slugs():
    slugs = build_tips.parse_sitemap(SITEMAP_XML)
    assert slugs["passage-through-mirkwood"] == \
        "https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/"
    assert "shadows-of-mirkwood" not in slugs   # undated cycle-guide page excluded


def test_match_article_exact_slug():
    slugs = build_tips.parse_sitemap(SITEMAP_XML)
    assert build_tips.match_article("passage-through-mirkwood", slugs) == \
        slugs["passage-through-mirkwood"]


def test_match_article_normalizes_possessive_apostrophe():
    # our slugify() keeps "shelob-s-lair" (hyphen before the possessive s);
    # WordPress's own slugs drop the apostrophe outright ("shelobs-lair").
    slugs = build_tips.parse_sitemap(SITEMAP_XML)
    assert build_tips.match_article("shelob-s-lair", slugs) == slugs["shelobs-lair"]


def test_match_article_returns_none_when_absent():
    slugs = build_tips.parse_sitemap(SITEMAP_XML)
    assert build_tips.match_article("coast-of-umbar", slugs) is None


# --- pickable_scenarios: same filter as the picker's own -------------------

def test_pickable_scenarios_filters_nightmare_and_non_quest():
    index = {"scenarios": [
        {"slug": "a", "name": "A", "kind": "quest", "stageCount": 3},
        {"slug": "a-nightmare", "name": "A - Nightmare", "kind": "quest", "stageCount": 3},
        {"slug": "b", "name": "B", "kind": "nightmare", "stageCount": 3},
        {"slug": "c", "name": "C", "kind": "encounter", "stageCount": 0},
        {"slug": "d", "name": "D", "kind": "quest", "stageCount": 0},
    ]}
    got = [s["slug"] for s in build_tips.pickable_scenarios(index)]
    assert got == ["a"]


# --- load_project_notes: quests/*.md -> {slug: [tip, ...]} -----------------

_QUEST_NOTE = """---
title: Test Quest
tags:
  - lotr-lcg/quest
  - core-set
---

# Test Quest

> [!tip] Companion value
> Stage points are fixed: **1 = 8, 2 = 2**. A quest picker could preload
> them so the player never types them.

> [!warning] Threat watch (the app tracks threat)
> - **Watcher** engages at **30** and deals 3 damage to the engaged hero.
> - Avoid: rely on them too much though.
> - **Goblin Scout** (20 eng) returns to staging on a blank shadow.

> [!note] Design commentary
> This callout type is never parsed regardless of wording, so a threat
> value here like 99 must never appear in tips.json.
"""

_CYCLE_NOTE = """---
title: Test Cycle
type: cycle-index
tags:
  - lotr-lcg/cycle
---

# Test Cycle

> [!tip] Cycle-level tip
> The Watcher engages at 30 and deals 3 damage to the engaged hero.
"""


def _write_note(dir_path, filename, text):
    path = os.path.join(dir_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def test_load_project_notes_filters_by_frontmatter_tag(tmp_path):
    notes_dir = str(tmp_path)
    _write_note(notes_dir, "test-quest.md", _QUEST_NOTE)
    _write_note(notes_dir, "test-cycle.md", _CYCLE_NOTE)
    result = build_tips.load_project_notes(notes_dir)
    assert "test-quest" in result
    assert "test-cycle" not in result   # "lotr-lcg/cycle" tag, not "lotr-lcg/quest"


def test_load_project_notes_parses_tip_and_warning_bullets_and_gates_them(tmp_path):
    notes_dir = str(tmp_path)
    _write_note(notes_dir, "test-quest.md", _QUEST_NOTE)
    tips = build_tips.load_project_notes(notes_dir)["test-quest"]

    # The two real, useful bullets/sentences survive...
    assert "Watcher engages at 30 and deals 3 damage to the engaged hero." in tips
    assert "Goblin Scout (20 eng) returns to staging on a blank shadow." in tips
    # ...but the "Avoid: ... though." bullet embedded in the SAME warning
    # callout is rejected by the exact same gate used everywhere else.
    assert not any("avoid: rely on them" in t.lower() for t in tips)
    # And nothing from the [!note] callout (never parsed) leaks through -
    # its "99" would otherwise be an easy false-accept via the digit check.
    assert not any("99" in t for t in tips)


def test_load_project_notes_ignores_note_and_check_callouts(tmp_path):
    notes_dir = str(tmp_path)
    text = _QUEST_NOTE.replace("[!note] Design commentary",
                                "[!check] Design commentary")
    _write_note(notes_dir, "test-quest.md", text)
    tips = build_tips.load_project_notes(notes_dir)["test-quest"]
    assert not any("99" in t for t in tips)


def test_load_project_notes_caps_at_max_tips_and_dedupes(tmp_path):
    notes_dir = str(tmp_path)
    bullets = "\n".join(
        "> - **Card%d** engages at %d and deals 1 damage." % (n, n * 10)
        for n in range(1, 8))
    text = """---
tags:
  - lotr-lcg/quest
---

> [!warning] Many threats
%s
""" % bullets
    _write_note(notes_dir, "many.md", text)
    tips = build_tips.load_project_notes(notes_dir, max_tips=4)["many"]
    assert len(tips) == 4

    dup_text = """---
tags:
  - lotr-lcg/quest
---

> [!warning] Repeats
> - **Watcher** engages at 30 and deals 3 damage to the engaged hero.
> - **Watcher** engages at 30 and deals 3 damage to the engaged hero.
"""
    _write_note(notes_dir, "dup.md", dup_text)
    tips = build_tips.load_project_notes(notes_dir)["dup"]
    assert len(tips) == 1


def test_load_project_notes_returns_empty_for_missing_directory():
    assert build_tips.load_project_notes("/no/such/directory/at/all") == {}


def test_load_project_notes_returns_empty_when_nothing_passes_the_gate(tmp_path):
    notes_dir = str(tmp_path)
    text = """---
tags:
  - lotr-lcg/quest
---

> [!tip] Only filler
> There is no single right answer here for everyone in this group.
"""
    _write_note(notes_dir, "empty-quest.md", text)
    assert build_tips.load_project_notes(notes_dir) == {}


def test_load_project_notes_real_quests_directory():
    # Locks in the real, shipped behavior against the actual quests/*.md
    # files (see CLAUDE.md) - not just synthetic fixtures. If this ever
    # regresses, it means either a note was edited in a way that no
    # longer parses/gates as expected, or the parser/gate itself changed.
    result = build_tips.load_project_notes(build_tips.DEFAULT_NOTES)
    assert "passage-through-mirkwood" in result
    assert "journey-along-the-anduin" in result
    for slug, tips in result.items():
        assert 1 <= len(tips) <= build_tips.MAX_TIPS
        for t in tips:
            assert build_tips.is_useful_tip(t)
    # escape-from-dol-guldur.md has only a [!note] callout (no tip/
    # warning) - it must contribute nothing.
    assert "escape-from-dol-guldur" not in result
    # Real content spot-check (see the passage-through-mirkwood.md
    # "[!warning] Threat / engagement watch" callout).
    assert "Ungoliant's Spawn: 32 eng, When Revealed -1 willpower; " \
           "9 HP / 5 atk / 2 def boss." in result["passage-through-mirkwood"]


# --- build(): end-to-end with a faked network (no real HTTP) ---------------

class _FakeResponse:
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._text.encode("utf-8")


def test_build_writes_expected_shape_with_faked_network(tmp_path, monkeypatch):
    index = {"scenarios": [
        {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
         "kind": "quest", "stageCount": 3},
        {"slug": "no-match-quest", "name": "No Match Quest",
         "kind": "quest", "stageCount": 2},
    ]}
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index))

    article_url = "https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/"
    article_html = open(FIXTURE, encoding="utf-8").read()
    responses = {build_tips.SITEMAP_URL: SITEMAP_XML, article_url: article_html}

    def _fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        return _FakeResponse(responses[url])

    monkeypatch.setattr(build_tips.urllib.request, "urlopen", _fake_urlopen)

    out_path = tmp_path / "tips.json"
    cache_dir = tmp_path / "cache"
    # notes_dir points at an empty/nonexistent directory so this stays a
    # pure scraped-pipeline test, isolated from the real quests/ notes
    # (which DO cover "passage-through-mirkwood" - see test_build_prefers_
    # project_notes_over_scraped_material for that precedence, tested
    # separately).
    summary = build_tips.build(str(index_path), str(out_path), str(cache_dir), delay=0,
                                notes_dir=str(tmp_path / "no_notes"))

    assert summary["resolved"] == 1
    assert summary["no_url"] == 1
    data = json.loads(out_path.read_text())
    assert isinstance(data["generated"], str) and data["generated"]
    assert "passage-through-mirkwood" in data["scenarios"]
    assert "no-match-quest" not in data["scenarios"]
    entry = data["scenarios"]["passage-through-mirkwood"]
    assert entry["attribution"]["url"] == article_url
    assert entry["general"]
    assert all(len(t) <= 140 for t in entry["general"])


def test_build_caches_so_a_second_run_makes_no_network_calls(tmp_path, monkeypatch):
    index = {"scenarios": [{"slug": "passage-through-mirkwood",
                             "name": "Passage Through Mirkwood",
                             "kind": "quest", "stageCount": 3}]}
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index))

    article_url = "https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/"
    article_html = open(FIXTURE, encoding="utf-8").read()
    responses = {build_tips.SITEMAP_URL: SITEMAP_XML, article_url: article_html}
    calls = []

    def _fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        calls.append(url)
        return _FakeResponse(responses[url])

    monkeypatch.setattr(build_tips.urllib.request, "urlopen", _fake_urlopen)
    out_path = tmp_path / "tips.json"
    cache_dir = tmp_path / "cache"
    no_notes = str(tmp_path / "no_notes")   # isolate from real quests/ notes

    build_tips.build(str(index_path), str(out_path), str(cache_dir), delay=0,
                      notes_dir=no_notes)
    assert len(calls) == 2   # sitemap + one article

    def _boom(req, timeout=None):
        raise AssertionError("should not hit the network on a cached run")
    monkeypatch.setattr(build_tips.urllib.request, "urlopen", _boom)

    summary = build_tips.build(str(index_path), str(out_path), str(cache_dir), delay=0,
                                notes_dir=no_notes)
    assert summary["resolved"] == 1


def test_build_degrades_gracefully_when_sitemap_fetch_fails(tmp_path, monkeypatch, capsys):
    index = {"scenarios": [{"slug": "passage-through-mirkwood",
                             "name": "Passage Through Mirkwood",
                             "kind": "quest", "stageCount": 3}]}
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index))

    import urllib.error

    def _boom(req, timeout=None):
        raise urllib.error.URLError("simulated network failure")
    monkeypatch.setattr(build_tips.urllib.request, "urlopen", _boom)

    out_path = tmp_path / "tips.json"
    cache_dir = tmp_path / "cache"
    summary = build_tips.build(str(index_path), str(out_path), str(cache_dir), delay=0,
                                notes_dir=str(tmp_path / "no_notes"))

    assert summary["resolved"] == 0
    data = json.loads(out_path.read_text())
    assert data["scenarios"] == {}
    assert "sitemap" in capsys.readouterr().out.lower()


def test_build_prefers_project_notes_over_scraped_material(tmp_path, monkeypatch):
    # "passage-through-mirkwood" has both a VotP article match (faked
    # network below) AND a quests/*.md note with real tip/warning
    # callouts (synthetic fixture here) - the note must win, and the
    # article must never even be fetched (see the module docstring's
    # Sources preference order).
    index = {"scenarios": [{"slug": "passage-through-mirkwood",
                             "name": "Passage Through Mirkwood",
                             "kind": "quest", "stageCount": 3}]}
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index))

    article_url = "https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/"
    article_html = open(FIXTURE, encoding="utf-8").read()
    responses = {build_tips.SITEMAP_URL: SITEMAP_XML, article_url: article_html}
    calls = []

    def _fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        calls.append(url)
        return _FakeResponse(responses[url])

    monkeypatch.setattr(build_tips.urllib.request, "urlopen", _fake_urlopen)

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    _write_note(str(notes_dir), "passage-through-mirkwood.md", _QUEST_NOTE)

    out_path = tmp_path / "tips.json"
    cache_dir = tmp_path / "cache"
    summary = build_tips.build(str(index_path), str(out_path), str(cache_dir), delay=0,
                                notes_dir=str(notes_dir))

    assert summary["resolved"] == 1
    assert summary["from_notes"] == 1
    # The sitemap is still fetched unconditionally (build() doesn't know in
    # advance which scenarios notes will cover), but the per-scenario
    # ARTICLE fetch - the one that would return the scraped fixture - must
    # never happen once a slug is satisfied by notes.
    assert article_url not in calls

    data = json.loads(out_path.read_text())
    entry = data["scenarios"]["passage-through-mirkwood"]
    assert entry["attribution"] == {"name": build_tips.PROJECT_SOURCE_NAME, "url": ""}
    assert "Watcher engages at 30 and deals 3 damage to the engaged hero." in entry["general"]
    # The scraped fixture's own tip must NOT be present - notes replace,
    # not merge with, the scraped source for a scenario covered by both.
    assert not any("hummerhorns" in t.lower() for t in entry["general"])


def test_tips_are_ascii_only_for_the_device_font():
    """The device's bitmap8 glyph table only covers printable ASCII, so a tip
    containing an arrow/en-dash/curly quote would render as garbage on
    hardware. Source notes and articles both contain them."""
    src = "Hummerhorns engage at 40 -> deal 5 dmg — the “engaged” hero’s fate; -1 willpower"
    out = build_tips._clean_ws(src)
    assert all(32 <= ord(c) < 127 for c in out), out
    assert "->" in out and "-1 willpower" in out
    assert '"engaged"' in out and "hero's" in out
