from __future__ import annotations

from typing import Any

from .config import CHANNELS


def _button(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def _keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def channel_menu(record_id: str) -> dict[str, Any]:
    return _keyboard(
        [
            [_button(channel.label, f"ch|{record_id}|{channel.key}")]
            for channel in CHANNELS.values()
        ]
    )


def option_menu(record_id: str, channel_key: str) -> dict[str, Any]:
    channel = CHANNELS.get(channel_key)
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


def channel_label(channel_key: str) -> str:
    channel = CHANNELS.get(channel_key)
    return channel.label if channel else channel_key


def option_label(channel_key: str, option_key: str) -> str:
    channel = CHANNELS.get(channel_key)
    option = channel.logo_option(option_key) if channel else None
    return option.label.lower() if option else option_key

