from __future__ import annotations

from typing import Any

from .config import CHANNELS, SIDES


def _button(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def _keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def channel_menu(record_id: str) -> dict[str, Any]:
    return _keyboard(
        [
            [_button("Sportcore", f"ch|{record_id}|sportcore")],
            [_button("Sportcore Finds", f"ch|{record_id}|sportcorefinds")],
            [_button("Music Core", f"ch|{record_id}|musiccore")],
            [_button("Больше", f"ch|{record_id}|bolshe")],
        ]
    )


def side_menu(record_id: str, channel_key: str) -> dict[str, Any]:
    return _keyboard(
        [
            [
                _button("Слева", f"pos|{record_id}|{channel_key}|left"),
                _button("Справа", f"pos|{record_id}|{channel_key}|right"),
            ],
            [_button("Назад к каналам", f"again|{record_id}")],
        ]
    )


def again_menu(record_id: str) -> dict[str, Any]:
    return _keyboard([[_button("Другой логотип для этого фото", f"again|{record_id}")]])


def channel_label(channel_key: str) -> str:
    channel = CHANNELS.get(channel_key)
    return channel.label if channel else channel_key


def side_label(side: str) -> str:
    return SIDES.get(side, side)

