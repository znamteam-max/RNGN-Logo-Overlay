from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler
from typing import Any

from .config import BOT_TOKEN, MAX_INPUT_MB, TOO_LARGE_MESSAGE, WEBHOOK_SECRET, get_channel
from .image_processing import render_overlay
from .keyboards import again_menu, channel_label, channel_menu, side_label, side_menu
from .state_store import get_state_store, new_record_id
from .telegram_api import TelegramClient, TelegramError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _is_image_document(document: dict[str, Any]) -> bool:
    mime = str(document.get("mime_type") or "")
    if mime.startswith("image/"):
        return True
    filename = str(document.get("file_name") or "").lower()
    return any(filename.endswith(ext) for ext in IMAGE_EXTENSIONS)


def _extract_image_file(message: dict[str, Any]) -> tuple[str, int, bool] | None:
    document = message.get("document") or {}
    if document and _is_image_document(document):
        return str(document.get("file_id") or ""), int(document.get("file_size") or 0), True

    photos = message.get("photo") or []
    if photos:
        largest = photos[-1]
        return str(largest.get("file_id") or ""), int(largest.get("file_size") or 0), False
    return None


def _help_text() -> str:
    return (
        "Пришли фото файлом без сжатия: скрепка → Файл. "
        "После загрузки выбери канал и сторону логотипа.\n\n"
        f"Сейчас бот принимает файлы до {MAX_INPUT_MB} MB и приводит результат к 4:5."
    )


def _handle_message(message: dict[str, Any], tg: TelegramClient) -> None:
    chat_id = int((message.get("chat") or {})["id"])
    text = (message.get("text") or message.get("caption") or "").strip()
    command = text.split(" ", 1)[0].lower() if text else ""
    if "@" in command:
        command = command.split("@", 1)[0]

    if command in {"/start", "/help", "start", "help"}:
        tg.set_my_commands()
        tg.send_message(chat_id, _help_text())
        return

    image = _extract_image_file(message)
    if not image:
        tg.send_message(chat_id, _help_text())
        return

    file_id, file_size, is_document = image
    if not file_id:
        tg.send_message(chat_id, "Не смог прочитать файл. Попробуй отправить фото еще раз.")
        return
    if file_size and file_size > MAX_INPUT_MB * 1024 * 1024:
        tg.send_message(chat_id, TOO_LARGE_MESSAGE)
        return

    record_id = new_record_id()
    get_state_store().set(
        f"upload:{record_id}",
        {
            "chat_id": chat_id,
            "file_id": file_id,
            "is_document": is_document,
        },
    )

    note = "" if is_document else "\n\nЛучше отправлять как файл, чтобы Telegram не сжимал исходник."
    tg.send_message(chat_id, f"Фото принято. Выбери канал:{note}", reply_markup=channel_menu(record_id))


def _handle_channel_choice(chat_id: int, message_id: int, record_id: str, channel_key: str, tg: TelegramClient) -> None:
    record = get_state_store().get(f"upload:{record_id}")
    if not record:
        tg.edit_message_text(chat_id, message_id, "Сессия истекла. Пришли фото еще раз.")
        return

    channel = get_channel(channel_key)
    if not channel:
        tg.edit_message_text(chat_id, message_id, "Не нашел такой канал. Выбери заново.", reply_markup=channel_menu(record_id))
        return
    if not channel.is_ready:
        tg.edit_message_text(
            chat_id,
            message_id,
            f"Логотипы для «{channel.label}» еще не загружены. Выбери другой канал:",
            reply_markup=channel_menu(record_id),
        )
        return

    tg.edit_message_text(
        chat_id,
        message_id,
        f"{channel.label}: выбери сторону логотипа.",
        reply_markup=side_menu(record_id, channel_key),
    )


def _handle_position_choice(
    chat_id: int,
    message_id: int,
    record_id: str,
    channel_key: str,
    side: str,
    tg: TelegramClient,
) -> None:
    record = get_state_store().get(f"upload:{record_id}")
    if not record:
        tg.edit_message_text(chat_id, message_id, "Сессия истекла. Пришли фото еще раз.")
        return

    channel = get_channel(channel_key)
    if not channel or not channel.is_ready:
        tg.edit_message_text(chat_id, message_id, "Этот логотип пока недоступен.", reply_markup=channel_menu(record_id))
        return

    overlay_path = channel.logo_path(side)
    if side not in {"left", "right"} or not overlay_path.exists():
        tg.edit_message_text(chat_id, message_id, "Не нашел логотип для этой стороны.", reply_markup=side_menu(record_id, channel_key))
        return

    tg.edit_message_text(chat_id, message_id, "Генерирую картинку...")
    source = tg.download_file(str(record["file_id"]))
    result, ext, mime = render_overlay(source, overlay_path)
    filename = f"{channel_key}_{side}_4x5.{ext}"
    caption = f"Готово: {channel_label(channel_key)}, {side_label(side)}"
    tg.send_document(chat_id, result, filename, mime, caption=caption)
    tg.send_message(chat_id, "Можно сделать еще один вариант с этим же фото.", reply_markup=again_menu(record_id))


def _handle_callback(callback: dict[str, Any], tg: TelegramClient) -> None:
    query_id = str(callback.get("id") or "")
    message = callback.get("message") or {}
    chat_id = int((message.get("chat") or {})["id"])
    message_id = int(message.get("message_id") or 0)
    data = str(callback.get("data") or "")
    parts = data.split("|")

    try:
        if parts[0] == "again" and len(parts) == 2:
            tg.answer_callback_query(query_id)
            record_id = parts[1]
            tg.edit_message_text(chat_id, message_id, "Выбери канал:", reply_markup=channel_menu(record_id))
            return

        if parts[0] == "ch" and len(parts) == 3:
            tg.answer_callback_query(query_id)
            _handle_channel_choice(chat_id, message_id, parts[1], parts[2], tg)
            return

        if parts[0] == "pos" and len(parts) == 4:
            tg.answer_callback_query(query_id, "Готовлю картинку...")
            _handle_position_choice(chat_id, message_id, parts[1], parts[2], parts[3], tg)
            return

        tg.answer_callback_query(query_id, "Не понял действие", show_alert=True)
    except TelegramError as exc:
        print(f"[callback] telegram error: {exc}")
        tg.answer_callback_query(query_id, "Не смог обработать запрос", show_alert=True)
        try:
            tg.send_message(chat_id, str(exc))
        except Exception:
            pass
    except Exception as exc:
        print(f"[callback] failed: {exc}")
        tg.answer_callback_query(query_id, "Ошибка обработки", show_alert=True)
        try:
            tg.send_message(chat_id, "Не получилось собрать картинку. Пришли фото еще раз.")
        except Exception:
            pass


class WebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        _json_response(
            self,
            {
                "ok": True,
                "service": "logo-overlay-bot",
                "token_configured": bool(BOT_TOKEN),
            },
        )

    def do_POST(self) -> None:
        try:
            if WEBHOOK_SECRET:
                got = self.headers.get("x-telegram-bot-api-secret-token", "")
                if got != WEBHOOK_SECRET:
                    _json_response(self, {"ok": False, "error": "forbidden"}, status=403)
                    return

            length = int(self.headers.get("content-length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            update = json.loads(raw.decode("utf-8"))
            tg = TelegramClient()

            if "message" in update:
                _handle_message(update["message"] or {}, tg)
            elif "callback_query" in update:
                _handle_callback(update["callback_query"] or {}, tg)
            else:
                print(f"[webhook] unsupported update keys: {list(update.keys())}")

            _json_response(self, {"ok": True})
        except Exception as exc:
            print(f"[webhook] fatal: {exc}")
            _json_response(self, {"ok": True})
