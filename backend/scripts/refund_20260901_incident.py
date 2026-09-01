"""Refund the three failed main-generation attempts from the 2026-09-01 incident."""

import argparse
import os
import sqlite3
from pathlib import Path


INCIDENT_START = "2026-08-31T16:00:00+00:00"
INCIDENT_END = "2026-09-01T07:50:15+00:00"
ENDPOINT = "/api/v1/generate"
MARKER = "incident_refund_20260901"


def _database_path() -> Path:
    default = Path(__file__).resolve().parents[1] / "data" / "roommate.db"
    return Path(os.getenv("AUTH_DB_PATH", str(default))).resolve()


def _candidate_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            u.id AS user_id,
            GROUP_CONCAT(g.id) AS usage_ids,
            COUNT(g.id) AS incident_attempts
        FROM users u
        JOIN generation_usage g ON g.user_id = u.id
        WHERE g.endpoint = ?
          AND g.created_at >= ?
          AND g.created_at < ?
          AND u.generation_used >= u.generation_limit
        GROUP BY u.id
        HAVING COUNT(g.id) = 3
        """,
        (ENDPOINT, INCIDENT_START, INCIDENT_END),
    ).fetchall()


def run(apply: bool) -> tuple[int, int, bool]:
    db_path = _database_path()
    if apply:
        conn = sqlite3.connect(db_path, timeout=10)
    else:
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        marker = conn.execute(
            "SELECT value FROM app_counters WHERE name = ?", (MARKER,)
        ).fetchone()
        if marker:
            return 0, int(marker["value"]), True

        candidates = _candidate_rows(conn)
        attempt_count = sum(row["incident_attempts"] for row in candidates)
        if not apply:
            return len(candidates), attempt_count, False

        conn.execute("BEGIN IMMEDIATE")
        for row in candidates:
            usage_ids = [int(value) for value in row["usage_ids"].split(",")]
            placeholders = ",".join("?" for _ in usage_ids)
            conn.execute(
                f"DELETE FROM generation_usage WHERE id IN ({placeholders})",
                usage_ids,
            )
            conn.execute(
                """
                UPDATE users
                SET generation_used = MAX(0, generation_used - ?)
                WHERE id = ?
                """,
                (len(usage_ids), row["user_id"]),
            )

        conn.execute(
            """
            UPDATE app_counters
            SET value = MAX(0, value - ?)
            WHERE name = 'global_generation_used'
            """,
            (attempt_count,),
        )
        conn.execute(
            "INSERT INTO app_counters(name, value) VALUES (?, ?)",
            (MARKER, attempt_count),
        )
        conn.commit()
        return len(candidates), attempt_count, False
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    users, attempts, already_applied = run(args.apply)
    mode = "apply" if args.apply else "dry-run"
    print(
        f"mode={mode} candidate_users={users} "
        f"candidate_attempts={attempts} already_applied={already_applied}"
    )
