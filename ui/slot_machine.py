"""
ui/slot_machine.py

Reusable slot-machine spin widget: three text panels (prev / current /
next), the center one larger, cycling through a shuffled pool with
increasing intervals (fast -> slow, an ease-out) before landing exactly
on a predetermined result.

The actual roll outcome is decided instantly elsewhere (a module's
roller.py) -- this widget is purely the visual reveal, so nothing about
fairness or weighting lives here. Not game-specific: any module wanting
this effect can reuse it.
"""

import random

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, Signal


class SlotMachine(QWidget):
    finished = Signal(str)

    def __init__(self, text_color="#ffffff", dim_color="#888888",
                 font_family="Arial", parent=None):
        super().__init__(parent)
        self._font_family = font_family

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.prev_lbl = self._make_label(dim_color, 14)
        self.current_lbl = self._make_label(text_color, 24, bold=True)
        self.next_lbl = self._make_label(dim_color, 14)

        layout.addWidget(self.prev_lbl, stretch=1)
        layout.addWidget(self.current_lbl, stretch=2)
        layout.addWidget(self.next_lbl, stretch=1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._ring = []
        self._index = 0
        self._landing_index = 0
        self._schedule = []
        self._step = 0
        self._result = None

    def _make_label(self, color, size, bold=False):
        lbl = QLabel("")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(
            f"color: {color}; font-family: '{self._font_family}'; "
            f"font-size: {size}px; font-weight: {weight};"
        )
        return lbl

    def spin(self, pool: list[str], result: str, duration_ms: int = 2200):
        """
        pool: eligible option names at roll time (for visual variety --
              doesn't need to be exhaustive, just needs a few entries).
        result: the already-determined roll outcome. Guaranteed to be
                what's showing in the center label when this finishes.
        """
        if self._timer.isActive():
            self._timer.stop()

        others = [p for p in pool if p != result]
        random.shuffle(others)
        if not others:
            others = [result]

        # Build a ring long enough to spin through, with `result` placed
        # partway along it (not at the very end, so there's a "next"
        # neighbor to show once landed).
        ring = []
        while len(ring) < 14:
            ring += others
        random.shuffle(ring)
        landing_index = len(ring) // 2
        ring.insert(landing_index, result)

        self._ring = ring
        self._landing_index = landing_index
        self._index = 0
        self._result = result
        self._schedule = self._build_schedule(landing_index, duration_ms)
        self._step = 0

        self._update_labels()
        if self._schedule:
            self._timer.start(self._schedule[0])
        else:
            self._index = landing_index
            self._update_labels()
            self.finished.emit(result)

    def _build_schedule(self, steps: int, duration_ms: int) -> list[int]:
        """Per-tick interval durations (ms), short first growing longer --
        an ease-out so the spin visually decelerates into the landing."""
        steps = max(steps, 1)
        base = 35
        # Scale max interval so the whole schedule roughly sums to duration_ms
        max_interval = max(base + 20, int(duration_ms / steps * 1.6))
        schedule = []
        for i in range(steps):
            t = i / max(1, steps - 1)
            interval = int(base + (max_interval - base) * (t ** 2))
            schedule.append(interval)
        return schedule

    def _tick(self):
        self._index += 1
        self._update_labels()

        if self._step + 1 >= len(self._schedule):
            self._timer.stop()
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
        self.prev_lbl.setText(self._ring[prev_i])
        self.current_lbl.setText(self._ring[i])
        self.next_lbl.setText(self._ring[next_i])

    def set_static(self, text: str):
        """Skip the animation entirely and just show a result -- used for
        locked rolls where nothing actually changed."""
        if self._timer.isActive():
            self._timer.stop()
        self.prev_lbl.setText("")
        self.current_lbl.setText(text)
        self.next_lbl.setText("")