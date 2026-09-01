import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.services.auth_service import AuthService, QuotaError


class AuthQuotaContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_env = {
            key: os.environ.get(key)
            for key in ("AUTH_DB_PATH", "FREE_GENERATION_LIMIT", "GLOBAL_GENERATION_LIMIT")
        }
        os.environ["AUTH_DB_PATH"] = str(Path(self.temp_dir.name) / "auth.db")
        os.environ["FREE_GENERATION_LIMIT"] = "3"
        os.environ["GLOBAL_GENERATION_LIMIT"] = "60"
        self.service = AuthService()

    def tearDown(self):
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def test_registration_creates_session_and_three_credits(self):
        user, token = self.service.register("demo_user", "securepass123")
        authenticated = self.service.authenticate(token)
        self.assertEqual(authenticated.username, "demo_user")
        self.assertEqual(self.service.quota_snapshot(user.id)["remaining"], 3)

    def test_concurrent_requests_cannot_exceed_user_limit(self):
        user, _ = self.service.register("parallel_user", "securepass123")

        def reserve():
            try:
                self.service.reserve_generation(user.id, "/test")
                return True
            except QuotaError:
                return False

        with ThreadPoolExecutor(max_workers=10) as pool:
            accepted = list(pool.map(lambda _: reserve(), range(10)))

        self.assertEqual(sum(accepted), 3)
        self.assertEqual(self.service.quota_snapshot(user.id)["remaining"], 0)

    def test_global_limit_is_shared_by_accounts(self):
        self.service.global_limit = 2
        first, _ = self.service.register("first_user", "securepass123")
        second, _ = self.service.register("second_user", "securepass123")
        self.service.reserve_generation(first.id, "/test")
        self.service.reserve_generation(second.id, "/test")
        with self.assertRaises(QuotaError) as captured:
            self.service.reserve_generation(first.id, "/test")
        self.assertEqual(captured.exception.reason, "global_exhausted")

    def test_failed_generation_is_refunded_once(self):
        user, _ = self.service.register("refund_user", "securepass123")
        reservation = self.service.reserve_generation(user.id, "/test")

        self.assertEqual(reservation.quota["remaining"], 2)
        refunded = self.service.refund_generation(reservation.id, user.id)
        refunded_again = self.service.refund_generation(reservation.id, user.id)

        self.assertEqual(refunded["remaining"], 3)
        self.assertEqual(refunded["global_used"], 0)
        self.assertEqual(refunded_again, refunded)

    def test_incident_migration_refunds_exactly_three_exhausted_attempts(self):
        user, _ = self.service.register("incident_user", "securepass123")
        for _ in range(3):
            self.service.reserve_generation(user.id, "/api/v1/generate")

        with self.service._connect() as conn:
            conn.execute(
                """
                UPDATE generation_usage
                SET created_at = '2026-09-01T03:00:00+00:00'
                WHERE user_id = ?
                """,
                (user.id,),
            )

        restarted_service = AuthService()
        snapshot = restarted_service.quota_snapshot(user.id)
        with restarted_service._connect() as conn:
            marker = conn.execute(
                """SELECT value FROM app_counters
                WHERE name = 'incident_refund_20260901'"""
            ).fetchone()

        self.assertEqual(snapshot["remaining"], 3)
        self.assertEqual(snapshot["global_used"], 0)
        self.assertEqual(marker["value"], 3)


if __name__ == "__main__":
    unittest.main()
