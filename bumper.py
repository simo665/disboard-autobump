"""
Auto-Bump Management System — Bump Execution Engine

Manages Discord self-bot client instances and executes bump commands.
Each account runs its own discord.Client in a dedicated thread with its own event loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from discord.ext import commands

from config import BUMP_COMMAND_ID

logger = logging.getLogger("bumper")


@dataclass
class BumpResult:
    """Result of a bump attempt."""
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class AccountClient:
    """
    Wraps a single Discord self-bot client running in its own thread.
    Provides a thread-safe interface to execute bump commands.
    """

    def __init__(self, account_id: int, token: str, name: str = ""):
        self.account_id = account_id
        self.token = token
        self.name = name or f"Account-{account_id}"
        self.bot: Optional[commands.Bot] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()
        self._connected = False
        self._error: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self.bot is not None and not self.bot.is_closed()

    @property
    def error(self) -> Optional[str]:
        return self._error

    def start(self):
        """Start the Discord client in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("%s: Already running", self.name)
            return

        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._run_client,
            name=f"discord-{self.name}",
            daemon=True,
        )
        self._thread.start()

        # Wait up to 30 seconds for the client to be ready
        if not self._ready.wait(timeout=30):
            self._error = "Connection timeout (30s)"
            logger.error("%s: %s", self.name, self._error)

    def _run_client(self):
        """Thread entry: create event loop, start bot, run forever."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self.bot = commands.Bot(
            command_prefix=";",
            case_insensitive=True,
            self_bot=True,
            chunk_guilds_at_startup=False,
            request_guilds=False,
        )
        self.bot.remove_command("help")

        @self.bot.event
        async def on_ready():
            self._connected = True
            self._ready.set()
            logger.info("✅ %s: Logged in as %s", self.name, self.bot.user)

        try:
            self._loop.run_until_complete(
                self.bot.start(self.token, reconnect=True)
            )
        except Exception as e:
            self._error = str(e)
            self._connected = False
            self._ready.set()  # Unblock waiters
            logger.error("❌ %s: Client crashed — %s", self.name, e)
        finally:
            self._loop.close()

    async def _execute_bump_async(self, channel_id: int) -> BumpResult:
        """Execute the bump command on a channel (runs inside the client's loop)."""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return BumpResult(success=False, error=f"Channel {channel_id} not found")

            app_commands = await channel.application_commands()
            bump_command = None
            for cmd in app_commands:
                if cmd.id == BUMP_COMMAND_ID:
                    bump_command = cmd
                    break

            if bump_command is None:
                return BumpResult(
                    success=False,
                    error=f"Bump command (ID {BUMP_COMMAND_ID}) not found in channel",
                )

            response = await bump_command.__call__(channel=channel)

            if not response.message.flags.ephemeral:
                logger.info(
                    "✅ %s: Bumped successfully in channel %d", self.name, channel_id
                )
                return BumpResult(success=True)
            else:
                return BumpResult(
                    success=False, error="Bump failed — channel still on cooldown"
                )

        except Exception as e:
            logger.error("❗ %s: Bump error in channel %d — %s", self.name, channel_id, e)
            return BumpResult(success=False, error=str(e))

    def execute_bump(self, channel_id: int) -> BumpResult:
        """
        Thread-safe bump execution.
        Schedules the bump coroutine on the client's event loop and waits for the result.
        """
        if not self.is_connected:
            return BumpResult(success=False, error="Account not connected")

        if self._loop is None or self._loop.is_closed():
            return BumpResult(success=False, error="Event loop is closed")

        future = asyncio.run_coroutine_threadsafe(
            self._execute_bump_async(channel_id), self._loop
        )

        try:
            return future.result(timeout=30)
        except TimeoutError:
            return BumpResult(success=False, error="Bump command timed out (30s)")
        except Exception as e:
            return BumpResult(success=False, error=str(e))

    def stop(self):
        """Gracefully disconnect the client."""
        if self.bot and self._loop and not self._loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self.bot.close(), self._loop)
            try:
                future.result(timeout=10)
            except Exception:
                pass
        self._connected = False
        logger.info("🔌 %s: Disconnected", self.name)


class BumpManager:
    """
    Manages all AccountClient instances.
    Provides high-level methods to connect/disconnect accounts and execute bumps.
    """

    def __init__(self):
        self._clients: dict[int, AccountClient] = {}
        self._lock = threading.Lock()

    def connect_account(self, account_id: int, token: str, name: str = ""):
        """Start a Discord client for an account."""
        with self._lock:
            if account_id in self._clients:
                existing = self._clients[account_id]
                if existing.is_connected:
                    logger.info("Account %d already connected", account_id)
                    return
                # Clean up stale client
                existing.stop()

            client = AccountClient(account_id, token, name)
            client.start()
            self._clients[account_id] = client

            if client.error:
                logger.error(
                    "Failed to connect account %d: %s", account_id, client.error
                )

    def disconnect_account(self, account_id: int):
        """Stop and remove a client."""
        with self._lock:
            client = self._clients.pop(account_id, None)
            if client:
                client.stop()

    def disconnect_all(self):
        """Stop all clients."""
        with self._lock:
            for client in self._clients.values():
                client.stop()
            self._clients.clear()
            logger.info("All accounts disconnected")

    def execute_bump(self, account_id: int, channel_id: int) -> BumpResult:
        """Execute a bump for a specific account on a specific channel."""
        with self._lock:
            client = self._clients.get(account_id)

        if client is None:
            return BumpResult(success=False, error="Account client not found")

        return client.execute_bump(channel_id)

    def get_client_status(self, account_id: int) -> dict:
        """Get connection status for an account."""
        with self._lock:
            client = self._clients.get(account_id)
        if client is None:
            return {"connected": False, "error": None}
        return {"connected": client.is_connected, "error": client.error}

    def is_connected(self, account_id: int) -> bool:
        """Check if an account is connected."""
        with self._lock:
            client = self._clients.get(account_id)
        return client is not None and client.is_connected

    async def sync_with_database(self, db):
        """
        Connect all enabled accounts from the database,
        disconnect removed/disabled accounts.
        """
        accounts = await db.get_all_accounts()
        enabled_ids = set()

        for account in accounts:
            if account["enabled"]:
                enabled_ids.add(account["id"])
                if not self.is_connected(account["id"]):
                    self.connect_account(
                        account["id"], account["token"], account["name"]
                    )
            else:
                if self.is_connected(account["id"]):
                    self.disconnect_account(account["id"])

        # Disconnect accounts no longer in the database
        with self._lock:
            stale = [
                aid for aid in self._clients if aid not in enabled_ids
            ]
        for aid in stale:
            self.disconnect_account(aid)
