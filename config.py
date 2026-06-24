"""
Auto-Bump Management System Configuration
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "autobump.db"

# ── Cooldowns (seconds) ───────────────────────────────────────────────
CHANNEL_COOLDOWN = 2 * 60 * 60      # 2 hours between bumps on same channel
ACCOUNT_COOLDOWN = 30 * 60          # 30 minutes before account can bump again

# ── Human-like delay range (seconds) ─────────────────────────────────
HUMAN_DELAY_MIN = 3 * 60            # 3 minutes
HUMAN_DELAY_MAX = 20 * 60           # 20 minutes

# ── Discord ───────────────────────────────────────────────────────────
BUMP_COMMAND_ID = 947088344167366698  # Disboard /bump command ID

# ── API Server ────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "5000"))

# ── Scheduler ─────────────────────────────────────────────────────────
SCHEDULER_CHECK_INTERVAL = 30       # Seconds between scheduler ticks

# ── Logging ───────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s │ %(levelname)-7s │ %(name)-12s │ %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = BASE_DIR / "autobump.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB limit per log file
LOG_BACKUP_COUNT = 3             # Keep up to 3 backup log files
