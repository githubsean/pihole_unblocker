# Pi-hole Unblocker

A Python-based proxy server that provides a web interface to remotely enable/disable Pi-hole's DNS blocking feature for a configurable duration.

## Project Structure

```
pihole_unblocker/
├── .gitignore
├── README.md
├── pyproject.toml              # Package configuration and dependencies
├── pihole_proxy/               # Main Python package
│   ├── __init__.py             # Package initialization and exports
│   ├── __main__.py             # Entry point for `python -m pihole_proxy`
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

```bash
# Clone the repository
git clone <repository-url>
cd pihole_unblocker

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .
```

## Usage

### Command Line

```bash
# Set required environment variables
export PIHOLE_URL="https://pihole.sean-anderson.com"
export PIHOLE_PASSWORD="your_password"

# Run the server
python -m pihole_proxy

# Or use the entry point (after installation)
pihole-proxy
```

### With Custom Port

```bash
SERVER_PORT=8080 python -m pihole_proxy
```

### Docker

```bash
docker build -t pihole-unblocker .
docker run -e PIHOLE_URL="https://pihole.example.com" \
           -e PIHOLE_PASSWORD="your_password" \
           -p 12345:12345 \
           pihole-unblocker
```

## Systemd Service

The project includes a systemd service file for running as a background service:

1. Copy the service file:
   ```bash
   sudo cp systemd/unblock_pihole.service /etc/systemd/system/
   ```

2. Create a `.env` file at `/opt/unblock_pihole/.env`:
   ```
   PIHOLE_URL=https://pihole.sean-anderson.com
   PIHOLE_PASSWORD=your_password
   SERVER_PORT=12345
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable unblock_pihole
   sudo systemctl start unblock_pihole
   ```

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