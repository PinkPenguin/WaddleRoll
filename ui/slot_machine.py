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

Optional built-in lock toggle (show_lock=True): a small custom-painted
padlock (LockToggle, below) to the right of the reel, replacing the
pattern every module had been repeating -- a separate row of
QCheckBoxes underneath the whole result panel, one per result, wired up
by hand in each module's own ui.py. Baking it into this shared widget
means any module gets a working, consistently-styled lock for free just
by passing show_lock=True, rather than every module reimplementing the
same checkbox-plus-wiring. Off by default, so every existing usage
across the project is completely unaffected until a module explicitly
opts in.

The lock is a floating overlay (positioned in resizeEvent), not a
layout sibling of the reel -- the reel always fills this widget's FULL
width regardless of show_lock, so it's always centered on the row's
true center. A [reel][lock] side-by-side layout can't achieve that: the
lock eats space only from the right, so the reel's own centered point
drifts left of the row's true center by half the lock's footprint --
correct arithmetic for "centered within the remaining space," but not
what "centered" means visually.
"""

import random

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QAbstractButton, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QPen

IDLE_INTERVAL_MS = 35  # constant, fastest tick while idling


class LockToggle(QAbstractButton):
    """A small, custom-painted padlock -- shackle arc + body, drawn via
    QPainter rather than styled through a QCheckBox's own indicator
    (Qt's QSS can only draw boxes/circles via border-radius tricks, not
    an actual recognizable lock shape). QAbstractButton gives the same
    interaction semantics a QCheckBox has (setCheckable, isChecked,
    setChecked, a toggled signal) while leaving the visual entirely up
    to paintEvent -- exactly what's needed here, not a repurposed
    checkbox with unusual styling bolted on.

    Deliberately minimal: two shapes (an outlined arc, an outlined-or-
    filled rounded rect), no text, no extra ornamentation -- meant to
    read as "a lock" at a glance without competing for attention.

    color: single color used for both shapes; only the body FILLS when
    checked, the shackle stays an outline in both states (a padlock's
    shackle doesn't conceptually "fill") -- keeps the checked/unchecked
    difference to the smallest change that still reads clearly.

    unlocked_opacity: how visible the icon is before it's checked --
    translucent by default (a quiet, easy-to-ignore affordance until it
    matters), full opacity once checked. Adjustable per call site
    rather than hardcoded, since "how subtle is subtle enough" is
    exactly the kind of thing worth tuning without editing this file
    again.
    """

    def __init__(self, color: str, size: int = 14, unlocked_opacity: float = 0.10, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = color
        self._unlocked_opacity = unlocked_opacity
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        color = QColor(self._color)
        color.setAlphaF(1.0 if self.isChecked() else self._unlocked_opacity)

        pen = QPen(color)
        pen.setWidthF(max(1.0, w * 0.1))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Shackle: the top half of an ellipse, traced as an arc -- reads
        # as the rounded metal hook of a padlock. Always just an
        # outline, in both states.
        shackle_rect = QRectF(w * 0.30, h * 0.08, w * 0.40, h * 0.47)
        painter.drawArc(shackle_rect, 0, 180 * 16)  # Qt angles are in 1/16th of a degree; 0->180 traces the top half

        # Body: a small rounded rect, overlapping the shackle's base
        # slightly so the two shapes read as one connected lock rather
        # than two floating pieces. Outlined while unlocked, filled
        # solid once locked -- the one visual change between states.
        body_rect = QRectF(w * 0.15, h * 0.45, w * 0.70, h * 0.47)
        if self.isChecked():
            painter.setBrush(color)
        radius = min(body_rect.width(), body_rect.height()) * 0.25
        painter.drawRoundedRect(body_rect, radius, radius)

        painter.end()


def _normalize_entry(entry):
    """Accepts a plain name string or a (name, color) tuple; always
    returns a (name, color) tuple, color None if not given."""
    if isinstance(entry, tuple):
        return entry
    return (entry, None)


def _normalize_pool(pool):
    return [_normalize_entry(e) for e in pool]


def _build_varied_ring(entries: list, length: int) -> list:
    """Builds a ring of exactly `length` entries with no two adjacent
    entries sharing the same name, whenever that's mathematically
    possible -- guaranteed whenever there are 2+ distinct names, since
    each is repeated evenly here, via the standard "rearrange so no two
    adjacent items match" technique: group same-value entries together,
    then fill every-other ring position (0, 2, 4, ...) before wrapping
    to fill the remaining ones (1, 3, 5, ...). With only ONE distinct
    name, adjacent duplicates are unavoidable -- nothing else exists to
    show -- so this just returns that name repeated.

    Fixes a real bug: naively concatenating a short pool to reach the
    needed ring length, then shuffling the whole flat block, had a real
    chance of clustering the same name across several adjacent ring
    positions -- more likely the shorter/less varied the pool was, up
    to guaranteed with only one distinct "other" name. Since the
    slowest, most visible ticks are deliberately concentrated right
    before landing (the ease-out curve, then the fizzle tail on top of
    it), a slow tick landing inside such a cluster looked exactly like
    the reel visibly stalling on one entry right before flipping to the
    real result.

    Also fixes the ring's own wraparound (last entry back to first) --
    relevant for start_idle(), which spins indefinitely and does
    eventually wrap the index around (unlike a real spin() landing,
    which by construction never needs enough ticks to reach the wrap
    point -- see spin()'s own ring-sizing comment)."""
    unique_entries = list(entries)
    if len(unique_entries) <= 1:
        return list(unique_entries) * max(1, length)

    repeats = -(-length // len(unique_entries))  # ceil division
    shuffled_names = list(unique_entries)
    random.shuffle(shuffled_names)  # randomizes which name's "group" goes first
    grouped_pool = []
    for entry in shuffled_names:
        grouped_pool += [entry] * repeats
    grouped_pool = grouped_pool[:length]

    ring = [None] * length
    pos = 0
    for item in grouped_pool:
        ring[pos] = item
        pos += 2
        if pos >= length:
            pos = 1

    # The even/odd fill guarantees no adjacent duplicate in sequence,
    # but not across the ring's own wrap (index length-1 back to index
    # 0) -- possible when length is odd and the repeat counts don't
    # divide evenly. Best-effort fix: swap the last entry with an
    # earlier one that would be compatible at BOTH swap sites (not just
    # checking the position being swapped INTO -- the value actually
    # being moved there needs checking, not whatever was sitting there
    # before). Not always achievable: with exactly 2 distinct names on
    # an odd-length ring, one name must occur more than floor(n/2)
    # times, which makes a wraparound clash mathematically unavoidable
    # (pigeonhole) -- in that case this just leaves it, since forcing a
    # swap would only move the clash elsewhere, not remove it.
    if length >= 2 and ring[-1][0] == ring[0][0]:
        last_val = ring[-1][0]
        for i in range(1, length - 1):
            candidate_val = ring[i][0]
            last_val_ok_at_i = last_val != ring[i - 1][0] and last_val != ring[i + 1][0]
            candidate_ok_at_end = candidate_val != ring[length - 2][0] and candidate_val != ring[0][0]
            if last_val_ok_at_i and candidate_ok_at_end:
                ring[-1], ring[i] = ring[i], ring[-1]
                break

    return ring


class SlotMachine(QWidget):
    finished = Signal(str)
    clicked = Signal(str)  # emitted with the landed result, click only registers while stopped
    lock_toggled = Signal(bool)  # only emitted when show_lock=True

    def __init__(self, text_color="#ffffff", dim_color="#888888",
                 font_family="Arial", parent=None, compact: bool = False,
                 show_glow: bool = True, current_font_size: int = 34,
                 min_height: int = None, bordered_rows: bool = False,
                 show_lock: bool = False):
        """
        compact: when True, prev/next are still created and still added
        to the layout (so nothing else in this class needs to
        special-case their absence, and they're never left as
        unmanaged children -- an unmanaged child widget still gets
        shown at a default position when its parent is, which is
        exactly a bug this class once had), just collapsed to zero
        height, for a single-line reveal instead of a 3-line reel.
        Built for RimWorld rolling many quick small results in
        sequence, where a full reel per result would be needless
        overhead.

        show_glow: set False to disable the landing glow entirely --
        also built for RimWorld, where set_static() gets called
        rapidly in sequence with no pause between reveals, meaning the
        glow would either never render before being replaced
        (spin-based landings) or stay permanently on (set_static()
        never clears it the way spin() does at the start of a new one)
        -- neither is the intended "flash" effect, so it's better off
        disabled than half-working.

        current_font_size: size of the landed/current result specifically
        -- defaults to the original 34px so every existing usage is
        unaffected. Built for Hero Siege's secondary skill/relic reveal,
        which needed to read as visually smaller/subordinate to the
        primary class reveal happening in its own SlotMachine.

        min_height: explicit override for the compact-mode minimum
        height. None (the default) falls back to the built-in formula
        below. Exists because that formula is a flat additive constant
        that never scales down cleanly for every layout -- some modules
        need direct control rather than another guessed formula.

        bordered_rows: when True, each of the three stacked labels
        (prev/current/next) gets its own subtle border/radius, giving
        each visible reel position a defined "window" rather than free-
        floating text. Off by default so every existing usage is
        unaffected -- built for PoE1's full 3-line reel, where each row
        stays visible (unlike compact mode, where prev/next collapse to
        0px and a border on them would never show anyway).

        show_lock: adds a small checkbox to the right of the reel --
        is_locked()/set_locked() read and set it, lock_toggled fires on
        change. Off by default so every existing usage is unaffected.
        Deliberately just a bare checkbox, no label text next to it, to
        stay visually quiet -- this sits directly beside a result a
        person is actively looking at, not off in a separate row of
        checkboxes underneath the whole panel like every module used to
        build by hand. Locking state is never touched automatically by
        start_idle()/spin()/set_static() -- only set_locked() changes
        it, so a lock persists across rolls exactly the way every
        module's own hand-built checkbox already worked, until the
        module itself explicitly clears it (e.g. on a Clear action).
        """
        super().__init__(parent)
        self.setObjectName("slot_machine_root")
        self.setStyleSheet("QWidget#slot_machine_root { background: transparent; }")
        self._font_family = font_family
        self._text_color = text_color
        self._dim_color = dim_color
        self._compact = compact
        self._show_glow = show_glow
        self._bordered_rows = bordered_rows
        self._show_lock = show_lock

        # Always the simple, single QVBoxLayout, regardless of
        # show_lock -- the reel (prev/current/next stack) fills this
        # widget's FULL width either way, so it's always centered on
        # the row's true center point. A [reel][lock] side-by-side
        # layout (an earlier version of this) can't achieve that: the
        # lock only eats space from the right, so the reel's own
        # centered point drifts left of the row's true center by half
        # the lock's footprint -- correct arithmetic for "centered
        # within the remaining space," but not what "centered" should
        # mean visually. The lock checkbox (when show_lock) is instead
        # a floating overlay positioned in resizeEvent, not a layout
        # sibling competing for horizontal space at all.
        layout = QVBoxLayout(self)

        if compact:
            # prev/next are genuinely 0px tall here, but Qt's layout
            # spacing still reserves space AROUND them regardless of
            # their own size -- spacing only goes away if a widget is
            # actually hidden, not just zero-height. Confirmed real via
            # direct testing (current_font_size=0, min_height=0 still
            # produced a large frame) -- the full 10/10/10 margins+
            # spacing tuned for the non-compact 3-line reel were the
            # remaining overhead. Safe for every module still using the
            # default min_height formula (80px at the default font
            # size) since that floor stays larger than this smaller
            # natural size regardless -- only modules that also lower
            # min_height (like Last Epoch) actually see a difference.
            layout.setContentsMargins(0, 4, 0, 4)
            layout.setSpacing(2)
        else:
            layout.setContentsMargins(0, 10, 0, 10)
            layout.setSpacing(10)

        # Sizes bumped up from the original 13/24/13 -- the reel was
        # reading as squished vertically at the old sizes.
        self.prev_lbl = self._make_label(dim_color, 17)
        self.current_lbl = self._make_label(text_color, current_font_size, bold=True)
        self.next_lbl = self._make_label(dim_color, 17)

        # Compact mode: always add these to the layout (never leave them
        # as unmanaged children -- an unmanaged child widget still gets
        # shown when its parent is, at whatever default 0,0 position and
        # size it happens to have, which is exactly the "extra roll in
        # the top-left corner" bug this replaced). Collapsing height to
        # zero hides them cleanly without touching the visible property
        # at all, avoiding the separate setVisible-before-first-show
        # gotcha documented elsewhere in this project.
        if compact:
            self.prev_lbl.setFixedHeight(0)
            self.next_lbl.setFixedHeight(0)

        layout.addWidget(self.prev_lbl)
        layout.addWidget(self.current_lbl)
        layout.addWidget(self.next_lbl)

        self.lock_checkbox = None
        if show_lock:
            # text_color, not dim_color -- the lock reads as a
            # "prominent" element of the row (like the landed result
            # itself), translucent until checked via LockToggle's own
            # unlocked_opacity rather than needing a separate dim
            # color. Explicitly parented (LockToggle(..., parent=self))
            # since it isn't added to any layout, which would otherwise
            # handle parenting automatically.
            self.lock_checkbox = LockToggle(color=text_color, size=16, parent=self)
            self.lock_checkbox.setToolTip("Lock this result so it stays the same on the next roll")
            self.lock_checkbox.toggled.connect(self.lock_toggled.emit)
            self._position_lock_checkbox()

        if min_height is not None:
            self.setMinimumHeight(min_height)
        else:
            self.setMinimumHeight(150 if not compact else current_font_size + 46)

        # Soft glow on the center label, only while genuinely landed --
        # a clearer "this is the result" cue than the arrow markers used
        # before. One effect object, toggled via setEnabled rather than
        # attached/detached repeatedly (cheaper, avoids any flicker from
        # swapping graphics effects in and out).
        self._glow = QGraphicsDropShadowEffect()
        self._glow.setBlurRadius(28)
        self._glow.setOffset(0, 0)
        self._glow.setEnabled(False)
        self.current_lbl.setGraphicsEffect(self._glow)

        # Pointing-hand cursor is the click affordance, only while
        # actually landed -- set alongside the glow at every mode
        # transition. Starts as a plain arrow since nothing's landed yet.
        self.setCursor(Qt.CursorShape.ArrowCursor)

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
        lbl = QLabel("", self)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Labels themselves don't handle clicks -- let them fall through
        # to the SlotMachine widget underneath, which owns the actual
        # click logic (mode-aware, one place to reason about).
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setProperty("_base_size", size)
        lbl.setProperty("_base_bold", bold)
        self._apply_label_style(lbl, color, size, bold)
        return lbl

    def _apply_label_style(self, lbl, color, size, bold):
        weight = "bold" if bold else "normal"
        border = (
            f"border: 1px solid {self._dim_color}; border-radius: 4px; padding: 2px 10px;"
            if self._bordered_rows else "border: none;"
        )
        lbl.setStyleSheet(
            f"color: {color}; background: transparent; font-family: '{self._font_family}'; "
            f"font-size: {size}px; font-weight: {weight}; {border}"
        )

    def _set_label_color(self, lbl, color):
        """Swaps just the color, keeping this label's own fixed
        size/weight -- called every tick, so it stays cheap."""
        size = lbl.property("_base_size")
        bold = lbl.property("_base_bold")
        self._apply_label_style(lbl, color, size, bold)

    def _apply_landed_glow(self, color):
        if not self._show_glow:
            return
        self._glow.setColor(QColor(color))
        self._glow.setEnabled(True)

    def _clear_landed_glow(self):
        self._glow.setEnabled(False)

    def mousePressEvent(self, event):
        if self._mode == "stopped" and self._result:
            self.clicked.emit(self._result)
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_lock_checkbox()

    def _position_lock_checkbox(self):
        """The lock checkbox has no layout parent (it's a floating
        overlay, not a layout sibling -- see __init__'s own comment on
        why), so nothing repositions it automatically as this widget
        resizes; this does that manually. Right-aligned, vertically
        centered on the whole widget, with a small margin."""
        if self.lock_checkbox is None:
            return
        margin = 4
        x = self.width() - self.lock_checkbox.width() - margin
        y = (self.height() - self.lock_checkbox.height()) // 2
        self.lock_checkbox.move(max(0, x), max(0, y))

    def is_locked(self) -> bool:
        """False when show_lock wasn't set -- no checkbox exists to be
        checked, so there's nothing to lock."""
        return bool(self.lock_checkbox and self.lock_checkbox.isChecked())

    def set_locked(self, locked: bool):
        """No-op when show_lock wasn't set. Qt's own setChecked only
        fires the toggled signal (and so lock_toggled, via the
        constructor's connection) when the value actually changes, so
        this is safe to call unconditionally on every Clear without
        worrying about redundant signal emissions."""
        if self.lock_checkbox:
            self.lock_checkbox.setChecked(locked)

    def start_idle(self, pool):
        """Begin continuous fast spinning with no landing -- the default
        state whenever nothing's been rolled/committed yet.
        pool: list of names, or (name, color) tuples."""
        entries = _normalize_pool(pool) if pool else [("—", None)]
        ring = _build_varied_ring(entries, max(14, len(entries)))

        if self._timer.isActive():
            self._timer.stop()

        self._ring = ring
        self._index = 0
        self._mode = "idle"
        self._clear_landed_glow()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._update_labels()
        self._timer.start(IDLE_INTERVAL_MS)

    def spin(self, pool, result, duration_ms: int = 5000,
              fizzle_ticks: int = 3, fizzle_max_interval: int = 420,
              base_interval: int = None):
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
        base_interval: the FIRST tick's speed (and the floor the ease-
        out curve starts from). None (the default) uses the same speed
        idle mode ticks at (IDLE_INTERVAL_MS, 35ms) -- unchanged
        behavior for every existing call site. Worth raising for a spin
        that starts right as another one lands (a cascaded reveal, e.g.
        race starting only once class lands): the quadratic ease-out
        bunches most ticks toward the fast end of the curve by
        construction, and at 35ms several of those early ticks are
        individually too fast to read as distinct movement -- which, if
        nothing else is animating nearby to help sell "it's still
        rolling," can look like the reel freezing for a stretch before
        suddenly, visibly moving right at the end. Raising the floor
        (e.g. to 90ms) means every tick starts in the visibly-distinct
        range, no fast/blurry phase at all -- confirmed by actually
        computing the resulting schedule, not just guessing.
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
        if not others:
            others = [(result_name, result_color)]

        self._schedule = self._build_schedule(
            duration_ms, fizzle_ticks=fizzle_ticks, fizzle_max_interval=fizzle_max_interval,
            base_interval=base_interval,
        )
        self._step = 0
        landing_index = len(self._schedule)

        # Ring length is driven by how many ticks the schedule actually
        # needs, not a fixed pad -- otherwise a small pool caps the tick
        # count (via a short ring) and the animation undershoots the
        # requested duration regardless of how long the schedule wants
        # to run. _build_varied_ring (not a naive shuffle) keeps same-
        # name entries from clustering next to each other regardless of
        # how short `others` is -- see that function's own docstring.
        ring = _build_varied_ring(others, landing_index + 4)
        ring.insert(landing_index, (result_name, result_color))

        self._ring = ring
        self._landing_index = landing_index
        self._index = 0
        self._result = result_name
        self._mode = "spinning"
        self._clear_landed_glow()
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._update_labels()
        if self._schedule:
            self._timer.start(self._schedule[0])
        else:
            self._mode = "stopped"
            self._index = landing_index
            self._update_labels()
            self._apply_landed_glow(result_color or self._text_color)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.finished.emit(result_name)

    def _build_schedule(self, duration_ms: int, max_interval: int = 220,
                          fizzle_ticks: int = 3, fizzle_max_interval: int = 420,
                          base_interval: int = None) -> list[int]:
        """Per-tick interval durations (ms). Two phases:
          1. Main ease-out, short first growing longer, up to max_interval.
             Tick *count* is derived from duration_ms directly (via the
             quadratic ease-out's average interval), so total spin time
             stays close to the target regardless of pool size.
          2. Fizzle tail: a handful of extra ticks continuing to slow
             down past max_interval, up to fizzle_max_interval, before
             landing -- the actual wind-down feel. This is additive on
             top of duration_ms (a real spin now runs ~1s longer than
             duration_ms alone would suggest); tune fizzle_ticks /
             fizzle_max_interval to taste, or pass fizzle_ticks=0 to get
             the old hard-stop behavior back.

        base_interval: overrides the curve's own starting/floor speed
        (see spin()'s own docstring for why this exists). None uses
        IDLE_INTERVAL_MS, unchanged from before this parameter existed.
        """
        base = base_interval if base_interval is not None else IDLE_INTERVAL_MS
        avg_interval = base + (max_interval - base) / 3  # mean of a t^2 ease-out over [0,1]
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
            _, landed_color = self._ring[self._landing_index % len(self._ring)]
            self._apply_landed_glow(landed_color or self._text_color)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
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

        # Reversed roll direction: the entry "coming up next" (next_i)
        # renders in the prev_lbl slot, and the one that just passed
        # through center (prev_i) renders in next_lbl. This flips which
        # way the reel visually appears to scroll without changing the
        # index/landing math at all -- it still lands on ring[landing_index]
        # in the center label exactly as before.
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
        self._result = text
        self.prev_lbl.setText("")
        self.current_lbl.setText(text)
        self.next_lbl.setText("")
        self._set_label_color(self.current_lbl, color or self._text_color)
        self._apply_landed_glow(color or self._text_color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)