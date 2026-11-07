"""
Simple SQLite persistence layer for the bot.

Kept intentionally lightweight (plain sqlite3, no ORM) so the whole
project can run with zero external services. Good enough for a
single-process bot on one or a handful of servers.
"""
import os
import sqlite3
import json
import time
from pathlib import Path

def _resolve_db_path() -> Path:
    """Where the SQLite file lives. Priority:
    1. DB_PATH environment variable (explicit choice)
    2. RAILWAY_VOLUME_MOUNT_PATH (set automatically by Railway when a Volume is attached)
    3. next to this script (fine locally, but WIPED on every Railway deploy)
    """
    explicit = os.getenv("DB_PATH")
    if explicit:
        return Path(explicit)
    volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if volume:
        return Path(volume) / "bot_data.sqlite3"
    return Path(__file__).parent / "bot_data.sqlite3"


DB_PATH = _resolve_db_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

ON_RAILWAY = any(os.getenv(k) for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"))
RAILWAY_VOLUME = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")


def storage_status():
    """Returns (is_persistent, explanation). On Railway the disk is wiped at every deploy
    unless the database sits inside an attached Volume."""
    if not ON_RAILWAY:
        return True, "Running outside Railway: the database file is kept on this machine's disk."
    if not RAILWAY_VOLUME:
        return False, (
            "No Railway Volume is attached to this service, so the database is wiped at every "
            "deploy/restart (levels and points reset). Attach a Volume to fix it."
        )
    volume = Path(RAILWAY_VOLUME)
    if volume == DB_PATH.parent or volume in DB_PATH.parents:
        return True, f"Database is stored on the Railway Volume mounted at {RAILWAY_VOLUME}."
    return False, (
        f"A Volume is mounted at {RAILWAY_VOLUME}, but the database is at {DB_PATH}, outside it, "
        "so it is still wiped at every deploy. Remove the DB_PATH variable or point it inside the Volume."
    )

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

        CREATE TABLE IF NOT EXISTS level_config (
            guild_id INTEGER PRIMARY KEY,
            announce_channel_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            prefix TEXT NOT NULL DEFAULT '?',
            allowed_channel_id INTEGER,
            trivia_cooldown_minutes INTEGER NOT NULL DEFAULT 5,
            rps_cooldown_minutes INTEGER NOT NULL DEFAULT 5
        );

        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            last_message_ts REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS board_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            game_type TEXT NOT NULL,              -- 'chess' | 'dama'
            white_id INTEGER NOT NULL,
            black_id INTEGER NOT NULL,
            state TEXT NOT NULL,                  -- chess: UCI moves; dama: serialized position
            turn TEXT NOT NULL DEFAULT 'white',
            moves_played INTEGER NOT NULL DEFAULT 0,
            last_move TEXT,
            draw_offer_by INTEGER,
            status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'finished'
            result TEXT,                          -- 'white' | 'black' | 'draw' | 'abandoned'
            reason TEXT,
            winner_id INTEGER,
            rewarded INTEGER NOT NULL DEFAULT 0,
            channel_id INTEGER,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            finished_at REAL
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

        CREATE TABLE IF NOT EXISTS banned_words (
            guild_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            last_said_ts REAL NOT NULL DEFAULT 0,
            last_callout_ts REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, word)
        );

        CREATE TABLE IF NOT EXISTS bannedword_config (
            guild_id INTEGER PRIMARY KEY,
            alerts_enabled INTEGER NOT NULL DEFAULT 1,
            cooldown_seconds INTEGER NOT NULL DEFAULT 1800
        );
        """
    )
    _conn.commit()


_init_db()

# Migrations for databases created before these columns existed
for _ddl in (
    "ALTER TABLE guild_settings ADD COLUMN allowed_channel_id INTEGER",
    "ALTER TABLE guild_settings ADD COLUMN trivia_cooldown_minutes INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE guild_settings ADD COLUMN rps_cooldown_minutes INTEGER NOT NULL DEFAULT 5",
):
    try:
        _conn.execute(_ddl)
        _conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


# ---------- Diagnostics ----------

def storage_report(guild_id: int) -> dict:
    """Small summary used by the /dbinfo command."""
    cur = _conn.cursor()
    xp_rows = cur.execute("SELECT COUNT(*) AS n FROM levels WHERE guild_id = ?", (guild_id,)).fetchone()["n"]
    point_rows = cur.execute("SELECT COUNT(*) AS n FROM points WHERE guild_id = ?", (guild_id,)).fetchone()["n"]
    try:
        size = DB_PATH.stat().st_size
    except OSError:
        size = 0
    return {"path": str(DB_PATH), "size_bytes": size, "members_with_xp": xp_rows, "members_with_points": point_rows}


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


def get_level_announce_channel(guild_id: int):
    """Returns the configured channel_id for level-up announcements, or None if not set."""
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT announce_channel_id FROM level_config WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return row["announce_channel_id"] if row else None


def set_level_announce_channel(guild_id: int, channel_id: int):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO level_config (guild_id, announce_channel_id) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET announce_channel_id = excluded.announce_channel_id
        """,
        (guild_id, channel_id),
    )
    _conn.commit()


# ---------- Guild settings: command prefix ----------

DEFAULT_PREFIX = "?"


def get_prefix(guild_id: int) -> str:
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT prefix FROM guild_settings WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return row["prefix"] if row else DEFAULT_PREFIX


def get_allowed_channel(guild_id: int):
    """Channel where bot commands are allowed, or None if unrestricted."""
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT allowed_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return row["allowed_channel_id"] if row else None


def set_allowed_channel(guild_id: int, channel_id):
    """Pass None to remove the restriction."""
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO guild_settings (guild_id, allowed_channel_id) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET allowed_channel_id = excluded.allowed_channel_id
        """,
        (guild_id, channel_id),
    )
    _conn.commit()


DEFAULT_TRIVIA_COOLDOWN_MINUTES = 5


def get_trivia_cooldown(guild_id: int) -> int:
    """Minutes each member must wait between /trivia questions (0 = no limit)."""
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT trivia_cooldown_minutes FROM guild_settings WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return row["trivia_cooldown_minutes"] if row else DEFAULT_TRIVIA_COOLDOWN_MINUTES


def set_trivia_cooldown(guild_id: int, minutes: int):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO guild_settings (guild_id, trivia_cooldown_minutes) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET trivia_cooldown_minutes = excluded.trivia_cooldown_minutes
        """,
        (guild_id, minutes),
    )
    _conn.commit()


def set_prefix(guild_id: int, prefix: str):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO guild_settings (guild_id, prefix) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix
        """,
        (guild_id, prefix),
    )
    _conn.commit()


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


# ---------- Board games (chess / dama) ----------

BOARD_GAME_EXPIRY_SECONDS = 7 * 24 * 3600  # an active game with no activity for a week is closed


def create_board_game(guild_id: int, game_type: str, white_id: int, black_id: int,
                      state: str, channel_id: int) -> int:
    now = time.time()
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO board_games (guild_id, game_type, white_id, black_id, state, turn,
                                 channel_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'white', ?, ?, ?)
        """,
        (guild_id, game_type, white_id, black_id, state, channel_id, now, now),
    )
    _conn.commit()
    return cur.lastrowid


def get_board_game(game_id: int):
    row = _conn.execute("SELECT * FROM board_games WHERE id = ?", (game_id,)).fetchone()
    return dict(row) if row else None


def get_active_board_game(guild_id: int, game_type: str, user_id: int):
    """The user's running game of this type, or None. Games idle for a week are closed here."""
    row = _conn.execute(
        """
        SELECT * FROM board_games
        WHERE guild_id = ? AND game_type = ? AND status = 'active' AND (white_id = ? OR black_id = ?)
        ORDER BY id DESC LIMIT 1
        """,
        (guild_id, game_type, user_id, user_id),
    ).fetchone()
    if row and time.time() - row["updated_at"] > BOARD_GAME_EXPIRY_SECONDS:
        finish_board_game(row["id"], "abandoned", "no activity for 7 days")
        return get_active_board_game(guild_id, game_type, user_id)
    return dict(row) if row else None


def save_board_game(game_id: int, state: str, turn: str, moves_played: int, last_move: str):
    _conn.execute(
        """
        UPDATE board_games
        SET state = ?, turn = ?, moves_played = ?, last_move = ?, draw_offer_by = NULL, updated_at = ?
        WHERE id = ?
        """,
        (state, turn, moves_played, last_move, time.time(), game_id),
    )
    _conn.commit()


def set_board_game_draw_offer(game_id: int, user_id: int):
    _conn.execute(
        "UPDATE board_games SET draw_offer_by = ?, updated_at = ? WHERE id = ?",
        (user_id, time.time(), game_id),
    )
    _conn.commit()


def finish_board_game(game_id: int, result: str, reason: str, winner_id=None, rewarded: bool = False):
    now = time.time()
    _conn.execute(
        """
        UPDATE board_games
        SET status = 'finished', result = ?, reason = ?, winner_id = ?, rewarded = ?,
            finished_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (result, reason, winner_id, 1 if rewarded else 0, now, now, game_id),
    )
    _conn.commit()


def count_rewarded_board_wins(guild_id: int, user_id: int, since: float, against_id=None) -> int:
    """How many rewarded wins `user_id` got since `since` (optionally only against one opponent)."""
    query = ("SELECT COUNT(*) AS n FROM board_games "
             "WHERE guild_id = ? AND winner_id = ? AND rewarded = 1 AND finished_at >= ?")
    params = [guild_id, user_id, since]
    if against_id is not None:
        query += " AND (white_id = ? OR black_id = ?)"
        params += [against_id, against_id]
    return _conn.execute(query, params).fetchone()["n"]


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


# ---------- Banned words ----------

DEFAULT_BANNEDWORD_COOLDOWN_SECONDS = 1800  # 30 minutes, same default as the reference bot


def add_banned_word(guild_id: int, word: str):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO banned_words (guild_id, word) VALUES (?, ?)
        ON CONFLICT(guild_id, word) DO NOTHING
        """,
        (guild_id, word.lower()),
    )
    _conn.commit()


def remove_banned_word(guild_id: int, word: str) -> bool:
    cur = _conn.cursor()
    cur.execute(
        "DELETE FROM banned_words WHERE guild_id = ? AND word = ?",
        (guild_id, word.lower()),
    )
    _conn.commit()
    return cur.rowcount > 0


def list_banned_words(guild_id: int):
    cur = _conn.cursor()
    rows = cur.execute(
        "SELECT word, last_said_ts, last_callout_ts FROM banned_words WHERE guild_id = ? ORDER BY word",
        (guild_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_banned_word_said(guild_id: int, word: str, when: float):
    cur = _conn.cursor()
    cur.execute(
        "UPDATE banned_words SET last_said_ts = ? WHERE guild_id = ? AND word = ?",
        (when, guild_id, word.lower()),
    )
    _conn.commit()


def mark_banned_word_called_out(guild_id: int, word: str, when: float):
    cur = _conn.cursor()
    cur.execute(
        "UPDATE banned_words SET last_callout_ts = ? WHERE guild_id = ? AND word = ?",
        (when, guild_id, word.lower()),
    )
    _conn.commit()


def get_bannedword_config(guild_id: int):
    cur = _conn.cursor()
    row = cur.execute(
        "SELECT alerts_enabled, cooldown_seconds FROM bannedword_config WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    if row:
        return {"alerts_enabled": bool(row["alerts_enabled"]), "cooldown_seconds": row["cooldown_seconds"]}
    return {"alerts_enabled": True, "cooldown_seconds": DEFAULT_BANNEDWORD_COOLDOWN_SECONDS}


def set_bannedword_alerts(guild_id: int, enabled: bool):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO bannedword_config (guild_id, alerts_enabled) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET alerts_enabled = excluded.alerts_enabled
        """,
        (guild_id, int(enabled)),
    )
    _conn.commit()


def set_bannedword_cooldown(guild_id: int, seconds: int):
    cur = _conn.cursor()
    cur.execute(
        """
        INSERT INTO bannedword_config (guild_id, cooldown_seconds) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET cooldown_seconds = excluded.cooldown_seconds
        """,
        (guild_id, seconds),
    )
    _conn.commit()


DEFAULT_RPS_COOLDOWN_MINUTES = 5


def get_rps_cooldown(guild_id: int) -> int:
    """Minutes each member must wait between /rps games (0 = no limit)."""
    row = _conn.execute(
        "SELECT rps_cooldown_minutes FROM guild_settings WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return row["rps_cooldown_minutes"] if row else DEFAULT_RPS_COOLDOWN_MINUTES


def set_rps_cooldown(guild_id: int, minutes: int):
    _conn.execute(
        """
        INSERT INTO guild_settings (guild_id, rps_cooldown_minutes) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET rps_cooldown_minutes = excluded.rps_cooldown_minutes
        """,
        (guild_id, minutes),
    )
    _conn.commit()
