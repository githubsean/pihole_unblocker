#
# Server startup and signal handling for Pi-hole Proxy.
#
# Initializes the HTTP server, session manager, and cleanup thread.
#

import logging
import signal
import threading

from unblock_pihole.config import config

logger = logging.getLogger(__name__)


def setup_logging():
    # Configure logging to stdout with a consistent format.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_session_manager():
    # Create and return the Pi-hole session manager.
    from unblock_pihole.session import PiHoleSession, SessionCleanupThread

    session_mgr = PiHoleSession()
    cleanup_thread = SessionCleanupThread(session_mgr, check_interval=10)
    cleanup_thread.start()
    logger.info("Session inactivity monitor started")
    return session_mgr, cleanup_thread


def create_server(port, session_mgr):
    # Create and configure the HTTP server with the proxy handler.
    import http.server

    from unblock_pihole.handlers import PiHoleProxyHandler

    # Inject session manager into the handler class
    PiHoleProxyHandler.session_mgr = session_mgr

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), PiHoleProxyHandler)
    return server


def _handle_signal(signum, frame, server, cleanup_thread):
    # Signal handler that gracefully stops the server and triggers cleanup.
    from signal import Signals

    logger.info(f"Received signal {Signals(signum).name}. Initiating shutdown...")

    if cleanup_thread:
        cleanup_thread.stop()

    threading.Thread(target=server.shutdown, daemon=True).start()


def main():
    # Main entry point for the Pi-hole Proxy server.
    setup_logging()

    print(f"Starting Pi-hole Control Panel on port {config.server_port}...")
    print(f"   Pi-hole URL: {config.pihole_url}")
    print(f"   Session Timeout: {config.session_timeout}s")
    logger.info("Server starting up")

    # Create session manager and cleanup thread
    session_mgr, cleanup_thread = create_session_manager()

    # Create and configure the HTTP server
    server = create_server(config.server_port, session_mgr)

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: _handle_signal(s, f, server, cleanup_thread))

    try:
        server.serve_forever()
    finally:
        logger.info("Server shutdown complete. Cleaning up resources...")
        if cleanup_thread:
            cleanup_thread.stop()
            cleanup_thread.join(timeout=5)
        session_mgr._logout_pihole()
        server.server_close()


if __name__ == "__main__":
    main()