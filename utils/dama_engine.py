"""
Rules engine for Italian draughts (dama italiana).

Board: 8x8, squares are (file, rank) with file 0-7 = a-h and rank 0-7 = 1-8.
Only the dark squares are used: (file + rank) is odd (so a1 is light, h1 is dark).
White starts on ranks 1-3 and moves up, Black starts on ranks 6-8 and moves down.

Rules implemented
  * Men move one step diagonally forward and capture only forward, one step over an adjacent enemy.
  * Kings ("dame") move and capture one step in every diagonal direction (they do not fly).
  * A man can never capture a king.
  * Capturing is compulsory and the best capture must be taken, in this order of priority:
      1. the sequence that captures the most pieces
      2. if equal, the one made with a king rather than a man
      3. if equal, the one that captures the most kings
      4. if equal, the one that captures a king earliest
  * Captured pieces are removed after the whole sequence (they can't be jumped twice).
  * A man that reaches the far rank becomes a king and its move ends there.
  * No legal move = loss. Threefold repetition and 40 plies without a capture or a man move = draw.
"""
import json
import re
from collections import namedtuple

Move = namedtuple("Move", "path captured")   # path: tuple of squares, captured: tuple of squares

FILES = "abcdefgh"
START_RANKS_WHITE = (0, 1, 2)
START_RANKS_BLACK = (5, 6, 7)
IDLE_DRAW_PLIES = 40
SQUARE_RE = re.compile(r"[a-h][1-8]", re.I)


def is_dark(sq) -> bool:
    return (sq[0] + sq[1]) % 2 == 1


def on_board(sq) -> bool:
    return 0 <= sq[0] < 8 and 0 <= sq[1] < 8


def name(sq) -> str:
    return f"{FILES[sq[0]]}{sq[1] + 1}"


def parse_square(text: str):
    return (FILES.index(text[0].lower()), int(text[1]) - 1)


def describe(move: Move) -> str:
    sep = "x" if move.captured else "-"
    return sep.join(name(s) for s in move.path)


def colour_of(piece: str) -> str:
    return "white" if piece.lower() == "w" else "black"


# ------------------------------------------------------------------ position

DARK_SQUARES = [(f, r) for r in range(8) for f in range(8) if is_dark((f, r))]   # 32, rank by rank


def initial_pieces() -> dict:
    pieces = {}
    for sq in DARK_SQUARES:
        if sq[1] in START_RANKS_WHITE:
            pieces[sq] = "w"
        elif sq[1] in START_RANKS_BLACK:
            pieces[sq] = "b"
    return pieces


def pieces_to_str(pieces: dict) -> str:
    return "".join(pieces.get(sq, ".") for sq in DARK_SQUARES)


def str_to_pieces(text: str) -> dict:
    return {sq: ch for sq, ch in zip(DARK_SQUARES, text) if ch != "."}


def _key(pieces: dict, turn: str) -> str:
    return pieces_to_str(pieces) + turn[0]


# ------------------------------------------------------------------ saved state

def initial_state() -> str:
    pieces = initial_pieces()
    return json.dumps({"b": pieces_to_str(pieces), "rep": {_key(pieces, "white"): 1}, "idle": 0})


def load_state(text: str):
    data = json.loads(text)
    return str_to_pieces(data["b"]), data["rep"], data["idle"]


# ------------------------------------------------------------------ move generation

def _directions(piece: str):
    if piece.isupper():
        return [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    dr = 1 if piece == "w" else -1
    return [(-1, dr), (1, dr)]


def _promotion_rank(colour: str) -> int:
    return 7 if colour == "white" else 0


def _captures_from(pieces: dict, origin) -> list:
    """All complete capture sequences for the piece standing on `origin`."""
    piece = pieces[origin]
    colour = colour_of(piece)
    results = []

    def dfs(pos, is_king, path, captured):
        extended = False
        for dx, dy in _directions("W" if is_king else piece):
            mid = (pos[0] + dx, pos[1] + dy)
            land = (pos[0] + 2 * dx, pos[1] + 2 * dy)
            if not on_board(land) or mid in captured:
                continue
            target = pieces.get(mid)
            if target is None or colour_of(target) == colour:
                continue
            if not is_king and target.isupper():          # a man can't take a king
                continue
            if land in pieces and land != origin:          # captured pieces still block until the end
                continue
            extended = True
            new_path, new_captured = path + [land], captured + [mid]
            if not is_king and land[1] == _promotion_rank(colour):
                results.append(Move(tuple(new_path), tuple(new_captured)))   # promotion ends the move
            else:
                dfs(land, is_king, new_path, new_captured)
        if not extended and captured:
            results.append(Move(tuple(path), tuple(captured)))

    dfs(origin, piece.isupper(), [origin], [])
    return results


def _priority(pieces: dict, move: Move):
    mover_is_king = pieces[move.path[0]].isupper()
    kings = [i for i, sq in enumerate(move.captured) if pieces[sq].isupper()]
    first_king = kings[0] if kings else 99
    return (len(move.captured), mover_is_king, len(kings), -first_king)


def legal_moves(pieces: dict, colour: str) -> list:
    own = [sq for sq, p in pieces.items() if colour_of(p) == colour]

    captures = []
    for sq in own:
        captures.extend(_captures_from(pieces, sq))
    if captures:
        best = max(_priority(pieces, m) for m in captures)
        return [m for m in captures if _priority(pieces, m) == best]

    moves = []
    for sq in own:
        for dx, dy in _directions(pieces[sq]):
            dest = (sq[0] + dx, sq[1] + dy)
            if on_board(dest) and dest not in pieces:
                moves.append(Move((sq, dest), ()))
    return moves


def apply_move(pieces: dict, move: Move) -> dict:
    """Returns the new position (the input is not modified)."""
    new = dict(pieces)
    piece = new.pop(move.path[0])
    for sq in move.captured:
        del new[sq]
    end = move.path[-1]
    if piece == "w" and end[1] == 7:
        piece = "W"
    elif piece == "b" and end[1] == 0:
        piece = "B"
    new[end] = piece
    return new


# ------------------------------------------------------------------ turning text into a move

def find_move(legal: list, text: str):
    """Understands 'c3 d4', 'c3-d4', 'c3xe5', 'c3 e5 g7'. Returns (move, error)."""
    squares = [parse_square(s) for s in SQUARE_RE.findall(text)]
    if len(squares) < 2:
        return None, "Write your move with the starting and the landing square, e.g. `c3 d4` or `c3 e5 g7`."

    exact = [m for m in legal if m.path == tuple(squares)]
    if len(exact) == 1:
        return exact[0], None
    ends = [m for m in legal if m.path[0] == squares[0] and m.path[-1] == squares[-1]]
    if len(ends) == 1:
        return ends[0], None
    if len(ends) > 1:
        options = ", ".join(f"`{describe(m)}`" for m in ends)
        return None, f"Two captures end there — write the whole path: {options}."
    return None, None


def legal_summary(legal: list, limit: int = 8) -> str:
    shown = ", ".join(f"`{describe(m)}`" for m in legal[:limit])
    return shown + (" …" if len(legal) > limit else "")


# ------------------------------------------------------------------ one full turn

class Result:
    def __init__(self, pieces, state, outcome=None, reason=None):
        self.pieces = pieces
        self.state = state          # new JSON state to save
        self.outcome = outcome      # None | "win" | "draw"
        self.reason = reason


def play(state_text: str, turn: str, move: Move) -> Result:
    """Applies `move` for the side `turn` and reports whether the game ended."""
    pieces, rep, idle = load_state(state_text)
    mover_piece = pieces[move.path[0]]
    pieces = apply_move(pieces, move)

    idle = 0 if (move.captured or not mover_piece.isupper()) else idle + 1
    nxt = "black" if turn == "white" else "white"
    key = _key(pieces, nxt)
    rep[key] = rep.get(key, 0) + 1
    state = json.dumps({"b": pieces_to_str(pieces), "rep": rep, "idle": idle})

    if not any(colour_of(p) == nxt for p in pieces.values()):
        return Result(pieces, state, "win", "capturing every piece")
    if not legal_moves(pieces, nxt):
        return Result(pieces, state, "win", "leaving no legal move")
    if rep[key] >= 3:
        return Result(pieces, state, "draw", "threefold repetition")
    if idle >= IDLE_DRAW_PLIES:
        return Result(pieces, state, "draw", "40 moves without a capture or a man move")
    return Result(pieces, state)
