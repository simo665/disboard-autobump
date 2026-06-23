"""
Auto-Bump Management System — Data Models
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ── API Request Models ────────────────────────────────────────────────

class AccountCreate(BaseModel):
    """Request body for adding a new account."""
    token: str
    name: str = ""
    channel_ids: list[str] = Field(default_factory=list)


class AccountUpdate(BaseModel):
    """Request body for updating an account."""
    enabled: Optional[bool] = None
    name: Optional[str] = None
    channel_ids: Optional[list[str]] = None


# ── API Response Models ───────────────────────────────────────────────

class AccountResponse(BaseModel):
    """Account data returned by the API (token masked)."""
    id: int
    token_hint: str          # last 6 chars only
    name: str
    enabled: bool
    last_bump: float
    error_status: Optional[str]
    channel_ids: list[str]
    created_at: float


class ChannelResponse(BaseModel):
    """Channel data returned by the API."""
    channel_id: str
    last_bump: float
    next_bump: float
    assigned_accounts: int


class BumpLogResponse(BaseModel):
    """Single bump log entry."""
    id: int
    channel_id: str
    account_id: Optional[int]
    account_name: str
    timestamp: float
    success: bool
    reason: Optional[str]


class StatsResponse(BaseModel):
    """Aggregate dashboard statistics."""
    total_accounts: int
    active_accounts: int
    total_channels: int
    total_bumps: int
    successful_bumps: int
    failed_bumps: int
    next_bump_time: Optional[float]
    next_bump_channel: Optional[str]


class SchedulerStatus(BaseModel):
    """Scheduler running state."""
    running: bool
    uptime: float
    channels_monitored: int
