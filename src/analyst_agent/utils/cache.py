"""
Cache utilities for the Data Analyst Agent using diskcache.
"""
import diskcache as dc
import hashlib
import json
from typing import Any, Optional
from pathlib import Path

try:
    from ..configs.settings import CACHE_DIR, CACHE_EXPIRE
except ImportError:
    # Fallback for direct script execution
    from ..configs.settings import CACHE_DIR, CACHE_EXPIRE


class AnalystCache:
    """Cache implementation for LLM responses and computation results."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self.cache = dc.Cache(cache_dir)

    def _generate_key(self, data: Any) -> str:
        """Generate a consistent hash key from input data."""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        elif isinstance(data, (list, tuple)):
            data_str = json.dumps(sorted(data) if all(isinstance(x, str) for x in data) else data)
        else:
            data_str = str(data)

        return hashlib.md5(data_str.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        try:
            return self.cache.get(key)
        except Exception as e:
            print(f"[Cache] Get failed for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, expire: int = CACHE_EXPIRE) -> bool:
        try:
            self.cache.set(key, value, expire=expire)
            return True
        except Exception as e:
            print(f"[Cache] Set failed for key {key}: {e}")
            return False

    def get_llm_response(self, prompt: str, model: str) -> Optional[str]:
        cache_key = f"llm:{self._generate_key({'prompt': prompt, 'model': model})}"
        return self.get(cache_key)

    def set_llm_response(self, prompt: str, model: str, response: str) -> bool:
        cache_key = f"llm:{self._generate_key({'prompt': prompt, 'model': model})}"
        return self.set(cache_key, response)

    def get_code_result(self, code: str, files: list) -> Optional[dict]:
        cache_key = f"code:{self._generate_key({'code': code, 'files': [f['name'] for f in files]})}"
        return self.get(cache_key)

    def set_code_result(self, code: str, files: list, result: dict) -> bool:
        cache_key = f"code:{self._generate_key({'code': code, 'files': [f['name'] for f in files]})}"
        return self.set(cache_key, result, expire=CACHE_EXPIRE // 2)

    def clear(self) -> bool:
        try:
            self.cache.clear()
            return True
        except Exception as e:
            print(f"[Cache] Clear failed: {e}")
            return False

    def size(self) -> int:
        try:
            return len(self.cache)
        except Exception:
            return 0


_cache_instance = None

def get_cache() -> AnalystCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = AnalystCache()
    return _cache_instance

def cache_get(key: str) -> Optional[Any]:
    return get_cache().get(key)

def cache_set(key: str, value: Any, expire: int = CACHE_EXPIRE) -> bool:
    return get_cache().set(key, value, expire)
