"""
Auto-Bump Management System Entry Point

Initializes the database, bump manager, scheduler, and starts the
FastAPI server with uvicorn.
"""

from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys
import uvicorn
from contextlib import asynccontextmanager

from config import (
    API_HOST,
    API_PORT,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)
from database import Database
from bumper import BumpManager
from scheduler import BumpScheduler
from api import create_app


# ── Logging Setup ─────────────────────────────────────────────────────

def setup_logging():
    """Configure the logging system."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    
    # Create rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler]
    )
    
    # Suppress noisy discord.py internals
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)


# ── Global Instances ──────────────────────────────────────────────────

db = Database()
bumper_manager = BumpManager()
scheduler = BumpScheduler(db, bumper_manager)

logger = logging.getLogger("main")


# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown lifecycle for the FastAPI app."""
    setup_logging()
    logger.info("=" * 60)
    logger.info("  Auto-Bump Management System Starting")
    logger.info("=" * 60)

    # Initialize database
    await db.connect()
    logger.info("Database initialized")

    # Sync account connections
    await bumper_manager.sync_with_database(db)
    logger.info("Account connections synced")

    # Start the scheduler
    await scheduler.start()

    logger.info("Dashboard: http://%s:%d", API_HOST, API_PORT)
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down...")
    await scheduler.stop()
    bumper_manager.disconnect_all()
    await db.close()
    logger.info("Goodbye!")


# ── App Creation ──────────────────────────────────────────────────────

app = create_app(db, scheduler, bumper_manager)
app.router.lifespan_context = lifespan


# ── Main ──────────────────────────────────────────────────────────────

def main():
    """Run the application."""
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        log_level=LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
