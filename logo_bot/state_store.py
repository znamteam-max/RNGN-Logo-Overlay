from __future__ import annotations

import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .config import STATE_TTL_SECONDS


def new_record_id() -> str:
    return secrets.token_urlsafe(9)


def _decode_json(raw: Any) -> dict[str, Any] | None:
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


@dataclass
class StoredRecord:
    value: dict[str, Any]
    expires_at: float


class MemoryStateStore:
    """Per-instance fallback. Hash records never expire, but die with the instance."""

    backend = "memory"
    persistent = False

    def __init__(self) -> None:
        self._items: dict[str, StoredRecord] = {}
        self._hashes: dict[str, dict[str, dict[str, Any]]] = {}

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

    def delete(self, key: str) -> None:
        self._items.pop(key, None)

    def hset(self, name: str, field: str, value: dict[str, Any]) -> None:
        self._hashes.setdefault(name, {})[field] = json.loads(json.dumps(value))

    def hget(self, name: str, field: str) -> dict[str, Any] | None:
        return self._hashes.get(name, {}).get(field)

    def hgetall(self, name: str) -> dict[str, dict[str, Any]]:
        return dict(self._hashes.get(name, {}))


class UpstashStateStore:
    backend = "redis"
    persistent = True

    def __init__(self, url: str, token: str) -> None:
        from upstash_redis import Redis

        self.redis = Redis(url=url, token=token)

    def set(self, key: str, value: dict[str, Any], ttl: int = STATE_TTL_SECONDS) -> None:
        self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    def get(self, key: str) -> dict[str, Any] | None:
        return _decode_json(self.redis.get(key))

    def delete(self, key: str) -> None:
        self.redis.delete(key)

    def hset(self, name: str, field: str, value: dict[str, Any]) -> None:
        self.redis.hset(name, field, json.dumps(value, ensure_ascii=False))

    def hget(self, name: str, field: str) -> dict[str, Any] | None:
        return _decode_json(self.redis.hget(name, field))

    def hgetall(self, name: str) -> dict[str, dict[str, Any]]:
        raw = self.redis.hgetall(name) or {}
        result: dict[str, dict[str, Any]] = {}
        for field, value in raw.items():
            if isinstance(field, bytes):
                field = field.decode("utf-8")
            decoded = _decode_json(value)
            if decoded is not None:
                result[str(field)] = decoded
        return result


_memory_store = MemoryStateStore()
_STORAGE_ENV_PATTERN = re.compile(r"REDIS|UPSTASH|^KV_|_REST_API_")


def storage_env_names() -> list[str]:
    """Names (never values) of env vars that look like Redis settings — for /api/health."""
    return sorted(name for name in os.environ if _STORAGE_ENV_PATTERN.search(name))


def _redis_rest_credentials() -> tuple[str, str]:
    for url_name, token_name in (
        ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"),
        ("KV_REST_API_URL", "KV_REST_API_TOKEN"),
    ):
        url = os.getenv(url_name, "").strip()
        token = os.getenv(token_name, "").strip()
        if url and token:
            return url, token

    # Vercel Marketplace lets the prefix be renamed: <PREFIX>_REST_API_URL / <PREFIX>_REST_API_TOKEN.
    for name in sorted(os.environ):
        if name.endswith("_REST_API_URL"):
            url = os.environ[name].strip()
            token = os.getenv(name.removesuffix("URL") + "TOKEN", "").strip()
            if url and token:
                return url, token

    # Only a redis:// URL: Upstash serves REST on the same host, the password is the REST token.
    for name in sorted(os.environ):
        if name.endswith("REDIS_URL") or name.endswith("KV_URL"):
            parsed = urlparse(os.environ[name].strip())
            if parsed.hostname and parsed.hostname.endswith(".upstash.io") and parsed.password:
                return f"https://{parsed.hostname}", parsed.password
    return "", ""


def get_state_store() -> MemoryStateStore | UpstashStateStore:
    url, token = _redis_rest_credentials()
    if url and token:
        try:
            return UpstashStateStore(url, token)
        except Exception as exc:
            print(f"[state] Upstash unavailable, using memory fallback: {exc}")
    return _memory_store
