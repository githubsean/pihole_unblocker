"""
HTTP request handlers for Pi-hole Proxy.

Handles all HTTP GET and POST request routing, validation, and response generation.
"""

import json
import logging
import secrets
import urllib.request
import ssl
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError

from pihole_proxy.config import config
from pihole_proxy.models import ApiResponse, DisableRequest, StatusResponse
from pihole_proxy.session import PiHoleSession
from pihole_proxy.templates import html_loader

logger = logging.getLogger(__name__)

# Reuse SSL context (same as in session.py, but we import from session for consistency)
SSL_CONTEXT = ssl.create_default_context()


class PiHoleProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Pi-hole control operations."""

    # Class-level reference to the session manager (set by server)
    session_mgr: PiHoleSession = None

    def do_GET(self):
        """Route GET requests to appropriate handlers."""
        if self.path == "/":
            self._serve_index()
        elif self.path == "/api/status":
            self._handle_status()
        elif self.path == "/static/styles.css":
            self._serve_static_css()
        else:
            logger.warning(f"Not found: {self.path}")
            self._send_error_json(404, {"error": "Not found"})

    def do_POST(self):
        """Route POST requests to appropriate handlers."""
        real_ip = self.get_real_ip()
        logger.info(f"POST {self.path} from {real_ip}")

        if self.path == "/api/disable":
            self._handle_disable()
        elif self.path == "/api/enable":
            self._handle_enable()
        else:
            logger.warning(f"Not found: {self.path}")
            self._send_error_json(404, {"error": "Not found"})

    # ------------------------------------------------------------------
    # Static file serving
    # ------------------------------------------------------------------

    def _serve_static_css(self):
        """Serve the CSS stylesheet."""
        try:
            css_path = html_loader.css_path()
            with open(css_path, "r", encoding="utf-8") as f:
                css_content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(css_content.encode("utf-8"))
        except FileNotFoundError:
            logger.error("CSS file not found")
            self._send_error_json(500, {"error": "Static file not found"})

    # ------------------------------------------------------------------
    # Main page
    # ------------------------------------------------------------------

    def _serve_index(self):
        """Serve the main HTML control panel with injected API secret."""
        logger.info("Serving main page")
        html_content = html_loader.load(config.api_secret)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    # ------------------------------------------------------------------
    # API handlers
    # ------------------------------------------------------------------

    def _handle_status(self):
        """Handle GET /api/status - Return current blocking status."""
        try:
            result = self._get_blocking_status()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result.to_dict()).encode())
        except Exception as e:
            logger.error(f"Exception in _handle_status: {str(e)}")
            # Return safe default on error to avoid breaking UI
            error_response = StatusResponse(status="unknown", error=str(e))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(error_response.to_dict()).encode())

    def _handle_disable(self):
        """Handle POST /api/disable - Disable Pi-hole blocking for a duration."""
        if not self._validate_secret():
            logger.warning(f"Unauthorized disable attempt from {self.client_address[0]}")
            self._send_error_json(403, {"error": "Invalid or missing secret"})
            return

        try:
            request_data = self._read_json_body()
            disable_request = DisableRequest.from_dict(request_data)
        except ValueError as e:
            logger.warning(f"Invalid disable request: {e}")
            self._send_error_json(400, {
                "status": "error",
                "message": str(e),
            })
            return
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Malformed request body: {e}")
            self._send_error_json(400, {
                "status": "error",
                "message": "Invalid JSON in request body.",
            })
            return

        api_timer_seconds = disable_request.timer * 60

        def perform_disable(sid):
            disable_url = f"{config.pihole_url}/api/dns/blocking?sid={sid}"
            payload = {"blocking": False, "timer": api_timer_seconds}
            self._make_pihole_request(disable_url, payload, method="POST")
            return f"Blocking disabled successfully for {disable_request.timer} minute{'s' if disable_request.timer != 1 else ''}."

        try:
            message = self.session_mgr.execute_with_retry(perform_disable)
            logger.info(message)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(ApiResponse(status="success", message=message).to_dict()).encode())
        except Exception as e:
            logger.error(f"Exception in _handle_disable: {str(e)}")
            self._send_error_json(500, {"status": "error", "error": str(e)})

    def _handle_enable(self):
        """Handle POST /api/enable - Re-enable Pi-hole blocking immediately."""
        if not self._validate_secret():
            logger.warning(f"Unauthorized enable attempt from {self.client_address[0]}")
            self._send_error_json(403, {"error": "Invalid or missing secret"})
            return

        def perform_enable(sid):
            enable_url = f"{config.pihole_url}/api/dns/blocking?sid={sid}"
            payload = {"blocking": True}
            self._make_pihole_request(enable_url, payload, method="POST")
            return "Blocking has been re-enabled successfully."

        try:
            message = self.session_mgr.execute_with_retry(perform_enable)
            logger.info(message)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(ApiResponse(status="success", message=message).to_dict()).encode())
        except Exception as e:
            logger.error(f"Exception in _handle_enable: {str(e)}")
            self._send_error_json(500, {"status": "error", "error": str(e)})

    # ------------------------------------------------------------------
    # Pi-hole API helpers
    # ------------------------------------------------------------------

    def _get_blocking_status(self) -> StatusResponse:
        """Fetch and parse the current blocking status from Pi-hole."""

        def fetch_status(sid):
            status_url = f"{config.pihole_url}/api/dns/blocking?sid={sid}"
            resp_data, _ = self._make_pihole_request(status_url)

            is_enabled = resp_data.get("blocking") == "enabled"
            timer_remaining = resp_data.get("timer", 0)

            return StatusResponse(
                status="enabled" if is_enabled else "disabled",
                timer=timer_remaining,
                is_blocked=not is_enabled,
            )

        return self.session_mgr.execute_with_retry(fetch_status)

    def _make_pihole_request(self, url, payload=None, method="GET"):
        """Make an HTTP request to the Pi-hole API."""
        headers = {
            "User-Agent": config.custom_user_agent,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode() if payload else None,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}, resp.status
        except HTTPError as e:
            try:
                body = e.read().decode()
            except Exception:
                body = ""
            raise HTTPError(e.url, e.code, body, e.hdrs, None)

    # ------------------------------------------------------------------
    # Validation and utility helpers
    # ------------------------------------------------------------------

    def _validate_secret(self) -> bool:
        """Validate the backend secret using constant-time comparison."""
        header = self.headers.get("X-Backend-Secret")
        if not header:
            return False
        return secrets.compare_digest(header, config.api_secret)

    def _read_json_body(self) -> dict:
        """Read and parse a JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        return json.loads(body)

    def get_real_ip(self) -> str:
        """
        Extract the real client IP from various proxy headers.

        Supports X-Forwarded-For, X-Real-IP, and RFC 7239 Forwarded headers.
        Falls back to the direct TCP connection IP.
        """
        # 1. X-Forwarded-For (client, proxy1, proxy2)
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()

        # 2. X-Real-IP (often set by Nginx)
        xri = self.headers.get("X-Real-IP")
        if xri:
            return xri

        # 3. RFC 7239 Forwarded header (used by Caddy, some modern proxies)
        fwd = self.headers.get("Forwarded")
        if fwd:
            for part in fwd.split(","):
                part = part.strip()
                if part.startswith("for="):
                    ip = part.split("=")[1].strip()
                    if ip.startswith("["):
                        ip = ip.strip("[]")
                    return ip

        # 4. Fallback to direct TCP connection IP
        return self.client_address[0]

    def _send_error_json(self, status_code, error_data):
        """Send a JSON error response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(error_data).encode())

    def log_message(self, format, *args):
        """Suppress default HTTP server logging to avoid duplicates with our custom logger."""
        pass