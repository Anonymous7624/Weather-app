"""
Configuration and preferences (default location, recent searches, favorites).
Stored in instance/ for persistence across restarts.
"""

import os
import json
from pathlib import Path

# Instance folder for local data
INSTANCE_PATH = Path(__file__).resolve().parent.parent / "instance"
CONFIG_FILE = INSTANCE_PATH / "config.json"
MAX_RECENT = 5
MAX_FAVORITES = 10


def _ensure_instance():
    INSTANCE_PATH.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text("{}")


def _load_config():
    _ensure_instance()
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_config(data):
    _ensure_instance()
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_config():
    return Config()


class Config:
    """Handles default location, recent searches, and favorites."""

    def __init__(self):
        self._data = _load_config()

    @property
    def default_location(self):
        return os.environ.get("DEFAULT_LOCATION") or self._data.get("default_location", "")

    def get_recent_searches(self):
        return self._data.get("recent_searches", [])[:MAX_RECENT]

    def add_recent_search(self, location):
        recent = self._data.get("recent_searches", [])
        location_lower = location.strip().lower()
        recent = [x for x in recent if x.strip().lower() != location_lower]
        recent.insert(0, location.strip())
        self._data["recent_searches"] = recent[:MAX_RECENT]
        _save_config(self._data)

    def get_favorites(self):
        return self._data.get("favorites", [])[:MAX_FAVORITES]

    def add_favorite(self, location):
        favs = self._data.get("favorites", [])
        loc = location.strip()
        if loc and loc not in favs:
            favs.append(loc)
            self._data["favorites"] = favs[:MAX_FAVORITES]
            _save_config(self._data)

    def remove_favorite(self, location):
        favs = self._data.get("favorites", [])
        loc = location.strip().lower()
        favs = [x for x in favs if x.strip().lower() != loc]
        self._data["favorites"] = favs
        _save_config(self._data)
