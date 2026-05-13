from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

from .config import STATE_TTL_SECONDS


def new_record_id() -> str:
    return secrets.token_urlsafe(9)


@dataclass
class StoredRecord:
    value: dict[str, Any]
    expires_at: float


class MemoryStateStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredRecord] = {}

    def set(self, key: str, value: dict[str, Any], ttl: int = STATE_TTL_SECONDS) -> None:
        self._items[key] = StoredRecord(value=value, expires_at=time.time() + ttl)

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._items.get(key)
        if not item:
            return None
        if item.expires_at < time.time():
            self._items.pop(key, None)
            return None
        return item.value


class UpstashStateStore:
    def __init__(self, url: str, token: str) -> None:
        from upstash_redis import Redis

        self.redis = Redis(url=url, token=token)

    def set(self, key: str, value: dict[str, Any], ttl: int = STATE_TTL_SECONDS) -> None:
        self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    def get(self, key: str) -> dict[str, Any] | None:
        raw = self.redis.get(key)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if not isinstance(raw, str):
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None


_memory_store = MemoryStateStore()


def get_state_store() -> MemoryStateStore | UpstashStateStore:
    url = (
        os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
        or os.getenv("KV_REST_API_URL", "").strip()
    )
    token = (
        os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
        or os.getenv("KV_REST_API_TOKEN", "").strip()
    )
    if url and token:
        try:
            return UpstashStateStore(url, token)
        except Exception as exc:
            print(f"[state] Upstash unavailable, using memory fallback: {exc}")
    return _memory_store

