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


def test_resource_planning_shows_framework_and_window_blocks():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" in texts
    assert "YOUR WINDOW" in texts
    accents = [c[5] for c in hw.display.calls if c[0] == "rect" and c[1] == 8 and c[3] == 4]
    assert pal.red in accents and pal.green in accents


def test_commit_view_shows_willpower_tokens_in_players_matrix():
    # Willpower now lives inside the flipped players zone (one shared tap
    # target) rather than a per-player row of "commit" buttons.
    hw, pal, game, screen = _setup("quest_commit")
    for i, c in enumerate((7, 8, 5, 6)):
        game.set_commit(i, c)
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    assert ids.count("players_detail") == 1
    assert "commit" not in ids
    texts = _texts(hw)
    for c in (7, 8, 5, 6):
        assert str(c) in texts


def test_players_detail_tap_opens_players_detail_modal():
    from ui.modals import PlayersDetailModal
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("players_detail",)), game)
    assert isinstance(result[1], PlayersDetailModal)


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
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution"
    assert game.pending_budget == 4
    assert game.quest_outcome == "success"


def test_resolve_failure_enters_resolution_with_outcome_toast():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = 2
    game.staging = 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution"     # outcome shown on the resolution view
    assert game.players[0].threat == 5         # shortfall applied to all
    assert game.quest_outcome == "fail"
    assert screen.toast is not None            # picked up by the main loop
    screen.draw(hw, game, pal)                 # fail resolution -> Travel CTA
    ids = [b.id[0] for b in screen.buttons]
    assert "advance" in ids


def test_banner_does_not_leak_to_other_views():
    hw, pal, game, screen = _setup("quest_staging")
    screen.banner = ("Quest failed. +5", "bad", "quest_staging")
    game.view = "travel"
    screen.draw(hw, game, pal)
    texts = [c[1] for c in hw.display.calls if c[0] == "text"]
    assert not any("failed" in str(t) for t in texts)


def test_commit_view_wp_tappable_stg_has_inline_thirds():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    ids = [b.id[0] for b in screen.buttons]
    assert "wp" in ids                          # opens the Questing for modal
    assert "wp-" not in ids and "wp+" not in ids  # wp stays a single tap target
    assert "stg" in ids                         # centre third -> counter modal
    assert "stg-" in ids and "stg+" in ids       # left/right thirds adjust inline


def test_commit_staging_thirds_geometry_flanks_centre():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    minus = _find(screen, ("stg-",))
    centre = _find(screen, ("stg",))
    plus = _find(screen, ("stg+",))
    for b in (minus, centre, plus):
        assert b.h == 84 and b.w >= 24           # layout linter's MIN_TARGET
    assert minus.x < centre.x < plus.x           # left / centre / right order
    assert minus.x + minus.w == centre.x         # thirds tile with no gaps
    assert centre.x + centre.w == plus.x
    assert minus.w == plus.w                     # outer thirds are symmetric


def test_commit_staging_thirds_step_and_floor_at_zero():
    hw, pal, game, screen = _setup("quest_commit")
    game.staging = 0
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stg-",)), game)
    assert game.staging == 0                     # floored, never negative
    screen.on_button(_find(screen, ("stg+",)), game)
    assert game.staging == 1


def test_commit_staging_caption_reads_reveal_estimate():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert ("+%d reveal estimate" % game.staging_reveal_estimate()) in _texts(hw)


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
    game.quest_outcome = "success"
    game.quest_outcome_n = 4
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


def test_progress_zone_shows_quest_loc_side_labels_and_remaining_values():
    hw, pal, game, screen = _setup("enc_optional")
    game.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 1}
    game.active_location = {"points": 9, "progress": 4}
    game.side_quests = [{"points": 9, "progress": 3}]
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    for t in ("Q", "L", "S1"):                       # flipped zone: short headers
        assert t in texts
    for remaining in ("7", "5", "6"):                # points - progress each
        assert remaining in texts


def test_progress_zone_tap_present_and_sq_add_card_dropped():
    # The +SQ placeholder card is gone; every play view routes progress edits
    # (incl. adding side quests) through the Questing Progress view.
    for view in ("resource_planning", "quest_commit", "quest_staging",
                 "enc_optional", "refresh", "travel"):
        hw, pal, game, screen = _setup(view)
        screen.draw(hw, game, pal)
        ids = [b.id[0] for b in screen.buttons]
        assert "progress_detail" in ids, view
        assert "sq_add" not in ids, view


def test_progress_detail_opens_questing_progress_modal():
    from ui.modals import QuestingProgressModal
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("progress_detail",)), game)
    assert isinstance(result[1], QuestingProgressModal)


def test_commit_view_shows_zones_then_note_at_content_y():
    from ui.screen_play import ZONE_TOP, CONTENT_Y
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert "Q" in _texts(hw)                         # progress zone quest column
    players = _find(screen, ("players_detail",))
    progress = _find(screen, ("progress_detail",))
    assert players.y == ZONE_TOP - 2 and progress.y == ZONE_TOP - 2
    assert players.x == 8 and progress.x == 174
    commit_tip = _find(screen, ("commit_tip",))
    # willpower now lives in the matrix -> no commit row -> note starts right
    # after the zones, at CONTENT_Y (not offset further down)
    assert commit_tip.y == CONTENT_Y


def test_zone_geometry_is_fixed_regardless_of_content():
    from ui.screen_play import ZONE_TOP
    hw, pal, game, screen = _setup("refresh")
    game.active_location = None
    game.side_quests = []
    screen.draw(hw, game, pal)
    players = _find(screen, ("players_detail",))
    progress = _find(screen, ("progress_detail",))
    assert (players.x, players.y, players.w, players.h) == (8, ZONE_TOP - 2, 156, 90)
    assert (progress.x, progress.y, progress.w, progress.h) == (174, ZONE_TOP - 2, 298, 90)


def test_progress_zone_caps_columns_keeping_oldest_side_quests_and_sailing():
    hw, pal, game, screen = _setup("resource_planning")
    game.active_location = {"points": 5, "progress": 0}
    game.sailing = True
    game.side_quests = [{"points": 5, "progress": 0} for _ in range(10)]
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    # maxCols = (472-174)//32 = 9; fixed = Q + L + sailing = 3 -> 6 sides kept
    for lab in ("Q", "L", "S1", "S2", "S3", "S4", "S5", "S6"):
        assert lab in texts
    for lab in ("S7", "S8", "S9", "S10"):
        assert lab not in texts                      # newest sides dropped


def test_progress_zone_shows_sailing_column_regardless_of_view():
    # Old behaviour gated the heading card to specific views via a
    # show_heading flag; the flipped zone shows it whenever game.sailing is
    # true, on every view - this scene never rendered a heading card before.
    from ui.screen_play import ZONE_TOP
    hw, pal, game, screen = _setup("travel")
    game.sailing = True
    game.heading = 2
    screen.draw(hw, game, pal)
    scx = 190 + 32                                   # Q is the only other column
    well_disc_row = ("rect", scx - 14, ZONE_TOP + 40, 29, 1, pal.well)
    assert well_disc_row in hw.display.calls


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


def test_commit_view_window_only_no_framework_block():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "YOUR WINDOW" in texts
    assert "FRAMEWORK" not in texts


def test_commit_tip_button_still_opens_commit_modal_at_new_geometry():
    from ui.modals import CommitModal
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    tip = _find(screen, ("commit_tip",))
    assert tip.w >= 24 and tip.h >= 24
    result = screen.on_button(tip, game)
    assert isinstance(result[1], CommitModal)


def test_commit_totals_row_moves_with_tip_height():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    tip = _find(screen, ("commit_tip",))
    ids = _ids(screen)
    assert "wp" in ids and "stg" in ids
    wp_button = _find(screen, ("wp",))
    assert wp_button.y >= tip.y + tip.h   # totals row starts at/after the tip's bottom


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


def test_resolution_apply_always_enabled_and_shows_discard():
    hw, pal, game, screen = _setup("quest_resolution")
    game.quest = {"stage_n": 1, "side": "B", "points": 8, "progress": 0}
    game.active_location = None
    game.quest_outcome = "success"
    game.pending_budget = 4
    screen.draw(hw, game, pal)          # auto-split places all 4
    assert any(b.id == ("apply_alloc",) for b in screen.buttons)
    screen.on_button(_find(screen, ("areset",)), game)   # clear allocation
    screen.draw(hw, game, pal)
    ids = [b.id for b in screen.buttons]
    assert ("apply_alloc",) in ids       # always enabled (no gating)
    assert "Unplaced (discarded)" in _texts(hw)


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


def test_progress_detail_edits_quest_and_logs_on_close():
    hw, pal, game, screen = _setup("travel")
    game.active_location = {"points": 3, "progress": 1}
    game.side_quests = [{"points": 5, "progress": 2}]
    screen.draw(hw, game, pal)
    m = screen.on_button(_find(screen, ("progress_detail",)), game)[1]
    m.draw(hw, game, pal)
    # bump quest progress via its stepper, bump the side quest, then close
    m.on_button([b for b in m.buttons if b.id == ("qP+", None)][0])
    m.on_button([b for b in m.buttons if b.id == ("sP+", 0)][0])
    m.on_button([b for b in m.buttons if b.id == ("close",)][0])
    assert game.quest["progress"] == 1
    assert game.side_quests[0]["progress"] == 3
    assert any("(progress view)" in e["text"] for e in game.log)


def test_questing_for_card_taps_open_modal_on_both_views():
    from ui.modals import PlayersDetailModal
    for view in ("quest_commit", "quest_staging"):
        hw, pal, game, screen = _setup(view)
        screen.draw(hw, game, pal)
        result = screen.on_button(_find(screen, ("wp",)), game)
        assert isinstance(result[1], PlayersDetailModal), view


# -- Task 8: Quest Setup (R0 pre-round-1) ----------------------------------

_QS_SCN = {"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
           "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}
_QS_STAGES = [{"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "Flies and Spiders", "text": "Setup: do the thing."},
              {"side": "B", "name": "Flies and Spiders", "text": None}]}]}]


def test_quest_setup_flip_to_b_enters_round_1():
    hw, pal, game, screen = _setup("quest_setup")
    game.preload_scenario(_QS_SCN, _QS_STAGES)
    for p in game.players:
        p.commit_touched = True
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("flip_to_b",)), game)
    assert result is True
    assert game.quest["side"] == "B" and game.quest["points"] == 8
    assert game.view == "resource_planning"        # VIEW_ORDER[0]
    assert all(not p.commit_touched for p in game.players)
    assert game._round_snap is not None
    messages = [e["text"] for e in game.log]
    assert any("Setup complete" in m and "1B" in m and "8" in m for m in messages)


def test_quest_setup_card_modal_button_opens_quest_card_modal():
    from ui.modals import QuestCardModal
    hw, pal, game, screen = _setup("quest_setup")
    game.preload_scenario(_QS_SCN, _QS_STAGES)
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("open_card_modal",)), game)
    assert isinstance(result, tuple) and result[0] == "modal"
    assert isinstance(result[1], QuestCardModal)


def test_quest_setup_card_modal_button_is_null_for_custom_game():
    # No preload_scenario call: game.stages == [] (custom/manual quest). The
    # quest_setup view itself assumes a loaded scenario elsewhere in its draw
    # path (not reachable via normal nav without one), so exercise on_button
    # directly with a synthetic button rather than via draw()+_find().
    from ui.widgets import Button
    hw, pal, game, screen = _setup("quest_setup")
    result = screen.on_button(Button(("open_card_modal",), 0, 0, 1, 1), game)
    assert result is None


def test_quest_setup_shows_stage_and_setup_text():
    hw, pal, game, screen = _setup("quest_setup")
    game.preload_scenario(_QS_SCN, _QS_STAGES)
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    assert "STAGE 1A" in texts
    assert any("Flies and Spiders" in t for t in texts)
    assert any("Setup: do the thing." in t for t in texts)
    assert any("Flip to Side B" in t and "8 qp" in t for t in texts)


def test_quest_setup_no_setup_text_shows_fallback():
    hw, pal, game, screen = _setup("quest_setup")
    stages = [{"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "x", "text": None},
                  {"side": "B", "name": "x", "text": None}]}]}]
    game.preload_scenario(_QS_SCN, stages)
    screen.draw(hw, game, pal)
    assert any("No setup instructions for this stage." in t for t in _texts(hw))
