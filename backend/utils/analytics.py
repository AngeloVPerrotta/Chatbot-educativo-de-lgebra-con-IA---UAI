import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = '/tmp/analytics.db'


def _get_conn():
    return sqlite3.connect(DB_PATH)


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (datetime('now')),
                session_id TEXT,
                topic TEXT,
                user_message_length INTEGER,
                bot_response_length INTEGER,
                response_time_ms INTEGER
            )
        """)
        # Backward-compatible migration: add user_email if not present
        try:
            conn.execute("ALTER TABLE interactions ADD COLUMN user_email TEXT")
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT (datetime('now')),
                tokens_used INTEGER DEFAULT 0,
                token_limit INTEGER DEFAULT 50000
            )
        """)
        conn.commit()


_init_db()


def log_interaction(
    session_id: str,
    topic: str,
    user_msg_len: int,
    bot_resp_len: int,
    response_time_ms: int,
    user_email: Optional[str] = None,
):
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO interactions
                (session_id, topic, user_message_length, bot_response_length, response_time_ms, user_email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, topic, user_msg_len, bot_resp_len, response_time_ms, user_email),
        )
        conn.commit()


# --- User management ---

def register_user(name: str, email: str) -> dict:
    """Returns {'ok': True, 'user': {...}} or {'ok': False, 'error': '...'}."""
    try:
        with _get_conn() as conn:
            conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
            conn.commit()
        return {"ok": True, "user": get_user_by_email(email)}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "El email ya está registrado"}


def get_user_by_email(email: str) -> Optional[dict]:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def add_tokens_used(email: str, tokens: int):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET tokens_used = tokens_used + ? WHERE email = ?",
            (tokens, email),
        )
        conn.commit()


def check_token_limit(email: str) -> bool:
    """Returns True if the user can still send messages, False if limit exceeded."""
    user = get_user_by_email(email)
    if not user:
        return True  # Unknown user — don't block
    return user["tokens_used"] < user["token_limit"]


def get_all_users() -> list:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, email, created_at, tokens_used, token_limit FROM users ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# --- Existing analytics ---

def get_stats() -> dict:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row

        total = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]
        unique = conn.execute("SELECT COUNT(DISTINCT session_id) as c FROM interactions").fetchone()["c"]
        avg_resp = conn.execute("SELECT AVG(bot_response_length) as a FROM interactions").fetchone()["a"] or 0.0

        by_day_rows = conn.execute(
            """
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM interactions
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
            """
        ).fetchall()

        top_topics_rows = conn.execute(
            """
            SELECT topic, COUNT(*) as count
            FROM interactions
            GROUP BY topic
            ORDER BY count DESC
            LIMIT 10
            """
        ).fetchall()

    return {
        "total_interactions": total,
        "unique_sessions": unique,
        "avg_response_length": round(avg_resp, 2),
        "interactions_by_day": [{"date": r["date"], "count": r["count"]} for r in by_day_rows],
        "top_topics": [{"topic": r["topic"], "count": r["count"]} for r in top_topics_rows],
    }


def get_recent_interactions(limit: int = 50) -> list:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, timestamp, session_id, topic, user_message_length, bot_response_length, response_time_ms, user_email
            FROM interactions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
