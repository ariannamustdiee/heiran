"""
Simple SQLite persistence layer for the bot.

Kept intentionally lightweight (plain sqlite3, no ORM) so the whole
project can run with zero external services. Good enough for a
single-process bot on one or a handful of servers.
"""
import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "bot_data.sqlite3"

_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def _init_db():
    cur = _conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS points (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS counting_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            current_count INTEGER NOT NULL DEFAULT 0,
            last_user_id INTEGER,
            high_score INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS custom_roles (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            last_message_ts REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS sudoku_games (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            puzzle TEXT NOT NULL,
            solution TEXT NOT NULL,
            board TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            started_at REAL NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );
        """
    )
    _conn.commit()


_init_db()


# ---------- Points / economy ----------

def add_points(guild_id: int, user_id: int, amount: int) -> int:
    """Add (or subtract, if amount is negative) points. Returns new total."""
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO points (guild_id, user_id, points) VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET points = points + excluded.points
        """,
        (guild_id, user_id, amount),
    )
    _conn.commit()
    return get_points(guild_id, user_id)


def get_points(guild_id: int, user_id: int) -> int:
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT points FROM points WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    return row["points"] if row else 0


def get_leaderboard(guild_id: int, limit: int = 10):
    cur = _conn.cursor()
    rows = cur.execute(
        """
        SELECT user_id, points FROM points
        WHERE guild_id = ? ORDER BY points DESC LIMIT ?
        """,
        (guild_id, limit),
    ).fetchall()
    return [(r["user_id"], r["points"]) for r in rows]


# ---------- Counting game ----------

def get_counting_config(guild_id: int):
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT * FROM counting_config WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return dict(row) if row else None


def set_counting_channel(guild_id: int, channel_id: int):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO counting_config (guild_id, channel_id, current_count, last_user_id, high_score)
        VALUES (?, ?, 0, NULL, 0)
        ON CONFLICT(guild_id)
        DO UPDATE SET channel_id = excluded.channel_id, current_count = 0, last_user_id = NULL
        """,
        (guild_id, channel_id),
    )
    _conn.commit()


def update_counting(guild_id: int, new_count: int, last_user_id: int):
    cur = _conn.cursor()
    cfg = get_counting_config(guild_id)
    high_score = max(cfg["high_score"], new_count) if cfg else new_count
    cur.execute(
        """
        UPDATE counting_config
        SET current_count = ?, last_user_id = ?, high_score = ?
        WHERE guild_id = ?
        """,
        (new_count, last_user_id, high_score, guild_id),
    )
    _conn.commit()


def reset_counting(guild_id: int):
    update_counting(guild_id, 0, None)


# ---------- Leveling / XP ----------

def get_xp(guild_id: int, user_id: int) -> int:
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    return row["xp"] if row else 0


def get_last_message_ts(guild_id: int, user_id: int) -> float:
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT last_message_ts FROM levels WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    return row["last_message_ts"] if row else 0.0


def add_xp(guild_id: int, user_id: int, amount: int, message_ts: float) -> int:
    """Adds XP and records the message timestamp (for the anti-spam cooldown).
    Returns the new total XP."""
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO levels (guild_id, user_id, xp, last_message_ts) VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET xp = xp + excluded.xp, last_message_ts = excluded.last_message_ts
        """,
        (guild_id, user_id, amount, message_ts),
    )
    _conn.commit()
    return get_xp(guild_id, user_id)


def set_xp(guild_id: int, user_id: int, new_xp: int):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO levels (guild_id, user_id, xp, last_message_ts) VALUES (?, ?, ?, 0)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp
        """,
        (guild_id, user_id, new_xp),
    )
    _conn.commit()


def get_xp_leaderboard(guild_id: int, limit: int = 10):
    cur = _conn.cursor()
    rows = cur.execute(
        "SELECT user_id, xp FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit),
    ).fetchall()
    return [(r["user_id"], r["xp"]) for r in rows]


# ---------- Shop: custom color roles ----------

def get_custom_role(guild_id: int, user_id: int):
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT role_id FROM custom_roles WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    return row["role_id"] if row else None


def set_custom_role(guild_id: int, user_id: int, role_id: int):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO custom_roles (guild_id, user_id, role_id) VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET role_id = excluded.role_id
        """,
        (guild_id, user_id, role_id),
    )
    _conn.commit()


# ---------- Sudoku ----------

def save_sudoku_game(guild_id, user_id, puzzle, solution, board, difficulty):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO sudoku_games (guild_id, user_id, puzzle, solution, board, difficulty, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET puzzle=excluded.puzzle, solution=excluded.solution,
                      board=excluded.board, difficulty=excluded.difficulty,
                      started_at=excluded.started_at
        """,
        (
            guild_id,
            user_id,
            json.dumps(puzzle),
            json.dumps(solution),
            json.dumps(board),
            difficulty,
            time.time(),
        ),
    )
    _conn.commit()


def get_sudoku_game(guild_id, user_id):
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT * FROM sudoku_games WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    if not row:
        return None
    return {
        "puzzle": json.loads(row["puzzle"]),
        "solution": json.loads(row["solution"]),
        "board": json.loads(row["board"]),
        "difficulty": row["difficulty"],
        "started_at": row["started_at"],
    }


def update_sudoku_board(guild_id, user_id, board):
    cur = _conn.cursor()
    cur.execute(
        "UPDATE sudoku_games SET board = ? WHERE guild_id = ? AND user_id = ?",
        (json.dumps(board), guild_id, user_id),
    )
    _conn.commit()


def delete_sudoku_game(guild_id, user_id):
    cur = _conn.cursor()
    cur.execute(
        "DELETE FROM sudoku_games WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    _conn.commit()
