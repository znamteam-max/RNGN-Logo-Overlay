"""Projects added through the bot (on top of the built-in CHANNELS).

Each project is one field of the Redis hash ``projects:v1``:
    {"key": "p1a2b3c", "label": "Высота 3.0.5",
     "options": [{"key": "o1", "label": "Без Винлайн", "file_id": "...", "file_unique_id": "..."}],
     "created_by": "@user (123)", "created_at": "2026-10-15T12:00:00+00:00",
     "deleted_at": null}
Logo PNGs stay in Telegram; the bot re-downloads them by file_id.
Deletion is soft (deleted_at is set), so a removed project can be restored by hand.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any

from .config import CHANNELS, Channel, LogoOption
from .state_store import get_state_store, storage_env_names


PROJECTS_KEY = "projects:v1"

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(text: str) -> str:
    transliterated = "".join(_TRANSLIT.get(char, char) for char in text.lower())
    return re.sub(r"[^a-z0-9]+", "_", transliterated).strip("_") or "logo"


def normalize_label(text: str) -> str:
    return " ".join(text.split())


def same_label(left: str, right: str) -> bool:
    return normalize_label(left).casefold() == normalize_label(right).casefold()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_builtin_label(label: str) -> bool:
    return any(same_label(channel.label, label) for channel in CHANNELS.values())


def project_to_channel(record: dict[str, Any]) -> Channel | None:
    options = tuple(
        LogoOption(str(option["key"]), str(option["label"]), file_id=str(option["file_id"]))
        for option in record.get("options") or []
        if option.get("key") and option.get("file_id")
    )
    if not options or not record.get("key"):
        return None
    return Channel(str(record["key"]), str(record.get("label") or record["key"]), options, custom=True)


def load_project_records(store: Any = None) -> list[dict[str, Any]]:
    store = store or get_state_store()
    records = [record for record in store.hgetall(PROJECTS_KEY).values() if not record.get("deleted_at")]
    return sorted(records, key=lambda record: str(record.get("created_at") or ""))


def get_project_record(key: str) -> dict[str, Any] | None:
    record = get_state_store().hget(PROJECTS_KEY, key)
    if not record or record.get("deleted_at"):
        return None
    return record


def find_project_by_label(label: str) -> dict[str, Any] | None:
    for record in load_project_records():
        if same_label(str(record.get("label") or ""), label):
            return record
    return None


def all_channels() -> list[Channel]:
    channels = list(CHANNELS.values())
    try:
        records = load_project_records()
    except Exception as exc:
        # Redis trouble must not take the built-in channels down with it.
        print(f"[projects] failed to load custom projects: {exc}")
        return channels
    for record in records:
        channel = project_to_channel(record)
        if channel:
            channels.append(channel)
    return channels


def find_channel(key: str) -> Channel | None:
    channel = CHANNELS.get(key)
    if channel:
        return channel
    try:
        record = get_project_record(key)
    except Exception as exc:
        print(f"[projects] failed to load project {key}: {exc}")
        return None
    return project_to_channel(record) if record else None


def _next_option_number(options: list[dict[str, Any]]) -> int:
    numbers = [int(key[1:]) for key in (str(option.get("key") or "") for option in options) if re.fullmatch(r"o\d+", key)]
    return max(numbers, default=0) + 1


def save_project(
    label: str,
    new_options: list[dict[str, Any]],
    author: str,
    project_key: str | None = None,
) -> dict[str, Any]:
    """Create a project, or append options to an existing one. Returns the saved record."""
    store = get_state_store()
    record = get_project_record(project_key) if project_key else None
    if not record:
        record = find_project_by_label(label)
    if not record:
        record = {
            "key": "p" + secrets.token_hex(3),
            "label": normalize_label(label),
            "options": [],
            "created_by": author,
            "created_at": _now(),
            "deleted_at": None,
        }

    options = list(record.get("options") or [])
    for option in new_options:
        options.append(
            {
                "key": f"o{_next_option_number(options)}",
                "label": option["label"],
                "file_id": option["file_id"],
                "file_unique_id": option.get("file_unique_id", ""),
                "added_by": author,
                "added_at": _now(),
            }
        )
    record["options"] = options
    store.hset(PROJECTS_KEY, record["key"], record)
    return record


def delete_project(key: str, author: str) -> dict[str, Any] | None:
    record = get_project_record(key)
    if not record:
        return None
    record["deleted_at"] = _now()
    record["deleted_by"] = author
    get_state_store().hset(PROJECTS_KEY, key, record)
    return record


def storage_status() -> dict[str, Any]:
    store = get_state_store()
    status: dict[str, Any] = {"storage": store.backend, "storage_env": storage_env_names()}
    try:
        status["custom_projects"] = len(load_project_records(store))
    except Exception as exc:
        status["storage_error"] = type(exc).__name__
    return status
