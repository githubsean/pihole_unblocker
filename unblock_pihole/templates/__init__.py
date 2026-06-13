#
# Template loading for Pi-hole Proxy.
#
# Provides centralized loading of HTML and CSS template files.
#

import os
from pathlib import Path


class TemplateLoader:
    # Loads HTML and CSS template files from the templates directory.

    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).parent
        self.base_dir = base_dir
        self._html_cache = None

    def load(self, api_secret: str) -> str:
        # Load the index.html template and inject the API secret.
        if self._html_cache is None:
            html_path = self.base_dir / "index.html"
            with open(html_path, "r", encoding="utf-8") as f:
                self._html_cache = f.read()
        return self._html_cache.replace("__API_SECRET_PLACEHOLDER__", api_secret)

    def css_path(self) -> Path:
        # Return the path to the CSS file.
        return self.base_dir / "styles.css"

    def favicon_path(self) -> Path:
        # Return the path to the favicon SVG file.
        return self.base_dir / "favicon.svg"


# Module-level singleton
html_loader = TemplateLoader()