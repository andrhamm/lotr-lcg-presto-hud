import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_play import ScreenPlay
from ui.modals import LocationPickModal
from gamestate import GameState


def _setup(view="resource_planning"):
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.view = view
    screen = ScreenPlay()
    return hw, pal, game, screen


def _find(screen, id):
    return [b for b in screen.buttons if b.id == id][0]


def _ids(screen):
    return [b.id[0] for b in screen.buttons]


def test_resource_planning_advances_to_commit():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("advance",)), game)
    assert game.view == "quest_commit"


def test_commit_view_has_per_player_willpower_cards():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert _ids(screen).count("commit") == 4


def test_commit_tap_opens_cycling_commit_modal():
    from ui.modals import CommitModal
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("commit", 1)), game)
    modal = result[1]
    assert isinstance(modal, CommitModal)
    assert modal.idx == 1


def test_staging_view_has_direct_steppers():
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    for k in ("wp-", "wp+", "stg-", "stg+"):
        assert k in ids


def test_resolve_success_enters_resolution_view_with_budget():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = 11
    game.staging = 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("resolve",)), game)
    assert game.view == "quest_resolution"
    assert game.pending_budget == 4


def test_resolve_failure_stays_on_staging_with_banner_and_travel_cta():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = 2
    game.staging = 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("resolve",)), game)
    assert game.view == "quest_staging"        # outcome shown where it happened
    assert game.players[0].threat == 5
    assert screen.banner[1] == "bad"
    assert screen.banner[2] == "quest_staging"
    screen.draw(hw, game, pal)                 # resolved -> CTA becomes Travel
    ids = [b.id[0] for b in screen.buttons]
    assert "resolve" not in ids
    assert "advance" in ids


def test_banner_does_not_leak_to_other_views():
    hw, pal, game, screen = _setup("quest_staging")
    screen.banner = ("Quest failed. +5", "bad", "quest_staging")
    game.view = "travel"
    screen.draw(hw, game, pal)
    texts = [c[1] for c in hw.display.calls if c[0] == "text"]
    assert not any("failed" in str(t) for t in texts)


def test_commit_view_wp_and_stg_cards_tappable_no_steppers():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    ids = [b.id[0] for b in screen.buttons]
    assert "wp" in ids                # opens the Questing for modal
    assert "stg" in ids               # staging editable via counter modal
    assert "wp-" not in ids and "stg+" not in ids


def test_commit_staging_tap_opens_counter():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("stg",)), game)
    assert result[0] == "modal"
    modal = result[1]
    modal.state.tap(5)
    modal.state.confirm()
    modal.on_commit(modal.state.value)
    assert game.staging == 5


def test_resolution_apply_places_and_goes_to_travel():
    hw, pal, game, screen = _setup("quest_resolution")
    game.quest = {"stage_n": 1, "side": "B", "points": 8, "progress": 0}
    game.pending_budget = 4
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("apply_alloc",)), game)
    assert game.quest["progress"] == 4
    assert game.view == "travel"
    assert game.pending_budget == 0


def test_travel_buttons_open_location_pick():
    hw, pal, game, screen = _setup("travel")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("travel_new",)), game)
    assert isinstance(result[1], LocationPickModal)


def test_travel_new_logs_precisely():
    g = GameState()
    m = LocationPickModal(g, mode="new")
    hw = FakeHardware()
    pal = Palette(hw.display)
    m.draw(hw, g, pal)
    save = [b for b in m.buttons if b.id == ("save",)][0]
    m.on_button(save)
    assert g.active_location == {"points": 3, "progress": 0}
    assert "Traveled to new location" in g.log[-1]["text"]


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_progress_row_shows_quest_loc_sq_labels():
    hw, pal, game, screen = _setup("enc_optional")
    game.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 6}
    game.active_location = {"points": 3, "progress": 2}
    game.side_quests = [{"points": 5, "progress": 1}]
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    for t in ("Q2B", "LOC", "SQ1", "6/8", "2/3", "1/5"):
        assert t in texts


def test_add_sq_only_in_planning_and_staging():
    for view, expect in (("resource_planning", True), ("quest_staging", True),
                         ("enc_optional", False), ("refresh", False),
                         ("travel", False)):
        hw, pal, game, screen = _setup(view)
        screen.draw(hw, game, pal)
        ids = [b.id[0] for b in screen.buttons]
        assert ("sq_add" in ids) is expect, view


def test_sq_add_opens_side_quest_manager():
    from ui.modals import SideQuestsModal
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("sq_add",)), game)
    assert isinstance(result[1], SideQuestsModal)


def test_commit_view_stacks_threat_progress_then_willpower():
    from ui.screen_play import STRIP_Y, PROG_Y, CONTENT_Y
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert "Q1A" in _texts(hw)                      # progress row present
    thr = _find(screen, ("thr", 0))
    commit = _find(screen, ("commit", 0))
    assert thr.y == STRIP_Y
    assert PROG_Y == STRIP_Y + 56 + 8               # immediately under threat
    assert commit.y == CONTENT_Y                    # willpower right after progress
    assert commit.w == thr.w                        # same card sizing/columns


def test_progress_cards_match_threat_card_width():
    from ui.screen_play import PROG_Y
    hw, pal, game, screen = _setup("refresh")
    game.active_location = None
    game.side_quests = []
    screen.draw(hw, game, pal)
    thr = _find(screen, ("thr", 0))
    # single Q card at chip width, chip column x
    rects = [c for c in hw.display.calls if c[0] == "rect" and c[2] == PROG_Y]
    assert any(r[1] == thr.x and r[3] == thr.w for r in rects)


def test_refresh_end_round_resets_view():
    hw, pal, game, screen = _setup("refresh")
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("endround",)), game)
    assert game.round == 2
    assert game.view == "resource_planning"


def test_totals_cards_renamed_with_currency_icons():
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    assert "Questing for" in texts and "Staging area" in texts
    assert "Willpower" not in texts and "Staging threat" not in texts


def test_staging_center_tap_opens_reminders():
    from ui.modals import RemindersModal
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("enc_rem",)), game)
    assert isinstance(result[1], RemindersModal)


def test_commit_tip_opens_commit_modal_from_p1():
    from ui.modals import CommitModal
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("commit_tip",)), game)
    assert isinstance(result[1], CommitModal)
    assert result[1].idx == 0


def test_notification_overlay_draws_with_pie_and_dismiss():
    hw, pal, game, screen = _setup("combat_shadow")
    screen.notif = ["Archery: deal damage now"]
    screen.notif_frac = 0.5
    screen.draw(hw, game, pal)
    assert any("Archery" in str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert any(c[0] == "tri" for c in hw.display.calls)   # pie fan drawn
    assert screen.notif_pie is not None
    screen.on_button(_find(screen, ("notif_dismiss",)), game)
    assert screen.notif is None


def test_notification_pie_fraction_controls_fan_size():
    from ui.screen_play import draw_notif_pie
    hw = FakeHardware()
    pal = Palette(hw.display)
    draw_notif_pie(hw.display, pal, 100, 100, 11, 1.0)
    full = sum(1 for c in hw.display.calls if c[0] == "tri")
    hw.display.calls.clear()
    draw_notif_pie(hw.display, pal, 100, 100, 11, 0.25)
    quarter = sum(1 for c in hw.display.calls if c[0] == "tri")
    assert full == 24 and quarter == 6


def test_apply_placement_disabled_until_budget_fully_placed():
    hw, pal, game, screen = _setup("quest_resolution")
    game.quest = {"stage_n": 1, "side": "B", "points": 8, "progress": 0}
    game.active_location = None
    game.pending_budget = 4
    screen.draw(hw, game, pal)          # auto-split places all 4 -> enabled
    assert any(b.id == ("apply_alloc",) for b in screen.buttons)
    screen.on_button(_find(screen, ("areset",)), game)   # clear allocation
    screen.draw(hw, game, pal)
    ids = [b.id for b in screen.buttons]
    assert ("apply_alloc",) not in ids   # gated
    assert "Place 4 more to continue" in _texts(hw)


def test_travel_modal_passes_contribution():
    hw, pal, game, screen = _setup("travel")
    game.active_location = None
    game.staging = 6
    screen.draw(hw, game, pal)
    m = screen.on_button(_find(screen, ("travel_new",)), game)[1]
    m.draw(hw, game, pal)
    ctr_plus = [b for b in m.buttons if b.id == ("ctr", 1)][0]
    m.on_button(ctr_plus)   # 2 -> 3
    save = [b for b in m.buttons if b.id == ("save",)][0]
    m.on_button(save)
    assert game.staging == 3


def test_header_shows_round_and_step_decimal():
    hw, pal, game, screen = _setup("quest_resolution")
    game.round = 2
    game.step = "3.4"
    screen.draw(hw, game, pal)
    assert "R2 3.4" in _texts(hw)


def test_setup_view_tip_and_quest_points_then_begin():
    hw, pal, game, screen = _setup("setup_game")
    screen.draw(hw, game, pal)
    assert any("mulligan" in str(c[1]) for c in hw.display.calls if c[0] == "text")
    for _ in range(8):
        screen.on_button(_find(screen, ("qp", 1)), game)
        screen.draw(hw, game, pal)
    assert game.quest["points"] == 8
    screen.on_button(_find(screen, ("advance",)), game)
    assert game.view == "resource_planning"
    assert any("needs 8" in e["text"] for e in game.log)


def test_progress_cards_open_logged_adjusters():
    hw, pal, game, screen = _setup("travel")
    game.active_location = {"points": 3, "progress": 1}
    game.side_quests = [{"points": 5, "progress": 2}]
    screen.draw(hw, game, pal)
    m = screen.on_button(_find(screen, ("prog_q",)), game)[1]
    m.state.tap(5)
    m.state.confirm()
    m.on_commit(m.state.value)
    assert game.quest["progress"] == 5
    assert any("(manual)" in e["text"] for e in game.log)
    m2 = screen.on_button(_find(screen, ("prog_sq", 0)), game)[1]
    m2.state.tap(1)
    m2.state.confirm()
    m2.on_commit(m2.state.value)
    assert game.side_quests[0]["progress"] == 3


def test_questing_for_card_taps_open_modal_on_both_views():
    from ui.modals import QuestingForModal
    for view in ("quest_commit", "quest_staging"):
        hw, pal, game, screen = _setup(view)
        screen.draw(hw, game, pal)
        result = screen.on_button(_find(screen, ("wp",)), game)
        assert isinstance(result[1], QuestingForModal), view
