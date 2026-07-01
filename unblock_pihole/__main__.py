"""
Allow running the package as a module: python -m unblock_pihole
"""

from unblock_pihole.server import main

if __name__ == "__main__":
    main()