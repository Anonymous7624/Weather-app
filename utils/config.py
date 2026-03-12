"""
Configuration for Clearcast.
Default location from environment. Favorites and recents are stored
client-side in localStorage for per-user privacy.
"""

import os


def get_default_location():
    """Return the configured default location (from environment or fallback)."""
    return os.environ.get("DEFAULT_LOCATION", "")
