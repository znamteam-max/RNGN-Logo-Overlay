from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .config import BOT_TOKEN, MAX_INPUT_BYTES, TOO_LARGE_MESSAGE


class TelegramError(RuntimeError):
    pass


@dataclass
class TelegramClient:
    token: str = BOT_TOKEN

    @property
    def api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    @property
    def file_base(self) -> str:
        return f"https://api.telegram.org/file/bot{self.token}"

    def _request_json(self, method: str, **kwargs: Any) -> dict[str, Any]:
        if not self.token:
            raise TelegramError("TELEGRAM_BOT_TOKEN is not configured")
        response = requests.post(f"{self.api_base}/{method}", timeout=30, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramError(f"Telegram returned non-JSON response for {method}") from exc
        if not response.ok or not data.get("ok"):
            description = str(data.get("description") or "").lower()
            if "file is too big" in description or "too big" in description:
                raise TelegramError(TOO_LARGE_MESSAGE)
            raise TelegramError(f"Telegram {method} failed: {data}")
        return data

    def send_message(self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self._request_json("sendMessage", json=payload)

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            self._request_json("editMessageText", json=payload)
        except TelegramError as exc:
            print(f"[tg] editMessageText ignored: {exc}")

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text
        try:
            self._request_json("answerCallbackQuery", json=payload)
        except TelegramError as exc:
            print(f"[tg] answerCallbackQuery ignored: {exc}")

    def set_my_commands(self) -> None:
        commands = [
            {"command": "start", "description": "инструкция"},
            {"command": "help", "description": "инструкция"},
        ]
        try:
            self._request_json("setMyCommands", json={"commands": commands})
        except TelegramError as exc:
            print(f"[tg] setMyCommands ignored: {exc}")

    def get_file(self, file_id: str) -> dict[str, Any]:
        data = self._request_json("getFile", json={"file_id": file_id})
        result = data.get("result") or {}
        if not result.get("file_path"):
            raise TelegramError("Telegram getFile response has no file_path")
        return result

    def download_file(self, file_id: str) -> bytes:
        info = self.get_file(file_id)
        file_size = int(info.get("file_size") or 0)
        if file_size and file_size > MAX_INPUT_BYTES:
            raise TelegramError(TOO_LARGE_MESSAGE)

        response = requests.get(f"{self.file_base}/{info['file_path']}", timeout=60)
        response.raise_for_status()
        content = response.content
        if len(content) > MAX_INPUT_BYTES:
            raise TelegramError(TOO_LARGE_MESSAGE)
        return content

    def send_document(
        self,
        chat_id: int,
        content: bytes,
        filename: str,
        mime_type: str,
        caption: str | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "chat_id": str(chat_id),
            "disable_content_type_detection": "true",
        }
        if caption:
            data["caption"] = caption
        files = {"document": (filename, content, mime_type)}
        self._request_json("sendDocument", data=data, files=files)
