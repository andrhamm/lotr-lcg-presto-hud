import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import ResolutionModal

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "S1", "text": None}, {"side": "B", "name": "S1", "text": None}]}]},
    {"stage": 2, "branch": "choice", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "S2", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "Cannot advance until X."}]},
        {"questPoints": 4, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "S2", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": None}]}]},
    {"stage": 3, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "S3", "text": "Final setup."}, {"side": "B", "name": "S3", "text": None}]}]},
]

def _game(**over):
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.flip_to_b()
    for k, v in over.items():
        setattr(g, k, v) if not isinstance(v, dict) else g.quest.update(v)
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_no_overflow_step_is_none():
    g = _game()
    m = ResolutionModal(g)
    assert m.step is None

def test_location_overflow_step_first():
    g = _game()
    g.active_locations = [{"points": 2, "progress": 3}]
    g.quest["progress"] = 2   # ALSO over - location must still come first
    m = ResolutionModal(g)
    assert m.step["kind"] == "location"

def test_resolving_location_feeds_quest_and_advances_to_branch_step():
    g = _game()
    g.active_locations = [{"points": 2, "progress": 3}]   # 1 excess -> quest
    g.quest["progress"] = 1                             # +1 excess = 2 = clears stage 1
    m = ResolutionModal(g)
    _draw(m, g)
    loc_btn = next(b for b in m.buttons if b.id[0] == "resolve_location")
    assert m.on_button(loc_btn) == "redraw"
    assert not g.active_locations and g.quest["progress"] == 2
    assert m.step["kind"] == "branch"        # stage 2 has 2 cards

def test_branch_pick_then_advance_then_reveal_then_flip():
    g = _game()
    g.quest["progress"] = 2       # clears stage 1 outright
    m = ResolutionModal(g)
    _draw(m, g)
    assert m.step["kind"] == "branch"
    pick = next(b for b in m.buttons if b.id == ("pick_branch", 1))   # choose Beorn's Path
    assert m.on_button(pick) == "redraw"
    assert m.step["kind"] == "advance" and m.step["card_idx"] == 1
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id[0] == "do_advance")
    assert m.on_button(adv) == "redraw"
    assert g.stage_idx == 1 and g.card_idx == 1 and g.quest["side"] == "A"
    assert m.step["kind"] == "reveal"
    _draw(m, g)
    flip = next(b for b in m.buttons if b.id[0] == "do_flip")
    assert m.on_button(flip) == "redraw"
    assert g.quest["side"] == "B" and g.quest["points"] == 4
    assert m.step is None        # 4qp target, 0 progress: nothing left to resolve

def test_conditional_stage_halts_without_looping():
    g = _game()
    g.quest["progress"] = 2
    m = ResolutionModal(g)
    pick0 = {"kind": "branch"}
    _draw(m, g)
    pick = next(b for b in m.buttons if b.id == ("pick_branch", 0))   # "Don't Leave the Path!", 0 qp
    m.on_button(pick)
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id[0] == "do_advance")
    m.on_button(adv)
    _draw(m, g)
    flip = next(b for b in m.buttons if b.id[0] == "do_flip")
    m.on_button(flip)
    assert g.quest["points"] == 0 and g.quest["side"] == "B"
    assert m.step is None                 # halts - no auto-loop on a 0-point stage

def test_force_advance_shows_underfilled_caution():
    g = _game()
    g.quest["progress"] = 0        # nowhere near the 2 needed
    m = ResolutionModal(g, force_advance=True)
    assert m.step["kind"] in ("branch", "advance")
    if m.step["kind"] == "branch":
        _draw(m, g)
        m.on_button(next(b for b in m.buttons if b.id == ("pick_branch", 1)))
    assert m.step["kind"] == "advance" and m.step["underfilled"] is True

def test_victory_step_at_last_stage():
    g = _game(stage_idx=2, card_idx=0)
    g.quest.update({"points": 3, "progress": 3, "side": "B", "stage_n": 3})
    m = ResolutionModal(g)
    assert m.step["kind"] == "victory"
    _draw(m, g)
    b = next(x for x in m.buttons if x.id[0] == "declare_victory")
    assert m.on_button(b) == "close"
    assert g.game_over["result"] == "victory"

def test_side_quest_step_resolve_and_skip():
    g = _game()
    g.side_quests = [{"points": 2, "progress": 2, "name": "Gather Information"},
                      {"points": 3, "progress": 3, "name": "Scout Ahead"}]
    m = ResolutionModal(g)
    assert m.step["kind"] == "side_quest" and m.step["idx"] == 0
    _draw(m, g)
    skip = next(b for b in m.buttons if b.id[0] == "skip_side_quest")
    m.on_button(skip)
    assert m.step["kind"] == "side_quest" and m.step["idx"] == 1   # moved past the skipped one
    _draw(m, g)
    done = next(b for b in m.buttons if b.id[0] == "resolve_side_quest")
    m.on_button(done)
    assert len(g.side_quests) == 1                                 # only the resolved one popped
    assert m.step is None

def test_interrupted_reveal_resumes_first():
    g = _game()
    g.stage_idx = 1
    g.quest.update({"side": "A", "points": 0, "progress": 0, "stage_n": 2})
    g.active_locations = [{"points": 2, "progress": 2}]   # a fresh overflow too
    m = ResolutionModal(g)
    assert m.step["kind"] == "reveal"     # finishes the interrupted flip before the location


# --------------------------------------------------------------------------
# The regression that motivated position-keyed faces (2026-07-30 playtest)
# --------------------------------------------------------------------------

def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def _reveal(stage_faces):
    """Draw the stage-advance panel for a single stage card with these faces."""
    stages = [{"stage": 1, "cards": [{"questPoints": 5, "victory": None,
                                      "sailing": False, "faces": stage_faces}]}]
    g = gamestate.GameState(1, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set",
                        "cycle": "Core Set", "source": "official",
                        "kind": "quest", "nightmare": False, "mode": "Standard"},
                       stages)
    # stay on side A so _quest_step yields the reveal step
    m = ResolutionModal(g, True)
    return _texts(_draw(m, g))


def test_reveal_shows_text_printed_only_on_the_back_face():
    """75 of 514 stage cards in the catalog print their When Revealed on the
    BACK and nothing on the front. The panel read face "A" alone and told the
    player "No setup instructions for this stage." on every one of them - The
    Oath's stage 2, whose back face adds a location to the staging area AND
    states the condition for defeating the stage."""
    out = " ".join(_reveal([
        {"side": "A", "name": "Mirkwood Forest", "text": None},
        {"side": "B", "name": "Mirkwood Forest",
         "text": "When Revealed: Each player searches the encounter deck for a Forest location."}]))
    assert "searches the encounter deck" in out
    assert "no Setup instructions" not in out


def test_reveal_titles_a_card_whose_faces_are_not_lettered_a_and_b():
    """22 stage cards have no "A" face at all - ("C","D"), ("E","F"),
    ("G","H"). The front lookup returned {} for all of them, so the panel drew
    an EMPTY title and the no-instructions fallback over a card that prints
    both a name and rules."""
    out = _reveal([
        {"side": "C", "name": "Attack on Dol Guldur", "text": "When Revealed: Do a thing."},
        {"side": "D", "name": "Attack on Dol Guldur", "text": None}])
    assert "Attack on Dol Guldur" in out
    assert any("Do a thing" in t for t in out)


def test_reveal_falls_back_only_when_neither_face_prints_anything():
    out = " ".join(_reveal([{"side": "A", "name": "S", "text": None},
                            {"side": "B", "name": "S", "text": None}]))
    assert "no Setup instructions" in out


def test_every_catalog_stage_card_with_text_shows_some_of_it():
    """The catalog-wide gate. Walks every quest stage card in docs/data and
    asserts the panel never claims "no Setup instructions" for a card that
    prints some, and never draws an empty title. This is the test that would
    have caught the playtest bug."""
    import glob, json
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = sorted(glob.glob(os.path.join(root, "docs", "data", "scenarios", "*.json")))
    if not files:
        return          # generated catalog absent (bare tree) - nothing to gate
    checked = 0
    for path in files:
        with open(path) as fh:
            data = json.load(fh)
        quest = data.get("quest")
        if not quest:
            continue
        for stage in quest.get("stages", []):
            for card in stage.get("cards", []):
                faces = card.get("faces") or []
                if not faces:
                    continue
                printed = any((f.get("text") or "") for f in faces)
                named = any((f.get("name") or "") for f in faces)
                out = _reveal(faces)
                joined = " ".join(out)
                checked += 1
                if printed:
                    assert "no Setup instructions" not in joined, (
                        "%s stage %s claims no setup text but prints some"
                        % (data.get("name"), stage.get("stage")))
                if named:
                    # out[0] is "STAGE n REVEALED"; out[1] is the card name.
                    assert len(out) > 1 and out[1].strip(), (
                        "%s stage %s drew an empty title"
                        % (data.get("name"), stage.get("stage")))
    assert checked > 400, "expected the full stage-card catalog, got %d" % checked


class _Btn:
    """Bare button stand-in for handler tests that skip draw() - same idiom
    as test_modals.py's _btn."""
    def __init__(self, id_):
        self.id = id_


def _final_stage_game(progress=6):
    """A one-stage scenario sitting at its quest points, i.e. the victory
    prompt's precondition."""
    stages = [{"stage": 1, "cards": [{"questPoints": 6, "victory": None,
        "sailing": False, "faces": [
            {"side": "A", "name": "The Rearguard", "text": "When Revealed: Add Goblin Troop."},
            {"side": "B", "name": "The Rearguard",
             "text": "This stage cannot be defeated while Goblin Troop is in play."}]}]}]
    g = gamestate.GameState(1, 29)
    g.preload_scenario({"slug": "the-oath", "name": "The Oath", "pack": "Core Set",
                        "cycle": "Core Set", "source": "official", "kind": "quest",
                        "nightmare": False, "mode": "Standard"}, stages)
    g.flip_to_b()
    g.quest["progress"] = progress
    return g


def test_victory_prompt_states_the_condition_that_makes_it_declinable():
    """The prompt used to say only "That was the final stage!". The sentence
    that decides whether the game is actually won lives on the stage's BACK
    face, which this screen never read - so in the playtest the HUD offered
    victory with Goblin Troop still alive in the staging area."""
    g = _final_stage_game()
    m = ResolutionModal(g)
    assert m.step["kind"] == "victory"
    out = " ".join(_texts(_draw(m, g)))
    assert "cannot be defeated while Goblin Troop is in play" in out


def test_declining_victory_closes_instead_of_redrawing_the_same_prompt():
    """continue_without_victory returned "redraw" and _derive() recomputed the
    identical victory step, so the modal put the same screen back and the tap
    read as a no-op - pressed three times in the playtest before DONE."""
    g = _final_stage_game()
    m = ResolutionModal(g)
    assert m.on_button(_Btn(("continue_without_victory",))) == "close"
    assert any("Victory declined" in e["text"] for e in g.log)
    assert g.game_over is None


def test_more_card_hands_off_through_the_routers_pending_flags():
    """A modal cannot open a modal. main.py checks pending_quest_card BEFORE
    pending_resolution, so the card opens and closing it reopens this modal."""
    g = _final_stage_game()
    m = ResolutionModal(g)
    assert m.on_button(_Btn(("more_card",))) == "close"
    assert g.pending_quest_card is True
    assert g.pending_resolution is True
