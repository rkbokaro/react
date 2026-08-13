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
TEXT_COLOR   = (0, 0, 0)
TIME_COLOR   = (60, 60, 60)
NOW_COLOR    = (220, 0, 0)     # current time line (RED)

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
# TIME → X
# =========================================================

def time_to_x_fixed(t, chart_x, chart_w):
    t_day = t % SECONDS_IN_DAY
    return chart_x + (t_day / SECONDS_IN_DAY) * chart_w


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
    stations_order,width,height
):
    
    stations_order = stations_order[1:]
    # print(stations_order)
    # input("stations_order")
    STRING_CHART_X = LEFT_MARGIN
    STRING_CHART_Y = TOP_MARGIN
    STRING_CHART_W = width - LEFT_MARGIN - RIGHT_MARGIN
    STRING_CHART_H = height - TOP_MARGIN - BOTTOM_MARGIN

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

    # ---------------- ANCHOR STATIONS ----------------
    anchors = get_junction_stations_in_order(station_meta)
    # print("Anchor===",anchors)
    if not anchors:
        anchors = stations_order[:]   # fallback
    anchors=stations_order
    anchor_y = build_anchor_station_y(
        anchors,
        STRING_CHART_H,
        top_margin=10,
        bottom_margin=10
    )

    # print(anchor_y)
    # input("stations_order")

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

    # ---------------- TIME AXIS ----------------
    for h in range(0, 25, 2):
        frac = h / 24.0

        # pull last label slightly inside
        if h == 24:
            frac = 0.985

        x = STRING_CHART_X + frac * STRING_CHART_W

        pygame.draw.line(
            screen, GRID_COLOR,
            (x, STRING_CHART_Y),
            (x, STRING_CHART_Y + STRING_CHART_H), 1
        )

        label = font.render(f"{h:02d}", True, TIME_COLOR)
        screen.blit(
            label,
            (x - label.get_width() // 2, STRING_CHART_Y - 24)
        )


        pygame.draw.line(
            screen, GRID_COLOR,
            (x, STRING_CHART_Y),
            (x, STRING_CHART_Y + STRING_CHART_H), 1
        )

        label = font.render(f"{h:02d}", True, TIME_COLOR)
        screen.blit(label, (x - label.get_width() // 2, STRING_CHART_Y - 24))

    # ---------------- CURRENT TIME ----------------
    x_now = time_to_x_fixed(sim_time, STRING_CHART_X, STRING_CHART_W)

    pygame.draw.line(
        screen, NOW_COLOR,
        (x_now, STRING_CHART_Y),
        (x_now, STRING_CHART_Y + STRING_CHART_H), 2
    )

    # ---------------- TRAIN TRAJECTORIES ----------------
    mx, my = pygame.mouse.get_pos()
    hover_train = None

    for tr in trains:
        

        segments = []
        current_seg = []
        prev_x = None
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

            x = time_to_x_fixed(t, STRING_CHART_X, STRING_CHART_W)

            y = STRING_CHART_Y + interpolate_station_y(st, station_meta, anchor_y)

            if prev_x is not None and x < prev_x:
                if len(current_seg) >= 2:
                    segments.append(current_seg)
                current_seg = []

            current_seg.append((x, y))
            prev_x = x

        if len(current_seg) >= 2:
            segments.append(current_seg)
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
            pygame.draw.circle(screen, (255, 0, 0), (xh, yh), 4)

            hit_rect = pygame.Rect(xh - 6, yh - 6, 12, 12)
            if hit_rect.collidepoint(mx, my):
                tooltip_text = f"Train {tr.train_no} | {sec_to_hhmmss(sim_time)}"
                draw_tooltip(screen, tooltip_text, (mx, my), font)
    
    

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




    

