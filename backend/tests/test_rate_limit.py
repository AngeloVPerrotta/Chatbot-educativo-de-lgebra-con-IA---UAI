"""Tests for the new fp-anchored rate limiting system."""

import os
import sys
import sqlite3
import unittest
from unittest.mock import patch

# Use in-memory DB for tests
os.environ.setdefault("TESTING", "1")

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import utils.analytics as analytics

# Override DB to in-memory for isolation
_TEST_DB = ":memory:"


def _fresh_db():
    """Create a fresh in-memory DB with the schema."""
    conn = sqlite3.connect(_TEST_DB)
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
    conn.commit()
    return conn


class RateLimitTestCase(unittest.TestCase):
    """Base that patches _get_conn to use a fresh in-memory DB per test."""

    def setUp(self):
        self.conn = _fresh_db()
        # Patch _get_conn to return our test connection
        self._patcher = patch.object(analytics, "_get_conn", return_value=self.conn)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.conn.close()


class TestAnonymousUser(RateLimitTestCase):
    """Test 1: anonymous user (no email) hits free limit then gets blocked."""

    def test_anonymous_15_free_then_blocked(self):
        fp = "fp:aabbccdd"

        # Use 15 free messages
        for i in range(15):
            result = analytics.consume_message(fp)
            self.assertTrue(result["allowed"], f"Message {i+1} should be allowed")
            self.assertEqual(result["source"], "free")
            self.assertEqual(result["remaining_free"], 15 - i - 1)

        # 16th message should be blocked
        result = analytics.consume_message(fp)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["source"], "none")

        # check_rate_limit should also report blocked
        status = analytics.check_rate_limit(fp)
        self.assertFalse(status["allowed"])
        self.assertEqual(status["remaining"], 0)


class TestLoggedInWithCredits(RateLimitTestCase):
    """Test 2: logged in user exhausts free quota, falls back to paid credits."""

    def test_free_then_credits(self):
        fp = "fp:11223344"
        email = "alumno@uai.edu.ar"

        # Link fp to email and grant 5 credits
        analytics.link_fp_email("11223344", email)
        analytics.grant_extra_messages(email, 5)

        # Use 15 free messages
        for i in range(15):
            result = analytics.consume_message(fp, email)
            self.assertTrue(result["allowed"])
            self.assertEqual(result["source"], "free")

        # Next 5 should use credits
        for i in range(5):
            result = analytics.consume_message(fp, email)
            self.assertTrue(result["allowed"])
            self.assertEqual(result["source"], "credit")
            self.assertEqual(result["credit_email"], email)
            self.assertEqual(result["credit_balance"], 5 - i - 1)

        # 21st message should be blocked
        result = analytics.consume_message(fp, email)
        self.assertFalse(result["allowed"])


class TestLoginLogoutRelogin(RateLimitTestCase):
    """Test 3: login -> use messages -> logout -> should NOT reset counter."""

    def test_logout_preserves_counter(self):
        fp = "fp:deadbeef"
        email = "pepe@gmail.com"

        # Login: link fp to email
        analytics.link_fp_email("deadbeef", email)

        # Use 10 messages while logged in
        for i in range(10):
            result = analytics.consume_message(fp, email)
            self.assertTrue(result["allowed"])

        # "Logout" — same fp, no email
        for i in range(5):
            result = analytics.consume_message(fp, None)
            self.assertTrue(result["allowed"])

        # 16th message total — should be blocked (same fp!)
        result = analytics.consume_message(fp, None)
        self.assertFalse(result["allowed"])

        # Re-login — still blocked (no credits)
        result = analytics.consume_message(fp, email)
        self.assertFalse(result["allowed"])


class TestTwoLinkedEmailsFIFO(RateLimitTestCase):
    """Test 4: two emails linked to same fp, credits consumed FIFO by first_seen."""

    def test_fifo_credit_consumption(self):
        fp = "fp:cafebabe"
        email_old = "viejo@uai.edu.ar"
        email_new = "nuevo@uai.edu.ar"

        # Link older email first, then newer
        analytics.link_fp_email("cafebabe", email_old)
        # Simulate time gap by manually inserting with earlier timestamp
        self.conn.execute(
            "UPDATE fp_email_links SET first_seen = datetime('now', '-1 day') WHERE email = ?",
            (email_old,),
        )
        self.conn.commit()
        analytics.link_fp_email("cafebabe", email_new)

        # Grant credits to both
        analytics.grant_extra_messages(email_old, 3)
        analytics.grant_extra_messages(email_new, 2)

        # Exhaust free quota
        for _ in range(15):
            analytics.consume_message(fp)

        # Next 3 credits should come from email_old (FIFO)
        for i in range(3):
            result = analytics.consume_message(fp)
            self.assertTrue(result["allowed"])
            self.assertEqual(result["credit_email"], email_old)

        # Next 2 credits should come from email_new
        for i in range(2):
            result = analytics.consume_message(fp)
            self.assertTrue(result["allowed"])
            self.assertEqual(result["credit_email"], email_new)

        # All credits exhausted — blocked
        result = analytics.consume_message(fp)
        self.assertFalse(result["allowed"])

        # Verify via get_fp_status
        status = analytics.get_fp_status("cafebabe")
        self.assertEqual(status["free_used_today"], 15)
        self.assertEqual(status["total_credits"], 0)
        self.assertIn(email_old, status["linked_emails"])
        self.assertIn(email_new, status["linked_emails"])
        # FIFO: old email should come first
        self.assertEqual(status["linked_emails"][0], email_old)


if __name__ == "__main__":
    unittest.main()
