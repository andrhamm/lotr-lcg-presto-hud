import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState


# -- defaults --------------------------------------------------------------

def test_new_game_progress_defaults():
    g = GameState()
    assert g.quest["stage_n"] == 1
    assert g.quest["side"] == "A"
    assert g.quest["progress"] == 0
    assert not g.active_locations
    assert g.side_quests == []


def test_quest_label():
    g = GameState()
    g.quest["stage_n"] = 2
    g.quest["side"] = "B"
    assert g.quest_label() == "2B"


# -- auto_split ------------------------------------------------------------

def test_auto_split_with_no_location_puts_all_on_quest():
    g = GameState()
    g.quest["points"] = 10
    assert not g.active_locations
    alloc = g.auto_split(5)
    assert alloc["locations"] == []      # no seat, so no row to fill
    assert alloc["quest"] == 5


def test_auto_split_fills_location_first_then_overflows_to_quest():
    g = GameState()
    g.quest["points"] = 10
    g.active_locations = [{"points": 3, "progress": 1}]  # 2 room left
    alloc = g.auto_split(5)
    assert alloc["locations"][0] == 2
    assert alloc["quest"] == 3


def test_auto_split_caps_quest_at_its_points_discarding_overflow():
    g = GameState()
    g.quest["points"] = 6
    g.quest["progress"] = 5              # 1 room left on the quest
    g.active_locations = [{"points": 3, "progress": 1}]  # 2 room left
    alloc = g.auto_split(7)
    assert alloc["locations"][0] == 2       # location fills first
    assert alloc["quest"] == 1          # quest capped at its room
    # remaining 4 is discarded (budget - location - quest)


def test_auto_split_smaller_than_location_room_stays_on_location():
    g = GameState()
    g.active_locations = [{"points": 4, "progress": 0}]
    alloc = g.auto_split(2)
    assert alloc["locations"][0] == 2
    assert alloc["quest"] == 0


# -- place_progress --------------------------------------------------------

def test_place_progress_on_quest_only():
    g = GameState()
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 6}
    completed = g.place_progress({"locations": [0], "quest": 1, "side_quests": []})
    assert g.quest["progress"] == 7
    assert completed == []


def test_place_progress_explores_location_and_clears_it():
    g = GameState()
    g.active_locations = [{"points": 3, "progress": 2}]
    completed = g.place_progress({"locations": [1], "quest": 0, "side_quests": []})
    assert not g.active_locations
    assert "Active Location explored" in completed


def test_place_progress_advances_quest_stage_on_reaching_points():
    g = GameState()
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 6}
    completed = g.place_progress({"locations": [0], "quest": 2, "side_quests": []})
    assert g.quest["stage_n"] == 3
    assert g.quest["side"] == "A"
    assert g.quest["progress"] == 0
    assert any("cleared" in c for c in completed)


def test_place_progress_advances_side_a_to_b_first():
    g = GameState()
    g.quest = {"stage_n": 1, "side": "A", "points": 2, "progress": 0}
    g.place_progress({"locations": [0], "quest": 2, "side_quests": []})
    assert g.quest["stage_n"] == 1
    assert g.quest["side"] == "B"


def test_place_progress_completes_and_removes_side_quest():
    g = GameState()
    g.side_quests = [{"points": 5, "progress": 3}]
    completed = g.place_progress({"locations": [0], "quest": 0, "side_quests": [2]})
    assert g.side_quests == []
    assert any("Side quest" in c for c in completed)


def test_place_progress_zero_point_quest_does_not_advance_forever():
    g = GameState()
    g.quest = {"stage_n": 1, "side": "A", "points": 0, "progress": 0}
    completed = g.place_progress({"locations": [0], "quest": 3, "side_quests": []})
    # points==0 must not loop forever; progress just accumulates
    assert g.quest["stage_n"] == 1
    assert completed == []


# -- resolve_quest ---------------------------------------------------------

def test_resolve_quest_success_returns_budget_without_placing():
    g = GameState()
    g.quest = {"stage_n": 1, "side": "B", "points": 8, "progress": 0}
    result = g.resolve_quest(willpower=11, staging=7)
    assert result["outcome"] == "success"
    assert result["budget"] == 4
    assert g.quest["progress"] == 0  # not applied yet — modal allocates


def test_resolve_quest_tie_is_no_change():
    g = GameState()
    result = g.resolve_quest(willpower=7, staging=7)
    assert result["outcome"] == "tie"
    for p in g.players:
        assert p.threat == 0


def test_resolve_quest_failure_raises_all_living_threat_by_shortfall():
    g = GameState()
    g.adjust_threat(0, 10)
    g.adjust_threat(1, 51)  # eliminated, must be skipped
    result = g.resolve_quest(willpower=4, staging=7)
    assert result["outcome"] == "fail"
    assert result["threat"] == 3
    assert g.players[0].threat == 13
    assert g.players[1].threat == 51

# -- two active locations ---------------------------------------------------
# Rules Reference, "Active Location": "There can only be one active location at
# a time." FIVE printed cards override that in their own text - Fisherman's
# Dock, The Gates of Moria, Ruined Tower, Dark Passages and ALeP's Widfast all
# say "There are now 2 active locations" or "There can be 2 active locations"
# (checked against docs/data/, 2026-07-30). Everything below is about that case.

def test_travel_appends_rather_than_replacing():
    g = GameState()
    g.travel_to(3, 1, "First")
    g.travel_to(4, 2, "Second")
    assert [l["name"] for l in g.active_locations] == ["First", "Second"]


def test_change_location_replaces_only_the_named_seat():
    # Discarding the other one alongside it would silently drop its progress.
    g = GameState()
    g.travel_to(3, 1, "First")
    g.travel_to(4, 2, "Second")
    g.active_locations[0]["progress"] = 2
    g.change_location(5, 0, "Swapped", idx=1)
    assert [l["name"] for l in g.active_locations] == ["First", "Swapped"]
    assert g.active_locations[0]["progress"] == 2


def test_auto_split_fills_the_seats_in_list_order_then_the_quest():
    g = GameState()
    g.quest["points"] = 10
    g.active_locations = [{"points": 3, "progress": 1},    # 2 room
                          {"points": 2, "progress": 0}]    # 2 room
    assert g.auto_split(7) == {"locations": [2, 2], "quest": 3, "side_quests": []}


def test_place_progress_explores_every_seat_that_fills():
    g = GameState()
    g.active_locations = [{"points": 3, "progress": 2},
                          {"points": 2, "progress": 1}]
    g.place_progress({"locations": [1, 1], "quest": 0, "side_quests": []})
    assert g.active_locations == []


def test_place_progress_credits_the_right_seat_when_only_one_fills():
    # Removing a seat shifts the ones after it, which is why placement runs
    # back to front. Going forward credited the wrong card here.
    g = GameState()
    g.active_locations = [{"points": 3, "progress": 2},
                          {"points": 9, "progress": 0}]
    g.place_progress({"locations": [1, 4], "quest": 0, "side_quests": []})
    assert len(g.active_locations) == 1
    assert g.active_locations[0]["points"] == 9
    assert g.active_locations[0]["progress"] == 4


def test_location_overflow_sums_the_excess_from_both_seats():
    # RR p.15: excess beyond a location's quest points flows on to the quest.
    g = GameState()
    g.active_locations = [{"points": 3, "progress": 5},    # 2 excess
                          {"points": 2, "progress": 4}]    # 2 excess
    assert g.resolve_location_overflow() == 4
    assert g.quest["progress"] == 4
    assert g.active_locations == []


def test_needs_resolution_sees_a_full_second_seat():
    g = GameState()
    g.quest["points"] = 10
    g.active_locations = [{"points": 3, "progress": 0},
                          {"points": 2, "progress": 2}]
    assert g.needs_resolution() is True


def test_quest_preview_room_counts_every_seat():
    g = GameState()
    g.quest["points"] = 5
    g.active_locations = [{"points": 3, "progress": 1},
                          {"points": 4, "progress": 0}]
    _, _, room = g.quest_preview()
    assert room == 5 + 2 + 4
