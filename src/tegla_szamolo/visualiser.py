"""
=============================================================
  visualiser.py  –  Braille segment visualiser
  Used by screen_wall_list() in main.py

  Braille block: each character encodes a 2×4 pixel grid
  We treat 1 braille "pixel" = 1 cm
=============================================================
"""

import curses

# -------------------------------------------------------------
#  SEGMENT COLOUR CYCLE
#  Pairs starting at index 20 — avoids colliding with C_* (1-8)
# -------------------------------------------------------------

_SEG_COLORS = [
    curses.COLOR_CYAN,
    curses.COLOR_YELLOW,
    curses.COLOR_GREEN,
    curses.COLOR_MAGENTA,
    curses.COLOR_RED,
    curses.COLOR_WHITE,
]

SEG_PAIR_BASE = 20  # pairs 20..25


def init_visualiser_colors():
    """Call once after curses.start_color() / use_default_colors()."""
    for i, fg in enumerate(_SEG_COLORS):
        curses.init_pair(SEG_PAIR_BASE + i, fg, -1)


def seg_color_pair(seg_index: int) -> int:
    """Return a curses attribute for the given segment index."""
    pair = SEG_PAIR_BASE + (seg_index % len(_SEG_COLORS))
    return curses.color_pair(pair)

# -------------------------------------------------------------
#  BRAILLE PIXEL ENGINE
#
#  Each braille char = 2 px wide × 4 px tall
#
#    col:  0     1
#    row0: 0x01  0x08
#    row1: 0x02  0x10
#    row2: 0x04  0x20
#    row3: 0x40  0x80
# -------------------------------------------------------------


_BRAILLE_BASE = 0x2800
_CELL_W = 2
_CELL_H = 4

_DOT_BIT = [
    [0x01, 0x08],
    [0x02, 0x10],
    [0x04, 0x20],
    [0x40, 0x80],
]


def _make_canvas(px_w: int, px_h: int):
    cols = max(1, (px_w + _CELL_W - 1) // _CELL_W)
    rows = max(1, (px_h + _CELL_H - 1) // _CELL_H)
    return [[0] * cols for _ in range(rows)], rows, cols


def _set_pixel(canvas, px_x: int, px_y: int):
    cell_col = px_x // _CELL_W
    cell_row = px_y // _CELL_H
    dot_col = px_x % _CELL_W
    dot_row = px_y % _CELL_H
    try:
        canvas[cell_row][cell_col] |= _DOT_BIT[dot_row][dot_col]
    except IndexError:
        pass


def _canvas_to_chars(canvas) -> list[str]:
    return [
        "".join(chr(_BRAILLE_BASE + cell) for cell in row)
        for row in canvas
    ]


def render_segment_braille(width_cm: int, height_cm: int,
                           label: str = "") -> list[str]:
    """
    Render a rectangle outline of (width_cm × height_cm) pixels
    using braille characters. Returns a list of strings (one per
    braille row). Label is centred inside the rectangle.
    """
    px_w = max(4, width_cm)
    px_h = max(8, height_cm)

    canvas, rows, cols = _make_canvas(px_w, px_h)

    # Draw outline — top & bottom
    for px_x in range(px_w):
        _set_pixel(canvas, px_x, 0)
        _set_pixel(canvas, px_x, px_h - 1)
    # Left & right
    for px_y in range(px_h):
        _set_pixel(canvas, 0,        px_y)
        _set_pixel(canvas, px_w - 1, px_y)

    lines = _canvas_to_chars(canvas)

    # Embed label at vertical centre
    lbl = label[:2]
    if lbl and rows >= 2:
        mid_row = rows // 2
        mid_col = max(0, (cols - len(lbl)) // 2)
        row_list = list(lines[mid_row])
        for ci, ch in enumerate(lbl):
            if mid_col + ci < len(row_list):
                row_list[mid_col + ci] = ch
        lines[mid_row] = "".join(row_list)

    return lines

# -------------------------------------------------------------
#  PANEL RENDERER
# -------------------------------------------------------------


_MAX_CM = 400   # safety cap


def draw_segment_panel(win, segments: list[dict]):
    """
    Draw the braille visualisation of `segments` into `win`.
    `win` must already be positioned correctly by the caller.

    All rectangles are top-aligned; segments are placed
    left-to-right with a 1-char gap between them.
    """
    win.erase()
    ph, pw = win.getmaxyx()

    # ── Title bar ────────────────────────────────────────────
    title = " 🧱 Segment View "
    title_x = max(0, (pw - len(title)) // 2)
    try:
        win.addstr(0, title_x, title,
                   curses.color_pair(2) | curses.A_BOLD)   # C_TITLE = 2
    except curses.error:
        pass

    # ── Vertical separator on the left edge of this window ───
    for row in range(ph):
        try:
            win.addstr(row, 0, "│", curses.color_pair(8))  # C_BORDER = 8
        except curses.error:
            pass

    if not segments:
        msg = "No segments"
        try:
            win.addstr(ph // 2,
                       max(1, (pw - len(msg)) // 2),
                       msg, curses.color_pair(5))           # C_DIM = 5
        except curses.error:
            pass
        win.noutrefresh()
        return

    # ── Scaling ───────────────────────────────────────────────
    # Available drawing area: rows 1..(ph-2), cols 1..(pw-2)
    draw_top = 1
    draw_left = 1
    avail_h = ph - draw_top - 1
    avail_w = pw - draw_left - 1

    max_h_cm = max(
        min(_MAX_CM, int(float(s["height_m"]) * 100))
        for s in segments
    )
    # Natural braille rows needed for tallest segment
    natural_rows = (max_h_cm + _CELL_H - 1) // _CELL_H
    scale = min(1.0, (avail_h - 1) / max(1, natural_rows))

    # ── Draw segments left-to-right ───────────────────────────
    cursor_x = draw_left

    for idx, seg in enumerate(segments):
        w_cm = min(_MAX_CM, int(float(seg["width_m"]) * 100))
        h_cm = min(_MAX_CM, int(float(seg["height_m"]) * 100))

        disp_w_cm = max(4,  int(w_cm * scale))
        disp_h_cm = max(8,  int(h_cm * scale))

        btype = str(seg.get("brick_type", "?"))
        label = btype[:2]

        lines = render_segment_braille(disp_w_cm, disp_h_cm, label)
        attr = seg_color_pair(idx) | curses.A_BOLD

        braille_cols = (disp_w_cm + _CELL_W - 1) // _CELL_W

        # Stop if we'd overflow horizontally
        if cursor_x + braille_cols > avail_w + draw_left:
            # Try to indicate more segments exist
            if cursor_x < avail_w + draw_left - 1:
                try:
                    win.addstr(draw_top, cursor_x, "…",
                               curses.color_pair(5))
                except curses.error:
                    pass
            break

        for row_i, line in enumerate(lines):
            screen_row = draw_top + row_i
            if screen_row >= ph - 1:
                break
            max_chars = min(len(line),
                            avail_w + draw_left - cursor_x)
            if max_chars <= 0:
                break
            try:
                win.addstr(screen_row, cursor_x,
                           line[:max_chars], attr)
            except curses.error:
                pass

        cursor_x += braille_cols + 1   # 1-char gap

    win.noutrefresh()
