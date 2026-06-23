"""
Auto-Bump Management System Database Module

Async SQLite database layer using aiosqlite.
All data operations are centralized here.
"""

from __future__ import annotations

import aiosqlite
import time
import logging
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH, CHANNEL_COOLDOWN, ACCOUNT_COOLDOWN

logger = logging.getLogger("database")


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str | Path = DATABASE_PATH):
        self.db_path = str(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Open the database connection and initialize schema."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        logger.info("Database connected: %s", self.db_path)

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed.")

    async def _init_schema(self):
        """Create tables if they don't exist."""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                token       TEXT NOT NULL UNIQUE,
                name        TEXT DEFAULT '',
                enabled     INTEGER DEFAULT 1,
                last_bump   REAL DEFAULT 0,
                error_status TEXT DEFAULT NULL,
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channels (
                channel_id  TEXT PRIMARY KEY,
                last_bump   REAL DEFAULT 0,
                next_bump   REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS account_channels (
                account_id  INTEGER NOT NULL,
                channel_id  TEXT NOT NULL,
                PRIMARY KEY (account_id, channel_id),
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bump_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id  TEXT NOT NULL,
                account_id  INTEGER,
                timestamp   REAL NOT NULL,
                success     INTEGER NOT NULL DEFAULT 0,
                reason      TEXT DEFAULT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_logs_timestamp
                ON bump_logs(timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_logs_channel
                ON bump_logs(channel_id);
        """)
        await self._db.commit()

    # ── Account Operations ────────────────────────────────────────────

    async def add_account(
        self, token: str, name: str = "", channel_ids: list[str] | None = None
    ) -> int:
        """Add a new account and assign it to channels. Returns account ID."""
        now = time.time()
        cursor = await self._db.execute(
            "INSERT INTO accounts (token, name, created_at) VALUES (?, ?, ?)",
            (token, name, now),
        )
        account_id = cursor.lastrowid

        if channel_ids:
            for ch_id in channel_ids:
                # Ensure channel row exists, set next_bump to 30s in the future if new
                await self._db.execute("""
                    INSERT INTO channels (channel_id, next_bump)
                    VALUES (?, ?)
                    ON CONFLICT(channel_id) DO NOTHING
                """, (ch_id, now + 30))
                await self._db.execute(
                    "INSERT OR IGNORE INTO account_channels (account_id, channel_id) VALUES (?, ?)",
                    (account_id, ch_id),
                )

        await self._db.commit()
        logger.info("Added account id=%d name='%s' with %d channels", account_id, name, len(channel_ids or []))
        return account_id

    async def remove_account(self, account_id: int) -> bool:
        """Remove an account. Returns True if a row was deleted."""
        cursor = await self._db.execute(
            "DELETE FROM accounts WHERE id = ?", (account_id,)
        )
        # Clean up orphaned channels
        await self._db.execute("""
            DELETE FROM channels
            WHERE channel_id NOT IN (SELECT DISTINCT channel_id FROM account_channels)
        """)
        await self._db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Removed account id=%d", account_id)
        return deleted

    async def toggle_account(self, account_id: int, enabled: bool) -> bool:
        """Enable or disable an account. Returns True if updated."""
        cursor = await self._db.execute(
            "UPDATE accounts SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, account_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def update_account(
        self,
        account_id: int,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
        channel_ids: Optional[list[str]] = None,
    ) -> bool:
        """Update account fields. Returns True if the account exists."""
        # Check account exists
        row = await self._db.execute_fetchall(
            "SELECT id FROM accounts WHERE id = ?", (account_id,)
        )
        if not row:
            return False

        if name is not None:
            await self._db.execute(
                "UPDATE accounts SET name = ? WHERE id = ?", (name, account_id)
            )

        if enabled is not None:
            await self._db.execute(
                "UPDATE accounts SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, account_id),
            )

        if channel_ids is not None:
            # Replace channel assignments
            await self._db.execute(
                "DELETE FROM account_channels WHERE account_id = ?", (account_id,)
            )
            now = time.time()
            for ch_id in channel_ids:
                await self._db.execute("""
                    INSERT INTO channels (channel_id, next_bump)
                    VALUES (?, ?)
                    ON CONFLICT(channel_id) DO NOTHING
                """, (ch_id, now + 30))
                await self._db.execute(
                    "INSERT OR IGNORE INTO account_channels (account_id, channel_id) VALUES (?, ?)",
                    (account_id, ch_id),
                )
            # Clean up orphaned channels
            await self._db.execute("""
                DELETE FROM channels
                WHERE channel_id NOT IN (SELECT DISTINCT channel_id FROM account_channels)
            """)

        await self._db.commit()
        return True

    async def get_account(self, account_id: int) -> Optional[dict]:
        """Get a single account by ID."""
        rows = await self._db.execute_fetchall(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        )
        if not rows:
            return None
        account = dict(rows[0])
        account["channel_ids"] = await self._get_account_channels(account_id)
        return account

    async def get_account_by_token(self, token: str) -> Optional[dict]:
        """Get a single account by token."""
        rows = await self._db.execute_fetchall(
            "SELECT * FROM accounts WHERE token = ?", (token,)
        )
        if not rows:
            return None
        account = dict(rows[0])
        account["channel_ids"] = await self._get_account_channels(account["id"])
        return account

    async def get_all_accounts(self) -> list[dict]:
        """Get all accounts with their channel assignments."""
        rows = await self._db.execute_fetchall("SELECT * FROM accounts ORDER BY id")
        accounts = []
        for row in rows:
            account = dict(row)
            account["channel_ids"] = await self._get_account_channels(account["id"])
            accounts.append(account)
        return accounts

    async def _get_account_channels(self, account_id: int) -> list[str]:
        """Get channel IDs assigned to an account."""
        rows = await self._db.execute_fetchall(
            "SELECT channel_id FROM account_channels WHERE account_id = ?",
            (account_id,),
        )
        return [row["channel_id"] for row in rows]

    async def set_account_error(self, account_id: int, error: str):
        """Mark an account as having an error."""
        await self._db.execute(
            "UPDATE accounts SET error_status = ? WHERE id = ?",
            (error, account_id),
        )
        await self._db.commit()

    async def clear_account_error(self, account_id: int):
        """Clear an account's error status."""
        await self._db.execute(
            "UPDATE accounts SET error_status = NULL WHERE id = ?",
            (account_id,),
        )
        await self._db.commit()

    async def update_account_last_bump(self, account_id: int, timestamp: float):
        """Update the last bump timestamp for an account."""
        await self._db.execute(
            "UPDATE accounts SET last_bump = ? WHERE id = ?",
            (timestamp, account_id),
        )
        await self._db.commit()

    # ── Channel Operations ────────────────────────────────────────────

    async def get_all_channels(self) -> list[dict]:
        """Get all channels with assigned account count."""
        rows = await self._db.execute_fetchall("""
            SELECT c.channel_id, c.last_bump, c.next_bump,
                   COUNT(ac.account_id) as assigned_accounts
            FROM channels c
            LEFT JOIN account_channels ac ON c.channel_id = ac.channel_id
            GROUP BY c.channel_id
            ORDER BY c.channel_id
        """)
        return [dict(row) for row in rows]

    async def get_channels_due(self) -> list[dict]:
        """Get channels whose next_bump time has passed (ready to bump)."""
        now = time.time()
        rows = await self._db.execute_fetchall(
            "SELECT * FROM channels WHERE next_bump <= ?", (now,)
        )
        return [dict(row) for row in rows]

    async def update_channel_bump(self, channel_id: str, bump_time: float):
        """Record a successful bump on a channel and schedule the next one."""
        next_bump = bump_time + CHANNEL_COOLDOWN
        await self._db.execute(
            "UPDATE channels SET last_bump = ?, next_bump = ? WHERE channel_id = ?",
            (bump_time, next_bump, channel_id),
        )
        await self._db.commit()

    async def update_channel_next_bump(self, channel_id: str, next_time: float):
        """Manually set the next bump time for a channel."""
        await self._db.execute(
            "UPDATE channels SET next_bump = ? WHERE channel_id = ?",
            (next_time, channel_id),
        )
        await self._db.commit()

    # ── Eligible Account Selection ────────────────────────────────────

    async def get_eligible_accounts(self, channel_id: str) -> list[dict]:
        """
        Get accounts eligible to bump a specific channel:
        - Assigned to the channel
        - Enabled
        - Not on cooldown (last_bump older than ACCOUNT_COOLDOWN)
        - No active error
        """
        cutoff = time.time() - ACCOUNT_COOLDOWN
        rows = await self._db.execute_fetchall("""
            SELECT a.*
            FROM accounts a
            JOIN account_channels ac ON a.id = ac.account_id
            WHERE ac.channel_id = ?
              AND a.enabled = 1
              AND a.last_bump <= ?
              AND a.error_status IS NULL
        """, (channel_id, cutoff))
        return [dict(row) for row in rows]

    # ── Bump Logging ──────────────────────────────────────────────────

    async def record_bump(
        self,
        channel_id: str,
        account_id: Optional[int],
        success: int,
        reason: Optional[str] = None,
    ):
        """Log a bump attempt."""
        now = time.time()
        await self._db.execute(
            "INSERT INTO bump_logs (channel_id, account_id, timestamp, success, reason) VALUES (?, ?, ?, ?, ?)",
            (channel_id, account_id, now, 1 if success else 0, reason),
        )
        await self._db.commit()

    async def get_bump_logs(self, limit: int = 50) -> list[dict]:
        """Get recent bump logs with account names."""
        rows = await self._db.execute_fetchall("""
            SELECT bl.*, COALESCE(a.name, 'Unknown') as account_name
            FROM bump_logs bl
            LEFT JOIN accounts a ON bl.account_id = a.id
            ORDER BY bl.timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in rows]

    # ── Statistics ────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Get aggregate dashboard statistics."""
        accounts = await self._db.execute_fetchall("SELECT COUNT(*) as c FROM accounts")
        active = await self._db.execute_fetchall(
            "SELECT COUNT(*) as c FROM accounts WHERE enabled = 1"
        )
        channels = await self._db.execute_fetchall("SELECT COUNT(*) as c FROM channels")
        total_bumps = await self._db.execute_fetchall(
            "SELECT COUNT(*) as c FROM bump_logs"
        )
        successful = await self._db.execute_fetchall(
            "SELECT COUNT(*) as c FROM bump_logs WHERE success = 1"
        )
        failed = await self._db.execute_fetchall(
            "SELECT COUNT(*) as c FROM bump_logs WHERE success = 0"
        )

        # Next scheduled bump
        next_bump_row = await self._db.execute_fetchall(
            "SELECT channel_id, next_bump FROM channels WHERE next_bump > 0 ORDER BY next_bump ASC LIMIT 1"
        )

        return {
            "total_accounts": accounts[0]["c"],
            "active_accounts": active[0]["c"],
            "total_channels": channels[0]["c"],
            "total_bumps": total_bumps[0]["c"],
            "successful_bumps": successful[0]["c"],
            "failed_bumps": failed[0]["c"],
            "next_bump_time": next_bump_row[0]["next_bump"] if next_bump_row else None,
            "next_bump_channel": next_bump_row[0]["channel_id"] if next_bump_row else None,
        }
