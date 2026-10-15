"""Step-by-step Telegram dialogs: add a project with logos, delete a project.

Dialog state lives under ``dialog:{chat_id}:{user_id}``:
    {"step": "name" | "confirm_existing" | "logo" | "option_name",
     "label": "Высота 3.0.5", "project_key": None, "existing_labels": [],
     "options": [{"label": "Без Винлайн", "file_id": "...", "file_unique_id": "...", "width": 1080, "height": 1350}],
     "pending": {...}}  # uploaded logo that still waits for its name
Nothing reaches the projects list until the user presses «Готово».
"""

from __future__ import annotations

import traceback
from typing import Any

from .config import (
    BOT_TOKEN,
    CHANNELS,
    MAX_INPUT_BYTES,
    MAX_OPTION_LABEL,
    MAX_PROJECT_LABEL,
    MAX_PROJECT_OPTIONS,
    TOO_LARGE_MESSAGE,
)
from .image_processing import LogoError, render_preview, validate_logo
from .keyboards import add_cancel_menu, add_existing_menu, add_logo_menu, delete_confirm_menu, delete_menu
from .projects import (
    delete_project,
    find_project_by_label,
    get_project_record,
    is_builtin_label,
    load_project_records,
    normalize_label,
    same_label,
    save_project,
)
from .state_store import get_state_store
from .telegram_api import TelegramClient, TelegramError


ADD_COMMANDS = {"/newproject", "/addproject"}
DELETE_COMMANDS = {"/deleteproject"}
ADD_PHRASES = {"добавить проект", "новый проект"}
DELETE_PHRASES = {"удалить проект"}
CANCEL_WORDS = {"отмена", "отменить", "/cancel"}
DONE_WORDS = {"готово", "/done"}
PROJECT_CALLBACKS = {"np", "dp", "dpc", "dpy"}

STORAGE_MISSING_TEXT = (
    "Не могу добавить проект: у бота не подключено постоянное хранилище (Redis), "
    "и новый проект пропал бы при перезапуске. Напиши тому, кто настраивал бота."
)


def normalize_phrase(text: str) -> str:
    words = text.replace("➕", " ").replace("🗑", " ").split()
    if words and words[0].startswith("/") and "@" in words[0]:
        words[0] = words[0].split("@", 1)[0]
    return " ".join(words).casefold()


def author_of(user: dict[str, Any]) -> str:
    username = str(user.get("username") or "")
    name = " ".join(str(part) for part in (user.get("first_name"), user.get("last_name")) if part)
    who = f"@{username}" if username else (name or "без имени")
    return f"{who} ({user.get('id')})"


def _dialog_key(chat_id: int, user: dict[str, Any]) -> str:
    return f"dialog:{chat_id}:{user.get('id') or chat_id}"


def _has_media(message: dict[str, Any]) -> bool:
    return bool(message.get("document") or message.get("photo"))


def _report_failure(chat_id: int, exc: Exception, tg: TelegramClient) -> None:
    print(f"[dialog] failed: {exc}")
    traceback.print_exc()
    details = f"{type(exc).__name__}: {exc}"
    if BOT_TOKEN:
        details = details.replace(BOT_TOKEN, "[token]")
    try:
        tg.send_message(chat_id, f"Что-то пошло не так, попробуй еще раз.\n\nТехническая причина: {details[:500]}")
    except Exception:
        pass


def drop_dialog(chat_id: int, user: dict[str, Any]) -> None:
    try:
        get_state_store().delete(_dialog_key(chat_id, user))
    except Exception as exc:
        print(f"[dialog] drop failed: {exc}")


# ---------- add project ----------


def _option_count(state: dict[str, Any]) -> int:
    return len(state.get("existing_labels") or []) + len(state.get("options") or [])


def _ask_logo_text(state: dict[str, Any]) -> str:
    return (
        f"Пришли логотип №{_option_count(state) + 1} для «{state['label']}» — PNG с прозрачным фоном, "
        "файлом без сжатия: скрепка → Файл.\n\n"
        "Можно сразу подписать файл названием варианта — например, «Без Винлайн»."
    )


def _logo_step_menu(state: dict[str, Any]) -> dict[str, Any]:
    return add_logo_menu() if state.get("options") else add_cancel_menu()


def _option_label_error(state: dict[str, Any], label: str) -> str | None:
    if not label:
        return "Название варианта не может быть пустым."
    if label.startswith("/"):
        return "Название варианта не должно начинаться с «/»."
    if len(label) > MAX_OPTION_LABEL:
        return f"Слишком длинное название варианта — нужно до {MAX_OPTION_LABEL} символов."
    taken = list(state.get("existing_labels") or []) + [option["label"] for option in state.get("options") or []]
    if any(same_label(existing, label) for existing in taken):
        return f"Вариант «{label}» уже есть в этом проекте. Придумай другое название."
    return None


def _accept_option(state: dict[str, Any], label: str, logo: dict[str, Any]) -> str:
    state.setdefault("options", []).append({"label": label, **logo})
    state["step"] = "logo"
    state.pop("pending", None)
    text = f"✅ Вариант {_option_count(state)} «{label}» принят."
    if _option_count(state) >= MAX_PROJECT_OPTIONS:
        return f"{text}\n\nЭто максимум — {MAX_PROJECT_OPTIONS} вариантов. Нажми «Готово»."
    return f"{text}\n\nПришли следующий логотип или нажми «Готово» — тогда проект появится в списке каналов."


def start_add(chat_id: int, user: dict[str, Any], tg: TelegramClient) -> None:
    try:
        store = get_state_store()
        if not store.persistent:
            tg.send_message(chat_id, STORAGE_MISSING_TEXT)
            return
        store.set(_dialog_key(chat_id, user), {"step": "name", "options": []})
        tg.send_message(
            chat_id,
            "Добавляем новый проект.\n\nКак он называется? Напиши название одним сообщением — например, Высота 3.0.5",
            reply_markup=add_cancel_menu(),
        )
    except Exception as exc:
        _report_failure(chat_id, exc, tg)


def handle_dialog_message(message: dict[str, Any], tg: TelegramClient) -> bool:
    """Returns False when the user has no active dialog, so the caller handles the message as usual."""
    chat_id = int((message.get("chat") or {})["id"])
    user = message.get("from") or {}
    store = get_state_store()
    key = _dialog_key(chat_id, user)
    state = store.get(key)
    if not state:
        return False

    try:
        text = str(message.get("text") or "").strip()
        word = normalize_phrase(text)
        step = state.get("step")
        if word in CANCEL_WORDS:
            store.delete(key)
            tg.send_message(chat_id, "Ок, отменил — ничего не сохранено.")
        elif step == "name":
            _on_project_name(chat_id, message, text, key, state, tg)
        elif step == "confirm_existing":
            tg.send_message(chat_id, "Выбери кнопкой: добавить логотипы к этому проекту или отменить.", reply_markup=add_existing_menu())
        elif step == "logo" and word in DONE_WORDS:
            _finish(chat_id, user, key, state, tg)
        elif step == "logo":
            _on_logo(chat_id, message, key, state, tg)
        elif step == "option_name":
            _on_option_name(chat_id, message, text, key, state, tg)
        else:
            store.delete(key)
            return False
    except Exception as exc:
        _report_failure(chat_id, exc, tg)
    return True


def _on_project_name(
    chat_id: int,
    message: dict[str, Any],
    text: str,
    key: str,
    state: dict[str, Any],
    tg: TelegramClient,
) -> None:
    if _has_media(message) or not text:
        tg.send_message(chat_id, "Сначала напиши название проекта текстом.", reply_markup=add_cancel_menu())
        return
    label = normalize_label(text)
    if label.startswith("/"):
        tg.send_message(chat_id, "Название не должно начинаться с «/». Напиши название проекта.", reply_markup=add_cancel_menu())
        return
    if len(label) > MAX_PROJECT_LABEL:
        tg.send_message(chat_id, f"Слишком длинное название — нужно до {MAX_PROJECT_LABEL} символов.", reply_markup=add_cancel_menu())
        return
    if is_builtin_label(label):
        tg.send_message(
            chat_id,
            f"«{label}» уже есть в боте как встроенный канал — его логотипы меняет программист. Придумай другое название.",
            reply_markup=add_cancel_menu(),
        )
        return

    existing = find_project_by_label(label)
    store = get_state_store()
    if existing:
        existing_labels = [str(option["label"]) for option in existing.get("options") or []]
        state.update(step="confirm_existing", label=existing["label"], project_key=existing["key"], existing_labels=existing_labels)
        store.set(key, state)
        tg.send_message(
            chat_id,
            f"Проект «{existing['label']}» уже есть, в нем варианты: {', '.join(existing_labels)}.\n\nДобавить к нему новые логотипы?",
            reply_markup=add_existing_menu(),
        )
        return

    state.update(step="logo", label=label, project_key=None, existing_labels=[])
    store.set(key, state)
    tg.send_message(chat_id, _ask_logo_text(state), reply_markup=add_cancel_menu())


def _on_logo(chat_id: int, message: dict[str, Any], key: str, state: dict[str, Any], tg: TelegramClient) -> None:
    if message.get("photo"):
        tg.send_message(
            chat_id,
            "Логотип пришел как сжатое фото — так Telegram убирает прозрачный фон. "
            "Пришли тот же PNG файлом: скрепка → Файл.",
            reply_markup=_logo_step_menu(state),
        )
        return
    document = message.get("document") or {}
    if not document:
        hint = " Если все логотипы загружены — нажми «Готово»." if state.get("options") else ""
        tg.send_message(chat_id, f"Жду PNG-файл логотипа.{hint}", reply_markup=_logo_step_menu(state))
        return
    if _option_count(state) >= MAX_PROJECT_OPTIONS:
        tg.send_message(chat_id, f"В проекте уже {MAX_PROJECT_OPTIONS} вариантов — это максимум. Нажми «Готово».", reply_markup=add_logo_menu())
        return
    if int(document.get("file_size") or 0) > MAX_INPUT_BYTES:
        tg.send_message(chat_id, TOO_LARGE_MESSAGE, reply_markup=_logo_step_menu(state))
        return

    try:
        data = tg.download_file(str(document["file_id"]))
    except TelegramError as exc:
        print(f"[dialog] logo download failed: {exc}")
        text = TOO_LARGE_MESSAGE if str(exc) == TOO_LARGE_MESSAGE else "Не смог скачать файл из Telegram. Пришли его еще раз."
        tg.send_message(chat_id, text, reply_markup=_logo_step_menu(state))
        return
    try:
        info = validate_logo(data)
    except LogoError as exc:
        tg.send_message(chat_id, f"{exc}\n\nПришли другой файл или нажми «Отмена».", reply_markup=_logo_step_menu(state))
        return

    logo = {
        "file_id": str(document["file_id"]),
        "file_unique_id": str(document.get("file_unique_id") or ""),
        "width": info.width,
        "height": info.height,
    }
    size_note = "" if info.is_4x5 else f"\n\n⚠️ Размер {info.width}×{info.height} — это не 4:5. Логотип встанет по центру снизу, как на превью."
    preview = render_preview(data)
    store = get_state_store()

    caption_label = normalize_label(str(message.get("caption") or ""))
    caption_error = _option_label_error(state, caption_label) if caption_label else None
    if caption_label and not caption_error:
        text = _accept_option(state, caption_label, logo)
        store.set(key, state)
        tg.send_photo(chat_id, preview, "preview.jpg", caption=f"{text}{size_note}", reply_markup=add_logo_menu())
        return

    state.update(step="option_name", pending=logo)
    store.set(key, state)
    ask = "Как назвать этот вариант? Например: «Без Винлайн»."
    if caption_error:
        ask = f"{caption_error}\n\n{ask}"
    tg.send_photo(chat_id, preview, "preview.jpg", caption=f"Так логотип ляжет на фото.{size_note}\n\n{ask}", reply_markup=add_cancel_menu())


def _on_option_name(
    chat_id: int,
    message: dict[str, Any],
    text: str,
    key: str,
    state: dict[str, Any],
    tg: TelegramClient,
) -> None:
    if _has_media(message) or not text or normalize_phrase(text) in DONE_WORDS:
        tg.send_message(chat_id, "Сначала напиши название для этого логотипа — например, «С Винлайн».", reply_markup=add_cancel_menu())
        return
    label = normalize_label(text)
    error = _option_label_error(state, label)
    if error:
        tg.send_message(chat_id, error, reply_markup=add_cancel_menu())
        return

    store = get_state_store()
    pending = state.get("pending")
    if not pending:
        state["step"] = "logo"
        store.set(key, state)
        tg.send_message(chat_id, _ask_logo_text(state), reply_markup=_logo_step_menu(state))
        return
    reply = _accept_option(state, label, pending)
    store.set(key, state)
    tg.send_message(chat_id, reply, reply_markup=add_logo_menu())


def _finish(chat_id: int, user: dict[str, Any], key: str, state: dict[str, Any], tg: TelegramClient) -> None:
    if state.get("step") == "option_name":
        tg.send_message(chat_id, "Сначала напиши название для последнего логотипа.", reply_markup=add_cancel_menu())
        return
    options = state.get("options") or []
    if not options:
        tg.send_message(chat_id, "Пока не загружено ни одного логотипа. Пришли PNG-файл или нажми «Отмена».", reply_markup=add_cancel_menu())
        return

    record = save_project(state["label"], options, author_of(user), state.get("project_key"))
    get_state_store().delete(key)
    labels = ", ".join(str(option["label"]) for option in record["options"])
    if state.get("project_key"):
        head = f"Готово! В проект «{record['label']}» добавлено логотипов: {len(options)}."
    else:
        head = f"Готово! Проект «{record['label']}» добавлен."
    tg.send_message(
        chat_id,
        f"{head}\nВарианты: {labels}.\n\nОн уже есть в списке каналов: пришли фото файлом и выбери «{record['label']}».",
    )


def _on_add_button(action: str, chat_id: int, message_id: int, user: dict[str, Any], tg: TelegramClient) -> None:
    if action == "start":
        start_add(chat_id, user, tg)
        return

    store = get_state_store()
    key = _dialog_key(chat_id, user)
    state = store.get(key)
    tg.remove_reply_markup(chat_id, message_id)
    if not state:
        tg.send_message(chat_id, "Добавление проекта уже завершено или истекло. Чтобы начать заново, напиши «добавить проект».")
        return
    if action == "cancel":
        store.delete(key)
        tg.send_message(chat_id, "Ок, отменил — ничего не сохранено.")
    elif action == "done":
        _finish(chat_id, user, key, state, tg)
    elif action == "existing" and state.get("step") == "confirm_existing":
        state["step"] = "logo"
        store.set(key, state)
        tg.send_message(chat_id, _ask_logo_text(state), reply_markup=add_cancel_menu())


# ---------- delete project ----------


def start_delete(chat_id: int, user: dict[str, Any], tg: TelegramClient) -> None:
    try:
        drop_dialog(chat_id, user)
        records = load_project_records()
        if not records:
            builtin = ", ".join(channel.label for channel in CHANNELS.values())
            tg.send_message(
                chat_id,
                f"Через бот пока не добавлено ни одного проекта.\n\nВстроенные каналы ({builtin}) удаляет только программист.",
            )
            return
        tg.send_message(chat_id, "Какой проект удалить? Здесь только проекты, добавленные через бот.", reply_markup=delete_menu(records))
    except Exception as exc:
        _report_failure(chat_id, exc, tg)


def _on_delete_choice(project_key: str, chat_id: int, message_id: int, tg: TelegramClient) -> None:
    record = get_project_record(project_key)
    if not record:
        tg.edit_message_text(chat_id, message_id, "Этот проект уже удален.")
        return
    labels = ", ".join(str(option["label"]) for option in record.get("options") or [])
    tg.edit_message_text(
        chat_id,
        message_id,
        f"Удалить проект «{record['label']}»?\nВарианты: {labels}.\n\nОн пропадет из списка каналов у всех.",
        reply_markup=delete_confirm_menu(project_key),
    )


def _on_delete_confirm(project_key: str, chat_id: int, message_id: int, user: dict[str, Any], tg: TelegramClient) -> None:
    record = delete_project(project_key, author_of(user))
    if not record:
        tg.edit_message_text(chat_id, message_id, "Этот проект уже удален.")
        return
    tg.edit_message_text(chat_id, message_id, f"Проект «{record['label']}» удален.")


# ---------- buttons ----------


def handle_project_callback(callback: dict[str, Any], tg: TelegramClient) -> bool:
    """Returns False for buttons that are not about projects."""
    parts = str(callback.get("data") or "").split("|")
    if len(parts) != 2 or parts[0] not in PROJECT_CALLBACKS:
        return False

    action, arg = parts
    message = callback.get("message") or {}
    chat_id = int((message.get("chat") or {})["id"])
    message_id = int(message.get("message_id") or 0)
    user = callback.get("from") or {}
    tg.answer_callback_query(str(callback.get("id") or ""))
    try:
        if action == "np":
            _on_add_button(arg, chat_id, message_id, user, tg)
        elif action == "dp" and arg == "start":
            start_delete(chat_id, user, tg)
        elif action == "dp":
            tg.edit_message_text(chat_id, message_id, "Ок, ничего не удаляю.")
        elif action == "dpc":
            _on_delete_choice(arg, chat_id, message_id, tg)
        elif action == "dpy":
            _on_delete_confirm(arg, chat_id, message_id, user, tg)
    except Exception as exc:
        _report_failure(chat_id, exc, tg)
    return True
