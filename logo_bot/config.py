from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
LOGO_DIR = BASE_DIR / "assets" / "logos"
OUTPUT_SIZE = (1080, 1350)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
MAX_INPUT_MB = int(os.getenv("MAX_INPUT_MB", "20"))
MAX_INPUT_BYTES = MAX_INPUT_MB * 1024 * 1024
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "PNG").strip().upper()
OUTPUT_QUALITY = int(os.getenv("OUTPUT_QUALITY", "100"))
JPEG_SUBSAMPLING = int(os.getenv("JPEG_SUBSAMPLING", "0"))
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "3600"))
TOO_LARGE_MESSAGE = f"Файл слишком большой, уменьшите до {MAX_INPUT_MB} МБ и загрузите заново."


@dataclass(frozen=True)
class LogoOption:
    key: str
    label: str
    filename: str

    @property
    def path(self) -> Path:
        return LOGO_DIR / self.filename


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    options: tuple[LogoOption, ...]

    def logo_option(self, option_key: str) -> LogoOption | None:
        for option in self.options:
            if option.key == option_key:
                return option
        return None

    def logo_path(self, option_key: str) -> Path:
        option = self.logo_option(option_key)
        if option:
            return option.path
        raise ValueError(f"Unsupported logo option: {option_key}")

    @property
    def is_ready(self) -> bool:
        return all(option.path.exists() for option in self.options)


CHANNELS: dict[str, Channel] = {
    "sportcore": Channel(
        "sportcore",
        "Sportcore",
        (
            LogoOption("left", "Слева", "sportcore_left.png"),
            LogoOption("right", "Справа", "sportcore_right.png"),
        ),
    ),
    "sportcorefinds": Channel(
        "sportcorefinds",
        "Sportcore Finds",
        (
            LogoOption("left", "Слева", "sportcorefinds_left.png"),
            LogoOption("right", "Справа", "sportcorefinds_right.png"),
        ),
    ),
    "musiccore": Channel(
        "musiccore",
        "Music Core",
        (
            LogoOption("left", "Слева", "musiccore_left.png"),
            LogoOption("right", "Справа", "musiccore_right.png"),
        ),
    ),
    "bolshe": Channel(
        "bolshe",
        "Больше",
        (
            LogoOption("purple", "Фиолетовый", "bolshe_purple.png"),
            LogoOption("yellow", "Желтый", "bolshe_yellow.png"),
            LogoOption("white", "Белый", "bolshe_white.png"),
        ),
    ),
    "homeofhockey": Channel(
        "homeofhockey",
        "Home of Hockey",
        (
            LogoOption("winline", "Винлайн", "home_of_hockey_winline.png"),
            LogoOption("fonbet", "Фонбет", "home_of_hockey_fonbet.png"),
        ),
    ),
}


def get_channel(key: str) -> Channel | None:
    return CHANNELS.get(key)


def output_extension_and_mime() -> tuple[str, str]:
    if OUTPUT_FORMAT == "PNG":
        return "png", "image/png"
    return "jpg", "image/jpeg"
