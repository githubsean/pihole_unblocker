#
# Pi-hole Proxy - A web interface to remotely enable/disable Pi-hole's DNS blocking feature.
#

from pihole_proxy.config import config
from pihole_proxy.server import main

__version__ = "1.0.0"
__all__ = ["config", "main"]