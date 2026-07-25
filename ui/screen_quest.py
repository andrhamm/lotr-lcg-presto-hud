"""Quest-picker pre-game screens (M4-B, Tasks 4-6): Scenario Source (source
gate) -> Pick Cycle (drill into a cycle) -> Choose Scenario (radio + submit).

Web twin: docs/js/screens_other.js (ScenarioSourceScreen / PickCycleScreen /
ChooseScenarioScreen). Routing (Task 9, not yet wired) constructs
PickCycleScreen(source, cycles) from quest_catalog.cycles_for(index, source)
and ChooseScenarioScreen(source, cycle, scenarios) from one group's
"scenarios" list (quest_catalog.group_by_cycle).
"""

from ui.header import draw_header
from ui.widgets import (Button, panel, bevel, text_center, text_left,
                         truncate_text, wrap_text, disc, arc_runs, note_panel)
from ui import icons
import quest_catalog


def _chevron(d, pal, cx, cy):
    """Right-pointing row-disclosure triangle (list rows drill further in)."""
    d.set_pen(pal.dim)
    d.triangle(cx, cy - 5, cx, cy + 5, cx + 5, cy)


def _chevron_down(d, pal, cx, cy):
    """Downward-pointing disclosure triangle (dropdown "tap to open"
    affordance; mirrors mock_quest.py's chevron(..., down=True))."""
    d.set_pen(pal.dim)
    d.triangle(cx - 5, cy - 2, cx + 5, cy - 2, cx, cy + 4)


def _radio(d, pal, cx, cy, on):
    """Radio-button glyph: ring, filled when selected (mirrors
    mock_quest.py's radio())."""
    arc_runs(d, cx, cy, 10, 8, 0, 360, pal.gold if on else pal.dim)
    if on:
        disc(d, cx, cy, 5, pal.gold)


def icon_slot(d, pal, x, y, s, glyph_pen=None, mask=None):
    """Bordered well for a scenario/set icon (M4-B icons, Task 3). When
    `mask` is a real rasterized icon (tools/build_icons.py's 24x24 masks,
    matched via quest_catalog.icon_for) it's drawn centred in the well with
    icons.draw() - the same primitive the stat icons already use, since it
    derives its size from len(mask) rather than hardcoding one. With no
    match (mask is None - unmatched set, or icons.json unavailable) this
    keeps today's placeholder triangle glyph, exactly as before. Mirrors
    mock_quest.py's icon_slot()."""
    panel(d, pal, x, y, s, s, fill=pal.iconslot)
    if mask:
        msize = len(mask)
        off = max(0, (s - msize) // 2)
        icons.draw(d, mask, x + off, y + off, glyph_pen or pal.gold, scale=1)
    else:
        d.set_pen(glyph_pen or pal.dim)
        d.triangle(x + s // 2, y + 5, x + 5, y + s - 5, x + s - 5, y + s - 5)


class ScenarioSourceScreen:
    """Source gate: Official (FFG) vs Community (ALeP) scenarios. Stateless
    - two big bevel buttons, no tip."""

    def __init__(self):
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="SCENARIO SOURCE",
                    round_label="R0")

        off = Button(("choose_scenario", "official"), 24, 96, 432, 120)
        bevel(d, pal, off.x, off.y, off.w, off.h, pal.btn)
        text_center(d, pal, "Official Scenarios", 240, 128, 3, pal.gold)
        text_center(d, pal, "Fantasy Flight Games content", 240, 168, 2, pal.muted)
        self.buttons.append(off)

        com = Button(("choose_scenario", "alep"), 24, 244, 432, 120)
        bevel(d, pal, com.x, com.y, com.w, com.h, pal.btn)
        text_center(d, pal, "Community Scenarios", 240, 276, 3, pal.gold)
        text_center(d, pal, "Community created content", 240, 316, 2, pal.muted)
        self.buttons.append(com)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "choose_scenario":
            return btn.id
        return None


class PickCycleScreen:
    """Cycle list for one source ("official"/"alep"): name / release date or
    quest count / chevron, Log-style pager, plus a pinned "Custom" row that
    bypasses the catalog entirely. Empty (no cycles for this source, e.g.
    Community pre-ALeP) renders a graceful placeholder instead of a blank
    list."""

    PER_PAGE = 7
    ROW_H = 44
    ROW_STRIDE = 45
    LIST_Y0 = 50
    CUSTOM_Y = 370
    CUSTOM_H = 38

    def __init__(self, source, cycles):
        self.source = source
        self.cycles = cycles          # [{"cycle","date","count"}, ...] (quest_catalog.cycles_for)
        self.page = 0
        self.buttons = []

    def _pages(self):
        return max(1, -(-len(self.cycles) // self.PER_PAGE))  # ceil div

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        d.set_pen(pal.card)
        d.rectangle(0, 0, 480, 40)
        d.set_pen(pal.border)
        d.rectangle(0, 40, 480, 1)
        text_left(d, pal, "< Source", 12, 12, 2, pal.muted)
        text_center(d, pal, "CHOOSE CYCLE", 250, 12, 2, pal.gold)
        self.buttons.append(Button(("back",), 0, 0, 150, 40))

        pages = self._pages()
        self.page = min(self.page, pages - 1)
        chunk = self.cycles[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]

        if not self.cycles:
            msg = ("No community scenarios yet" if self.source == "alep"
                   else "No official scenarios yet")
            text_center(d, pal, msg, 240, 200, 2, pal.dim)
        else:
            y = self.LIST_Y0
            for entry in chunk:
                name = truncate_text(entry["cycle"], 2, 320, d.measure_text)
                text_left(d, pal, name, 20, y + 13, 2, pal.tan)
                date = entry.get("date")
                count = entry.get("count", 0)
                right = date if date else "%d quest%s" % (count, "" if count == 1 else "s")
                rw = d.measure_text(right, 1)
                text_left(d, pal, right, 440 - rw, y + 16, 1, pal.dim)
                _chevron(d, pal, 452, y + 22)
                d.set_pen(pal.border)
                d.rectangle(8, y + self.ROW_H, 456, 1)
                self.buttons.append(Button(("cycle", entry["cycle"]), 8, y, 456, self.ROW_H))
                y += self.ROW_STRIDE

        custom = Button(("custom",), 8, self.CUSTOM_Y, 464, self.CUSTOM_H)
        bevel(d, pal, custom.x, custom.y, custom.w, custom.h, pal.btn)
        text_center(d, pal, "Custom / uncatalogued quest", 240, self.CUSTOM_Y + 12, 2, pal.tan)
        self.buttons.append(custom)

        d.set_pen(pal.border)
        d.rectangle(0, 410, 480, 1)
        if pages > 1:
            up = Button(("older",), 12, 420, 150, 46)
            dn = Button(("newer",), 318, 420, 150, 46)
            bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
            text_center(d, pal, "Up", up.x + 75, up.y + 14, 2, pal.tan)
            bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
            text_center(d, pal, "Down", dn.x + 75, dn.y + 14, 2, pal.tan)
            text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 434, 2, pal.muted)
            self.buttons.append(up)
            self.buttons.append(dn)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "back":
            return ("goto", "scenario_source")
        if k == "cycle":
            return ("choose_scenario_list", self.source, btn.id[1])
        if k == "custom":
            return ("start_custom",)
        if k == "older":
            self.page = max(0, self.page - 1)
            return "redraw"
        if k == "newer":
            self.page = min(self._pages() - 1, self.page + 1)
            return "redraw"
        return None


class ChooseScenarioScreen:
    """Radio-select scenario list for one cycle: circle + name (no chevron,
    no stage count - Task 6), one selection, Submit CTA, Log-style pager."""

    PER_PAGE = 6
    ROW_STRIDE = 46
    LIST_Y0 = 66

    def __init__(self, source, cycle, scenarios):
        self.source = source
        self.cycle = cycle
        self.scenarios = scenarios    # [{"slug","name",...}, ...] (one group_by_cycle group)
        self.selected = scenarios[0]["slug"] if scenarios else None
        self.page = 0
        self.buttons = []

    def _pages(self):
        return max(1, -(-len(self.scenarios) // self.PER_PAGE))

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        d.set_pen(pal.card)
        d.rectangle(0, 0, 480, 52)
        d.set_pen(pal.border)
        d.rectangle(0, 52, 480, 1)
        text_left(d, pal, "< Cycles", 12, 8, 2, pal.muted)
        text_center(d, pal, "Choose Scenario", 250, 6, 2, pal.gold)
        subtitle = truncate_text("Cycle: %s" % self.cycle, 1, 440, d.measure_text)
        text_center(d, pal, subtitle, 250, 30, 1, pal.dim)
        self.buttons.append(Button(("back",), 0, 0, 150, 52))

        pages = self._pages()
        self.page = min(self.page, pages - 1)
        chunk = self.scenarios[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]

        y = self.LIST_Y0
        for scn in chunk:
            on = scn["slug"] == self.selected
            if on:
                d.set_pen(pal.card_hi)
                d.rectangle(8, y, 456, 44)
            _radio(d, pal, 30, y + 22, on)
            name = truncate_text(scn["name"], 2, 400, d.measure_text)
            text_left(d, pal, name, 52, y + 13, 2, pal.tan if on else pal.muted)
            d.set_pen(pal.border)
            d.rectangle(8, y + 44, 456, 1)
            self.buttons.append(Button(("scn", scn["slug"]), 8, y, 456, 44))
            y += self.ROW_STRIDE

        if pages > 1:
            up = Button(("older",), 12, 352, 150, 46)
            dn = Button(("newer",), 318, 352, 150, 46)
            bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
            text_center(d, pal, "Up", up.x + 75, up.y + 14, 2, pal.tan)
            bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
            text_center(d, pal, "Down", dn.x + 75, dn.y + 14, 2, pal.tan)
            text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 366, 2, pal.muted)
            self.buttons.append(up)
            self.buttons.append(dn)

        submit = Button(("submit",), 130, 414, 220, 52)
        bevel(d, pal, submit.x, submit.y, submit.w, submit.h, pal.btn_ok, False, 3)
        text_center(d, pal, "Submit", 240, 432, 3, pal.ok_fg)
        self.buttons.append(submit)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "back":
            return ("goto_pick_cycle", self.source)
        if k == "scn":
            self.selected = btn.id[1]
            return "redraw"
        if k == "older":
            self.page = max(0, self.page - 1)
            return "redraw"
        if k == "newer":
            self.page = min(self._pages() - 1, self.page + 1)
            return "redraw"
        if k == "submit":
            return ("scenario_chosen", self.selected) if self.selected else None
        return None


class ScenarioOptionsScreen:
    """Scenario Options (Task 7): the chosen scenario (tap to reopen the
    chooser) + a "sets to gather" list + Difficulty/Mode dropdowns (each
    opens an OptionListModal) + a conditional contextual tip + a "Begin
    Setup" CTA. Mirrors mock_quest.py's frame_options().

    Constructed with `scenario` (the catalog index entry: slug/name/pack/
    cycle/source/...), `data` (the loaded per-scenario JSON - routing
    stashes this here after loadScenario(slug) so "begin_setup" can hand its
    stages to preload_scenario without re-fetching), and `icons` (M4-B
    icons, Task 3: the loaded docs/data/icons.json "icons" map, or {} - the
    router loads it once alongside the catalog index and passes it through,
    same as `data`; a miss/failure just means every icon_slot() falls back
    to its placeholder triangle, never a crash)."""

    # ONE dropdown, not two. Difficulty and Mode were separate until it turned
    # out the only combination the split allowed was Easy + Nightmare - no
    # scenario ships both a printed Mode card and a Nightmare deck (the one
    # Hard scenario and all three Epic Multiplayer ones have hasNightmare
    # False), so the second dropdown bought exactly one pairing. Folding
    # Nightmare in as a difficulty rung also means the tip panel never has to
    # show two messages, which is what forced it to shrink its own text.
    #
    # Easy and Standard always apply: Easy is a general rule (drop every
    # encounter card whose set icon carries the gold difficulty ring), not a
    # per-scenario card. Anything else - Hard, Epic Multiplayer - only exists
    # as a printed Mode card on the handful of scenarios that ship one, so it
    # is offered only when this scenario's catalog entry lists it. Of 349
    # scenarios exactly one prints a Hard Mode card (The Hunt for the
    # Dreadnaught) and three print an Epic Multiplayer Mode card.
    #
    # Nightmare is likewise per-scenario: it is a separately sold encounter
    # deck, and only 68 of the 349 scenarios have one. The catalog already
    # knows which (`hasNightmare`, from build_card_data.py) - offering it
    # everywhere was the same bug as offering Hard everywhere.
    BASE_DIFFICULTY_OPTIONS = ("Easy", "Standard")

    GATHER_Y0 = 116
    GATHER_ROW_H = 30
    MAX_GATHER_ROWS = 4

    # The Difficulty row: dropdown + "Quest card" button, together spanning
    # the 16..464 content width. 124 leaves 14px either side of the label at
    # scale 2 (96px), and the dropdown still clears its widest value,
    # "Epic Multiplayer" (150px), inside its 26px of chrome.
    CARD_BTN_W = 124
    CARD_BTN_X = 480 - 16 - CARD_BTN_W
    DD_W = CARD_BTN_X - 8 - 16

    CTA_Y = 410
    CTA_H = 54

    # Only Easy and Nightmare get authored copy, because only those two are
    # general rules. A scenario-specific mode (Hard, Epic Multiplayer) shows
    # that card's own printed setup text instead - the real rules, not a
    # paraphrase (CLAUDE.md Iron rule #4).
    # Both wordings follow FFG's own, not a paraphrase (CLAUDE.md Iron rule #4):
    #
    #   Easy - Learn to Play p.28 "Modes of Play", and the Easy Mode Rules
    #   (2013) p.1. It is TWO steps, and an earlier version of this tip shipped
    #   only the second: "1. Add one resource to each hero's resource pool.
    #   2. Remove any card from the encounter deck that has a gold border
    #   surrounding its encounter set icon." FFG calls that marker the
    #   "difficulty" indicator.
    #
    #   Nightmare - the printed Nightmare Setup card (wording consistent across
    #   the setup cards that carry full text). It is a swap, not a substitution:
    #   remove the listed cards from the standard encounter deck, "then, shuffle
    #   the encounter cards in this Nightmare Deck into the remainder".
    #
    # Kept short deliberately: each must wrap to at most 3 lines at scale 2, so
    # it still fits unclipped in the tightest layout (4 sets-to-gather rows).
    # There is a test for that - lengthen these and it fails rather than
    # silently truncating the rule.
    TIP_TEXT = {
        "Easy": "Easy: add 1 resource to each hero at setup, and remove "
                "every encounter card with a gold-bordered set icon.",
        "Nightmare": "Nightmare: a separately sold deck - remove the cards "
                     "its setup card lists, then shuffle it into the rest.",
    }

    def __init__(self, scenario, data, icons=None, difficulty="Standard"):
        self.scenario = scenario
        self.data = data or {}
        self.icons = icons or {}
        self.difficulty = difficulty
        self.buttons = []

    # -- data shaping --------------------------------------------------
    def _gather_sets(self):
        # B-data: the real multi-set gather list, merged into the per-
        # scenario JSON by build_card_data.py from Hall of Beorn's sets-to-
        # gather enrichment (tools/build_hob_enrichment.py) - see
        # docs/superpowers/plans/2026-07-24-catalog-enrichment.md. Falls
        # back to the scenario's own set alone when enrichment wasn't
        # merged for this scenario (an API miss/skip at build time, no
        # enrichment.json at all, or a pre-B-data catalog build) - never a
        # crash, never an empty list.
        sets = self.data.get("includedSets") or [
            self.data.get("name") or self.scenario.get("name", "Unknown scenario")]
        return [s for s in sets if s]

    def _gather_rows(self):
        """[(label, is_more), ...], at most MAX_GATHER_ROWS entries - a
        "+N more" row (is_more=True, no icon slot) replaces the tail when
        the scenario's real gather list runs long."""
        sets = self._gather_sets()
        if len(sets) <= self.MAX_GATHER_ROWS:
            return [(s, False) for s in sets]
        shown = sets[:self.MAX_GATHER_ROWS - 1]
        return [(s, False) for s in shown] + \
            [("+%d more" % (len(sets) - len(shown)), True)]

    def _scenario_modes(self):
        """Mode-card names this scenario actually prints, from the catalog
        index entry ("Easy Mode", "Hard Mode", "Epic Multiplayer Mode", ...).
        Standard/Normal variants are dropped - they are the default, not a
        choice worth listing."""
        out = []
        for name in self.scenario.get("modes") or []:
            label = name.replace(" Mode", "").replace(" Game", "").strip()
            if label.lower() in ("standard", "normal", ""):
                continue
            out.append(label)
        return out

    def difficulty_options(self):
        """Easy/Standard always, then any extra mode this scenario prints,
        then Nightmare if a Nightmare deck exists for it. Ordered easiest
        first so the list reads as one difficulty ladder."""
        extra = [m for m in self._scenario_modes() if m.lower() != "easy"]
        opts = tuple(self.BASE_DIFFICULTY_OPTIONS) + tuple(extra)
        if self.scenario.get("hasNightmare"):
            opts += ("Nightmare",)
        return opts

    def _mode_card_text(self, label):
        """The chosen mode card's own printed setup text, if the loaded
        scenario carries it - the actual rules rather than a paraphrase."""
        for card in self.data.get("modes") or []:
            if (card.get("name") or "").replace(" Mode", "").replace(" Game", "").strip() == label:
                for face in card.get("faces") or []:
                    if face.get("text"):
                        return face["text"]
        return None

    def _tip_messages(self):
        """At most one message - the tip always renders at the same size, so
        it must never have to fit two (see the scale note in draw())."""
        if self.difficulty in self.TIP_TEXT:
            return [self.TIP_TEXT[self.difficulty]]
        if self.difficulty == "Standard":
            return []
        # a scenario-specific mode card: show what it actually says
        return [self._mode_card_text(self.difficulty)
                or "%s: follow this quest's %s Mode card." % (self.difficulty, self.difficulty)]

    # -- draw --------------------------------------------------------------
    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="SCENARIO OPTIONS",
                    round_label="R0")

        name = self.scenario.get("name") or self.data.get("name", "Unknown scenario")
        pack = self.scenario.get("pack") or self.data.get("pack", "")

        scenario_mask = quest_catalog.icon_for(self.scenario.get("slug"), self.icons)
        icon_slot(d, pal, 16, 50, 40, pal.gold, mask=scenario_mask)
        name_s = truncate_text(name, 2, 480 - 66 - 14, d.measure_text)
        text_left(d, pal, name_s, 66, 54, 2, pal.gold)
        sub = truncate_text("%s - tap to change" % pack, 1, 480 - 66 - 14, d.measure_text)
        text_left(d, pal, sub, 66, 76, 1, pal.dim)
        self.buttons.append(Button(("retitle",), 8, 46, 464, 50))

        text_left(d, pal, "SETS TO GATHER", 16, 100, 1, pal.muted)
        gy = self.GATHER_Y0
        for label, is_more in self._gather_rows():
            if is_more:
                text_left(d, pal, label, 48, gy + 5, 2, pal.muted)
            else:
                # Slot is 26 (not the mask's exact 24) so panel()'s 1px
                # border ring stays visible around the icon, same look as
                # an unmatched placeholder - see the Task 3 report.
                row_mask = quest_catalog.icon_for(quest_catalog.slugify(label), self.icons)
                icon_slot(d, pal, 16, gy, 26, mask=row_mask)
                row_s = truncate_text(label, 2, 480 - 48 - 14, d.measure_text)
                text_left(d, pal, row_s, 48, gy + 5, 2, pal.tan)
            gy += self.GATHER_ROW_H

        # Dropdown y is derived from the actual gather-row count (not a
        # fixed offset) so 1-4 rows can never collide with the form below;
        # with the 3-row fixture this reproduces mock_quest.py's y=212
        # exactly (116 + 3*30 + 6).
        dd_y = gy + 6
        self._dropdown(d, pal, 16, dd_y, self.DD_W, "Difficulty", self.difficulty,
                       ("dd", "difficulty"))
        # Same read-only card reference the Quest Setup view and the progress
        # detail row open - reachable here so you can read the stages before
        # committing to the scenario. Sits on the dropdown's row (its box
        # starts 14px below the label), not under it.
        cb = Button(("open_card_modal",), self.CARD_BTN_X, dd_y + 14, self.CARD_BTN_W, 34)
        bevel(d, pal, cb.x, cb.y, cb.w, cb.h, pal.btn)
        text_center(d, pal, "Quest card", cb.x + cb.w // 2, cb.y + 9, 2, pal.tan)
        self.buttons.append(cb)

        msgs = self._tip_messages()
        if msgs:
            # Always the mock's scale (2). The tip used to shrink to scale 1
            # whenever two messages showed at once, which read as a bug - the
            # same panel rendering at two different sizes. There is only ever
            # one message now (see _tip_messages), and the authored copy is
            # kept short enough to wrap to 2 lines at this scale.
            scale = 2
            ty = dd_y + 62
            # A scenario-specific mode card's own setup text can run several
            # hundred characters - far past the CTA. Clip to the lines that
            # actually fit and mark the truncation rather than overflowing;
            # the full text lives on the physical card in front of the player.
            avail = self.CTA_Y - 10 - ty
            msgs = self._clip_to_height(d, msgs, scale, avail)
            note_panel(d, pal, 16, ty, 448, msgs, scale)

        begin = Button(("begin",), 16, self.CTA_Y, 448, self.CTA_H)
        bevel(d, pal, begin.x, begin.y, begin.w, begin.h, pal.btn_ok, False, 3)
        text_center(d, pal, "Begin Setup", 240, self.CTA_Y + 18, 3, pal.ok_fg)
        self.buttons.append(begin)

    def _clip_to_height(self, d, msgs, scale, avail):
        """Trim wrapped tip lines to what fits above the CTA, appending an
        ellipsis to the last kept line when anything was dropped."""
        # Mirror note_panel's own geometry exactly (ui/widgets.py): line
        # height is 10*scale+6 and the usable width is the panel minus its
        # padding and the pipe-icon gutter. Guessing these numbers is how an
        # earlier attempt at this clip still overflowed.
        from ui import icons as _icons
        gutter = len(_icons.PIPE) + 14
        usable = 448 - 16 - 12 - gutter
        line_h = 10 * scale + 6
        max_lines = max(1, (avail - 16) // line_h)
        lines = []
        for m in msgs:
            lines.extend(wrap_text(m, scale, usable, d.measure_text))
        if len(lines) <= max_lines:
            return msgs
        # Rejoin into ONE message: note_panel treats each list entry as its
        # own paragraph and adds spacing between them, so handing it the
        # pre-split lines would grow the panel instead of shrinking it.
        return [" ".join(lines[:max_lines]).rstrip() + " ..."]

    def _dropdown(self, d, pal, x, y, w, label, value, id):
        text_left(d, pal, label, x, y, 1, pal.muted)
        yy = y + 14
        panel(d, pal, x, yy, w, 34, pal.well)
        text_left(d, pal, value, x + 10, yy + 9, 2, pal.tan)
        _chevron_down(d, pal, x + w - 16, yy + 17)
        self.buttons.append(Button(id, x, yy, w, 34))

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "retitle":
            return ("choose_scenario_list", self.scenario.get("source"), self.scenario.get("cycle"))
        if k == "dd":
            return ("modal", OptionListModal(self, "difficulty", "Difficulty",
                                             self.difficulty_options()))
        if k == "open_card_modal":
            stages = (self.data.get("quest") or {}).get("stages") or []
            if not stages:
                return None    # nothing loaded for this scenario, nothing to show
            from ui.modals import QuestCardModal
            return ("modal", QuestCardModal(game, stages=stages, scenario=self.scenario))
        if k == "begin":
            return ("begin_setup", self.difficulty)
        return None


class OptionListModal:
    """Tiny radio-list picker for a Scenario Options dropdown (Difficulty or
    Mode): reuses the radio glyph from ChooseScenarioScreen. Tapping a row
    sets the value directly on the host ScenarioOptionsScreen and closes;
    Done closes without changing the current selection. Mirrors the
    full-screen modal protocol used throughout ui/modals.py:
    draw(hw, game, pal) / on_button(btn) -> "close"|None."""

    ROWS_Y0 = 110
    ROW_H = 64
    ROW_STRIDE = 74
    DONE_Y = 404
    DONE_H = 56

    def __init__(self, host, attr, title, options):
        self.host = host
        self.attr = attr
        self.title = title
        self.options = options
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Choose %s" % self.title, 240, 30, 3, pal.gold)

        current = getattr(self.host, self.attr)
        y = self.ROWS_Y0
        for opt in self.options:
            on = opt == current
            if on:
                d.set_pen(pal.card_hi)
                d.rectangle(24, y, 432, self.ROW_H)
            _radio(d, pal, 50, y + self.ROW_H // 2, on)
            text_left(d, pal, opt, 80, y + self.ROW_H // 2 - 12, 3, pal.tan if on else pal.muted)
            d.set_pen(pal.border)
            d.rectangle(24, y + self.ROW_H, 432, 1)
            self.buttons.append(Button(("opt", opt), 24, y, 432, self.ROW_H))
            y += self.ROW_STRIDE

        done = Button(("done",), 24, self.DONE_Y, 432, self.DONE_H)
        bevel(d, pal, done.x, done.y, done.w, done.h, pal.btn_ok, False, 3)
        text_center(d, pal, "Done", 240, self.DONE_Y + 18, 2, pal.ok_fg)
        self.buttons.append(done)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "opt":
            setattr(self.host, self.attr, btn.id[1])
            return "close"
        if k == "done":
            return "close"
        return None
