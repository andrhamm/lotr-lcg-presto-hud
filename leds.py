"""LED color logic + driver for the 7 onboard SK6812 LEDs.

The color-mapping helpers are pure (host-testable). apply()/flash() take a
hardware object exposing set_led_rgb(i, r, g, b) so they work with the real
Presto or the test shim.
"""

import phases

NUM_LEDS = 7

GREEN = (20, 160, 40)
AMBER = (200, 140, 20)
RED = (200, 40, 30)

# thresholds match the UI: green < 20, amber 20-34, red >= 35
AMBER_AT = 20
RED_AT = 35


def threat_color(threat):
    if threat >= RED_AT:
        return RED
    if threat >= AMBER_AT:
        return AMBER
    return GREEN


def danger_color(players):
    """Color for the highest living-player threat (green if all eliminated)."""
    living = [p["threat"] for p in players if not p["eliminated"]]
    if not living:
        return GREEN
    return threat_color(max(living))


def phase_color(step_id):
    """The LED color for the phase that owns a given step."""
    ph = phases.step(step_id)["phase"]
    return phases.phase(ph)["color"]


def apply(hw, color):
    """Set all LEDs to a single color. hw exposes set_led(i, color)."""
    for i in range(NUM_LEDS):
        hw.set_led(i, color)


def scale(color, brightness):
    """Scale an (r, g, b) color by brightness percent (0-100)."""
    return (color[0] * brightness // 100,
            color[1] * brightness // 100,
            color[2] * brightness // 100)


SCENES = ["phase", "danger", "torch", "off"]
SCENE_LABELS = {"phase": "Phase + danger", "danger": "Danger only",
                "torch": "Torchlight", "off": "Off"}

_TORCH_BASE = (200, 110, 25)


def scene_colors(scene, summary, tick=0):
    """Colors for the 7 LEDs. summary = {"step": id, "players": [...]}.
    Pure + deterministic (torch flicker keys off tick) so it is host-testable.
    """
    if scene == "off":
        return [(0, 0, 0)] * NUM_LEDS
    if scene == "danger":
        return [danger_color(summary["players"])] * NUM_LEDS
    if scene == "torch":
        out = []
        for i in range(NUM_LEDS):
            # cheap deterministic flicker: -30..+9 percent-ish per led/tick
            n = (tick * 2654435761 + i * 40503) & 0xffff
            f = 70 + (n % 40)  # 70..109
            out.append((min(255, _TORCH_BASE[0] * f // 100),
                        min(255, _TORCH_BASE[1] * f // 100),
                        min(255, _TORCH_BASE[2] * f // 100)))
        return out
    # "phase": phase color ring, danger color in the center
    ph = phase_color(summary["step"])
    dg = danger_color(summary["players"])
    return [dg if i == NUM_LEDS // 2 else ph for i in range(NUM_LEDS)]


def apply_scene(hw, scene, summary, brightness=100, tick=0):
    colors = scene_colors(scene, summary, tick)
    for i in range(NUM_LEDS):
        hw.set_led(i, scale(colors[i], brightness))
