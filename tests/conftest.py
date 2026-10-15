from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from logo_bot import state_store, webhook  # noqa: E402


CHAT_ID = 100
USER_ID = 7


class FakeTelegram:
    """Records every bot call instead of talking to Telegram."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.files: dict[str, bytes] = {}

    def _record(self, method: str, **kwargs: Any) -> None:
        self.calls.append((method, kwargs))

    def send_message(self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
        self._record("send_message", chat_id=chat_id, text=text, reply_markup=reply_markup)

    def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
        self._record("edit_message_text", chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup)

    def remove_reply_markup(self, chat_id: int, message_id: int) -> None:
        self._record("remove_reply_markup", chat_id=chat_id, message_id=message_id)

    def answer_callback_query(self, callback_query_id: str, text: str | None = None, show_alert: bool = False) -> None:
        self._record("answer_callback_query", text=text, show_alert=show_alert)

    def set_my_commands(self) -> None:
        self._record("set_my_commands")

    def download_file(self, file_id: str) -> bytes:
        self._record("download_file", file_id=file_id)
        return self.files[file_id]

    def send_document(self, chat_id: int, content: bytes, filename: str, mime_type: str, caption: str | None = None) -> None:
        self._record("send_document", chat_id=chat_id, content=content, filename=filename, caption=caption)

    def send_photo(
        self,
        chat_id: int,
        content: bytes,
        filename: str,
        caption: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self._record("send_photo", chat_id=chat_id, content=content, caption=caption, reply_markup=reply_markup)

    # --- helpers for assertions ---

    def texts(self) -> list[str]:
        return [str(kwargs.get("text") or kwargs.get("caption") or "") for _, kwargs in self.calls if "text" in kwargs or "caption" in kwargs]

    def last_text(self) -> str:
        return self.texts()[-1]

    def last_markup(self) -> dict[str, Any] | None:
        for _, kwargs in reversed(self.calls):
            if "reply_markup" in kwargs:
                return kwargs["reply_markup"]
        return None

    def calls_of(self, method: str) -> list[dict[str, Any]]:
        return [kwargs for name, kwargs in self.calls if name == method]


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> state_store.MemoryStateStore:
    for name in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "KV_REST_API_URL", "KV_REST_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    fresh = state_store.MemoryStateStore()
    fresh.persistent = True  # behave like Redis for the dialog
    monkeypatch.setattr(state_store, "_memory_store", fresh)
    webhook._OVERLAY_CACHE.clear()
    return fresh


@pytest.fixture
def tg() -> FakeTelegram:
    return FakeTelegram()


def logo_png(size: tuple[int, int] = (1080, 1350), transparent: bool = True, image_format: str = "PNG") -> bytes:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0) if transparent else (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((width // 4, height - height // 6, width * 3 // 4, height - 20), fill=(250, 200, 0, 255))
    out = BytesIO()
    if image_format == "JPEG":
        image.convert("RGB").save(out, format="JPEG")
    else:
        image.save(out, format=image_format)
    return out.getvalue()


def source_photo() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1600, 1200), "#3366aa").save(out, format="JPEG")
    return out.getvalue()


def text_message(text: str, user_id: int = USER_ID) -> dict[str, Any]:
    return {"message_id": 1, "chat": {"id": CHAT_ID}, "from": {"id": user_id, "username": "editor"}, "text": text}


def document_message(file_id: str, caption: str | None = None, user_id: int = USER_ID, mime: str = "image/png") -> dict[str, Any]:
    message: dict[str, Any] = {
        "message_id": 2,
        "chat": {"id": CHAT_ID},
        "from": {"id": user_id, "username": "editor"},
        "document": {"file_id": file_id, "file_unique_id": f"u-{file_id}", "file_name": f"{file_id}.png", "mime_type": mime, "file_size": 1000},
    }
    if caption:
        message["caption"] = caption
    return message


def photo_message(file_id: str, user_id: int = USER_ID) -> dict[str, Any]:
    return {
        "message_id": 3,
        "chat": {"id": CHAT_ID},
        "from": {"id": user_id, "username": "editor"},
        "photo": [{"file_id": f"{file_id}-small", "file_size": 100}, {"file_id": file_id, "file_size": 1000}],
    }


def callback(data: str, user_id: int = USER_ID, message_id: int = 55) -> dict[str, Any]:
    return {
        "id": "q1",
        "from": {"id": user_id, "username": "editor"},
        "message": {"message_id": message_id, "chat": {"id": CHAT_ID}},
        "data": data,
    }


def buttons(markup: dict[str, Any] | None) -> list[dict[str, str]]:
    return [button for row in (markup or {}).get("inline_keyboard", []) for button in row]
