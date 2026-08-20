"""Minimal self-service authentication and demo quota storage."""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{3,24}$")
SESSION_COOKIE = "roommate_session"
PBKDF2_ITERATIONS = 310_000


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class QuotaError(Exception):
    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.message = message
        self.reason = reason


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    generation_used: int
    generation_limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.generation_limit - self.generation_used)


class AuthService:
    def __init__(self):
        default_path = Path(__file__).resolve().parents[2] / "data" / "roommate.db"
        self.db_path = Path(os.getenv("AUTH_DB_PATH", str(default_path)))
        self.per_user_limit = int(os.getenv("FREE_GENERATION_LIMIT", "3"))
        self.global_limit = int(os.getenv("GLOBAL_GENERATION_LIMIT", "60"))
        self.session_days = int(os.getenv("AUTH_SESSION_DAYS", "30"))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    generation_used INTEGER NOT NULL DEFAULT 0,
                    generation_limit INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS generation_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    endpoint TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS app_counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO app_counters(name, value)
                VALUES ('global_generation_used', 0);
                """
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_password(password: str, salt: Optional[bytes] = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )
        return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _validate_credentials(username: str, password: str) -> str:
        normalized = username.strip()
        if not USERNAME_RE.fullmatch(normalized):
            raise AuthError("用户名需为3-24位中文、字母、数字或下划线")
        if not 8 <= len(password) <= 128:
            raise AuthError("密码长度需为8-128位")
        return normalized

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> AuthUser:
        return AuthUser(
            id=row["id"],
            username=row["username"],
            generation_used=row["generation_used"],
            generation_limit=row["generation_limit"],
        )

    def register(self, username: str, password: str) -> tuple[AuthUser, str]:
        username = self._validate_credentials(username, password)
        now = self._now().isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """INSERT INTO users
                    (username, password_hash, generation_limit, created_at)
                    VALUES (?, ?, ?, ?)""",
                    (username, self._hash_password(password), self.per_user_limit, now),
                )
                user_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise AuthError("该用户名已被使用", 409) from exc
        return self._create_session(user_id)

    def login(self, username: str, password: str) -> tuple[AuthUser, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)
            ).fetchone()
        if not row or not row["active"] or not self._verify_password(password, row["password_hash"]):
            raise AuthError("用户名或密码错误", 401)
        return self._create_session(row["id"])

    def _create_session(self, user_id: int) -> tuple[AuthUser, str]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = self._now()
        expires = now + timedelta(days=self.session_days)
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now.isoformat(),))
            conn.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, expires.isoformat(), now.isoformat()),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row), token

    def authenticate(self, token: Optional[str]) -> Optional[AuthUser]:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as conn:
            row = conn.execute(
                """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1""",
                (token_hash, self._now().isoformat()),
            ).fetchone()
        return self._row_to_user(row) if row else None

    def logout(self, token: Optional[str]) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def quota_snapshot(self, user_id: int) -> dict:
        with self._connect() as conn:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            global_used = conn.execute(
                "SELECT value FROM app_counters WHERE name = 'global_generation_used'"
            ).fetchone()["value"]
        auth_user = self._row_to_user(user)
        return {
            "used": auth_user.generation_used,
            "limit": auth_user.generation_limit,
            "remaining": auth_user.remaining,
            "global_used": global_used,
            "global_limit": self.global_limit,
            "global_remaining": max(0, self.global_limit - global_used),
        }

    def reserve_generation(self, user_id: int, endpoint: str) -> dict:
        now = self._now().isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            global_used = conn.execute(
                "SELECT value FROM app_counters WHERE name = 'global_generation_used'"
            ).fetchone()["value"]
            if not user or not user["active"]:
                raise QuotaError("账号不可用，请重新登录", "inactive")
            if user["generation_used"] >= user["generation_limit"]:
                raise QuotaError("你的3次免费生图机会已用完", "user_exhausted")
            if global_used >= self.global_limit:
                raise QuotaError("本轮免费体验名额已结束", "global_exhausted")
            conn.execute(
                "UPDATE users SET generation_used = generation_used + 1 WHERE id = ?",
                (user_id,),
            )
            conn.execute(
                "UPDATE app_counters SET value = value + 1 WHERE name = 'global_generation_used'"
            )
            conn.execute(
                "INSERT INTO generation_usage(user_id, endpoint, created_at) VALUES (?, ?, ?)",
                (user_id, endpoint, now),
            )
        return self.quota_snapshot(user_id)


auth_service = AuthService()
