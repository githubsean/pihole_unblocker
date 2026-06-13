"""
Allow running the package as a module: python -m pihole_proxy
"""

from pihole_proxy.server import main

if __name__ == "__main__":
    main()