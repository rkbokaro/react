# =========================================================
# STRING CHART CONFIG
# ==============================
# 1)Train started at first juncition
#  if not started:
                # if not station_meta[st].get("is_junction", False):
                #     continue
                # started = True
#
# 2) junction filter in this function(get_junction_stations_in_order)
# ===========================
#
# --- MULTI-DAY UPGRADE ---------------------------------------------------
# The original chart mapped time with `t % SECONDS_IN_DAY`, so any train
# still running past 24h wrapped back to the left edge and got treated as
# a brand-new segment. That's gone now. Instead, `StringChartView` owns a
# horizontal time *window* (in seconds, can be many hours or many days)
# and maps time -> x against that window instead of a fixed calendar day.
#
# Two ways to use it:
#
#   1) SELF-MOVING (no wiring needed) — just don't pass a `view` at all.
#      draw_string_chart() creates a temporary follow-mode view each call,
#      so the chart always shows the last `window_hours` of running and
#      auto-scrolls forward as sim_time advances, indefinitely, no wrap.
#
#   2) SCROLLABLE — create one `StringChartView` up front, keep it around
#      across frames, pass it into draw_string_chart(), and route pygame
#      events through view.handle_event(event, chart_rect) from your main
#      event loop. Mouse wheel / click-drag pan the chart; a "LIVE" button
#      jumps back to auto-follow. See the bottom of this file for a wiring
#      example.
# ---------------------------------------------------------------------------

import pygame
# from irsimpy13 import sec_to_hhmmss

LEFT_MARGIN   = 90
RIGHT_MARGIN  = 30
TOP_MARGIN    = 50
BOTTOM_MARGIN = 40

STRING_CHART_X = LEFT_MARGIN
STRING_CHART_Y = TOP_MARGIN


SECONDS_IN_DAY = 24 * 3600

# =========================================================
# COLORS
# =========================================================

BG_COLOR     = (255, 255, 255)
BORDER_COLOR = (0, 0, 0)
GRID_COLOR   = (210, 210, 210)
DAY_GRID_COLOR = (150, 150, 150)
TEXT_COLOR   = (0, 0, 0)
TIME_COLOR   = (60, 60, 60)
NOW_COLOR    = (220, 0, 0)     # current time line (RED)
LIVE_COLOR   = (0, 150, 0)
PAUSED_COLOR = (180, 120, 0)

# =========================================================
# TOOLTIP
# =========================================================


# ----------------------------
# Time formatting helper
# ----------------------------
def sec_to_hhmmss(sec):
    if sec is None:
        return "--:--:--"
    try:
        sec = int(sec)
    except (ValueError, TypeError):
        return "--:--:--"

    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_axis_time(t):
    """
    Multi-day label for an absolute simulation second, e.g. 'D2 08:00'
    for a train still running on the second calendar day. Day count is
    1-based (D1 = the first 24h of the run).
    """
    if t is None or t < 0:
        return "--:--"

    day = int(t // SECONDS_IN_DAY) + 1
    rem = int(t % SECONDS_IN_DAY)
    h = rem // 3600
    m = (rem % 3600) // 60
    return f"D{day} {h:02d}:{m:02d}"


def draw_tooltip(screen, text, pos, font):
    surf = font.render(text, True, (255, 255, 255))
    rect = surf.get_rect(topleft=(pos[0] + 10, pos[1] + 10))
    pygame.draw.rect(screen, (30, 30, 30), rect.inflate(8, 6))
    screen.blit(surf, rect)

# =========================================================
# STATION Y AXIS (ANCHOR = JUNCTIONS)
# =========================================================

def build_anchor_station_y(anchor_stations, chart_height,
                           top_margin=30, bottom_margin=30):

    if not anchor_stations:
        return {}

    usable_h = chart_height - top_margin - bottom_margin
    n = len(anchor_stations)

    if n == 1:
        return {anchor_stations[0]: top_margin}

    gap = usable_h / n

    return {
        st: top_margin + i * gap
        for i, st in enumerate(anchor_stations)
    }


def interpolate_station_y(st, station_meta, anchor_y):

    if st in anchor_y:
        return anchor_y[st]

    seq = station_meta[st].seq_no  # FIX: was station_meta[st]["seq_no"]

    anchors = sorted(
        anchor_y.keys(),
        key=lambda s: station_meta[s].seq_no  # FIX: was station_meta[s]["seq_no"]
    )

    for i in range(len(anchors) - 1):
        a, b = anchors[i], anchors[i + 1]
        sa = station_meta[a].seq_no  # FIX: was station_meta[a]["seq_no"]
        sb = station_meta[b].seq_no  # FIX: was station_meta[b]["seq_no"]

        if sa <= seq <= sb:
            frac = (seq - sa) / (sb - sa if sb > sa else 1)
            return anchor_y[a] + frac * (anchor_y[b] - anchor_y[a])

    return anchor_y[anchors[-1]]

# =========================================================
# TIME -> X   (legacy, 24h-wrapping — kept for backward compatibility;
#              draw_string_chart() no longer calls this internally)
# =========================================================

def time_to_x_fixed(t, chart_x, chart_w):
    """
    DEPRECATED for multi-day charts: wraps every 24h via `t % SECONDS_IN_DAY`.
    Kept in case other code in your project still imports/calls it directly.
    Use StringChartView.time_to_x() instead for anything that should span
    more than one day.
    """
    t_day = t % SECONDS_IN_DAY
    return chart_x + (t_day / SECONDS_IN_DAY) * chart_w


# =========================================================
# "IS ANY TRAIN AVAILABLE FOR PLOTTING" — data-availability checks
# =========================================================
#
# These answer the question you actually need when the chart looks empty
# or frozen: is there simply no train data (yet, or anymore) at this point
# in time, or is something else wrong? Use them to tell a legitimate gap
# apart from a stuck simulation instead of guessing from a blank screen.

def get_active_time_bounds(trains):
    """
    Returns (t_min, t_max) across every train's plotted string_points, or
    None if no train has plotted anything at all yet.

    t_min = earliest time any train started being drawn.
    t_max = latest time any train has reached so far.

    If t_max stops increasing call-over-call while sim_time keeps rising,
    that's a strong signal the *simulation* stalled (e.g. a stuck/deadlocked
    train — see find_stuck_trains() in train_sim.py) rather than anything
    wrong with the chart itself.
    """
    t_min = None
    t_max = None

    for tr in trains:
        pts = getattr(tr, "string_points", None)
        if not pts:
            continue

        for t, _st in pts:
            if t_min is None or t < t_min:
                t_min = t
            if t_max is None or t > t_max:
                t_max = t

    if t_min is None:
        return None

    return t_min, t_max


def has_train_data_after(trains, t):
    """True if at least one train has a plotted point beyond time t."""
    bounds = get_active_time_bounds(trains)
    if bounds is None:
        return False
    return bounds[1] > t


def has_train_data_in_range(trains, t_start, t_end):
    """True if any train has at least one plotted point inside [t_start, t_end]."""
    for tr in trains:
        pts = getattr(tr, "string_points", None)
        if not pts:
            continue
        for t, _st in pts:
            if t_start <= t <= t_end:
                return True
    return False


# =========================================================
# SCROLLABLE / SELF-MOVING TIME WINDOW
# =========================================================

def _pick_tick_interval_seconds(window_seconds):
    """Choose a readable gridline spacing based on how much time is visible."""
    hours = window_seconds / 3600.0

    if hours <= 6:
        return 1800        # 30 min
    if hours <= 12:
        return 3600        # 1 h
    if hours <= 30:
        return 2 * 3600    # 2 h
    if hours <= 72:
        return 6 * 3600    # 6 h
    return 12 * 3600       # 12 h


class StringChartView:
    """
    Owns the horizontal time window the string chart currently shows, so
    the chart can cover a run of any length instead of always wrapping at
    24 hours.

    Modes:
      follow=True  (default) — "self moving" strip chart. The window's
        right edge tracks whatever sim_time you pass to update(), so the
        chart auto-scrolls forward continuously as the sim runs.
      follow=False — manual/scrollable. The window stays wherever the user
        left it (mouse wheel / drag) until jump_to_live() is called again
        (e.g. by clicking the on-chart "LIVE" button).

    Typical use for a scrollable chart:

        view = StringChartView(window_hours=24, follow=True)
        ...
        while running:
            for event in pygame.event.get():
                view.handle_event(event, chart_rect)   # chart_rect from last draw
            view.update(sim_time)
            chart_rect = draw_string_chart(screen, font, trains, station_meta,
                                            sim_time, stations_order,
                                            width, height, view=view)

    Typical use for a self-moving chart with zero extra wiring: just don't
    create or pass a view at all — draw_string_chart() makes an ephemeral
    follow-mode one internally every call.
    """

    def __init__(self, window_hours=24, follow=True, lookahead_minutes=240):
        self.window_seconds = max(3600, window_hours * 3600)
        self.follow = follow
        self.lookahead_seconds = lookahead_minutes * 60
        self.window_start = 0.0

        self._dragging = False
        self._drag_start_mouse_x = 0
        self._drag_start_window = 0.0

        # populated each draw call so handle_event can hit-test the button
        self.live_button_rect = None

    # ---------------- window sizing ----------------

    def set_window_hours(self, hours):
        """Change how many hours are visible at once (zoom in/out)."""
        window_end = self.window_start + self.window_seconds
        self.window_seconds = max(3600, hours * 3600)
        if not self.follow:
            # keep the right edge roughly anchored when zooming manually
            self.window_start = max(0.0, window_end - self.window_seconds)

    # ---------------- per-frame update ----------------

    def update(self, sim_time, trains=None, anchor_to_data_start=True):
        """
        Call once per frame, before drawing.

        trains: optional. If given, two things improve:

          1. anchor_to_data_start (default True): a fresh trailing window
             normally reaches back `window_seconds` from sim_time, which
             is often mostly blank right after a train starts (e.g. the
             train's first point is on day 15, sim_time is early day 15 ->
             the window still reaches back into day 14, where nothing has
             ever existed). This clamps the window's start so it never
             shows time before the earliest point any train has plotted,
             instead of wasting screen space on guaranteed-empty history.

          2. self.has_data / self.last_known_max_t get set from
             get_active_time_bounds(trains), so you (or the on-chart
             overlay in draw_string_chart) can tell "no trains plotted
             here" apart from "chart looks frozen" — see
             has_train_data_after() / has_train_data_in_range().
        """
        self.has_data = False
        self.last_known_max_t = None

        earliest_data_t = None
        if trains is not None:
            bounds = get_active_time_bounds(trains)
            if bounds is not None:
                earliest_data_t, self.last_known_max_t = bounds
                self.has_data = True

        if self.follow:
            window_end = sim_time + self.lookahead_seconds
            window_start = max(0.0, window_end - self.window_seconds)

            if (
                anchor_to_data_start
                and earliest_data_t is not None
                and window_start < earliest_data_t
            ):
                # Don't show blank time before the first train ever plotted
                # anything — slide the window's start up to meet the data
                # instead of dragging a permanent empty gap behind it.
                window_start = min(earliest_data_t, window_end)

            self.window_start = window_start

    def visible_range(self):
        return self.window_start, self.window_start + self.window_seconds

    # ---------------- time <-> pixel ----------------

    def time_to_x(self, t, chart_x, chart_w):
        frac = (t - self.window_start) / self.window_seconds
        return chart_x + frac * chart_w

    def x_to_time(self, x, chart_x, chart_w):
        frac = (x - chart_x) / chart_w if chart_w else 0
        return self.window_start + frac * self.window_seconds

    def is_visible_x(self, x, chart_x, chart_w, margin=0):
        return (chart_x - margin) <= x <= (chart_x + chart_w + margin)

    # ---------------- scrolling / panning ----------------

    def scroll_by_seconds(self, delta_seconds):
        self.follow = False
        self.window_start = max(0.0, self.window_start + delta_seconds)

    def jump_to_live(self):
        self.follow = True

    def handle_event(self, event, chart_rect):
        """
        Route pygame events here from your normal event loop:
            for event in pygame.event.get():
                view.handle_event(event, chart_rect)

        chart_rect: pygame.Rect of the chart's plotting area (returned by
        draw_string_chart, or build it yourself as
        pygame.Rect(LEFT_MARGIN, TOP_MARGIN, width-LEFT_MARGIN-RIGHT_MARGIN,
        height-TOP_MARGIN-BOTTOM_MARGIN)).
        """
        # "LIVE" button takes priority over drag-start on the same click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.live_button_rect and self.live_button_rect.collidepoint(event.pos):
                self.jump_to_live()
                return

        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if chart_rect.collidepoint(mx, my):
                step = self.window_seconds * 0.1  # one notch ~= 10% of window
                self.scroll_by_seconds(-event.y * step)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if chart_rect.collidepoint(event.pos):
                self._dragging = True
                self._drag_start_mouse_x = event.pos[0]
                self._drag_start_window = self.window_start

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False

        elif event.type == pygame.MOUSEMOTION and self._dragging:
            dx = event.pos[0] - self._drag_start_mouse_x
            seconds_per_pixel = self.window_seconds / max(1, chart_rect.width)
            self.follow = False
            self.window_start = max(
                0.0,
                self._drag_start_window - dx * seconds_per_pixel
            )


# =========================================================
# JUNCTIONS
# =========================================================

def get_junction_stations_in_order(station_meta):
    junctions = [
        st for st, meta in station_meta.items()

        if getattr(meta, "is_junction", False)  # FIX: was meta.get("is_junction", False)
    ]
    junctions.sort(key=lambda st: station_meta[st].seq_no)  # FIX: was station_meta[st]["seq_no"]
    return junctions

# =========================================================
# MAIN DRAW FUNCTION
# =========================================================
def point_near_segment(px, py, x1, y1, x2, y2, tol=5):

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return (px-x1)**2 + (py-y1)**2 <= tol**2

    t = ((px-x1)*dx + (py-y1)*dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))

    nx = x1 + t*dx
    ny = y1 + t*dy

    return (px-nx)**2 + (py-ny)**2 <= tol**2


def draw_string_chart(
    screen, font, trains,
    station_meta, sim_time,
    stations_order, width, height,
    view=None, window_hours=24,
        ):
    """
    Draw the string chart for a window of time rather than a fixed 24h
    calendar day, so trains running for multiple days plot as one
    continuous line instead of wrapping back to the left edge.

    view: optional StringChartView. Pass one you keep across frames to get
        a scrollable/pannable chart with a "LIVE" follow button. If omitted,
        a temporary follow-mode view is created every call — this alone
        gives you a self-moving strip chart with no other code changes.
    window_hours: only used when `view` is None, to size that temporary
        follow-mode window (default 24h of trailing history).

    Returns the pygame.Rect of the chart's plotting area, so you can pass
    it straight into view.handle_event(event, chart_rect) in your event loop.
    """

    stations_order = stations_order[1:]

    STRING_CHART_X = LEFT_MARGIN
    STRING_CHART_Y = TOP_MARGIN
    STRING_CHART_W = width - LEFT_MARGIN - RIGHT_MARGIN
    STRING_CHART_H = height - TOP_MARGIN - BOTTOM_MARGIN
    chart_rect = pygame.Rect(STRING_CHART_X, STRING_CHART_Y, STRING_CHART_W, STRING_CHART_H)

    owns_view = view is None
    if owns_view:
        view = StringChartView(window_hours=window_hours, follow=True)
    view.update(sim_time, trains=trains)

    # ---------------- BACKGROUND ----------------
    pygame.draw.rect(
        screen, BG_COLOR,
        (STRING_CHART_X, STRING_CHART_Y,
         STRING_CHART_W, STRING_CHART_H)
    )
    pygame.draw.rect(
        screen, BORDER_COLOR,
        (STRING_CHART_X, STRING_CHART_Y,
         STRING_CHART_W, STRING_CHART_H), 1
    )

    # ---------------- TITLE ----------------
    title = font.render(
        "INDIAN RAILWAYS – STRING (MASTER) CHART",
        True, TEXT_COLOR
    )
    screen.blit(
        title,
        (STRING_CHART_X + STRING_CHART_W // 2 - title.get_width() // 2, 10)
    )

    # ---------------- LIVE / FOLLOW indicator (top-right of chart) ----------------
    label_text = "\u25cf LIVE" if view.follow else "\u23f8 PAUSED (click LIVE)"
    label_color = LIVE_COLOR if view.follow else PAUSED_COLOR
    live_surf = font.render(label_text, True, label_color)
    live_rect = live_surf.get_rect()
    live_rect.topright = (STRING_CHART_X + STRING_CHART_W - 8, STRING_CHART_Y - 24)
    pygame.draw.rect(screen, (245, 245, 245), live_rect.inflate(10, 6))
    pygame.draw.rect(screen, label_color, live_rect.inflate(10, 6), 1)
    screen.blit(live_surf, live_rect)
    view.live_button_rect = live_rect.inflate(10, 6)

    # ---------------- ANCHOR STATIONS ----------------
    anchors = get_junction_stations_in_order(station_meta)
    if not anchors:
        anchors = stations_order[:]   # fallback
    anchors = stations_order
    anchor_y = build_anchor_station_y(
        anchors,
        STRING_CHART_H,
        top_margin=10,
        bottom_margin=10
    )

    # ---------------- STATION GRID ----------------
    for st, y in anchor_y.items():
        yy = STRING_CHART_Y + y

        pygame.draw.line(
            screen, GRID_COLOR,
            (STRING_CHART_X, yy),
            (STRING_CHART_X + STRING_CHART_W, yy), 1
        )

        label = font.render(st, True, TEXT_COLOR)
        screen.blit(
            label,
            (STRING_CHART_X - label.get_width() - 8, yy - 8)
        )

    # ---------------- TIME AXIS (multi-day aware) ----------------
    window_start, window_end = view.visible_range()
    tick_interval = _pick_tick_interval_seconds(view.window_seconds)

    first_tick = int(window_start // tick_interval) * tick_interval
    t = first_tick
    while t <= window_end:
        x = view.time_to_x(t, STRING_CHART_X, STRING_CHART_W)

        if STRING_CHART_X <= x <= STRING_CHART_X + STRING_CHART_W:
            is_day_boundary = (t % SECONDS_IN_DAY == 0)
            color = DAY_GRID_COLOR if is_day_boundary else GRID_COLOR
            line_w = 2 if is_day_boundary else 1

            pygame.draw.line(
                screen, color,
                (x, STRING_CHART_Y),
                (x, STRING_CHART_Y + STRING_CHART_H), line_w
            )

            label_text = format_axis_time(t) if (is_day_boundary or view.window_seconds > SECONDS_IN_DAY) \
                else f"{(t % SECONDS_IN_DAY) // 3600:02d}:{((t % SECONDS_IN_DAY) % 3600) // 60:02d}"
            label = font.render(label_text, True, TIME_COLOR)
            screen.blit(
                label,
                (x - label.get_width() // 2, STRING_CHART_Y - 24)
            )

        t += tick_interval

    # ---------------- CURRENT TIME ----------------
    if window_start <= sim_time <= window_end:
        x_now = view.time_to_x(sim_time, STRING_CHART_X, STRING_CHART_W)
        pygame.draw.line(
            screen, NOW_COLOR,
            (x_now, STRING_CHART_Y),
            (x_now, STRING_CHART_Y + STRING_CHART_H), 2
        )

    # ---------------- TRAIN TRAJECTORIES ----------------
    mx, my = pygame.mouse.get_pos()
    hover_train = None
    any_segment_drawn = False

    for tr in trains:

        segments = []
        current_seg = []
        started = False

        for t, st in tr.string_points:
            if st not in stations_order:
                continue

            if st not in station_meta:
                continue

            if not started:
                if not getattr(station_meta[st], "is_junction", False):  # FIX: was station_meta[st].get("is_junction", False)
                    continue
                started = True

            # Skip points entirely outside the visible window — no need to
            # break the segment for this, just don't plot off-chart pixels.
            if t < window_start - view.window_seconds or t > window_end + view.window_seconds:
                continue

            x = view.time_to_x(t, STRING_CHART_X, STRING_CHART_W)
            y = STRING_CHART_Y + interpolate_station_y(st, station_meta, anchor_y)

            # No more 24h-wrap detection needed here — time is monotonic
            # within a window now, so points simply accumulate into one
            # continuous polyline for as many days as the train runs.
            current_seg.append((x, y))

        if len(current_seg) >= 2:
            segments.append(current_seg)

        if segments:
            any_segment_drawn = True

        tr.draw_segments = segments
        for seg in segments:
            pygame.draw.lines(screen, tr.color, False, seg, 2)
            for i in range(len(seg)-1):

                x1, y1 = seg[i]
                x2, y2 = seg[i+1]

                if point_near_segment(mx, my, x1, y1, x2, y2, 5):
                    hover_train = tr

        if segments:
            xh, yh = segments[-1][-1]
            if view.is_visible_x(xh, STRING_CHART_X, STRING_CHART_W, margin=20):
                pygame.draw.circle(screen, (0, 0, 255), (xh, yh), 2)

                hit_rect = pygame.Rect(xh - 6, yh - 6, 12, 12)
                if hit_rect.collidepoint(mx, my):
                    tooltip_text = f"Train {tr.train_no} | {sec_to_hhmmss(sim_time)}"
                    draw_tooltip(screen, tooltip_text, (mx, my), font)

    # ---------------- "no data here" / "sim looks stalled" overlay ----------------
    # This is the check you asked for: is any train even available to plot
    # in this window, and if not, is that because the run genuinely hasn't
    # got there yet, or because sim_time has raced ahead of the last thing
    # any train actually did (a strong sign of a stalled/deadlocked sim —
    # see find_stuck_trains() in train_sim.py).
    if not any_segment_drawn:
        window_start, window_end = view.visible_range()

        if not view.has_data:
            msg = "No train has plotted any data yet."
        elif view.last_known_max_t is not None and view.last_known_max_t < window_start - 60:
            gap_hours = (sim_time - view.last_known_max_t) / 3600
            msg = (
                f"No train activity since {format_axis_time(view.last_known_max_t)} "
                f"— sim_time is {gap_hours:.1f}h ahead of it. "
                f"Simulation may be stalled (check find_stuck_trains())."
            )
        else:
            msg = "No train data in this time window."

        msg_surf = font.render(msg, True, (150, 0, 0))
        screen.blit(
            msg_surf,
            (
                STRING_CHART_X + STRING_CHART_W // 2 - msg_surf.get_width() // 2,
                STRING_CHART_Y + STRING_CHART_H // 2,
            ),
        )

    if hover_train:
            for seg in hover_train.draw_segments:

                pygame.draw.lines(
                    screen,
                    (255, 255, 0),      # Yellow highlight
                    False,
                    seg,
                    15                  # Highlight width
                )

                pygame.draw.lines(
                    screen,
                    hover_train.color,  # Original train colour
                    False,
                    seg,
                    2
                )

            # Tooltip near mouse
            draw_tooltip(
                screen,
                hover_train.train_no,
                (mx, my),
                font
            )

            # =====================================================
            # Route Debug Panel
            # =====================================================
            panel_x = width - 300
            panel_y = 40

            pygame.draw.rect(
                screen,
                (255, 255, 220),
                (panel_x - 10, panel_y - 10, 290, height - 60)
            )

            pygame.draw.rect(
                screen,
                (0, 0, 0),
                (panel_x - 10, panel_y - 10, 290, height - 60),
                1
            )

            # Train Number
            screen.blit(
                font.render(
                    f"Train : {hover_train.train_no}",
                    True,
                    (0, 0, 255)
                ),
                (panel_x, panel_y)
            )

            panel_y += 25

            # Remove duplicate stations
            last_station = None

            for _, st in hover_train.string_points:

                if st == last_station:
                    continue

                last_station = st

                screen.blit(
                    font.render(st, True, (0, 0, 0)),
                    (panel_x, panel_y)
                )

                panel_y += 18

                # Prevent writing outside the panel
                if panel_y > height - 25:
                    break

    return chart_rect


# =========================================================
# EXAMPLE WIRING (not executed — reference for your main loop)
# =========================================================
"""
import pygame
from string_chart import StringChartView, draw_string_chart

pygame.init()
screen = pygame.display.set_mode((1400, 800))
font = pygame.font.SysFont("consolas", 14)

# Persistent view -> scrollable chart. Drop `view=` entirely if you only
# want the zero-config self-moving strip chart instead.
view = StringChartView(window_hours=24, follow=True)

chart_rect = pygame.Rect(0, 0, 1, 1)  # placeholder until first draw

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        view.handle_event(event, chart_rect)

    sim_time = get_current_sim_time()   # however your sim exposes this
    trains = get_trains()
    station_meta = get_station_meta()
    stations_order = get_stations_order()

    screen.fill((255, 255, 255))
    # draw_string_chart calls view.update(sim_time, trains=trains) for you
    # internally — it clamps the leading edge to the first real data point
    # and tracks has_data / last_known_max_t so the "no data here" overlay
    # can tell a genuine gap apart from a stalled sim.
    chart_rect = draw_string_chart(
        screen, font, trains, station_meta, sim_time,
        stations_order, 1400, 800, view=view,
    )
    pygame.display.flip()

    # Anywhere in your own code you can also ask directly:
    #   from string_chart import has_train_data_after
    #   if not has_train_data_after(trains, sim_time - 1):
    #       print("No train has moved in the last second of sim time.")
"""