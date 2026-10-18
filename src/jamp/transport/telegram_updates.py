from __future__ import annotations

import sqlite3
from pathlib import Path


class TelegramUpdateStoreError(RuntimeError):
    """Raised when Telegram update idempotency cannot be enforced."""


class TelegramUpdateStore:
    """Atomically claim Telegram update IDs in a persistent SQLite database."""

    def __init__(self, database_path: str | Path | None, *, timeout_seconds: float = 5.0) -> None:
        if database_path is None or not str(database_path).strip():
            self.database_path: Path | None = None
        else:
            self.database_path = Path(database_path)
        self.timeout_seconds = timeout_seconds

    def claim(self, update_id: int) -> bool:
        """Return True only for the first durable claim of an update ID."""
        if isinstance(update_id, bool) or not isinstance(update_id, int):
            raise ValueError("Telegram update_id must be an integer")
        if self.database_path is None:
            raise TelegramUpdateStoreError("Telegram update store is not configured")

        connection: sqlite3.Connection | None = None
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                self.database_path,
                timeout=self.timeout_seconds,
            )
            connection.execute(f"PRAGMA busy_timeout = {int(self.timeout_seconds * 1000)}")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_update_claims (
                    update_id INTEGER PRIMARY KEY,
                    claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor = connection.execute(
                "INSERT OR IGNORE INTO telegram_update_claims (update_id) VALUES (?)",
                (update_id,),
            )
            connection.commit()
            return cursor.rowcount == 1
        except (OSError, sqlite3.Error):
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            raise TelegramUpdateStoreError(
                "Unable to persist Telegram update claim"
            ) from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    raise TelegramUpdateStoreError(
                        "Unable to close Telegram update store"
                    ) from None
