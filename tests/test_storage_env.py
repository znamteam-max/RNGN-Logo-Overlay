from __future__ import annotations

import pytest

from logo_bot import state_store


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in state_store.storage_env_names():
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_no_redis_settings_means_memory(clean_env):
    assert state_store._redis_rest_credentials() == ("", "")
    assert state_store.get_state_store().backend == "memory"


def test_default_vercel_kv_names(clean_env):
    clean_env.setenv("KV_REST_API_URL", "https://kv.upstash.io")
    clean_env.setenv("KV_REST_API_TOKEN", "tok")
    clean_env.setenv("KV_REST_API_READ_ONLY_TOKEN", "readonly")
    assert state_store._redis_rest_credentials() == ("https://kv.upstash.io", "tok")


def test_custom_marketplace_prefix(clean_env):
    clean_env.setenv("LOGO_STORE_REST_API_URL", "https://custom.upstash.io")
    clean_env.setenv("LOGO_STORE_REST_API_TOKEN", "tok")
    assert state_store._redis_rest_credentials() == ("https://custom.upstash.io", "tok")


def test_upstash_redis_url_is_converted_to_rest(clean_env):
    clean_env.setenv("REDIS_URL", "rediss://default:secret@eu1-fine-fox-123.upstash.io:6379")
    assert state_store._redis_rest_credentials() == ("https://eu1-fine-fox-123.upstash.io", "secret")


def test_non_upstash_redis_url_is_not_used(clean_env):
    clean_env.setenv("REDIS_URL", "redis://default:secret@redis-123.cloud.redislabs.com:12345")
    assert state_store._redis_rest_credentials() == ("", "")
    assert state_store.storage_env_names() == ["REDIS_URL"]
