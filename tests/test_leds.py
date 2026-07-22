import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import leds


def test_threat_color_green_when_low():
    assert leds.threat_color(0) == leds.GREEN
    assert leds.threat_color(19) == leds.GREEN


def test_threat_color_amber_in_mid_band():
    assert leds.threat_color(20) == leds.AMBER
    assert leds.threat_color(34) == leds.AMBER


def test_threat_color_red_when_high():
    assert leds.threat_color(35) == leds.RED
    assert leds.threat_color(50) == leds.RED


def test_danger_level_uses_highest_living_threat():
    players = [
        {"threat": 14, "eliminated": False},
        {"threat": 41, "eliminated": False},
        {"threat": 60, "eliminated": True},   # eliminated ignored
    ]
    assert leds.danger_color(players) == leds.RED


def test_danger_level_ignores_all_eliminated():
    players = [{"threat": 60, "eliminated": True}]
    assert leds.danger_color(players) == leds.GREEN


def test_apply_sets_all_seven_leds_via_hardware_interface():
    from tests.fake_hardware import FakeHardware
    hw = FakeHardware()
    leds.apply(hw, leds.RED)
    assert hw.leds == [leds.RED] * 7


def test_scale_brightness():
    assert leds.scale((200, 100, 50), 100) == (200, 100, 50)
    assert leds.scale((200, 100, 50), 50) == (100, 50, 25)
    assert leds.scale((200, 100, 50), 0) == (0, 0, 0)


def _summary():
    return {"step": "3.4", "players": [{"threat": 41, "eliminated": False}]}


def test_scene_off_is_black():
    assert leds.scene_colors("off", _summary(), 0) == [(0, 0, 0)] * 7


def test_scene_danger_uses_threat_color_everywhere():
    colors = leds.scene_colors("danger", _summary(), 0)
    assert colors == [leds.RED] * 7


def test_scene_phase_has_danger_center():
    colors = leds.scene_colors("phase", _summary(), 0)
    assert colors[3] == leds.RED           # center = danger
    assert colors[0] == colors[6] != colors[3]


def test_scene_torch_flickers_deterministically():
    a = leds.scene_colors("torch", _summary(), tick=1)
    b = leds.scene_colors("torch", _summary(), tick=2)
    assert a != b                          # varies over time
    assert a == leds.scene_colors("torch", _summary(), tick=1)  # deterministic
