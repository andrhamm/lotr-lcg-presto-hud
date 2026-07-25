---
title: Wireless Board-State Camera — Feasibility Report
type: feasibility-report
tags:
  - lotr-lcg/hardware
  - lotr-lcg/feasibility
  - wifi
related:
  - "[[roadmap]]"
  - "[[2026-07-24-qwiic-audio-haptics-feasibility]]"
---

# Wireless Board-State Camera — Feasibility Report

Status: feasibility research (2026-07-24), no implementation. Source:
[[TODO]] Ideas — *"how could a basic wireless camera be incorporated? low
FPS / just occasional snapshots of the board state at the table. something
easy to build with raspberry pi / xioa camera, battery just adequate for a
single game session. 3d printed enclosure with 1/4-20 mount for gorillapod or
similar. communicates with the presto / web app over wifi, images saved."*

> [!important] Verdict
> **Feasible with caveats.** Cheap, well-documented camera hardware exists
> (recommend the Seeed XIAO ESP32S3 Sense, $13.99) and periodic-snapshot-over-
> WiFi is a well-trodden pattern with mature examples. The hard part isn't
> the camera — it's that Presto has **no WiFi stack yet** (this becomes a
> prerequisite, not an add-on), and the **web twin cannot display the images
> at all** as currently deployed (GitHub Pages serves HTTPS; browsers block
> fetching plain-HTTP images from a LAN camera and don't fall back). This
> ships firmware-first, breaking the project's usual web-first rule by
> necessity, not by choice — that exception should be a decision, not a
> surprise.

## What was verified

### Presto side: no networking exists yet
- Zero hits for `socket`, `urequests`, `network`, or WiFi anywhere in this
  repo's firmware modules outside `tests/` (checked directly against the
  source tree). [[roadmap|ROADMAP.md]] lists **"M2 — Connectivity: WiFi
  provisioning"** as **Planned**, not shipped.
- This means the camera feature's real first milestone is "Presto can join a
  WiFi network and make an HTTP request at all." Camera-specific work is the
  *second* milestone, layered on M2 — not independent scope.

### The web twin cannot load images from a LAN camera as deployed
- The web twin is served over **HTTPS** (GitHub Pages). Browsers auto-upgrade
  image/media "mixed content" requests from HTTP→HTTPS and do **not** fall
  back to plain HTTP on failure: *"browsers should automatically upgrade
  requests for upgradable content from HTTP to HTTPS, and block requests for
  the blockable content... For images specifically, browsers mitigate the
  risks of mixed content by auto-upgrading image, video, and audio mixed
  content requests from HTTP to HTTPS."*
  [MDN: Mixed content](https://developer.mozilla.org/en-US/docs/Web/Security/Mixed_content)
- A battery-powered camera pod has no practical way to serve HTTPS with a
  browser-trusted certificate at a bare LAN IP — self-signed certs work
  technically but need a manual per-device browser trust step, which is real
  friction, not a clean fix.
- **This is a hard constraint on the web twin specifically**, not on the
  firmware — native MicroPython code has no browser sandbox and can fetch
  plain HTTP freely. It directly cuts against this repo's Iron Rule #1 ("web
  first, then firmware... a change that lands in one and not the other is
  unfinished work"). Camera viewing is a case where firmware-only is the
  *correct* answer, not a lazy one, but it should be written down as a
  deliberate exception rather than discovered mid-implementation.

### Camera hardware options compared

| | Raspberry Pi Zero 2 W + Camera Module 3 | Seeed XIAO ESP32S3 Sense | ESP32-CAM (AI-Thinker) |
|---|---|---|---|
| Price | $15 + $25–35 = **~$40–50** | **$13.99** (camera + mic + SD included) | **~$7–10** |
| Compute | Quad Cortex-A53 @1GHz, 512MB RAM, full Linux | Dual ESP32-S3 @240MHz, 8MB PSRAM | ESP32 (older Xtensa LX6), 4MB PSRAM |
| Camera sensor | 12MP Sony IMX708, autofocus, HDR | OV2640, 1600×1200 (2MP), fixed focus | OV2640, 1600×1200 (2MP), fixed focus |
| Onboard battery charging | No — needs an add-on (e.g. PiSugar) | **Yes**, onboard LiPo charge management | No — needs an external charger module |
| Sleep power | Full Linux boot (~12s stock); not built for rapid duty-cycling | **14µA deep sleep** | 6mA @5V deep sleep |
| Active power | ~300–400mA @5V (~1.5–2W) | ~0.7W avg streaming, ~1.7W peak at shutter | Not separately benchmarked; same sensor class as XIAO |
| MicroPython + camera | N/A — runs Linux, not MicroPython | **Official Seeed guide**, incl. a WiFi streaming example | Community-only fork, older MicroPython base |

Sources: Pi Zero 2 W price/specs —
[raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/);
Camera Module 3 price —
[raspberrypi.com](https://www.raspberrypi.com/products/camera-module-3/)
("Available from $25 with your choice of standard and wide lenses, with or
without an infrared filter"); Pi Zero 2 W active power — real-world
bird-camera build, [curiousscientist.tech](https://curiousscientist.tech/blog/bird-camera-raspberry-pi-zero-2-w)
("streaming: around 400mA... idle: about 300mA"), corroborated by
[CNX Software's power deep-dive](https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/);
boot time —
[Hackster.io](https://www.hackster.io/news/manawyrm-digs-deep-into-raspberry-pi-power-optimization-to-slash-the-boot-time-to-just-3-5-seconds-40bcbb427189)
(3.5s heavily optimized) and
[Raspberry Pi forums](https://forums.raspberrypi.com/viewtopic.php?t=339214)
(~12s stock); XIAO ESP32S3 Sense price/contents —
[Seeed's own store](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html);
XIAO power figures and MicroPython support —
[Seeed getting-started wiki](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
("Average power Consumption: 5V/~140mA" streaming at 640×480, "Deep Sleep
Mode: 14μA", "Arduino / MicroPython supported") and the
[Seeed MicroPython guide](https://wiki.seeedstudio.com/XIAO_ESP32S3_Micropython/);
ESP32-CAM price/specs —
[LCSC](https://www.lcsc.com/product-detail/C277946.html) and
[espboards.dev](https://www.espboards.dev/esp32/esp32cam/) ("Deep-sleep:
6mA@5V"); community MicroPython camera driver —
[lemariva/micropython-camera-driver](https://github.com/lemariva/micropython-camera-driver).

### Power / battery-life estimate (own arithmetic, clearly separated from the sourced figures above)
- **Pi Zero 2 W + Camera Module 3**, continuous ~1.75W average: a
  [PiSugar S](https://www.pisugar.com/products/pisugar-s-raspberry-pi-zero-battery)
  (1200mAh = 4.44Wh, ~$30–40 depending on retailer) → **~2.5 hours** at
  continuous draw — *under* the ~3-hour target. Clearing a full session needs
  either a larger pack (~2500–3000mAh) or camera/network sleep between shots;
  full Linux boot time (see table) makes rapid power-cycling awkward, so
  "stay awake, sleep the camera/radio between shots" is the more realistic
  pattern than "power off between shots" for this path.
- **XIAO ESP32S3 Sense**, duty-cycled (deep sleep between shots, ~0.7–1.7W
  only for the few seconds of each wake-shoot-send cycle): a 2000mAh
  (7.4Wh) 3.7V LiPo — e.g. [Adafruit #328](https://www.adafruit.com/product/328),
  $12.50 — comfortably clears 3 hours even *without* aggressive duty-cycling
  (7.4Wh ÷ ~0.7W ≈ 10.5h), and clears it with wide margin once duty-cycled.
  The XIAO Sense's battery connector pitch was **not confirmed** in this
  research — verify against the board before ordering a pack; Adafruit's
  packs use JST-PH 2.0mm, which small-form-factor boards don't always match.
- **ESP32-CAM**: same sensor, similar-class SoC to the XIAO — comparable
  order-of-magnitude battery math — but no onboard charge management, so add
  an external charger module (e.g. TP4056, ~$1–2) and more wiring to the BOM.

### Enclosure + mount
- **1/4-20 UNC** is the universal tripod / GorillaPod thread standard. Joby's
  own GorillaPod listings specify compatibility with "any... device with a
  1/4"-20 tripod mount."
  [Joby GripTight GorillaPod product listing](https://www.amazon.com/JOBY-GripTight-GorillaPod-Stand-Smartphones/dp/B009GHYMB6)
- **Heat-set brass 1/4-20 threaded inserts** are a standard, cheap way to add
  this thread to a 3D-printed part — installed with a soldering iron, no
  design complexity beyond a correctly-sized pilot hole. Camera-thread-specific
  inserts are sold off the shelf, e.g.
  [CNC Kitchen's 1/4"-20×6.4mm camera-thread insert](https://cnckitchen.store/products/heat-set-insert-1-4-20x6-4-camera-thread-short-version-20-pieces),
  generic packs on [Amazon](https://www.amazon.com/initeq-4-20-Threaded-Inserts-Printing/dp/B078458CZY),
  and [Prusa's own store](https://www.prusa3d.com/product/heat-set-inserts-1-4-20-pcs/).
- This repo already has a working FreeCAD macro workflow for 3D-printed
  Presto accessories (`presto_build.FCMacro`, `presto_shell.FCMacro` at repo
  root — see [[2026-07-23-presto-diffuser-shell-design]]) — enclosure design
  is inside the project's demonstrated capability already, not a new tool to
  learn.

### Image transfer pattern
- Two well-documented patterns exist for ESP32-class cameras: the camera
  **serves** a small HTTP endpoint the consumer polls (pull), or the camera
  **POSTs** the JPEG to a known server on a timer (push). Both are mature and
  widely tutorialized:
  [take-photo-and-display](https://randomnerdtutorials.com/esp32-cam-take-photo-display-web-server/),
  [HTTP POST to a server](https://randomnerdtutorials.com/esp32-cam-http-post-php-arduino/),
  [periodic capture loop, every N seconds](https://dev.to/azure/esp32cam-webserver-taking-photos-every-n-seconds-arduino-5bfk).
  These examples are Arduino-flavored, but the *pattern* (not the code)
  transfers directly to MicroPython.
- Seeed publishes an **official MicroPython** streaming example for the XIAO
  ESP32S3 Sense (`streaming_server.py` on the board, `streaming_client.py` on
  a PC) — confirming a MicroPython camera+WiFi path exists out of the box,
  not only via community forks.
  [Seeed MicroPython guide](https://wiki.seeedstudio.com/XIAO_ESP32S3_Micropython/)
  Community MicroPython camera support for the plain ESP32/ESP32-CAM family
  also exists, but is unofficial and pinned to an older MicroPython base
  (v1.21.0): [lemariva/micropython-camera-driver](https://github.com/lemariva/micropython-camera-driver).
- "Low FPS / occasional snapshots" — the TODO item's own framing — is *less*
  demanding than every tutorial above, all of which default to continuous
  streaming. A timer-triggered single-shot-then-sleep loop is simpler and
  more power-friendly than what's already proven to work.

### Displaying a photo on the Presto itself
- Pimoroni's PicoGraphics stack (the same one this repo's `ui/` already uses)
  ships a `jpegdec` MicroPython module with a documented decode-to-display
  API:
  ```python
  j = jpegdec.JPEG(display)
  j.open_file("filename.jpeg")
  j.decode(0, 0, jpegdec.JPEG_SCALE_FULL, dither=True)
  ```
  [pimoroni-pico picographics module](https://github.com/pimoroni/pimoroni-pico/tree/main/micropython/modules/picographics)
  This research could **not** confirm `jpegdec` is specifically included in
  Presto's frozen module set — the source above documents it for the wider
  PicoGraphics board family, not Presto by name. Treat as likely, not
  certain, and confirm in the spike.
- A decoded 480×480 RGB565 frame is ~450KB (480 × 480 × 2 bytes) — trivial
  against Presto's 8MB PSRAM, with or without a small thumbnail cache. Own
  estimate; not a real constraint either way.

### Radio coexistence
- Presto's WiFi/BT chip (Infineon CYW43439, 2.4GHz-only) would be doing
  ordinary client WiFi to talk to the camera pod, which has its own,
  independent radio — this is normal two-device WiFi coexistence on one
  network, not a shared-bus problem.
  [thepihut.com/products/pimoroni-presto](https://thepihut.com/products/pimoroni-presto)
- This repo has no Bluetooth usage today (checked directly against the
  source tree); Spotify Connect, per [[roadmap|ROADMAP.md]] M3, is
  WiFi/internet-based, not local BT. So CYW43439's combo WiFi/BT radio
  time-sharing isn't a live concern — flagged only as a latent constraint if
  BT is ever added later.

## The concrete option

**Recommend: Seeed XIAO ESP32S3 Sense** — lower price, official MicroPython
support, onboard battery charging, and dramatically better sleep power than
either alternative.

| Part | Price | Notes |
|---|---|---|
| [Seeed XIAO ESP32S3 Sense](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html) | $13.99 | Board + OV2640 camera + mic + SD slot |
| 3.7V LiPo, ~1200–2000mAh | ~$8–13 | Confirm connector pitch against the Sense's onboard connector before ordering |
| microSD card (optional, local backup) | ~$5 | Board has a slot; local save as a fallback if WiFi push fails |
| 3D-printed enclosure w/ 1/4-20 heat-set insert | ~$1 insert + filament | Repo already has the FreeCAD workflow |
| GorillaPod or equivalent | user-supplied | Standard 1/4-20 mount, confirmed compatible |

**What changes if Pi Zero 2 W is chosen instead:** meaningfully better image
quality (12MP autofocus vs. 2MP fixed-focus) and an easier software stack
(full Python + Flask/`picamera2` instead of MicroPython + a community/official
camera driver), at roughly 3× the parts cost, a tighter battery story (own
estimate above: ~2.5h from a 1200mAh PiSugar at continuous draw, and Linux's
boot time makes sleep/wake duty-cycling impractical), and no onboard charge
management (add a PiSugar-style HAT, ~$30–40 more). Choose this path only if
2MP proves genuinely insufficient in the spike — image-quality needs are
unverified against the actual use case ("occasional snapshots of the board
state"), and 1600×1200 is very likely enough for a phone-sized reference
photo of a card table.

**Wiring:** none — both camera and Presto are WiFi-networked; no physical
link between them.

**Firmware work (Presto side):**
1. WiFi client bring-up (shared prerequisite with roadmap M2 — this is not
   additive scope on top of a finished app, it's the project's first network
   feature).
2. HTTP client (`urequests` or raw `socket`) to pull the camera's latest
   snapshot, or a tiny server to receive pushed images.
3. `jpegdec`-based decode-to-display (confirm availability in the spike).
4. New screen: a simple gallery/viewer (thumbnail strip or "latest photo"
   view), wired into the header-nav pattern this repo already uses
   (`ui/screen_*.py` + `main.py` view routing).
5. Optional: save received JPEGs to the microSD the Presto already has a
   slot for.

**Camera-pod work:** flash Seeed's MicroPython+camera firmware, adapt the
official streaming example into a timer-triggered single-shot-then-sleep
loop (or an HTTP GET endpoint Presto polls), tune the interval for
"occasional."

**Web-twin work:** per the mixed-content finding above, the deployed web
twin cannot pull images from the camera directly. Options, none free: (a)
mark this firmware-only and record the exception in `CLAUDE.md`; (b) the
camera pod serves self-signed HTTPS and the user manually trusts the cert
once per device (real but bounded friction); (c) skip live viewing on web
entirely, firmware saves to SD only, web support deferred indefinitely.
**(a) is the honest recommendation** — it matches how this feature actually
gets used (at the table, on the device) and avoids taking on a certificate
problem for what would only ever be a "nice to have" on web.

## Risks and blockers

- **Hard prerequisite on WiFi (M2).** This is the project's first real
  network feature, not incremental scope on a finished app. Estimate
  accordingly — don't scope "add a camera" alone.
- **Web-twin parity is structurally broken by browser mixed-content policy**,
  not by project choice — verified via MDN, not assumed. Decide and document
  the exception now rather than rediscovering it mid-implementation.
- **Battery math for the Pi Zero 2 W path is tight** (own estimate: ~2.5h
  from a 1200mAh PiSugar at continuous draw) — only a real risk if that path
  is chosen; the recommended XIAO path has wide margin.
- **`jpegdec` availability in Presto's actual frozen module set is
  unconfirmed.** If absent: either get it added to the firmware build, or
  fall back to a cruder path (downscale/convert off-device to a format
  Presto definitely supports before sending) — more work, not a dead end.
- **XIAO Sense LiPo connector pitch is unconfirmed** — cheap mistake (wrong
  battery), cheap fix (adapter cable, or buy Seeed's own matching battery).
- **Privacy, not just engineering.** A table-facing camera captures players'
  faces/hands/surroundings along with the board. Not a technical blocker,
  but worth a physical lens cover or hardware off-switch, and a one-line note
  in any README about what the camera does and doesn't send anywhere. This
  project has no cloud component today; keep it that way for this feature —
  images should stay on the local network by default.
- **Scope note, not a blocker:** the original idea named "raspberry pi /
  xioa camera" as either/or. This report priced both plus ESP32-CAM and
  found the XIAO ESP32S3 Sense strictly better for this specific use case
  (similar price to ESP32-CAM, official MicroPython support unlike either
  alternative, onboard charging unlike both alternatives, far better sleep
  power than the Pi). Recommend XIAO over the Pi Zero 2 W or generic
  ESP32-CAM — not because the alternatives are unworkable, but because there
  is no upside to them here unless the image-quality gap turns out to matter.

## Recommended next step

**Spike, ~$25, one weekend.** Buy one
[XIAO ESP32S3 Sense](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html)
($13.99) and a compatible small LiPo. Definition of done:
1. Flash Seeed's official MicroPython + camera firmware; run their
   `streaming_server.py` example unmodified.
2. From a laptop on the same WiFi, confirm a JPEG can be pulled over plain
   HTTP.
3. Once Presto has *any* WiFi client code (even a throwaway REPL script, not
   the real M2 feature), confirm `urequests.get()` can fetch that same JPEG
   from the Presto side.
4. Check whether `jpegdec` is present in Presto's frozen modules; if so,
   decode and paint the fetched JPEG to the display and time it (call it
   acceptable if under ~1s for a single 480×480-scaled image).
5. Convert the streaming example into a single-shot-then-deep-sleep loop and
   measure actual current draw with a USB power meter, replacing the
   estimates in this report with real numbers.

Explicitly out of scope for the spike: enclosure/mount design, the web-twin
question (already resolved as blocked — no need to re-prove it), and full
battery run-time validation (a single-cycle current reading is enough to
decide whether to proceed).

If all five pass, this is real scope for a plan: WiFi client (M2) +
camera-pod firmware + a new Presto screen + enclosure — worth its own
`writing-plans` pass once the spike closes the `jpegdec` and timing unknowns.
