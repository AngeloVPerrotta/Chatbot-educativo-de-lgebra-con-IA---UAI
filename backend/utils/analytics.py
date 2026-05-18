import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = '/data/analytics.db' if os.path.exists('/data') else './analytics.db'


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
        # Backward-compatible migration: add role if not present
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        except Exception:
            pass

        # Ensure superadmins exist
        for sa_email, sa_name in [
            ("perrottangelo340@gmail.com", "Angelo Perrotta"),
            ("angelovalentin.perrotta@alumnos.uai.edu.ar", "Angelo Perrotta"),
        ]:
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (sa_email,)).fetchone()
            if existing:
                conn.execute("UPDATE users SET role = 'superadmin' WHERE email = ?", (sa_email,))
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO users (name, email, role) VALUES (?, ?, 'superadmin')",
                    (sa_name, sa_email),
                )
        conn.commit()

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

        # Legacy table rename (one-time migration)
        try:
            conn.execute("ALTER TABLE rate_limits RENAME TO rate_limits_legacy")
        except Exception:
            pass  # already renamed or doesn't exist

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits_legacy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT UNIQUE NOT NULL,
                message_count INTEGER DEFAULT 0,
                window_start DATETIME NOT NULL,
                created_at DATETIME DEFAULT (datetime('now')),
                bonus_messages INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                identifier TEXT PRIMARY KEY,
                message_count INTEGER DEFAULT 0,
                day TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_credits (
                email TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                last_topup DATETIME
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_email_links (
                fingerprint TEXT NOT NULL,
                email TEXT NOT NULL,
                first_seen DATETIME DEFAULT (datetime('now')),
                PRIMARY KEY (fingerprint, email)
            )
        """)

        # Migrate legacy bonus_messages → email_credits (identifiers with '@')
        try:
            conn.execute("""
                INSERT OR IGNORE INTO email_credits (email, balance, last_topup)
                SELECT identifier, bonus_messages, created_at
                FROM rate_limits_legacy
                WHERE identifier LIKE '%@%' AND COALESCE(bonus_messages, 0) > 0
            """)
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                description TEXT,
                page TEXT,
                created_at DATETIME DEFAULT (datetime('now')),
                status TEXT DEFAULT 'pending'
            )
        """)
        # Backward-compatible migration for legacy table
        try:
            conn.execute("ALTER TABLE rate_limits_legacy ADD COLUMN bonus_messages INTEGER DEFAULT 0")
        except Exception:
            pass


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

def get_or_create_user(name: Optional[str], email: str) -> dict:
    """Returns {'ok': True, 'user': {...}, 'created': bool} or {'ok': False, 'error': '...'}."""
    existing = get_user_by_email(email)
    if existing:
        return {"ok": True, "user": existing, "created": False}
    if not name:
        return {"ok": False, "error": "not_found"}
    try:
        with _get_conn() as conn:
            conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
            conn.commit()
        return {"ok": True, "user": get_user_by_email(email), "created": True}
    except sqlite3.IntegrityError:
        existing = get_user_by_email(email)
        return {"ok": True, "user": existing, "created": False}


def get_user_by_email(email: str) -> Optional[dict]:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, email, created_at, tokens_used, token_limit, role FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return dict(row) if row else None


def set_user_role(email: str, role: str):
    with _get_conn() as conn:
        conn.execute("UPDATE users SET role = ? WHERE email = ?", (role, email))
        conn.commit()


def is_admin_or_super(email: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT role FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        return row[0] in ("admin", "superadmin")


def is_superadmin(email: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT role FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        return row[0] == "superadmin"


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
            "SELECT id, name, email, created_at, tokens_used, token_limit, role FROM users ORDER BY id DESC"
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


# --- Rate limiting ---

import logging as _logging
_rl_logger = _logging.getLogger("rate_limit")

FREE_DAILY_LIMIT = 15


def _today_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def link_fp_email(fingerprint: str, email: str):
    """Register a fingerprint ↔ email association (idempotent)."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO fp_email_links (fingerprint, email) VALUES (?, ?)",
            (fingerprint, email),
        )
        conn.commit()


def get_linked_emails(fingerprint: str) -> list:
    """Return emails linked to a fingerprint, ordered by first_seen ASC (FIFO)."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT email FROM fp_email_links WHERE fingerprint = ? ORDER BY first_seen ASC",
            (fingerprint,),
        ).fetchall()
    return [r[0] for r in rows]


def get_linked_fingerprints(email: str) -> list:
    """Return fingerprints linked to an email."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT fingerprint FROM fp_email_links WHERE email = ? ORDER BY first_seen ASC",
            (email,),
        ).fetchall()
    return [r[0] for r in rows]


def _get_free_count(identifier: str) -> int:
    """Get today's free message count for an identifier (fp or ip)."""
    today = _today_utc()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT message_count FROM rate_limits WHERE identifier = ? AND day = ?",
            (identifier, today),
        ).fetchone()
    return row[0] if row else 0


def _increment_free_count(identifier: str):
    """Increment today's free message count for an identifier."""
    today = _today_utc()
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT identifier FROM rate_limits WHERE identifier = ? AND day = ?",
            (identifier, today),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE rate_limits SET message_count = message_count + 1 WHERE identifier = ? AND day = ?",
                (identifier, today),
            )
        else:
            # New day or new identifier — clean old entry and insert fresh
            conn.execute("DELETE FROM rate_limits WHERE identifier = ?", (identifier,))
            conn.execute(
                "INSERT INTO rate_limits (identifier, message_count, day) VALUES (?, 1, ?)",
                (identifier, today),
            )
        conn.commit()


def _get_credit_balance(email: str) -> int:
    """Get paid credit balance for an email."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT balance FROM email_credits WHERE email = ?", (email,)
        ).fetchone()
    return row[0] if row else 0


def _decrement_credit(email: str):
    """Decrement one paid credit from an email."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE email_credits SET balance = balance - 1 WHERE email = ? AND balance > 0",
            (email,),
        )
        conn.commit()


def consume_message(fp_identifier: str, email: Optional[str] = None) -> dict:
    """Cascade: free quota → paid credits → block.

    Returns {allowed, source, remaining_free, credit_email, credit_balance}.
    """
    today = _today_utc()
    free_count = _get_free_count(fp_identifier)

    # Step 1: free daily quota
    if free_count < FREE_DAILY_LIMIT:
        _increment_free_count(fp_identifier)
        remaining = FREE_DAILY_LIMIT - free_count - 1
        _rl_logger.info(
            f"[FREE] {fp_identifier} msg #{free_count + 1}/{FREE_DAILY_LIMIT} | remaining={remaining}"
        )
        return {
            "allowed": True,
            "source": "free",
            "remaining_free": remaining,
            "credit_email": None,
            "credit_balance": 0,
        }

    # Step 2: paid credits — FIFO by first_seen across linked emails
    # Raw fingerprint without the "fp:" prefix for the links table
    raw_fp = fp_identifier[3:] if fp_identifier.startswith("fp:") else fp_identifier
    linked_emails = get_linked_emails(raw_fp)

    for linked_email in linked_emails:
        balance = _get_credit_balance(linked_email)
        if balance > 0:
            _decrement_credit(linked_email)
            _rl_logger.info(
                f"[CREDIT] {fp_identifier} charged 1 credit to {linked_email} | balance={balance - 1}"
            )
            return {
                "allowed": True,
                "source": "credit",
                "remaining_free": 0,
                "credit_email": linked_email,
                "credit_balance": balance - 1,
            }

    # Step 3: blocked
    _rl_logger.info(
        f"[BLOCKED] {fp_identifier} free={free_count}/{FREE_DAILY_LIMIT} linked_emails={linked_emails}"
    )
    return {
        "allowed": False,
        "source": "none",
        "remaining_free": 0,
        "credit_email": None,
        "credit_balance": 0,
    }


def check_rate_limit(fp_identifier: str, email: Optional[str] = None) -> dict:
    """Check status without consuming. Returns {allowed, remaining, resets_in_seconds}."""
    free_count = _get_free_count(fp_identifier)
    # Seconds until midnight UTC
    now = datetime.utcnow()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    resets_in = max(0, int((midnight - now).total_seconds()))

    if free_count < FREE_DAILY_LIMIT:
        return {"allowed": True, "remaining": FREE_DAILY_LIMIT - free_count, "resets_in_seconds": resets_in}

    # Check paid credits
    raw_fp = fp_identifier[3:] if fp_identifier.startswith("fp:") else fp_identifier
    linked_emails = get_linked_emails(raw_fp)
    total_credits = sum(_get_credit_balance(e) for e in linked_emails)

    if total_credits > 0:
        return {"allowed": True, "remaining": total_credits, "resets_in_seconds": resets_in}

    return {"allowed": False, "remaining": 0, "resets_in_seconds": resets_in}


def grant_extra_messages(email: str, amount: int = 50):
    """Add paid credits to an email account."""
    now = datetime.utcnow()
    _rl_logger.info(f"[TOPUP] {email} +{amount} credits")
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT email FROM email_credits WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE email_credits SET balance = balance + ?, last_topup = ? WHERE email = ?",
                (amount, now.isoformat(), email),
            )
        else:
            conn.execute(
                "INSERT INTO email_credits (email, balance, last_topup) VALUES (?, ?, ?)",
                (email, amount, now.isoformat()),
            )
        conn.commit()


def get_user_payment_status(email: str) -> dict:
    balance = _get_credit_balance(email)
    return {"email": email, "has_bonus": balance > 0, "bonus_messages": balance}


def get_fp_status(fingerprint: str) -> dict:
    """Full status for a fingerprint — for admin inspection."""
    fp_id = f"fp:{fingerprint}" if not fingerprint.startswith("fp:") else fingerprint
    raw_fp = fingerprint.lstrip("fp:")
    free_count = _get_free_count(fp_id)
    linked = get_linked_emails(raw_fp)
    credits_by_email = {e: _get_credit_balance(e) for e in linked}
    return {
        "fingerprint": raw_fp,
        "free_used_today": free_count,
        "free_limit": FREE_DAILY_LIMIT,
        "day": _today_utc(),
        "linked_emails": linked,
        "credits_by_email": credits_by_email,
        "total_credits": sum(credits_by_email.values()),
    }


# --- Error reports ---

def save_error_report(user_email: Optional[str], description: str, page: str) -> dict:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO error_reports (user_email, description, page) VALUES (?, ?, ?)",
            (user_email, description, page),
        )
        conn.commit()
        report_id = cur.lastrowid
    return {"id": report_id, "status": "pending"}


def get_error_reports(limit: int = 50) -> list:
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, user_email, description, page, created_at, status FROM error_reports ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_report_status(report_id: int, status: str):
    with _get_conn() as conn:
        conn.execute("UPDATE error_reports SET status = ? WHERE id = ?", (status, report_id))
        conn.commit()


def increment_rate_limit(identifier: str):
    """Legacy shim — redirects to _increment_free_count."""
    _increment_free_count(identifier)
