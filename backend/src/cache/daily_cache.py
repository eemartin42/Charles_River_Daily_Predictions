import json
from pathlib import Path

from src.paths import CACHE_DIR


class DailyCache:
    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir is not None else CACHE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key: str) -> Path:
        safe_key = key.replace(":", "_").replace("/", "_")
        return self.base_dir / f"{safe_key}.json"

    def get(self, key: str):
        path = self._key_path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def set(self, key: str, value):
        path = self._key_path(key)
        path.write_text(json.dumps(value))

