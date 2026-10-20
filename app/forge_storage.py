"""Key-value store that stands in for Forge Storage (architecture, table 6)."""
import json
import threading
from pathlib import Path

DEFAULTS: dict[str, dict] = {
    "weights.config": {"skills": 0.5, "workload": 0.25, "priority": 0.15, "deadline": 0.10},
    "settings.project": {
        "enabled": True,
        "top_n": 5,
        "timeout_ms": 3000,
        "workload_limit": 12,
        "max_new_per_candidate": 1,
        "demo_algorithm_outage": False,
    },
    "skills.catalog": {"version": 0, "items": []},
}


class ForgeStorage:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        if not path.exists():
            self._write(dict(DEFAULTS))

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str) -> dict:
        data = self._read()
        return data.get(key, DEFAULTS.get(key, {}))

    def set(self, key: str, value: dict) -> dict:
        with self.lock:
            data = self._read()
            data[key] = value
            self._write(data)
        return value
