"""
Session management for Pi-hole API authentication.

Provides thread-safe session handling with automatic retry on expired sessions
and background inactivity monitoring.
"""

import threading
import time
import logging
import json
import urllib.request
import ssl
from urllib.error import URLError, HTTPError

from pihole_proxy.config import config

logger = logging.getLogger(__name__)

# Reuse SSL context across all requests (performance + cleaner)
SSL_CONTEXT = ssl.create_default_context()


class PiHoleSession:
    """
    Manages a single authenticated session with the Pi-hole API.

    Provides thread-safe session handling with automatic re-authentication
    on expired sessions and proper cleanup.
    """

    def __init__(self):
        self.sid = None
        self.last_activity = time.time()
        self.lock = threading.Lock()

    def get_sid(self) -> str:
        """
        Returns a valid session ID, authenticating if necessary or expired. Thread-safe.
        """
        with self.lock:
            # Reset timer on any activity
            self.last_activity = time.time()

            # Return current session if already authenticated
            if self.sid:
                return self.sid

            logger.info("Authenticating with Pi-hole...")
            return self._authenticate()

    def _authenticate(self) -> str:
        """Perform authentication with the Pi-hole API."""
        auth_url = f"{config.pihole_url}/api/auth"
        payload = {"password": config.pihole_password}

        req = urllib.request.Request(
            auth_url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": config.custom_user_agent,
            },
        )

        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=config.pihole_timeout) as resp:
                auth_resp = json.loads(resp.read().decode())

            if not auth_resp.get("session", {}).get("valid"):
                raise Exception("Pi-hole authentication failed")

            self.sid = auth_resp["session"]["sid"]
            logger.info(f"Authentication successful. Session ID: {self.sid[:8]}...")
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise Exception(f"HTTP Error during Auth ({e.code}): {error_body}")
        except URLError as e:
            raise Exception(f"Network Error during Auth: {e.reason}")

        return self.sid

    def _logout_pihole(self):
        """
        Sends a logout request to Pi-hole and clears local state. Thread-safe.

        Note: Acquires lock only to read/clear sid, then performs I/O outside the lock
        to avoid blocking other threads.
        """
        with self.lock:
            sid = self.sid
            if not sid:
                return
            self.sid = None

        # Perform network request OUTSIDE the lock
        try:
            req = urllib.request.Request(
                f"{config.pihole_url}/api/auth?sid={sid}",
                method="DELETE",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": config.custom_user_agent,
                },
            )
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=config.pihole_timeout) as resp:
                pass  # 204 No Content is expected
        except Exception as e:
            logger.warning(f"Logout request failed (session likely already expired): {e}")

    def execute_with_retry(self, func, *args, **kwargs):
        """
        Executes a Pi-hole API function. Automatically retries once if session is invalid/expired.
        """
        try:
            sid = self.get_sid()
            return func(sid, *args, **kwargs)
        except HTTPError as e:
            error_body = ""
            if e.fp:
                try:
                    error_body = e.read().decode("utf-8")
                except Exception:
                    pass

            is_session_error = (
                e.code in [401, 403]
                or "unauthorized" in str(error_body).lower()
                or "expired" in str(error_body).lower()
            )

            if is_session_error:
                logger.info(
                    f"Session invalid/expired during operation (HTTP {e.code}). "
                    "Clearing local cache and retrying..."
                )
                self._logout_pihole()
                sid = self.get_sid()
                return func(sid, *args, **kwargs)
            raise


class SessionCleanupThread(threading.Thread):
    """
    Background thread that monitors session inactivity and logs out if timeout is reached.
    """

    def __init__(self, session_manager: PiHoleSession, check_interval: int = 10):
        super().__init__(daemon=True)
        self.session_mgr = session_manager
        self.check_interval = check_interval
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.wait(timeout=self.check_interval):
            if not self.stop_event.is_set():
                current_activity = time.time()
                should_logout = False
                with self.session_mgr.lock:
                    if (
                        self.session_mgr.sid
                        and (current_activity - self.session_mgr.last_activity)
                        >= config.session_timeout
                    ):
                        logger.info(
                            "Session inactive for too long. Logging out from background monitor."
                        )
                        should_logout = True
                # Call logout OUTSIDE the lock — _logout_pihole() acquires it internally
                if should_logout:
                    self.session_mgr._logout_pihole()

    def stop(self):
        """Signal the thread to stop."""
        self.stop_event.set()