"""
Unblock Pi-hole - A web interface to remotely enable/disable Pi-hole's DNS blocking feature.
"""

from unblock_pihole.config import config
from unblock_pihole.server import main

__version__ = "1.0.0"
__all__ = ["config", "main"]