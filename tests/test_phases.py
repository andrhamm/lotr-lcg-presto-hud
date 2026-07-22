import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phases


def test_step_order_matches_steps_list():
    assert phases.STEP_ORDER == [s["id"] for s in phases.STEPS]


def test_full_round_has_28_steps():
    assert len(phases.STEPS) == 28


def test_every_step_references_a_known_phase():
    phase_ids = {p["id"] for p in phases.PHASES}
    for s in phases.STEPS:
        assert s["phase"] in phase_ids


def test_quest_resolution_step_opens_action_window():
    assert phases.step("3.4")["action_window"] is True


def test_deal_shadow_cards_step_has_no_action_window():
    assert phases.step("6.2")["action_window"] is False


def test_first_and_last_steps():
    assert phases.STEP_ORDER[0] == "0.0"
    assert phases.STEP_ORDER[-1] == "8.0"
