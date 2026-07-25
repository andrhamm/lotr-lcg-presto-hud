---
title: Qwiic Audio + Haptics — Feasibility Report
type: feasibility-report
tags:
  - lotr-lcg/hardware
  - lotr-lcg/feasibility
  - qwiic
related:
  - "[[roadmap]]"
  - "[[2026-07-24-wireless-camera-feasibility]]"
---

# Qwiic Audio + Haptics — Feasibility Report

Status: feasibility research (2026-07-24), no implementation. Source:
[[TODO]] Ideas — *"could we add audio by taking advantage of the Qwiic port
and something like this (with a small speaker(s))
https://www.adafruit.com/product/6258"*, sub-bullet *"daisy chain qwiic to
add haptic feedback driver?"*. Revisits the original project plan's call to
rule out on-device audio (piezo = beep-quality only; Bluetooth A2DP not
viable in MicroPython) now that Presto has a Qwiic/STEMMA QT port.

> [!important] Verdict
> **Audio: not feasible as scoped.** The linked part is not audio hardware,
> Qwiic physically cannot carry the interface (I2S) real digital-audio DACs
> need, and Presto has no spare GPIO to wire I2S directly instead. **Haptics:
> feasible.** A Qwiic haptic driver (DRV2605L or DA7280) is a real, cheap,
> I2C-native part that daisy-chains cleanly off the same port. Recommendation:
> ship haptics; drop audio-via-Qwiic unless a current-production
> self-contained I2C audio-trigger module turns up.

## What was verified

### The linked part is not audio hardware
- **Adafruit product 6258 is the "DAC6578 Breakout — 8 x Channel 10-bit I2C
  DAC"** — an 8-channel, 10-bit, I2C-controlled *voltage* DAC (Texas
  Instruments DAC6578), STEMMA QT/Qwiic connector, 2.7–5.5V, "0.13mA/ch at
  5V", **$14.95**. [Adafruit product page](https://www.adafruit.com/product/6258) ·
  [Adafruit blog announcement](https://blog.adafruit.com/2025/03/06/new-product-adafruit-dac6578-breakout-8-x-channel-10-bit-i2c-dac/)
- Nothing on the product page or announcement mentions audio, an amplifier,
  or a speaker driver. This chip is meant for slow analog *reference/control*
  voltages (e.g. a threshold or calibration signal), not sample-rate signal
  generation, and there's no amplifier stage onboard to drive a speaker even
  if it could output audio-rate samples.
- **Conclusion: the specific part the idea names would not do what the idea
  describes, independent of any Qwiic bandwidth question.**

### Qwiic/STEMMA QT is I2C-only — it cannot carry digital audio
- Every STEMMA QT / Qwiic product checked in this research (DAC6578,
  DRV2605L, SparkFun Qwiic Speaker Amp, SparkFun Qwiic MP3 Trigger)
  consistently describes the same 4-wire JST-SH interface: **3V3, GND, SDA,
  SCL** — I2C, nothing else.
- Real digital-audio DACs and amps use **I2S** for the actual sample stream
  (a separate clock/word-select/data bus), with I2C — where present at all —
  used only for control registers. Confirmed by every I2S-audio part checked:
  [Adafruit PCM5102 I2S DAC](https://www.adafruit.com/product/6250),
  [Adafruit PCM5122 I2S DAC](https://www.adafruit.com/product/6421),
  [DFRobot MAX98357 I2S Amplifier Module](https://www.dfrobot.com/product-2614.html).
  None of these are offered over a STEMMA QT/Qwiic connector — I2S isn't part
  of that standard.
- *Engineering estimate, not a single-source citation:* I2C's raw clock rate
  (100kHz–1MHz) is nonzero bandwidth, but no product found in this research
  streams PCM audio samples over I2C. Everything either (a) is control-only
  with the actual audio arriving over separate analog/I2S pins, or (b) decodes
  and plays back audio *on the peripheral itself*, with I2C carrying only
  short trigger commands (see below). Bit-banging a continuous 44.1kHz stereo
  stream over an I2C bus that also needs to stay responsive for other Qwiic
  peripherals is impractical, not merely undocumented.

### Presto has no spare GPIO to wire I2S directly
- Presto exposes exactly **one** external connector for peripherals: the
  Qw/ST (Qwiic/STEMMA QT) port — plus USB-C, a 2-pin JST-PH battery input,
  and a microSD slot, none of which are general-purpose GPIO.
  [thepihut.com/products/pimoroni-presto](https://thepihut.com/products/pimoroni-presto)
- Confirmed by a real owner on Pimoroni's own support forum, in a thread
  specifically about the piezo being too quiet: *"I miss not having at least
  one GPIO pin I could use as I want — a string of Neopixels, a button, a
  potentiometer."* [PRESTO Sounds — Pimoroni forum, page 1](https://forums.pimoroni.com/t/presto-sounds/27025)
- That means there is no way to run I2S's extra lines (BCLK/LRCLK/DIN) from
  the RP2350B to an external DAC — the only external electrical path off the
  board is the 4-wire I2C bus.

### The one architecture that could work is a discontinued part
- **SparkFun Qwiic MP3 Trigger** ($19.95) decoded and amplified audio
  onboard (TI TPA2005D1, 1.4W class-D, microSD storage) and took only short
  I2C trigger commands from the host — e.g. `0x01 <track#>` to play a file,
  `0x07 <level>` for volume, default address `0x37`. This is exactly the
  architecture that fits Qwiic's I2C-only limit: the bandwidth-heavy work
  (decode + amplify) happens on the peripheral, not over the wire.
  [Hookup guide](https://learn.sparkfun.com/tutorials/qwiic-mp3-trigger-hookup-guide/all)
- **It is discontinued.** *"This product has been retired from our catalog
  and is no longer for sale."*
  [SparkFun product page](https://www.sparkfun.com/sparkfun-qwiic-mp3-trigger-dev-19030.html)
- This research did not find a current-production equivalent (self-contained,
  I2C-triggered, onboard-decode-and-amplify audio module). Absence of
  evidence in a bounded search isn't proof none exists — this is flagged as
  an open gap, not a closed door (see Recommended next step).
- Two adjacent, currently-sold products confirm the *other* pattern
  (I2C-configured amp needing a separately-supplied analog audio signal) and
  don't close the gap. The
  [SparkFun Qwiic Speaker Amp](https://www.sparkfun.com/sparkfun-qwiic-speaker-amp.html)
  ($15.50, TI TPA2016D2) states plainly that I2C controls only "Volume
  Control" and "Dynamic Range Compression (DRC)" — the audio itself arrives
  as an analog signal on a 3.5mm jack or screw terminals, which Presto has no
  way to generate (no DAC output, no spare PWM-capable GPIO). The
  [Adafruit TPA2016 I2C amp](https://www.adafruit.com/product/1712) is the
  same category.

### Haptics: a real, current, cheap part — and it daisy-chains
- **Adafruit DRV2605L Haptic Motor Controller** — STEMMA QT/Qwiic, I2C,
  **$7.95**. [Product page](https://www.adafruit.com/product/2305)
  Default 7-bit I2C address **0x5A**, per the TI datasheet.
  [DRV2605L datasheet PDF (hosted by SparkFun)](https://cdn.sparkfun.com/datasheets/Robotics/Haptic_Motor_Driver_DRV2605L.pdf)
  Drives LRA or ERM vibration motors and ships with ~123 built-in effect
  waveforms (clicks, ramps, pulses) triggered by writing a short sequence to
  onboard registers — a genuinely low-bandwidth I2C job, unlike audio.
- Alternative: **SparkFun Qwiic Haptic Driver – DA7280**, **$11.50**,
  includes its own small LRA motor onboard, controllable via I2C, PWM, or
  GPIO. [Product page](https://www.sparkfun.com/sparkfun-qwiic-haptic-driver-da7280.html)
- **Daisy-chaining is confirmed to work on this exact port.** Pimoroni's own
  getting-started guide, describing two Qwiic sensors plugged in together:
  *"Both devices connect via the I2C bus (all aboard!) and have different I2C
  addresses, so you can have them both connected at the same time if you
  want."* [Getting Started with Presto](https://learn.pimoroni.com/article/getting-started-with-presto)
  A DRV2605L at `0x5A` is very unlikely to collide with anything else this
  project would put on the bus — nothing is on it today.
- **MicroPython support is not official for either part.** Adafruit ships
  Arduino + CircuitPython drivers for the DRV2605L — not MicroPython
  (CircuitPython and MicroPython are different, incompatible runtimes; the
  CircuitPython library will not run as-is on Presto's firmware).
  [Adafruit product page](https://www.adafruit.com/product/2305)
  A community MicroPython port already exists, though:
  [VynDragon/Adafruit_MicroPython_DRV2605](https://github.com/VynDragon/Adafruit_MicroPython_DRV2605)
  ("Micropython port of CircuitPython module for the DRV2605 haptic feedback
  motor driver"). The DA7280 has only an
  [Arduino library](https://github.com/sparkfun/Qwiic_Haptic_Driver_DA7280) —
  no MicroPython port was found; it would need to be written from the
  register map.

### Presto's I2C bus binding for Qw/ST is not publicly documented
- Presto's own MicroPython API reference lists display, touch, LED, and
  wireless (`presto.connect()`) methods — **no `presto.i2c` or equivalent
  accessor.** [pimoroni/presto docs/presto.md](https://github.com/pimoroni/presto/blob/main/docs/presto.md)
- The piezo buzzer is driven by a plain `machine.PWM` on a GPIO pin (a small
  `Buzzer` class in `presto.py`, `self.pwm = PWM(Pin(pin))`), unrelated to
  I2C. [pimoroni/presto modules/py_frozen/presto.py](https://github.com/pimoroni/presto/blob/main/modules/py_frozen/presto.py)
- This research could not confirm which `machine.I2C` bus id / SDA-SCL pin
  pair the Qw/ST connector is wired to. Pimoroni's getting-started guide
  shows working Qwiic-sensor examples, but the fetched content didn't include
  the literal `machine.I2C(...)` construction line. **This is the first
  thing to resolve in a spike** (below) — very likely a five-minute REPL
  check once hardware is in hand, not a research blocker, but flagged so it
  isn't silently assumed.

### The original plan's Bluetooth-audio ruling still holds
- MicroPython's Bluetooth module implements **BLE only** (Central,
  Peripheral, Broadcaster, Observer roles) — no Classic Bluetooth, no A2DP.
  [MicroPython bluetooth docs](https://docs.micropython.org/en/latest/library/ubluetooth.html)
  A2DP is a Classic-Bluetooth audio profile; it isn't reachable from
  MicroPython on this chip regardless of the radio's own capability.
- Presto's wireless chip is the **Infineon CYW43439** (via the Raspberry Pi
  RM2 module) — WiFi 4 (802.11b/g/n, 2.4GHz only) + Bluetooth 5.4.
  [thepihut.com/products/pimoroni-presto](https://thepihut.com/products/pimoroni-presto)
- Piezo quality is confirmed weak in practice, not just on paper: a Presto
  owner reported the onboard buzzer was barely audible ("requiring hearing
  aids and close listening") running code that was loud on a different
  RP2040 board; Pimoroni staff (ZodiusInfuser) reproduced the quiet output
  and confirmed it wasn't a code bug. The community's best fix for *louder*
  sound via the Qwiic port was an I2C GPIO-expander driving an external
  **passive buzzer via PWM** — still a louder monophonic beep, not digital
  audio. [PRESTO Sounds, page 1](https://forums.pimoroni.com/t/presto-sounds/27025) ·
  [page 2](https://forums.pimoroni.com/t/presto-sounds/27025?page=2)

## The concrete option: haptics only

| Part | Price | Interface | Notes |
|---|---|---|---|
| [Adafruit DRV2605L](https://www.adafruit.com/product/2305) | $7.95 | STEMMA QT/Qwiic, I2C @ 0x5A | Recommended — cheaper, has a MicroPython port already |
| [SparkFun Qwiic Haptic Driver DA7280](https://www.sparkfun.com/sparkfun-qwiic-haptic-driver-da7280.html) | $11.50 | Qwiic, I2C | Includes its own LRA motor; no MicroPython port found — would need one written |
| [STEMMA QT / Qwiic cable, 100mm](https://www.adafruit.com/product/4210) | $0.95 | JST-SH 4-pin | Presto ships with a compatible port |

**Wiring:** plug-and-play — one JST-SH cable from Presto's Qw/ST port to the
breakout's Qw/ST-in port. No soldering.

**Power budget:** DRV2605L is 3–5V compliant; standing current is sub-mA
idle, with tens of mA drawn only for the ~50–200ms an effect actually plays.
Not a meaningful load on Presto's own supply.

**Firmware work:**
1. Resolve the Qw/ST I2C bus/pin binding (spike, below).
2. Port/adapt VynDragon's MicroPython DRV2605 driver (or hand-roll ~30 lines
   against the documented register map — `MODE`, `WAVESEQ1`, `GO`) into a
   small `haptics.py`, following this repo's `hardware.py` thin-wrapper
   pattern.
3. Pick 3–5 event hooks worth a buzz: elimination confirm, threat crossing a
   danger threshold, phase-advance confirm, maybe end-of-round. Map each to
   a built-in DRV2605L effect ID (e.g. "Strong Click", "Double Click").
4. Guard it behind a Settings toggle — this app already has an LED-scene
   settings tile to follow as a pattern (`ui/screen_settings.py`).

**Web-twin work:** none needed for real parity — a vibration motor has no
browser equivalent. The nearest analog, `navigator.vibrate()` on supporting
mobile browsers, is a fundamentally different, optional, cosmetic gesture,
not a hardware port. Recommend treating haptics as a firmware-only feature
and noting the exception explicitly (this is a case where Iron Rule #1's
web-first mandate doesn't apply, not a violation of it).

## Risks and blockers

- **Audio-via-Qwiic: no known current part closes the loop.** This cannot
  ship today without either (a) finding a live self-contained
  I2C-audio-trigger module (unverified to exist), or (b) a Presto hardware
  revision exposing spare GPIO for real I2S wiring (outside this project's
  control). Recommend dropping it rather than leaving it open-ended.
- **Haptics' I2C bus binding is unverified.** Low risk — very likely a
  standard `machine.I2C` on fixed pins, following Pimoroni's usual pattern on
  their other boards — but must be confirmed on real hardware before writing
  the driver.
- **DA7280 has no MicroPython library.** If the DRV2605L path hits some
  unforeseen issue, the fallback part means more from-scratch driver work,
  not zero.
- No haptic-specific display/UI risk surfaced — this is the lowest-risk
  hardware addition surveyed across both feasibility reports written today
  (see [[2026-07-24-wireless-camera-feasibility|the camera report]]).

## Recommended next step

**Haptics — spike, ~$9, one afternoon.** Buy one
[DRV2605L STEMMA QT breakout](https://www.adafruit.com/product/2305) ($7.95)
and one [Qwiic cable](https://www.adafruit.com/product/4210) ($0.95) if one
isn't already on hand. Definition of done:
1. Plug into Presto's Qw/ST port.
2. From a MicroPython REPL, find the working `machine.I2C(id, sda=, scl=)`
   construction for the port (try the obvious bus/pin candidates; check
   Pimoroni's C++ source if REPL guess-and-check doesn't land quickly).
3. `i2c.scan()` returns `0x5A`.
4. Port VynDragon's MicroPython DRV2605 driver (or hand-roll from the
   register map), trigger effect ID 14 ("Strong Click"), confirm it buzzes.
5. Confirm touch-polling / display redraw don't visibly stall while the I2C
   transaction is in flight (expected sub-millisecond; sanity check, not
   expected to be a real problem).

If all five pass, this is a small, well-scoped follow-on: write it as a
normal plan (`haptics.py` + a handful of event hooks + a Settings toggle)
once the spike closes the bus-binding unknown.

**Audio — do not spike hardware yet.** Spend at most 30 minutes searching for
a current-production, self-contained, I2C-triggered audio module (a
discontinued-successor to the
[SparkFun Qwiic MP3 Trigger](https://www.sparkfun.com/sparkfun-qwiic-mp3-trigger-dev-19030.html) —
check SparkFun/Adafruit/DFRobot new-product feeds, Tindie, and general
search). If nothing turns up, close the [[TODO]] Ideas item as **dropped**
with a one-line reason (wrong part linked; no I2S path on Qwiic; no spare
GPIO on Presto; no live self-contained I2C audio module found), so it
doesn't resurface without new information. Keep Spotify Connect (already on
the [[roadmap]] as M3) as the sanctioned path to real music/audio — it was
the right call in the original plan and nothing found here changes that.
