import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional
from app.config import settings

class LocalCache:
    def __init__(self, cache_dir: Optional[Path] = None, ttl_hours: int = 72):
        self.cache_dir = cache_dir or settings.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self._memory_cache = {}

    def _generate_key(self, namespace: str, key_data: Any) -> str:
        serialized = json.dumps(key_data, sort_keys=True, default=str)
        hash_val = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{namespace}_{hash_val}"

    def get(self, namespace: str, key_data: Any) -> Optional[Any]:
        key = self._generate_key(namespace, key_data)
        
        # Memory check
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() - entry["timestamp"] < self.ttl_seconds:
                return entry["data"]
            else:
                del self._memory_cache[key]
        
        # Disk check
        file_path = self.cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if time.time() - entry.get("timestamp", 0) < self.ttl_seconds:
                    self._memory_cache[key] = entry
                    return entry.get("data")
                else:
                    file_path.unlink(missing_ok=True)
            except Exception:
                pass
        return None

    def set(self, namespace: str, key_data: Any, value: Any) -> None:
        key = self._generate_key(namespace, key_data)
        entry = {
            "timestamp": time.time(),
            "data": value
        }
        self._memory_cache[key] = entry
        file_path = self.cache_dir / f"{key}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
        except Exception:
            pass

cache = LocalCache()
