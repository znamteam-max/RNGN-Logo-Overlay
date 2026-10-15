from __future__ import annotations

from typing import Any

from .projects import all_channels, find_channel


def _button(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def _keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def channel_menu(record_id: str) -> dict[str, Any]:
    return _keyboard(
        [
            [_button(channel.label, f"ch|{record_id}|{channel.key}")]
            for channel in all_channels()
        ]
    )


def option_menu(record_id: str, channel_key: str) -> dict[str, Any]:
    channel = find_channel(channel_key)
    if not channel:
        return channel_menu(record_id)

    rows = []
    buttons = [_button(option.label, f"pos|{record_id}|{channel_key}|{option.key}") for option in channel.options]
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index : index + 2])
    rows.append([_button("Назад к каналам", f"again|{record_id}")])
    return _keyboard(rows)


def again_menu(record_id: str) -> dict[str, Any]:
    return _keyboard([[_button("Другой логотип для этого фото", f"again|{record_id}")]])


def start_menu() -> dict[str, Any]:
    return _keyboard(
        [
            [_button("➕ Добавить проект", "np|start")],
            [_button("🗑 Удалить проект", "dp|start")],
        ]
    )


def add_cancel_menu() -> dict[str, Any]:
    return _keyboard([[_button("Отмена", "np|cancel")]])


def add_logo_menu() -> dict[str, Any]:
    return _keyboard([[_button("✅ Готово", "np|done"), _button("Отмена", "np|cancel")]])


def add_existing_menu() -> dict[str, Any]:
    return _keyboard(
        [
            [_button("Добавить к нему логотипы", "np|existing")],
            [_button("Отмена", "np|cancel")],
        ]
    )


def delete_menu(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [[_button(str(record.get("label") or record["key"]), f"dpc|{record['key']}")] for record in records]
    rows.append([_button("Отмена", "dp|cancel")])
    return _keyboard(rows)


def delete_confirm_menu(project_key: str) -> dict[str, Any]:
    return _keyboard([[_button("Да, удалить", f"dpy|{project_key}"), _button("Нет", "dp|cancel")]])
