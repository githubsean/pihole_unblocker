#!/usr/bin/env python3
import http.server
import json
import urllib.request
import ssl
import os
from urllib.error import URLError, HTTPError
import logging
import time
import threading
import signal
import secrets

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration (override with environment variables for better security)
PIHOLE_URL = os.getenv("PIHOLE_URL", "https://pihole.sean-anderson.com")
PIHOLE_PASSWORD = os.getenv("PIHOLE_PASSWORD")
SERVER_PORT = int(os.getenv("SERVER_PORT", 12345))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", 60))
PIHOLE_TIMEOUT = int(os.getenv("PIHOLE_TIMEOUT", 5))
API_SECRET = secrets.token_hex(32)
CUSTOM_USER_AGENT = f"Pihole_Unblocker/1.0 ({os.uname().nodename})"

# Reuse SSL context across all requests (performance + cleaner)
SSL_CONTEXT = ssl.create_default_context()

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Disable PiHole</title>
    
    <!-- 32x32 Green Shield Favicon -->
    <link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHBhdGggZD0iTTE2IDJMNCA4djEwYzAgNyA1IDEyIDEyIDE0IDctMiAxMi03IDEyLTE0VjhMMTYgMnoiIGZpbGw9IiMyZWNjNDEiLz48L3N2Zz4=">
    
    <style>
        /* ... (CSS remains exactly the same) ... */
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif; background-color: #f5f7fa; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; width: 90%; }
        h1 { color: #2c3e50; margin-top: 0; font-size: 1.5rem; }
        .status-indicator { display: flex; align-items: center; padding: 0.75rem; border-radius: 8px; margin-bottom: 1.5rem; font-weight: 600; transition: all 0.3s ease; }
        .status-indicator.enabled { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-indicator.disabled { background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .status-dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 0.75rem; animation: pulse 2s infinite; }
        .enabled .status-dot { background-color: #28a745; }
        .disabled .status-dot { background-color: #ffc107; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .form-group { margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 0.5rem; color: #34495e; font-weight: 500; }
        .slider-container { position: relative; margin-top: 0.5rem; }
        input[type="range"] { width: 100%; height: 8px; border-radius: 4px; background: #e1e8ed; outline: none; -webkit-appearance: none; appearance: none; }
        input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 24px; height: 24px; border-radius: 50%; background: #3498db; cursor: pointer; transition: background-color 0.2s; }
        input[type="range"]::-webkit-slider-thumb:hover { background: #2980b9; }
        input[type="range"]::-moz-range-thumb { width: 24px; height: 24px; border-radius: 50%; background: #3498db; cursor: pointer; border: none; }
        .slider-value { text-align: center; font-size: 1.1rem; color: #2c3e50; margin-top: 0.75rem; font-weight: 600; }
        button { width: 100%; padding: 0.75rem; border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; transition: all 0.2s; margin-bottom: 0.75rem; }
        button:last-child { margin-bottom: 0; }
        .btn-disable { background-color: #e74c3c; color: white; }
        .btn-disable:hover:not(:disabled) { background-color: #c0392b; }
        .btn-enable { background-color: #28a745; color: white; }
        .btn-enable:hover:not(:disabled) { background-color: #218838; }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .message { margin-top: 1rem; padding: 0.75rem; border-radius: 6px; display: none; }
        .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Disable PiHole</h1>
        
        <div id="statusIndicator" class="status-indicator enabled">
            <span class="status-dot"></span>
            <span id="statusText">Blocking is ENABLED</span>
        </div>



        <form id="disableForm">
            <div class="form-group">
                <label for="minutesSlider">Minutes</label>
                <div class="slider-container">
                    <input type="range" id="minutesSlider" name="minutes" min="0" max="60" value="5" step="1">
                    <div class="slider-value" id="sliderDisplay">5 minutes</div>
                </div>
            </div>
            
            <button type="submit" id="disableBtn" class="btn-disable">Disable Pihole</button>
            <button type="button" id="enableBtn" class="btn-enable">Enable Pihole</button>
        </form>
        
        <div id="responseMessage" class="message"></div>
    </div>

    <script>
        const BACKEND_SECRET = "__API_SECRET_PLACEHOLDER__";
        const slider = document.getElementById("minutesSlider");
        const display = document.getElementById("sliderDisplay");
        
        slider.addEventListener("input", function() {
            const val = parseInt(this.value);
            display.textContent = `${val} minute${val === 1 ? '' : 's'}`;
        });
        
        let pollInterval;
        function updateStatus() {
            fetch("/api/status")
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById("statusIndicator");
                    const statusText = document.getElementById("statusText");
                    
                    if (data.status === "enabled") {
                        statusDiv.className = "status-indicator enabled";
                        statusText.textContent = "Blocking is ENABLED";
                    } else if (data.status === "disabled") {
                        statusDiv.className = "status-indicator disabled";
                        
                        const timerSeconds = data.timer || 0;
                        if (timerSeconds < 60) {
                            statusText.textContent = `Blocking is DISABLED (${Math.ceil(timerSeconds)}s remaining)`;
                        } else {
                            const minutesRemaining = Math.ceil(timerSeconds / 60);
                            statusText.textContent = `Blocking is DISABLED (${minutesRemaining}m remaining)`;
                        }
                    } else {
                        statusDiv.className = "status-indicator disabled";
                        statusText.textContent = "Status unknown - check server logs";
                    }
                })
                .catch(error => {
                    console.log("Status poll failed:", error);
                });
        }
        
        updateStatus();
        pollInterval = setInterval(updateStatus, 10000);



        document.getElementById("disableForm").addEventListener("submit", async function(e) {
            e.preventDefault();
            
            const btn = document.getElementById("disableBtn");
            const messageDiv = document.getElementById("responseMessage");
            const minutes = parseInt(slider.value);
            
            if (isNaN(minutes) || minutes < 0 || minutes > 60) {
                showMessage("Please enter a value between 0 and 60 minutes.", "error");
                return;
            }
            
            btn.disabled = true;
            btn.textContent = "Disabling...";
            messageDiv.style.display = "none";
            
            try {
                const response = await fetch("/api/disable", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-Backend-Secret": BACKEND_SECRET },
                    body: JSON.stringify({ timer: minutes })
                });
                
                const data = await response.json();
                
                if (data.status === "success") {
                    showMessage(data.message, "success");
                    updateStatus();
                } else {
                    showMessage(data.error || "An unexpected error occurred.", "error");
                }
            } catch (error) {
                showMessage("Network error: Could not connect to the backend service. Please check your connection and try again.", "error");
            } finally {
                btn.disabled = false;
                btn.textContent = "Disable Pihole";
            }
        });



        document.getElementById("enableBtn").addEventListener("click", async function() {
            const btn = this;
            const messageDiv = document.getElementById("responseMessage");
            
            btn.disabled = true;
            btn.textContent = "Enabling...";
            messageDiv.style.display = "none";
            
            try {
                const response = await fetch("/api/enable", {
                    method: "POST",
                    headers: { "X-Backend-Secret": BACKEND_SECRET }                    
                });
                
                const data = await response.json();
                
                if (data.status === "success") {
                    showMessage(data.message, "success");
                    updateStatus();
                } else {
                    showMessage(data.error || "An unexpected error occurred.", "error");
                }
            } catch (error) {
                showMessage("Network error: Could not connect to the backend service. Please check your connection and try again.", "error");
            } finally {
                btn.disabled = false;
                btn.textContent = "Enable Pihole";
            }
        });
        
        function showMessage(text, type) {
            const messageDiv = document.getElementById("responseMessage");
            messageDiv.textContent = text;
            messageDiv.className = `message ${type}`;
            messageDiv.style.display = "block";
            
            if (type === "success") {
                setTimeout(() => {
                    messageDiv.style.display = "none";
                }, 5000);
            }
        }
    </script>
</body>
</html>"""



class PiHoleSession:
    # Manages a single authenticated session with the Pi-hole API.
    def __init__(self):
        self.sid = None
        self.last_activity = time.time()
        self.lock = threading.Lock()  # Thread safety for session state
        
    def get_sid(self):
        # Returns a valid session ID, authenticating if necessary or expired. Thread-safe.
        with self.lock:  # FIXED: Proper lock acquisition
            # Reset timer on any activity
            current_activity = time.time()
            self.last_activity = current_activity
            
            # Return current session if already authorised
            if self.sid:
                return self.sid
                
            logger.info("Authenticating with Pi-hole...")
            auth_url = f"{PIHOLE_URL}/api/auth"
            payload = {"password": PIHOLE_PASSWORD}
            
            req = urllib.request.Request(auth_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "User-Agent": CUSTOM_USER_AGENT})
            
            try:
                with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=PIHOLE_TIMEOUT) as resp:
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
        # Sends a logout request to Pi-hole and clears local state. Thread-safe.
        # 1. Acquire lock ONLY to safely read and clear self.sid
        with self.lock:
            sid = self.sid
            if not sid:
                return
            self.sid = None  # Clear immediately to prevent race conditions

        # 2. Perform network request OUTSIDE the lock
        # Holding a lock during I/O blocks other threads and can cause deadlocks
        try:
            req = urllib.request.Request(f"{PIHOLE_URL}/api/auth?sid={sid}", method="DELETE", headers={"Content-Type": "application/json","User-Agent": CUSTOM_USER_AGENT})
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=PIHOLE_TIMEOUT) as resp:
                pass # 204 No Content is expected
        except Exception as e:
            logger.warning(f"Logout request failed (session likely already expired): {e}")

    def execute_with_retry(self, func, *args, **kwargs):
        # Executes a Pi-hole API function. Automatically retries once if session is invalid/expired.
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
                    
            is_session_error = (e.code in [401, 403] or 
                                "unauthorized" in str(error_body).lower() or 
                                "expired" in str(error_body).lower())
            
            if is_session_error:
                logger.info(f"Session invalid/expired during operation (HTTP {e.code}). Clearing local cache and retrying...")
                self._logout_pihole()  # ✅ Properly cleans up both locally and on Pi-hole
                
                sid = self.get_sid()
                return func(sid, *args, **kwargs)
            raise



class SessionCleanupThread(threading.Thread):
    # Background thread that monitors session inactivity and logs out if timeout is reached.
    def __init__(self, session_manager, check_interval=10):
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
                    if self.session_mgr.sid and (current_activity - self.session_mgr.last_activity) >= SESSION_TIMEOUT:
                        logger.info("Session inactive for too long. Logging out from background monitor.")
                        should_logout = True
                # ✅ Call logout OUTSIDE the lock — _logout_pihole() acquires it internally
                if should_logout:
                    self.session_mgr._logout_pihole()
                    
class PiHoleProxyHandler(http.server.BaseHTTPRequestHandler):

    def get_real_ip(self):
        # 1. X-Forwarded-For is the most common standard (client, proxy1, proxy2)
        xff = self.headers.get('X-Forwarded-For')
        if xff:
            return xff.split(',')[0].strip()
        
        # 2. X-Real-IP is often set by Nginx
        xri = self.headers.get('X-Real-IP')
        if xri:
            return xri
            
        # 3. RFC 7239 Forwarded header (used by Caddy, some modern proxies)
        fwd = self.headers.get('Forwarded')
        if fwd:
            for part in fwd.split(','):
                part = part.strip()
                if part.startswith('for='):
                    ip = part.split('=')[1].strip()
                    if ip.startswith('['):  # IPv6 bracket notation
                        ip = ip.strip('[]')
                    return ip
        
        # 4. Fallback to the direct TCP connection IP
        return self.client_address[0]

    def do_GET(self):
        if self.path == "/":
            logger.info("Serving main page")
            # Inject the runtime-generated secret before serving
            injected_html = HTML_PAGE.replace("__API_SECRET_PLACEHOLDER__", API_SECRET)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(injected_html.encode("utf-8"))
        elif self.path == "/api/status":
            self._handle_status()
        else:
            logger.warning(f"Not found: {self.path}")
            self.send_error_json(404, {"error": "Not found"})



    def do_POST(self):
        real_ip = self.get_real_ip()  # Extract once per request

        if self.path == "/api/disable":
            logger.info(f"Disable request from {real_ip}")
            self._handle_disable()
        elif self.path == "/api/enable":
            logger.info(f"Enable request from {real_ip}")
            self._handle_enable()
        else:
            logger.warning(f"Not found: {self.path}")
            self.send_error_json(404, {"error": "Not found"})



    def send_error_json(self, status_code, error_data):
        # Helper to send proper JSON error responses.
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(error_data).encode())



    def _make_pihole_request(self, sid, url, payload=None, method="GET"):
        req = urllib.request.Request(url,
                                    data=json.dumps(payload).encode() if payload else None,
                                    headers={"Content-Type": "application/json","User-Agent": CUSTOM_USER_AGENT} if payload else {},
                                    method=method)
        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}, resp.status
        except HTTPError as e:
            # Return the status and body for higher‑level handling
            try:
                body = e.read().decode()
            except Exception:
                body = ""
            raise HTTPError(e.url, e.code, body, e.hdrs, None)

    def _validate_secret(self):
        header = self.headers.get("X-Backend-Secret")
        if not header:
            return False
        # Constant-time comparison prevents timing attacks on the secret
        return secrets.compare_digest(header, API_SECRET)

    def _handle_disable(self):
        if not self._validate_secret():
            logger.warning(f"Unauthorized disable attempt from {self.client_address[0]}")
            self.send_error_json(403, {"error": "Invalid or missing secret"})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            data = json.loads(body)
            minutes = data.get("timer", 5)
            
            if not isinstance(minutes, int) or minutes < 0 or minutes > 60:
                logger.warning(f"Invalid timer value: {minutes}")
                self.send_error_json(400, {"status": "error", "message": "Invalid input. Timer must be a number between 0 and 60 minutes."})
                return



            api_timer_seconds = minutes * 60
            
            def perform_disable(sid):
                disable_url = f"{PIHOLE_URL}/api/dns/blocking?sid={sid}"
                payload = {"blocking": False, "timer": api_timer_seconds}
                resp_data, _ = self._make_pihole_request(sid, disable_url, payload, method="POST")
                return f"Blocking disabled successfully for {minutes} minute{'s' if minutes != 1 else ''}."

            message = session_mgr.execute_with_retry(perform_disable)
            logger.info(message)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": message}).encode())
            
        except Exception as e:
            logger.error(f"Exception in _handle_disable: {str(e)}")
            self.send_error_json(500, {"status": "error", "error": str(e)})



    def _handle_enable(self):
        if not self._validate_secret():
            logger.warning(f"Unauthorized enable attempt from {self.client_address[0]}")
            self.send_error_json(403, {"error": "Invalid or missing secret"})
            return

        try:
            def perform_enable(sid):
                enable_url = f"{PIHOLE_URL}/api/dns/blocking?sid={sid}"
                payload = {"blocking": True}
                resp_data, _ = self._make_pihole_request(sid, enable_url, payload, method="POST")
                return "Blocking has been re-enabled successfully."

            message = session_mgr.execute_with_retry(perform_enable)
            logger.info(message)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": message}).encode())
            
        except Exception as e:
            logger.error(f"Exception in _handle_enable: {str(e)}")
            self.send_error_json(500, {"status": "error", "error": str(e)})



    def _handle_status(self):
        try:
            def perform_status(sid):
                status_url = f"{PIHOLE_URL}/api/dns/blocking?sid={sid}"
                resp_data, _ = self._make_pihole_request(sid, status_url)
                
                is_enabled = resp_data.get("blocking") == "enabled"
                timer_remaining = resp_data.get("timer", 0)
                
                return {
                    "status": "enabled" if is_enabled else "disabled",
                    "timer": timer_remaining,
                    "is_blocked": not is_enabled
                }

            result = session_mgr.execute_with_retry(perform_status)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            logger.error(f"Exception in _handle_status: {str(e)}")
            # Return safe default on error to avoid breaking UI
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "unknown", "error": str(e)}).encode())



    def log_message(self, format, *args):
        pass  # Suppress default HTTP server logging to avoid duplicates with our custom logger



# Module-level state
session_mgr = PiHoleSession()
cleanup_thread = None
server = None



def _handle_signal(signum, frame):
    # Signal handler that gracefully stops the server and triggers cleanup.
    logger.info(f"Received signal {signal.Signals(signum).name}. Initiating shutdown...")
    
    if cleanup_thread:
        cleanup_thread.stop_event.set()
        
    threading.Thread(target=server.shutdown, daemon=True).start()



if __name__ == "__main__":
    print(f"Starting Pi-hole Control Panel on port {SERVER_PORT}...")
    print(f"   Pi-hole URL: {PIHOLE_URL}")
    print(f"   Session Timeout: {SESSION_TIMEOUT}s")
    logger.info("Server starting up")

    server = http.server.ThreadingHTTPServer(("0.0.0.0", SERVER_PORT), PiHoleProxyHandler)
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)
        
    cleanup_thread = SessionCleanupThread(session_mgr, check_interval=10)
    cleanup_thread.start()
    logger.info("Session inactivity monitor started")
    
    try:
        server.serve_forever()
    finally:
        logger.info("Server shutdown complete. Cleaning up resources...")
        if cleanup_thread:
            cleanup_thread.stop_event.set()  # Ensure thread exits cleanly
            cleanup_thread.join(timeout=5)
        session_mgr._logout_pihole()  # Safe to call without lock during single-threaded shutdown
        server.server_close()
