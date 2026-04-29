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
        try:
            conn.execute("ALTER TABLE interactions ADD COLUMN rag_confidence TEXT")
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
        # Backward-compatible migration: add pin if not present
        try:
            conn.execute("ALTER TABLE users ADD COLUMN pin TEXT")
        except Exception:
            pass
        # Backward-compatible migration: add is_admin if not present
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                rating INTEGER NOT NULL,
                message TEXT,
                created_at DATETIME DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT (datetime('now'))
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
    rag_confidence: Optional[str] = None,
):
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO interactions
                (session_id, topic, user_message_length, bot_response_length, response_time_ms, user_email, rag_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, topic, user_msg_len, bot_resp_len, response_time_ms, user_email, rag_confidence),
        )
        conn.commit()


# --- User management ---

def register_user(name: str, email: str, pin: str) -> dict:
    """Returns {'ok': True, 'user': {...}} or {'ok': False, 'error': '...'}."""
    try:
        with _get_conn() as conn:
            conn.execute("INSERT INTO users (name, email, pin) VALUES (?, ?, ?)", (name, email, pin))
            conn.commit()
        return {"ok": True, "user": get_user_by_email(email)}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "El email ya está registrado"}


def get_user_by_email(email: str) -> Optional[dict]:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, email, created_at, tokens_used, token_limit FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return dict(row) if row else None


def verify_pin(email: str, pin: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT pin FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        return row[0] == pin


def set_admin(email: str):
    with _get_conn() as conn:
        conn.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
        conn.commit()


def is_admin_user(email: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT is_admin FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        return bool(row[0])


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

        rag_rows = conn.execute(
            """
            SELECT COALESCE(rag_confidence, 'none') as conf, COUNT(*) as count
            FROM interactions
            GROUP BY conf
            """
        ).fetchall()

    rag_stats = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for r in rag_rows:
        key = r["conf"] if r["conf"] in rag_stats else "none"
        rag_stats[key] += r["count"]

    return {
        "total_interactions": total,
        "unique_sessions": unique,
        "avg_response_length": round(avg_resp, 2),
        "interactions_by_day": [{"date": r["date"], "count": r["count"]} for r in by_day_rows],
        "top_topics": [{"topic": r["topic"], "count": r["count"]} for r in top_topics_rows],
        "rag_stats": rag_stats,
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


# --- Feedback ---

def save_feedback(user_email: str, rating: int, message: Optional[str] = None):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO feedback (user_email, rating, message) VALUES (?, ?, ?)",
            (user_email, rating, message),
        )
        conn.commit()


def get_feedback_stats() -> dict:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) as c FROM feedback").fetchone()["c"]
        avg = conn.execute("SELECT AVG(rating) as a FROM feedback").fetchone()["a"] or 0.0
        dist_rows = conn.execute(
            "SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating ORDER BY rating"
        ).fetchall()
    distribution = {str(i): 0 for i in range(1, 6)}
    for r in dist_rows:
        distribution[str(r["rating"])] = r["count"]
    return {
        "average_rating": round(avg, 2),
        "total_feedback": total,
        "rating_distribution": distribution,
    }


def get_recent_feedback(limit: int = 20) -> list:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, user_email, rating, message, created_at FROM feedback ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Chat history ---

def save_chat_message(user_email: str, session_id: str, role: str, content: str):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_history (user_email, session_id, role, content) VALUES (?, ?, ?, ?)",
            (user_email, session_id, role, content),
        )
        conn.commit()


def get_user_sessions(email: str) -> list:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT h.session_id,
                   MIN(h.created_at) as started_at,
                   (SELECT h2.content FROM chat_history h2
                    WHERE h2.session_id = h.session_id AND h2.role = 'user'
                    ORDER BY h2.id ASC LIMIT 1) as preview
            FROM chat_history h
            WHERE h.user_email = ?
            GROUP BY h.session_id
            ORDER BY started_at DESC
            """,
            (email,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_messages(session_id: str) -> list:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM chat_history WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]
