"""
=============================================================
  Brick Calculator - Wall Manager  (TUI Edition)
  Navigate with arrow keys, Enter to select, Q/Esc to go back
=============================================================
"""

import os
import csv
import math
import curses
from datetime import datetime

# -------------------------------------------------------------
#  PATHS  -  {script_dir}/resources/
# -------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_RES_DIR = os.path.join(_SCRIPT_DIR, "resources")
os.makedirs(_RES_DIR, exist_ok=True)

CSV_FILE = os.path.join(_RES_DIR, "walls.csv")
SEGMENT_FILE = os.path.join(_RES_DIR, "segments.csv")

# -------------------------------------------------------------
#  BRICK SPECIFICATIONS
# -------------------------------------------------------------

BRICK_TYPES = {
    "10": {
        "label":        "Porotherm 10 N+F - 10 cm partition wall",
        "length_cm":    50.0,
        "height_cm":    23.8,
        "thickness_cm": 10.0,
        "mortar_cm":    1.2,
        "units_per_m2": 8.0,
    },
    "25": {
        "label":        "Porotherm 25 N+F - 25 cm wall",
        "length_cm":    37.5,
        "height_cm":    23.8,
        "thickness_cm": 25.0,
        "mortar_cm":    1.2,
        "units_per_m2": 10.7,
    },
    "30": {
        "label":        "Porotherm 30 N+F - 30 cm wall",
        "length_cm":    25.0,
        "height_cm":    23.8,
        "thickness_cm": 30.0,
        "mortar_cm":    1.2,
        "units_per_m2": 16.0,
    },
    "38": {
        "label":        "Porotherm 38 N+F - 38 cm wall",
        "length_cm":    25.0,
        "height_cm":    23.8,
        "thickness_cm": 38.0,
        "mortar_cm":    1.2,
        "units_per_m2": 16.0,
    },
    "classic": {
        "label":        "Classic solid brick - 25x12x6.5 cm",
        "length_cm":    25.0,
        "height_cm":    6.5,
        "thickness_cm": 12.0,
        "mortar_cm":    1.0,
        "units_per_m2": 102,
    },
}

CSV_WALL_HEADERS = ["wall_name", "created_at", "last_modified"]
CSV_SEGMENT_HEADERS = ["wall_name", "seg_index", "width_m", "height_m",
                       "brick_type", "area_m2", "bricks_needed"]

# -------------------------------------------------------------
#  BRICK CALCULATION
# -------------------------------------------------------------


def calculate_bricks(width_m, height_m, brick_type):
    spec = BRICK_TYPES[brick_type]
    mortar = spec["mortar_cm"]
    unit_w_m = (spec["length_cm"] + mortar) / 100.0
    unit_h_m = (spec["height_cm"] + mortar) / 100.0
    bricks_m2 = 1.0 / (unit_w_m * unit_h_m)
    area_m2 = width_m * height_m
    total = math.ceil(area_m2 * bricks_m2)
    return {
        "area_m2":       round(area_m2, 4),
        "bricks_per_m2": round(bricks_m2, 2),
        "bricks_needed": total,
        "unit_w_cm":     round(unit_w_m * 100, 2),
        "unit_h_cm":     round(unit_h_m * 100, 2),
    }

# -------------------------------------------------------------
#  DATA LAYER
# -------------------------------------------------------------


def load_walls():
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_walls(walls):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_WALL_HEADERS)
        w.writeheader()
        w.writerows(walls)


def load_segments():
    if not os.path.exists(SEGMENT_FILE):
        return []
    with open(SEGMENT_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_segments(segs):
    with open(SEGMENT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_SEGMENT_HEADERS)
        w.writeheader()
        w.writerows(segs)


def segs_for_wall(segs, wall_name):
    return [s for s in segs if s["wall_name"] == wall_name]


def wall_totals(segs, wall_name):
    ws = segs_for_wall(segs, wall_name)
    total_area = sum(float(s["area_m2"]) for s in ws)
    total_bricks = sum(int(s["bricks_needed"]) for s in ws)
    return {
        "segments": len(ws),
        "area_m2":  round(total_area, 3),
        "bricks":   total_bricks,
    }


def find_wall(walls, name):
    for i, w in enumerate(walls):
        if w["wall_name"].lower() == name.lower():
            return i
    return -1

# -------------------------------------------------------------
#  COLOUR PAIRS  (native / transparent terminal background)
#  BG = -1  means "inherit the terminal\'s own background".
# -------------------------------------------------------------


C_NORMAL = 1   # white on native bg
C_TITLE = 2   # yellow on native bg
C_SELECTED = 3   # black on cyan  (highlight bar)
C_HEADER = 4   # cyan on native bg
C_DIM = 5   # grey on native bg
C_ERROR = 6   # red on native bg
C_OK = 7   # green on native bg
C_BORDER = 8   # blue on native bg


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    BG = -1
    curses.init_pair(C_NORMAL,   curses.COLOR_WHITE,  BG)
    curses.init_pair(C_TITLE,    curses.COLOR_YELLOW, BG)
    curses.init_pair(C_SELECTED, curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(C_HEADER,   curses.COLOR_CYAN,   BG)
    curses.init_pair(C_DIM,
                     8 if curses.COLORS >= 256 else curses.COLOR_WHITE, BG)
    curses.init_pair(C_ERROR,    curses.COLOR_RED,    BG)
    curses.init_pair(C_OK,       curses.COLOR_GREEN,  BG)
    curses.init_pair(C_BORDER,   curses.COLOR_BLUE,   BG)

# -------------------------------------------------------------
#  LOW-LEVEL DRAWING HELPERS
# -------------------------------------------------------------


def safe_addstr(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0:
        return
    available = w - x - 1
    if available <= 0:
        return
    try:
        win.addstr(y, x, text[:available], attr)
    except curses.error:
        pass


def draw_box(win, y, x, h, w, color_pair=C_BORDER):
    attr = curses.color_pair(color_pair)
    safe_addstr(win, y,     x,     "\u2554", attr)
    safe_addstr(win, y,     x+w-1, "\u2557", attr)
    safe_addstr(win, y+h-1, x,     "\u255a", attr)
    safe_addstr(win, y+h-1, x+w-1, "\u255d", attr)
    for i in range(1, w - 1):
        safe_addstr(win, y,     x+i, "\u2550", attr)
        safe_addstr(win, y+h-1, x+i, "\u2550", attr)
    for i in range(1, h - 1):
        safe_addstr(win, y+i, x,     "\u2551", attr)
        safe_addstr(win, y+i, x+w-1, "\u2551", attr)


def center_text(win, y, text, attr=0):
    _, w = win.getmaxyx()
    x = max(0, (w - len(text)) // 2)
    safe_addstr(win, y, x, text, attr)


def fill_bg(win):
    """Clear window using the native terminal background (no colour fill)."""
    h, w = win.getmaxyx()
    for row in range(h):
        try:
            win.addstr(row, 0, " " * (w - 1))
        except curses.error:
            pass

# -------------------------------------------------------------
#  INLINE INPUT  (readline-style)
# -------------------------------------------------------------


def get_input(win, y, x, width, initial=""):
    """Single-line text input inside a curses window.
    Returns the entered string, or None if ESC was pressed."""
    curses.curs_set(1)
    buf = list(initial)
    pos = len(buf)
    attr_s = curses.color_pair(C_SELECTED)

    while True:
        safe_addstr(win, y, x, " " * width, attr_s)
        visible = "".join(buf)[:width - 1]
        safe_addstr(win, y, x, visible, attr_s)
        try:
            win.move(y, x + min(pos, width - 2))
        except curses.error:
            pass
        win.refresh()

        ch = win.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            break
        elif ch == 27:
            curses.curs_set(0)
            return None
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if pos > 0:
                buf.pop(pos - 1)
                pos -= 1
        elif ch == curses.KEY_DC:
            if pos < len(buf):
                buf.pop(pos)
        elif ch == curses.KEY_LEFT:
            pos = max(0, pos - 1)
        elif ch == curses.KEY_RIGHT:
            pos = min(len(buf), pos + 1)
        elif ch == curses.KEY_HOME:
            pos = 0
        elif ch == curses.KEY_END:
            pos = len(buf)
        elif 32 <= ch <= 126:
            buf.insert(pos, chr(ch))
            pos += 1

    curses.curs_set(0)
    return "".join(buf).strip()


# -------------------------------------------------------------
#  MODAL DIALOGS
# -------------------------------------------------------------

def modal_message(stdscr, title, lines, color_pair=C_NORMAL):
    """Centred message box; press any key to dismiss."""
    sh, sw = stdscr.getmaxyx()
    w = min(sw - 4, max(52, max(len(l) for l in lines) + 8))
    h = len(lines) + 6
    y = max(0, (sh - h) // 2)
    x = max(0, (sw - w) // 2)
    win = curses.newwin(h, w, y, x)
    fill_bg(win)
    draw_box(win, 0, 0, h, w, C_BORDER)
    center_text(win, 1, " " + title + " ",
                curses.color_pair(C_TITLE) | curses.A_BOLD)
    for i, line in enumerate(lines):
        safe_addstr(win, 3 + i, 3, line, curses.color_pair(color_pair))
    center_text(win, h - 2, "[ Press any key ]", curses.color_pair(C_DIM))
    win.refresh()
    win.getch()


def modal_confirm(stdscr, title, question):
    """Yes / No modal.  Returns True for Yes."""
    sh, sw = stdscr.getmaxyx()
    w = min(sw - 4, max(52, len(question) + 10))
    h = 8
    y = max(0, (sh - h) // 2)
    x = max(0, (sw - w) // 2)
    sel = 0   # 0 = No, 1 = Yes

    win = curses.newwin(h, w, y, x)
    win.keypad(True)  # ← CRITICAL: enables KEY_LEFT / KEY_RIGHT in this window

    while True:
        fill_bg(win)
        draw_box(win, 0, 0, h, w, C_BORDER)
        center_text(win, 1, " " + title + " ",
                    curses.color_pair(C_TITLE) | curses.A_BOLD)
        center_text(win, 3, question, curses.color_pair(C_NORMAL))
        bx_no = w // 2 - 10
        bx_yes = w // 2 + 2
        win.addstr(5, bx_no,  "  No  ",
                   curses.color_pair(C_SELECTED) | curses.A_BOLD
                   if sel == 0 else curses.color_pair(C_NORMAL))
        win.addstr(5, bx_yes, "  Yes  ",
                   curses.color_pair(C_SELECTED) | curses.A_BOLD
                   if sel == 1 else curses.color_pair(C_NORMAL))
        win.refresh()
        ch = win.getch()
        if ch in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("\t")):
            sel = 1 - sel
        elif ch in (ord("y"), ord("Y")):  # ← shortcut: Y = Yes
            return True
        elif ch in (ord("n"), ord("N")):  # ← shortcut: N = No
            return False
        elif ch in (curses.KEY_ENTER, 10, 13):
            return sel == 1
        elif ch == 27:
            return False


def modal_input_form(stdscr, title, fields):
    """
    Step-through form modal.
    fields = [{"label": str, "default": str, "validator": callable | None}, ...]
    Returns {label: value} or None on ESC.
    """
    sh, sw = stdscr.getmaxyx()
    w = min(sw - 4, 66)
    h = len(fields) * 3 + 6
    y = max(0, (sh - h) // 2)
    x = max(0, (sw - w) // 2)
    win = curses.newwin(h, w, y, x)

    results = {}

    for fi, field in enumerate(fields):
        while True:
            fill_bg(win)
            draw_box(win, 0, 0, h, w, C_BORDER)
            center_text(win, 1, " " + title + " ",
                        curses.color_pair(C_TITLE) | curses.A_BOLD)

            for i, f in enumerate(fields):
                row = 3 + i * 3
                lbl = f["label"]
                val = results.get(lbl, f.get("default", ""))
                lbl_attr = (curses.color_pair(C_HEADER) | curses.A_BOLD
                            if i == fi else curses.color_pair(C_DIM))
                safe_addstr(win, row,     3, lbl + ":", lbl_attr)
                safe_addstr(win, row + 1, 5, " " * (w - 8),
                            curses.color_pair(C_SELECTED))
                safe_addstr(win, row + 1, 5, str(val)[:w - 8],
                            curses.color_pair(C_SELECTED))

            safe_addstr(win, h - 2, 3,
                        "Enter=confirm  Esc=cancel",
                        curses.color_pair(C_DIM))
            win.refresh()

            val = get_input(win, 3 + fi * 3 + 1, 5, w - 8,
                            initial=str(field.get("default", "")))
            if val is None:
                return None

            validator = field.get("validator")
            if validator:
                ok, msg = validator(val)
                if not ok:
                    safe_addstr(win, 3 + fi * 3 + 2, 5,
                                ("  ! " + msg)[:w - 8],
                                curses.color_pair(C_ERROR) | curses.A_BOLD)
                    win.refresh()
                    curses.napms(1400)
                    continue

            results[field["label"]] = val
            break

    return results

# -------------------------------------------------------------
#  VALIDATORS
# -------------------------------------------------------------


def val_nonempty(v):
    return (True, "") if v.strip() else (False, "Cannot be empty.")


def val_positive_float(v):
    try:
        f = float(v.replace(",", "."))
        return (True, "") if f > 0 else (False, "Must be greater than 0.")
    except ValueError:
        return False, "Enter a number, e.g. 3.5"


def val_brick_type(v):
    if v.strip().lower() in BRICK_TYPES:
        return True, ""
    return False, "Choose from: " + " / ".join(BRICK_TYPES.keys())

# -------------------------------------------------------------
#  SCREEN: MAIN MENU
# -------------------------------------------------------------


LOGO = [
    "  ██████╗ ██████╗ ██╗ ██████╗██╗  ██╗",
    "  ██╔══██╗██╔══██╗██║██╔════╝██║ ██╔╝",
    "  ██████╔╝██████╔╝██║██║     █████╔╝ ",
    "  ██╔══██╗██╔══██╗██║██║     ██╔═██╗ ",
    "  ██████╔╝██║  ██║██║╚██████╗██║  ██╗",
    "  ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝",
    "",
    "  🧱   C A L C U L A T O R   🧱",
]

MAIN_ITEMS = [
    ("\u2728  New Project Wall",    "new"),
    ("\U0001f4c2  Open / Manage Walls", "open"),
    ("\u274c  Delete a Wall",       "delete"),
    ("\U0001f6aa  Exit",            "exit"),
]


def screen_main(stdscr, walls, segs):
    sel = 0
    while True:
        stdscr.erase()
        sh, sw = stdscr.getmaxyx()

        logo_start = max(1, (sh - len(LOGO) - len(MAIN_ITEMS) * 2 - 4) // 2)
        for i, line in enumerate(LOGO):
            attr = (curses.color_pair(C_HEADER) | curses.A_BOLD
                    if i == len(LOGO) - 1
                    else curses.color_pair(C_TITLE) | curses.A_BOLD)
            center_text(stdscr, logo_start + i, line, attr)

        menu_start = logo_start + len(LOGO) + 2
        for i, (label, _) in enumerate(MAIN_ITEMS):
            row = menu_start + i * 2
            text = "  " + label + "  "
            x = max(0, (sw - len(text)) // 2)
            attr = (curses.color_pair(C_SELECTED) | curses.A_BOLD
                    if i == sel else curses.color_pair(C_NORMAL))
            safe_addstr(stdscr, row, x, text, attr)

        footer = "\u2191\u2193 Navigate   Enter Select   Q Quit"
        safe_addstr(stdscr, sh - 2,
                    max(0, (sw - len(footer)) // 2),
                    footer, curses.color_pair(C_DIM))

        stdscr.refresh()
        ch = stdscr.getch()

        if ch == curses.KEY_UP:
            sel = (sel - 1) % len(MAIN_ITEMS)
        elif ch == curses.KEY_DOWN:
            sel = (sel + 1) % len(MAIN_ITEMS)
        elif ch in (curses.KEY_ENTER, 10, 13):
            action = MAIN_ITEMS[sel][1]
            if action == "exit":
                return
            elif action == "new":
                screen_new_wall(stdscr, walls, segs)
            elif action == "open":
                screen_wall_list(stdscr, walls, segs)
            elif action == "delete":
                screen_delete_wall(stdscr, walls, segs)
        elif ch in (ord("q"), ord("Q")):
            return

# -------------------------------------------------------------
#  SCREEN: NEW WALL
# -------------------------------------------------------------


def screen_new_wall(stdscr, walls, segs):
    def _val_name(v):
        ok, msg = val_nonempty(v)
        if not ok:
            return ok, msg
        if find_wall(walls, v) != -1:
            return False, "'" + v + "' already exists."
        return True, ""

    result = modal_input_form(stdscr, "\u2728  Create New Wall", [
        {"label": "Wall name", "default": "", "validator": _val_name},
    ])
    if result is None:
        return

    name = result["Wall name"].strip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    walls.append({"wall_name": name, "created_at": now, "last_modified": now})
    save_walls(walls)
    modal_message(stdscr, "\u2705 Created",
                  ["Wall \'" + name + "\' created successfully.",
                   "Open it from the wall list to add segments."],
                  C_OK)

# -------------------------------------------------------------
#  SCREEN: DELETE WALL
# -------------------------------------------------------------


def screen_delete_wall(stdscr, walls, segs):
    if not walls:
        modal_message(stdscr, "\u2139  Info", ["No walls to delete yet."])
        return

    sel = 0
    while True:
        stdscr.erase()
        sh, sw = stdscr.getmaxyx()
        draw_box(stdscr, 0, 0, sh, sw, C_BORDER)
        center_text(stdscr, 1, " \u274c  DELETE WALL ",
                    curses.color_pair(C_TITLE) | curses.A_BOLD)

        hdr = "  {:&lt;28}  {:&gt;4}  {:&gt;8}".format(
            "Wall Name", "Segs", "Bricks")
        safe_addstr(stdscr, 3, 2, hdr[:sw - 4],
                    curses.color_pair(C_HEADER) | curses.A_BOLD)
        safe_addstr(stdscr, 4, 2, "\u2500" * (sw - 5),
                    curses.color_pair(C_BORDER))

        list_h = sh - 8
        for i, wall in enumerate(walls):
            if i >= list_h:
                break
            row = 5 + i
            name = wall["wall_name"]
            tot = wall_totals(segs, name)
            text = "  {:<28}  {:>4}  {:>8}".format(
                name, tot["segments"], tot["bricks"])
            attr = (curses.color_pair(C_SELECTED) | curses.A_BOLD
                    if i == sel else curses.color_pair(C_NORMAL))
            safe_addstr(stdscr, row, 2, text[:sw - 4], attr)

        safe_addstr(stdscr, sh - 2, 3,
                    "\u2191\u2193 Select   Enter Delete   Q Back",
                    curses.color_pair(C_DIM))
        stdscr.refresh()
        ch = stdscr.getch()

        if ch == curses.KEY_UP:
            sel = (sel - 1) % len(walls)
        elif ch == curses.KEY_DOWN:
            sel = (sel + 1) % len(walls)
        elif ch in (curses.KEY_ENTER, 10, 13):
            name = walls[sel]["wall_name"]
            if modal_confirm(stdscr, "Confirm Delete",
                             "Delete \'" + name + "\' and ALL its segments?"):
                segs[:] = [s for s in segs if s["wall_name"] != name]
                walls.pop(sel)
                save_walls(walls)
                save_segments(segs)
                modal_message(stdscr, "\U0001f5d1  Deleted",
                              ["Wall \'" + name + "\' has been deleted."],
                              C_ERROR)
                if not walls:
                    return
                sel = min(sel, len(walls) - 1)
        elif ch in (ord("q"), ord("Q"), 27):
            return

# -------------------------------------------------------------
#  SCREEN: WALL LIST
# -------------------------------------------------------------


def screen_wall_list(stdscr, walls, segs):
    if not walls:
        modal_message(stdscr, "\u2139  Info",
                      ["No walls yet.",
                       "Use \'New Project Wall\' from the main menu."])
        return

    sel = 0
    scroll = 0

    while True:
        stdscr.erase()
        sh, sw = stdscr.getmaxyx()
        draw_box(stdscr, 0, 0, sh, sw, C_BORDER)
        center_text(stdscr, 1, " 📋  WALL LIST ",
                    curses.color_pair(C_TITLE) | curses.A_BOLD)

        hdr = "  {:<28}  {:>4}  {:>8}  {:>8}  {:<19}".format(
            "Wall Name", "Segs", "Area m2", "Bricks", "Last modified")
        safe_addstr(stdscr, 3, 2, hdr[:sw - 4],
                    curses.color_pair(C_HEADER) | curses.A_BOLD)
        safe_addstr(stdscr, 4, 2, "─" * (sw - 5),
                    curses.color_pair(C_BORDER))

        list_h = sh - 9
        visible = walls[scroll: scroll + list_h]

        for i, wall in enumerate(visible):
            g_idx = scroll + i
            row = 5 + i
            name = wall["wall_name"]
            tot = wall_totals(segs, name)
            mod = wall.get("last_modified", "-")[:19]
            text = "  {:<28}  {:>4}  {:>8.2f}  {:>8}  {:<19}".format(
                name, tot["segments"], tot["area_m2"], tot["bricks"], mod)
            attr = (curses.color_pair(C_SELECTED) | curses.A_BOLD
                    if g_idx == sel else curses.color_pair(C_NORMAL))
            safe_addstr(stdscr, row, 2, text[:sw - 4], attr)

        grand_bricks = sum(wall_totals(segs, w["wall_name"])[
            "bricks"] for w in walls)
        grand_area = sum(wall_totals(segs, w["wall_name"])[
            "area_m2"] for w in walls)
        safe_addstr(stdscr, sh - 4, 2, "─" * (sw - 5),
                    curses.color_pair(C_BORDER))
        totals_txt = "  TOTAL  {} wall(s)   {:>8.2f} m2   {:>8} bricks".format(
            len(walls), grand_area, grand_bricks)
        safe_addstr(stdscr, sh - 3, 2, totals_txt[:sw - 4],
                    curses.color_pair(C_HEADER) | curses.A_BOLD)

        footer = "↑↓ Navigate   Enter Open Wall   Q Back"
        safe_addstr(stdscr, sh - 2, 3, footer, curses.color_pair(C_DIM))

        stdscr.refresh()
        ch = stdscr.getch()

        if ch == curses.KEY_UP:
            if sel > 0:
                sel -= 1
                if sel < scroll:
                    scroll -= 1
        elif ch == curses.KEY_DOWN:
            if sel < len(walls) - 1:
                sel += 1
                if sel >= scroll + list_h:
                    scroll += 1
        elif ch in (curses.KEY_ENTER, 10, 13):
            screen_wall_detail(stdscr, walls, segs, sel)
        elif ch in (ord("q"), ord("Q"), 27):
            return

# -------------------------------------------------------------
#  SCREEN: WALL DETAIL
# -------------------------------------------------------------


def screen_wall_detail(stdscr, walls, segs, wall_idx):
    sel = 0
    scroll = 0

    while True:
        wall = walls[wall_idx]
        name = wall["wall_name"]
        ws = segs_for_wall(segs, name)
        tot = wall_totals(segs, name)

        stdscr.erase()
        sh, sw = stdscr.getmaxyx()
        draw_box(stdscr, 0, 0, sh, sw, C_BORDER)

        center_text(stdscr, 1, " \U0001f9f1  " + name + " ",
                    curses.color_pair(C_TITLE) | curses.A_BOLD)

        summary = "  Segments: {}   Total area: {:.2f} m2   Total bricks: {}".format(
            tot["segments"], tot["area_m2"], tot["bricks"])
        safe_addstr(stdscr, 2, 2, summary[:sw - 4],
                    curses.color_pair(C_HEADER))

        hdr = "  {:>3}  {:>8}  {:>9}  {:>8}  {:<10}  {:>8}".format(
            "#", "Width m", "Height m", "Area m2", "Type", "Bricks")
        safe_addstr(stdscr, 4, 2, hdr[:sw - 4],
                    curses.color_pair(C_HEADER) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 2, "─" * (sw - 5),
                    curses.color_pair(C_BORDER))

        list_h = sh - 11
        visible_segs = ws[scroll: scroll + list_h]

        if not ws:
            center_text(stdscr, 7,
                        "No segments yet - press  A  to add one",
                        curses.color_pair(C_DIM))
        else:
            for i, s in enumerate(visible_segs):
                g_idx = scroll + i
                row = 6 + i
                text = "  {:>3}  {:>8.2f}  {:>9.2f}  {:>8.2f}  {:<10}  {:>8}".format(
                    g_idx + 1,
                    float(s["width_m"]),
                    float(s["height_m"]),
                    float(s["area_m2"]),
                    s["brick_type"],
                    s["bricks_needed"])
                attr = (curses.color_pair(C_SELECTED) | curses.A_BOLD
                        if g_idx == sel else curses.color_pair(C_NORMAL))
                safe_addstr(stdscr, row, 2, text[:sw - 4], attr)

        safe_addstr(stdscr, sh - 5, 2, "\u2500" * (sw - 5),
                    curses.color_pair(C_BORDER))
        hdr = "  {:>3}  {:>8}  {:>9}  {:>8}  {:<10}  {:>8}".format(
            "#", "Width m", "Height m", "Area m2", "Type", "Bricks")
        safe_addstr(stdscr, 4, 2, hdr[:sw - 4],
                    curses.color_pair(C_HEADER) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 2, "─" * (sw - 5),
                    curses.color_pair(C_BORDER))

        footer = "\u2191\u2193 Navigate   A Add   E Edit   D Delete segment   Q Back"
        safe_addstr(stdscr, sh - 2, 3, footer[:sw - 4],
                    curses.color_pair(C_DIM))

        stdscr.refresh()
        ch = stdscr.getch()

        if ch == curses.KEY_UP:
            if sel > 0:
                sel -= 1
                if sel < scroll:
                    scroll -= 1
        elif ch == curses.KEY_DOWN:
            if ws and sel < len(ws) - 1:
                sel += 1
                if sel >= scroll + list_h:
                    scroll += 1
        elif ch in (ord("a"), ord("A")):
            _add_segment(stdscr, walls, segs, wall_idx)
            ws_new = segs_for_wall(segs, name)
            sel = max(0, len(ws_new) - 1)
            scroll = max(0, sel - list_h + 1)
        elif ch in (ord("e"), ord("E")):
            if ws:
                _edit_segment(stdscr, walls, segs, wall_idx, sel)
        elif ch in (ord("d"), ord("D")):
            if ws:
                _delete_segment(stdscr, walls, segs, wall_idx, sel)
                ws_new = segs_for_wall(segs, name)
                sel = max(0, min(sel, len(ws_new) - 1))
                scroll = max(0, min(scroll, max(0, len(ws_new) - list_h)))
        elif ch in (ord("q"), ord("Q"), 27):
            return

# -------------------------------------------------------------
#  SEGMENT OPERATIONS
# -------------------------------------------------------------


_BRICK_LABEL = "Brick type  (10 / 25 / 30 / 38 / classic)"


def _add_segment(stdscr, walls, segs, wall_idx):
    wall = walls[wall_idx]
    name = wall["wall_name"]

    result = modal_input_form(
        stdscr,
        "\u2795  Add Segment to \'" + name + "\'",
        [
            {"label": "Width (m)",  "default": "",
             "validator": val_positive_float},
            {"label": "Height (m)", "default": "",
             "validator": val_positive_float},
            {"label": _BRICK_LABEL, "default": "38", "validator": val_brick_type},
        ],
    )
    if result is None:
        return

    w_m = float(result["Width (m)"].replace(",", "."))
    h_m = float(result["Height (m)"].replace(",", "."))
    btype = result[_BRICK_LABEL].strip().lower()
    calc = calculate_bricks(w_m, h_m, btype)

    existing = segs_for_wall(segs, name)
    seg = {
        "wall_name":     name,
        "seg_index":     len(existing),
        "width_m":       round(w_m, 4),
        "height_m":      round(h_m, 4),
        "brick_type":    btype,
        "area_m2":       calc["area_m2"],
        "bricks_needed": calc["bricks_needed"],
    }
    segs.append(seg)
    save_segments(segs)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    walls[wall_idx]["last_modified"] = now
    save_walls(walls)

    modal_message(
        stdscr, "\u2705  Segment Added",
        [
            "Width  : " + str(w_m) + " m",
            "Height : " + str(h_m) + " m",
            "Type   : " + BRICK_TYPES[btype]["label"],
            "Area   : " + str(calc["area_m2"]) + " m2",
            "Bricks : " + str(calc["bricks_needed"]) + " pcs",
        ],
        C_OK,
    )


def _edit_segment(stdscr, walls, segs, wall_idx, seg_sel):
    wall = walls[wall_idx]
    name = wall["wall_name"]
    ws = segs_for_wall(segs, name)
    if not ws or seg_sel >= len(ws):
        return

    seg = ws[seg_sel]

    result = modal_input_form(
        stdscr,
        "Edit Segment #" + str(seg_sel + 1) + " of \'" + name + "\'",
        [
            {"label": "Width (m)",  "default": str(seg["width_m"]),
             "validator": val_positive_float},
            {"label": "Height (m)", "default": str(seg["height_m"]),
             "validator": val_positive_float},
            {"label": _BRICK_LABEL, "default": seg["brick_type"],
             "validator": val_brick_type},
        ],
    )
    if result is None:
        return

    w_m = float(result["Width (m)"].replace(",", "."))
    h_m = float(result["Height (m)"].replace(",", "."))
    btype = result[_BRICK_LABEL].strip().lower()
    calc = calculate_bricks(w_m, h_m, btype)

    seg["width_m"] = round(w_m, 4)
    seg["height_m"] = round(h_m, 4)
    seg["brick_type"] = btype
    seg["area_m2"] = calc["area_m2"]
    seg["bricks_needed"] = calc["bricks_needed"]
    save_segments(segs)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    walls[wall_idx]["last_modified"] = now
    save_walls(walls)

    modal_message(
        stdscr, "\u2705  Segment Updated",
        [
            "Width  : " + str(w_m) + " m",
            "Height : " + str(h_m) + " m",
            "Type   : " + BRICK_TYPES[btype]["label"],
            "Area   : " + str(calc["area_m2"]) + " m2",
            "Bricks : " + str(calc["bricks_needed"]) + " pcs",
        ],
        C_OK,
    )


def _delete_segment(stdscr, walls, segs, wall_idx, seg_sel):
    wall = walls[wall_idx]
    name = wall["wall_name"]
    ws = segs_for_wall(segs, name)
    if not ws or seg_sel >= len(ws):
        return

    seg = ws[seg_sel]
    if not modal_confirm(
        stdscr, "Delete Segment",
        "Delete segment #" + str(seg_sel + 1) +
        "  (" + str(seg["width_m"]) + " m x " + str(seg["height_m"]) + " m)?"
    ):
        return

    segs.remove(seg)
    for i, s in enumerate(segs_for_wall(segs, name)):
        s["seg_index"] = i
    save_segments(segs)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    walls[wall_idx]["last_modified"] = now
    save_walls(walls)

# -------------------------------------------------------------
#  ENTRY POINT
# -------------------------------------------------------------


def _run(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()

    walls = load_walls()
    segs = load_segments()

    screen_main(stdscr, walls, segs)


def main():
    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass
    print("\\n  \U0001f44b  Goodbye! Happy building! \U0001f3e0\\n")


if __name__ == "__main__":
    main()
