# Pi-hole Unblocker

A Python-based proxy server that provides a web interface to remotely enable/disable Pi-hole's DNS blocking feature for a configurable duration.

## Project Structure

```
pihole_unblocker/
├── .gitignore
├── README.md
├── pyproject.toml              # Package configuration and dependencies
├── unblock_pihole/               # Main Python package
│   ├── __init__.py             # Package initialization and exports
│   ├── __main__.py             # Entry point for `python -m unblock_pihole`
│   ├── config.py               # Configuration management (env vars)
│   ├── models.py               # Data models (Pydantic-style dataclasses)
│   ├── session.py              # Pi-hole API session management
│   ├── handlers.py             # HTTP request handlers
│   ├── server.py               # Server startup and signal handling
│   └── templates/
│       ├── __init__.py         # Template loader utilities
│       ├── index.html          # Main control panel HTML
│       └── styles.css          # Stylesheet
├── docs/                       # Documentation
├── scripts/                    # Utility scripts
├── systemd/
│   └── unblock_pihole.service  # systemd service unit file
└── tests/                      # Unit and integration tests
```

## Module Breakdown

### `config.py` — Configuration Management
Centralized configuration loaded from environment variables using a frozen dataclass:

| Variable | Default | Description |
|----------|---------|-------------|
| `PIHOLE_URL` | *(required)* | Pi-hole API URL (e.g., `https://pihole.example.com`) |
| `PIHOLE_PASSWORD` | *(required)* | Pi-hole API password |
| `SERVER_PORT` | `12345` | HTTP server listening port |
| `SESSION_TIMEOUT` | `60` | Session inactivity timeout in seconds |
| `PIHOLE_TIMEOUT` | `5` | Pi-hole API request timeout in seconds |
| `API_SECRET` | *(auto-generated)* | Backend secret for frontend validation |


### `models.py` — Data Models
Type-safe dataclasses for request/response handling:
- **`StatusResponse`** — Blocking status API response
- **`ApiResponse`** — Generic success/error response wrapper
- **`DisableRequest`** — Parsed and validated disable request body

### `session.py` — Session Management
- **`PiHoleSession`** — Thread-safe Pi-hole API authentication with automatic re-authentication on expired sessions
- **`SessionCleanupThread`** — Background daemon that monitors session inactivity and logs out after the configured timeout

### `handlers.py` — HTTP Request Handling
- **`PiHoleProxyHandler`** — Handles all HTTP routes:
  - `GET /` — Serves the HTML control panel
  - `GET /static/styles.css` — Serves the CSS stylesheet
  - `GET /api/status` — Returns current blocking status and timer
  - `POST /api/disable` — Disables blocking for a specified duration (0–60 min)
  - `POST /api/enable` — Re-enables blocking immediately

### `server.py` — Server Lifecycle
- `setup_logging()` — Configures structured logging
- `create_session_manager()` — Initializes session and cleanup thread
- `create_server()` — Creates the `ThreadingHTTPServer` with configured handler
- `main()` — Entry point with signal handling and graceful shutdown

### `templates/` — Frontend Assets
- **`index.html`** — Self-contained control panel with embedded JavaScript (slider for duration, real-time status polling)
- **`styles.css`** — Responsive styling with animated status indicators

## Key Features

- **Security:** API secret (generated at startup via `secrets.token_hex(32)`) injected into the frontend; constant-time comparison for secret validation
- **Configuration via environment variables:** `PIHOLE_URL`, `PIHOLE_PASSWORD`, `SERVER_PORT`, `SESSION_TIMEOUT`, `PIHOLE_TIMEOUT`
- **Proxy-aware IP detection:** Supports `X-Forwarded-For`, `X-Real-IP`, and RFC 7239 `Forwarded` headers
- **Graceful shutdown:** Signal handlers for SIGINT/SIGTERM, proper session cleanup
- **SSL context reuse** across requests for performance
- **Thread-safe session management** with automatic retry on expired sessions

## Installation

### Option 1: Install to /opt (Recommended for systemd service)

This is the recommended approach for production deployments using systemd:

```bash
# Create a new user for the service
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --comment "Unblock PiHole service" unblock-pihole

# Create the installation directory
sudo mkdir -p /opt/unblock_pihole
sudo chown unblock-pihole:unblock-pihole /opt/unblock_pihole

# Clone the repository. You may have to sudo this and then change the owner of all the files/directories to the unblock-pihole user
cd /opt/unblock_pihole
git clone <repository-url> .

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package in editable mode
pip install -e .
```

### Option 2: Install system-wide

```bash
# Clone the repository
git clone <repository-url>
cd pihole_unblocker

# Install system-wide (may require sudo)
pip install .
```

### Option 3: Development install

```bash
# Clone the repository
git clone <repository-url>
cd pihole_unblocker

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable/development mode
pip install -e .
```

## Configuration

Create a `.env` file with the required configuration. The file should be placed at the path referenced by your deployment method:

```bash
PIHOLE_URL=https://pihole.example.com
PIHOLE_PASSWORD=your_password
SERVER_PORT=12345
SESSION_TIMEOUT=60
PIHOLE_TIMEOUT=5
```

## Usage

### Running via systemd (recommended for production)

1. Install the package to `/opt/unblock_pihole` (see Installation above)

2. Create the `.env` file at `/opt/unblock_pihole/.env`:
   ```bash
   PIHOLE_URL=https://pihole.example.com
   PIHOLE_PASSWORD=your_password
   SERVER_PORT=12345
   ```

3. Copy the service file and enable it:
   ```bash
   sudo cp systemd/unblock_pihole.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable unblock_pihole
   sudo systemctl start unblock_pihole
   ```

4. Check status:
   ```bash
   sudo systemctl status unblock_pihole
   ```

### Running from command line

```bash
# Set required environment variables
export PIHOLE_URL="https://pihole.example.com"
export PIHOLE_PASSWORD="your_password"

# Run using the package module entry point
python -m unblock_pihole

# Or use the installed command-line entry point (after pip install)
unblock_pihole
```

### With custom port

```bash
SERVER_PORT=8080 python -m unblock_pihole
```

### How the module path works

When running `python -m unblock_pihole`, Python searches for the `unblock_pihole` package in:
1. The current working directory
2. Directories listed in `sys.path` (includes the directory of the script being run)
3. Python's site-packages (where `pip install` places packages)

For the systemd service, the `ExecStart` uses the full path to the virtual environment's Python interpreter (`/opt/unblock_pihole/.venv/bin/python`), and since the package is installed in that virtual environment, Python can find `unblock_pihole` automatically.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main control panel page |
| GET | `/api/status` | Get current blocking status |
| POST | `/api/disable` | Disable blocking (body: `{"timer": 5}`) |
| POST | `/api/enable` | Enable blocking immediately |

All API endpoints require the `X-Backend-Secret` header with the value generated at server startup.

## License

MIT

## AI Statement
This project was developed with the assistance of AI.
I mostly used Qwen 3.6 integrated with VS Code and Cline.
I also used Claude.ai for other general advice.