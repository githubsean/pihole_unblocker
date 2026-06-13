"""
Configuration management for Pi-hole Proxy.

Loads settings from environment variables with sensible defaults.
"""

import os
import secrets
import socket
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Config:
    """Immutable configuration for the Pi-hole Proxy server."""

    # Pi-hole API URL
    pihole_url: str
    # Pi-hole API password (required)
    pihole_password: Optional[str]
    # HTTP server port
    server_port: int
    # Session timeout in seconds
    session_timeout: int
    # Pi-hole API request timeout in seconds
    pihole_timeout: int
    # API secret for frontend validation (generated at startup)
    api_secret: str
    # Custom User-Agent string for Pi-hole API requests
    custom_user_agent: str


def _get_env(key: str, default: str = "", *, required: bool = False) -> str:
    """Get an environment variable with optional required check."""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable '{key}' is not set")
    return value


def create_config() -> Config:
    """Create and return the application configuration."""
    pihole_url = _get_env("PIHOLE_URL", required=True)
    pihole_password = _get_env("PIHOLE_PASSWORD", required=False)
    server_port = int(_get_env("SERVER_PORT", "12345"))
    session_timeout = int(_get_env("SESSION_TIMEOUT", "60"))
    pihole_timeout = int(_get_env("PIHOLE_TIMEOUT", "5"))
    api_secret = _get_env("API_SECRET", secrets.token_hex(32))

    nodename = socket.gethostname()
    custom_user_agent = f"Pihole_Unblocker/1.0 ({nodename})"

    return Config(
        pihole_url=pihole_url,
        pihole_password=pihole_password,
        server_port=server_port,
        session_timeout=session_timeout,
        pihole_timeout=pihole_timeout,
        api_secret=api_secret,
        custom_user_agent=custom_user_agent,
    )


# Module-level singleton
config = create_config()