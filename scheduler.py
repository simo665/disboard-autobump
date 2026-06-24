"""
Auto-Bump Management System Scheduler

Continuously monitors channels and dispatches bumps with human-like delays.
Runs as an async background task alongside the FastAPI server.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Optional

from config import (
    CHANNEL_COOLDOWN,
    HUMAN_DELAY_MIN,
    HUMAN_DELAY_MAX,
    SCHEDULER_CHECK_INTERVAL,
)
from database import Database
from bumper import BumpManager

logger = logging.getLogger("scheduler")


class BumpScheduler:
    """
    Async scheduler that monitors channels and dispatches bump commands.

    Algorithm per tick:
        1. Query channels whose next_bump time has passed.
        2. For each due channel (not already being processed):
            a. Apply a random human-like delay (3–20 min).
            b. Find eligible accounts for the channel.
            c. Shuffle and try each account until one succeeds.
            d. On success: record bump, update cooldowns.
            e. On failure: log, try next account.
    """

    def __init__(self, db: Database, bumper: BumpManager):
        self.db = db
        self.bumper = bumper
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._started_at: float = 0
        self._active_channels: dict[str, float] = {}  # channel_id -> estimated bump time

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def uptime(self) -> float:
        if not self._running or self._started_at == 0:
            return 0
        return time.time() - self._started_at

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._started_at = time.time()
        self._task = asyncio.create_task(self._loop())
        logger.info("🚀 Scheduler started")

    async def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("🛑 Scheduler stopped")

    async def _loop(self):
        """Main scheduler loop."""
        # Connect accounts on first run
        await self.bumper.sync_with_database(self.db)

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error("Scheduler tick error: %s", e, exc_info=True)

            await asyncio.sleep(SCHEDULER_CHECK_INTERVAL)

    async def _tick(self):
        """Single scheduler tick: check all channels and dispatch bumps."""
        channels = await self.db.get_channels_due()

        for channel in channels:
            channel_id = channel["channel_id"]

            # Skip if this channel is already being processed
            if channel_id in self._active_channels:
                continue

            # Spawn a task so multiple channels can be processed concurrently
            asyncio.create_task(self._process_channel(channel_id))

    async def _process_channel(self, channel_id: str):
        """Process a single channel: delay, select account, bump."""
        if channel_id in self._active_channels:
            return

        # ── Human-like delay ──────────────────────────────────
        delay = random.randint(HUMAN_DELAY_MIN, HUMAN_DELAY_MAX)
        estimated_bump_at = time.time() + delay
        self._active_channels[channel_id] = estimated_bump_at
        try:
            # Record a log entry in database that the delay has started
            await self.db.record_bump(
                channel_id=channel_id,
                account_id=None,
                success=2,
                reason=f"Waiting {delay // 60}m {delay % 60}s before bumping"
            )

            logger.info(
                "⏱️  Channel %s is due waiting %d seconds (%.1f min) before bumping",
                channel_id, delay, delay / 60,
            )
            await asyncio.sleep(delay)

            # Re-check if still running after delay
            if not self._running:
                return

            # ── Get eligible accounts ─────────────────────────────
            eligible = await self.db.get_eligible_accounts(channel_id)

            if not eligible:
                logger.warning(
                    "⚠️  Channel %s: No eligible accounts available", channel_id
                )
                # Schedule a re-check in 5 minutes
                await self.db.update_channel_next_bump(
                    channel_id, time.time() + 300
                )
                return

            # Randomize account selection order
            random.shuffle(eligible)

            # ── Try each account ──────────────────────────────────
            bumped = False
            for account in eligible:
                account_id = account["id"]
                account_name = account["name"] or f"Account-{account_id}"

                logger.info(
                    "🎯 Channel %s: Trying account '%s' (id=%d)",
                    channel_id, account_name, account_id,
                )

                # Ensure account is connected
                if not self.bumper.is_connected(account_id):
                    conn_err = await asyncio.to_thread(
                        self.bumper.connect_account,
                        account_id,
                        account["token"],
                        account_name,
                    )
                    if conn_err:
                        await self.db.set_account_error(account_id, conn_err)
                        await self.db.record_bump(
                            channel_id, account_id, success=False, reason=f"Connection failed: {conn_err}"
                        )
                        logger.warning(
                            "❌ Channel %s: Connection failed for '%s' (%s)",
                            channel_id, account_name, conn_err,
                        )
                        continue
                    else:
                        await self.db.clear_account_error(account_id)
                    # Brief wait for connection
                    await asyncio.sleep(2)

                # Execute bump in thread pool (since bumper uses thread-safe sync call)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, self.bumper.execute_bump, account_id, int(channel_id)
                )

                if result.success:
                    now = time.time()
                    await self.db.record_bump(channel_id, account_id, success=True)
                    await self.db.update_channel_bump(channel_id, now)
                    await self.db.update_account_last_bump(account_id, now)
                    await self.db.clear_account_error(account_id)

                    logger.info(
                        "✅ Channel %s: Bumped by '%s' next bump at +2h",
                        channel_id, account_name,
                    )
                    bumped = True
                    break
                else:
                    await self.db.record_bump(
                        channel_id, account_id, success=False, reason=result.error
                    )
                    await self.db.set_account_error(account_id, result.error)
                    logger.warning(
                        "❌ Channel %s: Bump failed with '%s' %s",
                        channel_id, account_name, result.error,
                    )
                    # Small delay before trying next account
                    await asyncio.sleep(3)

            if not bumped:
                logger.error(
                    "🚫 Channel %s: All accounts exhausted, no successful bump",
                    channel_id,
                )
                # Re-check in 5 minutes
                await self.db.update_channel_next_bump(
                    channel_id, time.time() + 300
                )

        except Exception as e:
            logger.error(
                "Error processing channel %s: %s", channel_id, e, exc_info=True
            )
        finally:
            self._active_channels.pop(channel_id, None)

    def get_pending_channels(self) -> dict[str, float]:
        """Get channels currently waiting through their human-like delay.
        Returns {channel_id: estimated_bump_timestamp}.
        """
        return dict(self._active_channels)

    async def get_status(self) -> dict:
        """Get scheduler status info."""
        channels = await self.db.get_all_channels()
        return {
            "running": self._running,
            "uptime": self.uptime,
            "channels_monitored": len(channels),
            "pending_channels": self.get_pending_channels(),
        }
