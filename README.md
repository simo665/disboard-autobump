# Discord Auto-Bump Management System

An autonomous system designed to manage multiple Discord accounts and coordinate server bumps via the Disboard `/bump` slash command. It includes a modern web-based management dashboard, a centralized SQLite database, and a robust background scheduling engine.

---

## Features

- **Account Management**: Add, remove, enable, or disable Discord user tokens. View real-time connection status and last-bump statistics.
- **Dynamic Channel Coordination**: Configure accounts to bump specific channels.
- **Smart Scheduling**:
  - Automatically respects the **2-hour Disboard channel cooldown** and a **30-minute account cooldown**.
  - Applies a randomized **human-like delay** (default: 3 to 20 minutes) after the cooldown expires to keep accounts safe.
  - Shuffles eligible accounts per channel to distribute bump activities naturally.
- **Real-Time Dashboard**:
  - View overall stats: Total accounts, active accounts, configured channels, next scheduled bump, and success/failure statistics.
  - Log viewer: Read real-time success logs and failure status messages.
  - Toggle switch to start/stop the scheduler dynamically.
- **Clean Architecture**: Built with FastAPI, SQLite (`aiosqlite`), and standard vanilla CSS/JS.

---

## Tech Stack

- **Backend**: Python, [FastAPI](https://fastapi.tiangolo.com/), `uvicorn`
- **Frontend**: Vanilla HTML5, CSS3, and JavaScript (served statically by FastAPI)
- **Database**: SQLite (via `aiosqlite` for asynchronous connection pooling)
- **Discord Integration**: Custom embedded `discord` self-bot compatible client wrapper with `discord-protos` support

---

## Project Structure

```text
autobump/
├── api.py           # FastAPI REST API endpoints
├── bumper.py        # Discord client wrapper to execute the /bump slash command
├── config.py        # Cooldowns, port settings, and log formats
├── database.py      # SQLite database layer using aiosqlite
├── discord/         # Self-bot compatible Discord library
├── main.py          # Application entry point (initializes db & scheduler, starts server)
├── models.py        # Pydantic data schemas for API requests/responses
├── requirements.txt # Project Python package dependencies
├── scheduler.py     # Background scheduler loop managing human delays and eligibility
├── static/          # Dashboard frontend assets
│   ├── css/         # Styling files
│   ├── js/          # Frontend logic / API controllers
│   └── index.html   # Main single-page application dashboard
└── LICENSE          # MIT License
```

---

## Setup & Installation

### 1. Clone & Set Up Directory
Ensure Python 3.8+ is installed on your machine.

### 2. Install Dependencies
Run the following command to install the required Python packages:

```bash
pip install -r requirements.txt
```

### 3. Start the Server
Run the entry point file:

```bash
python main.py
```

The server will start on `127.0.0.1:5000` by default. You can configure host/port by editing `config.py` or setting the environment variables:
- `API_HOST` (Default: `127.0.0.1`)
- `API_PORT` (Default: `5000`)
- `LOG_LEVEL` (Default: `INFO`)

### 4. Access the Dashboard
Open your web browser and navigate to:
[http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## Configuration Settings (`config.py`)

You can customize the behavior of the auto-bumper by modifying variables in [config.py](file:///c:/Users/jumpu/Dev/projects/discord/autobump/config.py):

* **`CHANNEL_COOLDOWN`**: Time in seconds to wait before a channel can be bumped again (Default: `7200` seconds / 2 hours).
* **`ACCOUNT_COOLDOWN`**: Time in seconds a single account must wait between bumps across any channels (Default: `1800` seconds / 30 minutes).
* **`HUMAN_DELAY_MIN` & `HUMAN_DELAY_MAX`**: The range (in seconds) for a randomized delay added after a channel becomes due, simulating human-like timing (Default: `180` to `1200` seconds).
* **`SCHEDULER_CHECK_INTERVAL`**: How often the scheduler checks the database for channels that are due (Default: `30` seconds).

---

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/simo665/disboard-autobump?tab=MIT-1-ov-file) file for details.
