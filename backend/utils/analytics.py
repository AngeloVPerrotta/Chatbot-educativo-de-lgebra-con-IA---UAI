import sqlite3
from pathlib import Path
from datetime import datetime

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
        conn.commit()


_init_db()


def log_interaction(session_id: str, topic: str, user_msg_len: int, bot_resp_len: int, response_time_ms: int):
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO interactions (session_id, topic, user_message_length, bot_response_length, response_time_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, topic, user_msg_len, bot_resp_len, response_time_ms)
        )
        conn.commit()


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
            SELECT id, timestamp, session_id, topic, user_message_length, bot_response_length, response_time_ms
            FROM interactions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
