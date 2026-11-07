"""
Draws chess and checkers boards as PNG images (Pillow), plus plain-text fallbacks.

The chess pieces use the Unicode chess glyphs of the bundled DejaVu Sans font
(assets/fonts/DejaVuSans.ttf), so nothing has to be installed on the server.
"""
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SQUARE = 72
MARGIN = 30
BOARD = SQUARE * 8
SIZE = BOARD + 2 * MARGIN

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"

MARGIN_BG = (43, 43, 43)
LABEL_FG = (205, 205, 205)

CHESS_LIGHT = (240, 217, 181)
CHESS_DARK = (181, 136, 99)
CHECKERS_LIGHT = (238, 238, 210)
CHECKERS_DARK = (118, 150, 86)

LAST_MOVE = (255, 235, 59, 105)
CHECK = (230, 30, 30, 140)

CHESS_GLYPHS = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}


class BoardImageError(RuntimeError):
    pass


@lru_cache(maxsize=8)
def _font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (str(FONT_PATH), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    raise BoardImageError("DejaVu Sans font not found (expected at assets/fonts/DejaVuSans.ttf)")


def _label_font():
    try:
        return _font(18)
    except BoardImageError:
        return ImageFont.load_default()


def _square_box(file: int, rank: int):
    """Pixel box of a square. file 0-7 = a-h, rank 0-7 = 1-8; white is at the bottom."""
    x = MARGIN + file * SQUARE
    y = MARGIN + (7 - rank) * SQUARE
    return (x, y, x + SQUARE, y + SQUARE)


def _center(file: int, rank: int):
    x0, y0, x1, y1 = _square_box(file, rank)
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _canvas(light, dark, dark_when_sum_is_odd: bool):
    """Empty board with coordinates. `dark_when_sum_is_odd` picks which diagonal is dark
    (chess: a1 is dark -> sum even; Italian dama: a1 is light -> sum odd)."""
    img = Image.new("RGB", (SIZE, SIZE), MARGIN_BG)
    draw = ImageDraw.Draw(img, "RGBA")
    font = _label_font()
    for rank in range(8):
        for file in range(8):
            is_dark = ((file + rank) % 2 == 1) == dark_when_sum_is_odd
            draw.rectangle(_square_box(file, rank), fill=dark if is_dark else light)
    for i in range(8):
        cx, _ = _center(i, 0)
        draw.text((cx, SIZE - MARGIN / 2), "abcdefgh"[i], font=font, fill=LABEL_FG, anchor="mm")
        draw.text((cx, MARGIN / 2), "abcdefgh"[i], font=font, fill=LABEL_FG, anchor="mm")
        _, cy = _center(0, i)
        draw.text((MARGIN / 2, cy), str(i + 1), font=font, fill=LABEL_FG, anchor="mm")
        draw.text((SIZE - MARGIN / 2, cy), str(i + 1), font=font, fill=LABEL_FG, anchor="mm")
    return img, draw


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ------------------------------------------------------------------ chess

def render_chess(board, last_move=None) -> bytes:
    """`board` is a python-chess Board; `last_move` an optional chess.Move to highlight."""
    import chess  # local import: only needed for chess

    img, draw = _canvas(CHESS_LIGHT, CHESS_DARK, dark_when_sum_is_odd=False)

    if last_move is not None:
        for sq in (last_move.from_square, last_move.to_square):
            draw.rectangle(_square_box(chess.square_file(sq), chess.square_rank(sq)), fill=LAST_MOVE)
    if board.is_check():
        ksq = board.king(board.turn)
        draw.rectangle(_square_box(chess.square_file(ksq), chess.square_rank(ksq)), fill=CHECK)

    font = _font(58)
    for sq, piece in board.piece_map().items():
        cx, cy = _center(chess.square_file(sq), chess.square_rank(sq))
        glyph = CHESS_GLYPHS[piece.symbol().lower()]
        if piece.color == chess.WHITE:
            draw.text((cx, cy + 2), glyph, font=font, fill=(255, 255, 255), anchor="mm",
                      stroke_width=2, stroke_fill=(15, 15, 15))
        else:
            draw.text((cx, cy + 2), glyph, font=font, fill=(25, 25, 25), anchor="mm",
                      stroke_width=1, stroke_fill=(235, 235, 235))
    return _to_png(img)


def chess_text(board) -> str:
    """Plain-text board (uppercase = white, lowercase = black)."""
    lines = ["  a b c d e f g h"]
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            piece = board.piece_at(rank * 8 + file)
            row.append(piece.symbol() if piece else ".")
        lines.append(f"{rank + 1} " + " ".join(row) + f" {rank + 1}")
    lines.append("  a b c d e f g h")
    return "\n".join(lines)


# --------------------------------------------------------------- checkers

def _crown(draw, cx, cy, s):
    pts = [(-1.0, 0.7), (-1.0, -0.6), (-0.5, 0.05), (0.0, -0.8), (0.5, 0.05), (1.0, -0.6), (1.0, 0.7)]
    poly = [(cx + x * s, cy + y * s) for x, y in pts]
    draw.polygon(poly, fill=(255, 205, 40), outline=(110, 75, 0))
    draw.line(poly + [poly[0]], fill=(110, 75, 0), width=2)


def render_checkers(pieces: dict, last_path=()) -> bytes:
    """`pieces` maps (file, rank) -> 'w' | 'W' | 'b' | 'B' (uppercase = king).
    `last_path` is a sequence of (file, rank) squares to highlight."""
    img, draw = _canvas(CHECKERS_LIGHT, CHECKERS_DARK, dark_when_sum_is_odd=True)

    for file, rank in last_path:
        draw.rectangle(_square_box(file, rank), fill=LAST_MOVE)

    radius = SQUARE * 0.36
    for (file, rank), piece in pieces.items():
        cx, cy = _center(file, rank)
        white = piece.lower() == "w"
        fill, edge, inner = ((246, 246, 246), (130, 130, 130), (222, 222, 222)) if white \
            else ((45, 45, 45), (0, 0, 0), (80, 80, 80))
        draw.ellipse((cx - radius, cy - radius + 3, cx + radius, cy + radius + 3), fill=(0, 0, 0, 90))  # shadow
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill, outline=edge, width=3)
        r2 = radius * 0.68
        draw.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), outline=inner, width=2)
        if piece.isupper():
            _crown(draw, cx, cy, SQUARE * 0.17)
    return _to_png(img)


def checkers_text(pieces: dict) -> str:
    """Plain-text board (w/b = men, W/B = kings)."""
    lines = ["  a b c d e f g h"]
    for rank in range(7, -1, -1):
        row = [pieces.get((file, rank), "." if (file + rank) % 2 == 1 else " ") for file in range(8)]
        lines.append(f"{rank + 1} " + " ".join(row) + f" {rank + 1}")
    lines.append("  a b c d e f g h")
    return "\n".join(lines)
