"""
ui/slot_machine.py

Reusable slot-machine spin widget: three text panels (prev / current /
next), stacked vertically like a real reel, the center one larger.

Two modes:
  - idle: spins continuously at max speed, no landing -- call start_idle()
    whenever there's nothing committed yet (on load, after Clear).
  - spinning: a decelerating spin (ease-out) that lands exactly on a
    predetermined result after ~duration_ms, then winds down through a
    short "fizzle" tail before actually stopping -- call spin() to
    trigger, e.g. on a Roll button click. Interrupts idle mode
    automatically.

The actual roll outcome is decided instantly elsewhere (a module's
roller.py) -- this widget is purely the visual reveal, so nothing about
fairness or weighting lives here. Not game-specific: any module wanting
this effect can reuse it.

Entries (pool items and the result) may be plain strings, or
(name, color) tuples where color is a CSS color string or None. This
lets a caller (e.g. poe2/ui.py tagging item/ascendancy skills) attach a
display-only color per entry without this widget knowing anything about
what the color *means* -- color is opaque here.
"""

import random

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, Signal

IDLE_INTERVAL_MS = 35  # constant, fastest tick while idling


def _normalize_entry(entry):
    """Accepts a plain name string or a (name, color) tuple; always
    returns a (name, color) tuple, color None if not given."""
    if isinstance(entry, tuple):
        return entry
    return (entry, None)


def _normalize_pool(pool):
    return [_normalize_entry(e) for e in pool]


class SlotMachine(QWidget):
    finished = Signal(str)

    def __init__(self, text_color="#ffffff", dim_color="#888888",
                 font_family="Arial", parent=None):
        super().__init__(parent)
        self._font_family = font_family
        self._text_color = text_color
        self._dim_color = dim_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(10)

        # Sizes bumped up from the original 13/24/13 -- the reel was
        # reading as squished vertically at the old sizes.
        self.prev_lbl = self._make_label(dim_color, 17)
        self.current_lbl = self._make_label(text_color, 34, bold=True)
        self.next_lbl = self._make_label(dim_color, 17)

        layout.addWidget(self.prev_lbl)
        layout.addWidget(self.current_lbl)
        layout.addWidget(self.next_lbl)

        self.setMinimumHeight(150)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._ring = []
        self._index = 0
        self._landing_index = 0
        self._schedule = []
        self._step = 0
        self._result = None
        self._mode = "stopped"  # "idle" | "spinning" | "stopped"

    def _make_label(self, color, size, bold=False):
        lbl = QLabel("")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setProperty("_base_size", size)
        lbl.setProperty("_base_bold", bold)
        self._apply_label_style(lbl, color, size, bold)
        return lbl

    def _apply_label_style(self, lbl, color, size, bold):
        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(
            f"color: {color}; font-family: '{self._font_family}'; "
            f"font-size: {size}px; font-weight: {weight};"
        )

    def _set_label_color(self, lbl, color):
        """Swaps just the color, keeping this label's own fixed
        size/weight -- called every tick, so it stays cheap."""
        size = lbl.property("_base_size")
        bold = lbl.property("_base_bold")
        self._apply_label_style(lbl, color, size, bold)

    def start_idle(self, pool):
        """Begin continuous fast spinning with no landing -- the default
        state whenever nothing's been rolled/committed yet.
        pool: list of names, or (name, color) tuples."""
        entries = _normalize_pool(pool) if pool else [("—", None)]
        ring = []
        while len(ring) < 14:
            ring += entries
        random.shuffle(ring)

        if self._timer.isActive():
            self._timer.stop()

        self._ring = ring
        self._index = 0
        self._mode = "idle"
        self._update_labels()
        self._timer.start(IDLE_INTERVAL_MS)

    def spin(self, pool, result, duration_ms: int = 5000,
              fizzle_ticks: int = 3, fizzle_max_interval: int = 420):
        """
        pool: eligible option names at roll time (for visual variety --
              doesn't need to be exhaustive, just needs a few entries).
              Names, or (name, color) tuples.
        result: the already-determined roll outcome -- a plain name, or
                a (name, color) tuple. If given as a plain name and that
                name appears in pool with a color, that color is reused
                so the landed result is colored consistently with how it
                showed up while spinning.
        fizzle_ticks / fizzle_max_interval: after the main ease-out
        reaches max_interval, a few extra ticks continue slowing down
        past it (up to fizzle_max_interval) before the reel actually
        stops -- avoids the landing feeling like a hard cut from "still
        ticking at speed" to "frozen".
        Interrupts idle mode automatically if it was running.
        """
        if self._timer.isActive():
            self._timer.stop()

        entries = _normalize_pool(pool)

        if isinstance(result, tuple):
            result_name, result_color = result
        else:
            result_name = result
            result_color = None
            for name, color in entries:
                if name == result_name:
                    result_color = color
                    break

        others = [e for e in entries if e[0] != result_name]
        random.shuffle(others)
        if not others:
            others = [(result_name, result_color)]

        self._schedule = self._build_schedule(
            duration_ms, fizzle_ticks=fizzle_ticks, fizzle_max_interval=fizzle_max_interval
        )
        self._step = 0
        landing_index = len(self._schedule)

        ring = []
        while len(ring) < landing_index + 4:
            ring += others
        random.shuffle(ring)
        ring.insert(landing_index, (result_name, result_color))

        self._ring = ring
        self._landing_index = landing_index
        self._index = 0
        self._result = result_name
        self._mode = "spinning"

        self._update_labels()
        if self._schedule:
            self._timer.start(self._schedule[0])
        else:
            self._mode = "stopped"
            self._index = landing_index
            self._update_labels()
            self.finished.emit(result_name)

    def _build_schedule(self, duration_ms: int, max_interval: int = 220,
                          fizzle_ticks: int = 3, fizzle_max_interval: int = 420) -> list[int]:
        """Per-tick interval durations (ms). Two phases:
          1. Main ease-out, short first growing longer, up to max_interval.
             Tick *count* is derived from duration_ms directly (via the
             quadratic ease-out's average interval), so total spin time
             stays close to the target regardless of pool size.
          2. Fizzle tail: a handful of extra ticks continuing to slow
             down past max_interval, up to fizzle_max_interval, before
             landing -- the actual wind-down feel. Additive on top of
             duration_ms; pass fizzle_ticks=0 for the old hard-stop.
        """
        base = IDLE_INTERVAL_MS
        avg_interval = base + (max_interval - base) / 3
        steps = max(1, round(duration_ms / avg_interval))

        schedule = []
        for i in range(steps):
            t = i / max(1, steps - 1)
            interval = int(base + (max_interval - base) * (t ** 2))
            schedule.append(interval)

        for i in range(1, fizzle_ticks + 1):
            t = i / fizzle_ticks
            interval = int(max_interval + (fizzle_max_interval - max_interval) * t)
            schedule.append(interval)

        return schedule

    def _tick(self):
        if self._mode == "idle":
            self._index += 1
            self._update_labels()
            self._timer.start(IDLE_INTERVAL_MS)
            return

        self._index += 1
        self._update_labels()

        if self._step + 1 >= len(self._schedule):
            self._timer.stop()
            self._mode = "stopped"
            self._index = self._landing_index
            self._update_labels()
            self.finished.emit(self._result)
            return

        self._step += 1
        self._timer.start(self._schedule[self._step])

    def _update_labels(self):
        i = self._index % len(self._ring)
        prev_i = (i - 1) % len(self._ring)
        next_i = (i + 1) % len(self._ring)

        prev_name, prev_color = self._ring[prev_i]
        cur_name, cur_color = self._ring[i]
        next_name, next_color = self._ring[next_i]

        self.prev_lbl.setText(next_name)
        self.current_lbl.setText(cur_name)
        self.next_lbl.setText(prev_name)

        self._set_label_color(self.prev_lbl, next_color or self._dim_color)
        self._set_label_color(self.current_lbl, cur_color or self._text_color)
        self._set_label_color(self.next_lbl, prev_color or self._dim_color)

    def set_static(self, text, color=None):
        """Skip the animation entirely and just show a result -- used for
        locked rolls where nothing actually changed."""
        if self._timer.isActive():
            self._timer.stop()
        self._mode = "stopped"
        self.prev_lbl.setText("")
        self.current_lbl.setText(text)
        self.next_lbl.setText("")
        self._set_label_color(self.current_lbl, color or self._text_color)