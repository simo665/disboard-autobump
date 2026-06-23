"""
Auto-Bump Management System — FastAPI REST API

Serves the dashboard and provides API endpoints for managing accounts,
channels, bump logs, and the scheduler.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import BASE_DIR
from models import (
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    ChannelResponse,
    BumpLogResponse,
    StatsResponse,
    SchedulerStatus,
)
from database import Database
from scheduler import BumpScheduler
from bumper import BumpManager

logger = logging.getLogger("api")


def create_app(db: Database, scheduler: BumpScheduler, bumper: BumpManager) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Auto-Bump Management System",
        description="Discord auto-bump management dashboard API",
        version="1.0.0",
    )

    # ── Helper ────────────────────────────────────────────────────────

    def mask_token(token: str) -> str:
        """Mask a token, showing only the last 6 characters."""
        if len(token) <= 6:
            return "••••••"
        return "•" * 6 + token[-6:]

    def account_to_response(account: dict) -> dict:
        """Convert a raw account dict to an API response."""
        return {
            "id": account["id"],
            "token_hint": mask_token(account["token"]),
            "name": account["name"],
            "enabled": bool(account["enabled"]),
            "last_bump": account["last_bump"],
            "error_status": account["error_status"],
            "channel_ids": account["channel_ids"],
            "created_at": account["created_at"],
        }

    # ── Account Endpoints ─────────────────────────────────────────────

    @app.get("/api/accounts")
    async def list_accounts():
        """List all accounts (tokens masked)."""
        accounts = await db.get_all_accounts()
        result = []
        for acc in accounts:
            data = account_to_response(acc)
            # Include live connection status
            status = bumper.get_client_status(acc["id"])
            data["connected"] = status["connected"]
            data["connection_error"] = status["error"]
            result.append(data)
        return result

    @app.post("/api/accounts", status_code=201)
    async def add_account(body: AccountCreate):
        """Add a new account."""
        # Check for duplicate token
        existing = await db.get_account_by_token(body.token)
        if existing:
            raise HTTPException(status_code=409, detail="Account with this token already exists")

        account_id = await db.add_account(
            token=body.token,
            name=body.name,
            channel_ids=body.channel_ids,
        )

        # Connect the account immediately
        bumper.connect_account(account_id, body.token, body.name)

        account = await db.get_account(account_id)
        return account_to_response(account)

    @app.delete("/api/accounts/{account_id}")
    async def remove_account(account_id: int):
        """Remove an account."""
        # Disconnect first
        bumper.disconnect_account(account_id)

        deleted = await db.remove_account(account_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"detail": "Account removed"}

    @app.patch("/api/accounts/{account_id}")
    async def update_account(account_id: int, body: AccountUpdate):
        """Update account settings."""
        updated = await db.update_account(
            account_id,
            name=body.name,
            enabled=body.enabled,
            channel_ids=body.channel_ids,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Account not found")

        # Handle enable/disable connection
        account = await db.get_account(account_id)
        if body.enabled is True:
            bumper.connect_account(account_id, account["token"], account["name"])
        elif body.enabled is False:
            bumper.disconnect_account(account_id)

        return account_to_response(account)

    # ── Channel Endpoints ─────────────────────────────────────────────

    @app.get("/api/channels")
    async def list_channels():
        """List all configured channels."""
        channels = await db.get_all_channels()
        return channels

    # ── Bump Log Endpoints ────────────────────────────────────────────

    @app.get("/api/logs")
    async def get_logs(limit: int = Query(default=50, ge=1, le=500)):
        """Get recent bump history."""
        logs = await db.get_bump_logs(limit)
        return logs

    # ── Stats Endpoint ────────────────────────────────────────────────

    @app.get("/api/stats")
    async def get_stats():
        """Get dashboard statistics."""
        return await db.get_stats()

    # ── Scheduler Endpoints ───────────────────────────────────────────

    @app.get("/api/scheduler/status")
    async def scheduler_status():
        """Get scheduler running state."""
        return await scheduler.get_status()

    @app.post("/api/scheduler/toggle")
    async def toggle_scheduler():
        """Start or stop the scheduler."""
        if scheduler.is_running:
            await scheduler.stop()
            return {"running": False, "detail": "Scheduler stopped"}
        else:
            await scheduler.start()
            return {"running": True, "detail": "Scheduler started"}

    # ── Dashboard Static Files ────────────────────────────────────────

    @app.get("/")
    async def dashboard():
        """Serve the dashboard."""
        return FileResponse(BASE_DIR / "static" / "index.html")

    # Mount static files AFTER explicit routes
    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )

    return app
