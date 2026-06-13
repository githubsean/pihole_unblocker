# Pi-hole Unblocker

A simple Python-based proxy server that provides a web interface to remotely enable/disable Pi-hole's DNS blocking feature.

## Project Structure

```
pihole_unblocker/
├── .gitignore
├── README.md
├── docs/              (empty)
├── scripts/           (empty)
├── src/
│   └── pihole_proxy.py   (main application - 585 lines)
├── systemd/
│   └── unblock_pihole.service
└── tests/             (empty)
```

## Main Application (`src/pihole_proxy.py`)

A self-contained Python HTTP server (~585 lines) with these key components:

- **`PiHoleSession`** - Manages authenticated sessions with the Pi-hole API, including thread-safe session handling, automatic retry on expired sessions, and proper logout.
- **`SessionCleanupThread`** - Background daemon thread that monitors session inactivity and logs out after a configurable timeout (default 60s).
- **`PiHoleProxyHandler`** - HTTP request handler serving:
  - `GET /` - A styled HTML control panel with a slider to select disable duration (0-60 min)
  - `GET /api/status` - Returns current blocking status and timer
  - `POST /api/disable` - Disables Pi-hole blocking for a specified duration
  - `POST /api/enable` - Re-enables Pi-hole blocking immediately

## Key Features

- **Security:** API secret (generated at startup via `secrets.token_hex(32)`) injected into the frontend; constant-time comparison for secret validation
- **Configuration via environment variables:** `PIHOLE_URL`, `PIHOLE_PASSWORD`, `SERVER_PORT`, `SESSION_TIMEOUT`, `PIHOLE_TIMEOUT`
- **Proxy-aware IP detection:** Supports `X-Forwarded-For`, `X-Real-IP`, and RFC 7239 `Forwarded` headers
- **Graceful shutdown:** Signal handlers for SIGINT/SIGTERM, proper session cleanup
- **SSL context reuse** across requests for performance

## Systemd Service

Configured to run as the `pihole` user from `/opt/unblock_pihole`, with environment loaded from `.env`, auto-restart on failure, and proper signal handling.