from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, path: str = ".citeagle_cache.json", disabled: bool = False) -> None:
        self._path = Path(path)
        self._disabled = disabled
        self._data: dict[str, Any] = {}
        if not disabled and self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> Any | None:
        if self._disabled:
            return None
        entry = self._data.get(key)
        if entry is None:
            return None
        # entries are plain dicts or None
        return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        if self._disabled:
            return
        self._data[key] = {"value": value, "ts": time.time()}
        try:
            self._path.write_text(json.dumps(self._data, indent=2))
        except OSError:
            pass

    def __contains__(self, key: str) -> bool:
        return not self._disabled and key in self._data
